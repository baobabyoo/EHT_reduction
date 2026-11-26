"""Verify coverage, candidate and command correspondence in the assembled report.

Usage in inspection/: python verify_visibility_report.py REPORT.pdf QA_DIR
Requires pypdfium2, NumPy and Pillow. Render every page and save contact sheets.
"""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,ast,csv,json,math,re
import pypdfium2 as pdfium
import numpy as np
from PIL import Image,ImageDraw


def verify(pdf,qa):
    qa.mkdir(parents=True,exist_ok=True)
    doc=pdfium.PdfDocument(str(pdf))
    groups=defaultdict(list)
    for r in csv.DictReader(open('M87_visibility_coverage.csv')):
        groups[int(r['scan'])].append(r)
    root=Path('M87_checkpoints')
    diag=json.loads((root/'channels'/'inventory.json').read_text())
    decoded={(x['scan'],x['baseline']) for x in diag if x['state']=='decoded'}
    pols=['RR','LL','RL','LR']
    alltext=[]
    for idx in range(len(doc)):
        p=doc[idx]
        tp=p.get_textpage(); text=tp.get_text_range();alltext.append(text)
        image=p.render(scale=.22).to_pil().convert('RGB')
        assert np.mean(np.asarray(image)<215)>.003,(idx,'blank')
        if idx%16==0:
            board=Image.new('RGB',(4*196,4*230),'#cbd6d9');draw=ImageDraw.Draw(board)
        x=(idx%4)*196;y=(idx%16//4)*230
        board.paste(image,(x+5,y));draw.text((x+6,y+207),str(idx+1),fill='black')
        if idx%16==15 or idx==len(doc)-1:board.save(qa/f'contact-{idx//16:02d}.jpg')
        if idx in [0,1,2,3,6,7,98,99,len(doc)-1]:p.render(scale=1.05).to_pil().save(qa/f'page-{idx+1}.png')
        tp.close();p.close()
    pol_details=json.loads((root/'full_pol_plan.json').read_text())['details']
    revised=any('Evidence before flagging' in page for page in alltext)
    idx=next(i for i,text in enumerate(alltext) if 'Weighted complex means' in text and 'Scan' in text and ('After selections' in text if revised else True)) if revised else 2
    if revised:
        ids=[int(id_) for text in alltext[:idx] if 'Evidence before flagging' in text for id_ in re.findall(r'\bC(\d{3,})\b',text)]
        n=len(json.loads((root/'flag_plan.json').read_text()))+sum(len(json.loads((root/'full_pol_plan.json').read_text())[k]) for k in ('commands','closure'))
        assert sorted(ids)==list(range(1,n+1))
    nplot=0;nevent=0
    for s,rows in groups.items():
        events=json.loads((root/'findings'/f'scan{s}.json').read_text())
        with np.load(root/'channels'/f'scan{s}.npz') as c,np.load(root/'uv'/f'scan{s}.npz') as u:
            for r in rows:
                k=r['station1']+'-'+r['station2'];v=u[k+'_v']; good=np.isfinite(v)
                assert np.array_equal(good,u[k+'_w']>0) and good.sum()==int(r['valid'])
                assert ((s,k) in decoded)==bool(int(r['valid']))
                if (s,k) in decoded:
                    a,ph=c[k]
                    assert np.array_equal(np.isfinite(a),np.isfinite(ph)) and a.shape==(3712,4)
                nevent+=len(events[k])
            for j in range(0,len(rows),6):
                for native in (False,True):
                    page=alltext[idx]
                    assert ('Individual integrations' if native else 'Weighted complex means') in page
                    baselines = {r['station1']+'-'+r['station2'] for r in rows[j:j+6]}
                    expected_labels = Counter()
                    for detail in pol_details:
                        if detail['scan'] == s and detail['baseline'] in baselines:
                            spws = detail['spw'].replace('~', '–').replace(',', ', ')
                            unit = 'SPW' if spws.isdigit() else 'SPWs'
                            expected_labels[f"{detail['missing']} missing in {unit} {spws}"] += 2
                    if revised:
                        assert 'After selections' in page
                    else:
                        assert page.count(' missing in SPW') == sum(expected_labels.values())
                    for label, count in ([] if revised else expected_labels.items()):
                        assert page.count(label) == count, (idx+1, label)
                    if not revised:assert ('at least one listed spectral window' in page) == bool(expected_labels)
                    for r in rows[j:j+6]:
                        k=r['station1']+'-'+r['station2']
                        assert page.count(k)==2,(idx+1,k)
                        assert page.count('Scan '+str(s))>=2
                    idx+=1;nplot+=1
    assert 'Interpretation and selection criteria' in alltext[idx]
    back='\n'.join(alltext[idx:])
    assert f'of {nevent}' in back and 'What to inspect first' in alltext[0]
    found=[]
    for call in re.findall(r'flagdata\([^)]*?\)',back,flags=re.S):
        obj=ast.parse(call.strip(),mode='eval').body
        found.append({q.arg:ast.literal_eval(q.value) for q in obj.keywords})
    expected=[dict(vis='M87_calibrated.ms' if p['target']=='export' else 'channelized_working_copy.ms',
                   mode='manual',field='M87',**p['kwargs']) for p in json.loads((root/'flag_plan.json').read_text())]
    pol_plan=json.loads((root/'full_pol_plan.json').read_text())
    for p in pol_plan['commands']+pol_plan['closure']:
        expected.append(dict(vis='M87_calibrated.ms',mode='manual',field='M87',**p['kwargs']))
    canonical=lambda a:Counter(json.dumps(q,sort_keys=True) for q in a)
    assert canonical(found)==canonical(expected),(len(found),len(expected))
    print(f'Verified {len(doc)} rendered pages, {nplot} plot pages, {sum(map(len,groups.values()))} selections, {nevent} candidates and {len(found)} executable printed calls.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pdf',type=Path);p.add_argument('qa',type=Path)
    args=p.parse_args();verify(args.pdf,args.qa)
