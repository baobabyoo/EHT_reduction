"""Verify the newly built PDFs. Run using the Python PDF dependencies."""
from pathlib import Path
import re,json,ast
import pypdfium2 as pdf
import numpy as np

coverage=json.loads(Path('coverage.json').read_text())
for tag,k in [('initialflag','initial'),('2ndflag','residual')]:
    path=Path(f'M87_{tag}_summary.pdf')
    doc=pdf.PdfDocument(path)
    texts=[]
    for i,p in enumerate(doc):
        textpage=p.get_textpage();text=textpage.get_text_range()
        texts.append(text)
        image=p.render(scale=.2).to_pil()
        assert np.mean(np.array(image)<220)>.001,(i,'blank')
        if i==2 and tag=='initialflag':p.render(scale=.83).to_pil().save('layout_check.png')
        textpage.close();p.close()
    n=2
    for scan in sorted(set(x['scan'] for x in coverage)):
        pairs=[x['baseline'] for x in coverage if x['scan']==scan]
        for j in range(0,len(pairs),6):
            for typ in ['Weighted complex averages','Native exported samples']:
                assert typ in texts[n]
                for b in pairs[j:j+6]:
                    assert texts[n].count(b)==2,(n,b)
                n+=1
    assert n==98
    calls=[]
    for src in re.findall(r'flagdata\([^)]*\)','\n'.join(texts),re.S):
        calls.append({kw.arg:ast.literal_eval(kw.value) for kw in ast.parse(src,mode='eval').body.keywords})
    assert calls==[e['k'] for e in json.loads(Path(k+'.json').read_text())]
    print(tag,len(doc),'pages checked; 96 plot pages;',len(calls),'printed calls verified')
