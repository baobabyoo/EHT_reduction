"""Assemble the M87 report. Requires reportlab and pypdf. Run in inspection/.
The overview records the scientific review of this observation. For another run,
regenerate findings, attribution and decisions before reusing its report text.
"""
import argparse
import numpy as np
import csv
import json
import math
import tempfile
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from pypdf import PdfReader,PdfWriter

ROOT=Path('M87_checkpoints')
W,H=842.4,936
INK='#172e3a'
TEAL='#006d77'
MUTED='#45606c'


class Sheet:
    def __init__(self,path,offset):
        self.c=Canvas(str(path),pagesize=(W,H));self.n=offset;self.active=False
    def line(self,text,x,y,size=11,font='Helvetica',color=INK):
        c=self.c;c.setFillColor(HexColor(color));c.setFont(font,size);c.drawString(x,y,text)
    def finish(self):
        if self.active:
            self.line('M87  /  e26m17-1-b3',40,24,9,color=MUTED)
            self.line(str(self.n),W-64,24,9,color=MUTED)
            self.c.showPage();self.active=False
    def page(self,title,sub=''):
        self.finish();self.n+=1;self.active=True;self.title=title
        self.line(title,40,H-54,23,'Helvetica-Bold')
        self.line(sub,40,H-75,10,color=MUTED)
        self.c.setStrokeColor(HexColor('#b5c6ca'));self.c.line(40,H-85,W-40,H-85)
        self.y=H-110
    def room(self,lines=1):
        if self.y < 55+lines*16:
            self.page(self.title+' (continued)' if not self.title.endswith('(continued)') else self.title)
    def para(self,text,size=11):
        words=text.split();line=''
        for w in words:
            if stringWidth((line+' '+w).strip(),'Helvetica',size)>W-88:
                self.room();self.line(line,42,self.y,size);self.y-=size*1.4;line=''
            line=(line+' '+w).strip()
        if line:self.room();self.line(line,42,self.y,size);self.y-=size*1.4
        self.y-=9
    def heading(self,title):
        self.room(3);self.line(title,42,self.y,14,'Helvetica-Bold',TEAL);self.y-=19
    def close(self):
        self.finish();self.c.save()


def emit_report(dest,model):
    rows=list(csv.DictReader(open('M87_visibility_coverage.csv')))
    byscan=defaultdict(list)
    for row in rows:byscan[int(row['scan'])].append(row)
    findings={s:json.loads((ROOT/'findings'/f'scan{s}.json').read_text()) for s in byscan}
    plans=json.loads((ROOT/'flag_plan.json').read_text())
    audit=json.loads((ROOT/'export_flag_audit.json').read_text())
    exp=[p for p in plans if p['target']=='export']
    assert len(exp)==len(audit) and all(v['mismatch']==0 and v['kwargs']==p['kwargs'] for p,v in zip(exp,audit))
    fullness=json.loads((ROOT/'full_pol_plan.json').read_text())
    counts=fullness['counts']
    checked={name:json.loads((ROOT/f'full_pol_{name}.json').read_text()) for name in ('fresh','quality')}
    assert all(a['mismatches']==0 and a['partial_after']==0 for a in checked.values())
    assert checked['fresh']['new_flags']==counts['valid_to_flag']
    valid_samples=sum(int(r['valid']) for r in rows)
    total_samples=sum(int(r['total']) for r in rows)
    perkind=Counter(e['kind'] for b in findings.values() for events in b.values() for e in events)
    narrow={}
    for p in plans:
        if p['target']!='channelized':continue
        q=p['kwargs']; a,bs=q['antenna'].split('&')
        for b in bs.split(','):
            for sel in q['spw'].split(','):
                key=(p['scan'],'-'.join(sorted([a,b])),sel)
                narrow.setdefault(key,set()).update(q['correlation'].split(','))
    inv=json.loads((ROOT/'channels'/'inventory.json').read_text())
    pages={(r['scan'],r['baseline']):r['page'] for r in inv if r['state']=='decoded'}
    ordered=sorted(plans,key=lambda p:(0 if '&' not in p['kwargs']['antenna'] else 1 if ',' in p['kwargs']['antenna'] else 2 if p['target']=='export' else 3,p['scan'],p['kwargs']['antenna']))
    all_commands=ordered+fullness['commands']+fullness['closure']
    evidence_counts=Counter(p['scan'] for p in all_commands)
    evidence_pages=sum(math.ceil(n/3) for n in evidence_counts.values())
    lookup={};first=0
    for s,group in byscan.items():
        for j,r in enumerate(group):lookup[s,r['station1']+'-'+r['station2']]=first+2*(j//6)
        first+=2*math.ceil(len(group)/6)
    plot_count=first
    from datetime import timedelta
    observed={}
    for s,group in byscan.items():
        with np.load(ROOT/'uv'/f'scan{s}.npz') as uv:
            times=[uv[r['station1']+'-'+r['station2']+'_t'] for r in group]
        anchor=datetime.strptime(group[0]['start_utc'],'%H:%M:%S.%f')
        stamp_utc=lambda sec:(anchor+timedelta(seconds=float(sec))).strftime('%H:%M:%S.%f')[:-3]
        interval=stamp_utc(min(t.min() for t in times))+' – '+stamp_utc(max(t.max() for t in times))
        if group[0].get('measured_start_utc'):
            interval=' – '.join(group[0][k].split('T')[1] for k in ('measured_start_utc','measured_end_utc'))
        observed[s]=interval
    stamp=datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d %H:%M UTC+8')
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);front=tmp/'front.pdf';back=tmp/'back.pdf'
        page=Sheet(front,0)
        page.page('M87 calibrated visibility inspection',f"17 March 2026   /   {min(observed.values()).split(' – ')[0]}–{max(observed.values()).split(' – ')[1]} UTC   /   {len(byscan)} scans   /   {len(rows)} baseline–scan selections" )
        page.heading('What to inspect first')
        page.para('PV loses its parallel-hand signal shortly after scan 20 begins. On AA-PV the first 4 s RR mean is 0.415 on the plotted scale; on NN-PV it is 0.284. From 8 s onward the respective medians are 0.013 and 0.012. AA-NN and AA-KT remain stable. The flagged candidate is the long low interval, from 05:48:08 UTC to scan end. The bright opening bins establish the reference.')
        page.para('MG drops out during scan 23, 06:11:04-06:11:32 UTC. Inside the interval AA-MG has median RR/LL amplitudes of 0.017/0.015 versus 0.269/0.267 outside it. KT-MG falls to 0.019/0.016 from 0.090/0.099, while AA-KT and AA-PV remain stable. The abrupt recovery and independent partners support an MG selection.')
        page.para('NN is implicated in two interior-channel features. All 26 detections at SPW 11 channel 41 and all 27 at SPW 28 channel 97 occur on baselines to NN. Across the run all six partners contribute at each location. The channel figures also show a broader SPW 28 distortion on AA-NN and NN-PV. Individual hand behavior differs by partner, so retain the supported hands and partners for each scan.')
        page.para('The most common peaks are at the final channel (115) in SPWs 24, 8 and 3. They recur on 224, 223 and 211 of 240 available baseline spectra, respectively. Their widespread occurrence favors a shared spectral-edge problem. A station diagnosis requires a feature confined to baselines sharing that station.')
        page.heading('Incomplete polarization coverage')
        page.para(f"{counts['partial']:,} integration-by-SPW cells contain only two valid hands, all in scans 2, 4, 6 and 8. AX, GL and KT contribute only R at the affected windows. The final appendix lists the missing products by baseline and the CASA calls for enforcing four-hand coverage.")
        page.heading('Plotted files and provenance')
        page.para('M87_calibrated.uvf supplies integrations, original IF centers, correlations and weights. The source-specific M87_scan<N>_plots_vs_freq.ps files under diagnostics_2026-09-16_15-00-11/PLOTS_VISIBILITIES supply scan-level channel spectra. Substitute the original scan ID from the index for <N>. Their printed baseline labels and polarization legends identify the source pages. Original scan IDs and channel grids come from the matching list.obs.')
        page.para(f'Analysis model: {model}. Report assembled {stamp}. Usage attributable solely to this analysis is unavailable.')
        page.heading('How to read the figures')
        page.para('The first plot sequence shows representative input data for each numbered command. The next sequence covers every baseline after masking. In that sequence each group has an averaged page followed immediately by the same baselines at finer resolution. Upper panels show amplitude; lower panels show wrapped phase. RR is red, RL green, LR blue and LL dark slate. On command evidence pages, a missing-product label identifies the affected exported windows. Other windows can still supply that hand. In cleaned coverage, a magenta bar means at least one contribution was removed or withheld within the marked interval. Amber bands identify time intervals for inspection. Blue bands and rings mark spectral candidates. Inspect the full event ledger for affected hands and precise limits.')
        page.para('UVFITS BUNIT is UNCALIB. Time-domain and averaged amplitudes use 1000 times the stored modulus. Fine spectra use mJy from the diagnostic Jy axis. Absolute flux calibration is uncertain: picard.out reports missing weather and ANTAB inputs. Compare ratios within a view.')
        page.page('Scan index and data coverage','Plot pages are numbered by their physical position in this PDF. Every occupied cell carries its baseline and original scan ID.')
        columns=[42,95,314,419,559,695]
        titles=['Scan','Measured UTC interval','Baselines','Valid samples (input)','Available spectra','Clean plot pages']
        def table_header():
            for x,title in zip(columns,titles):page.line(title,x,page.y,10,'Helvetica-Bold')
            page.y-=20
        table_header()
        for s,group in byscan.items():
            if page.y<80:
                page.page('Scan index and data coverage (continued)');table_header()
            interval=observed[s]
            values=[str(s),interval,str(len(group)),f"{sum(int(r['valid']) for r in group):,}",str(sum((s,r['station1']+'-'+r['station2']) in pages for r in group))]
            for x,value in zip(columns,values):page.line(value,x,page.y,10)
            page.c.saveState();page.c.translate(columns[-1],page.y);page.c.doForm('range'+str(s));page.c.restoreState()
            page.y-=19
        page.y-=12;page.heading('Selection and averaging')
        page.para(f'{valid_samples:,} of {total_samples:,} exported complex samples have finite values and positive weights. For each hand, average wV and divide by the sum of weights before taking modulus and phase. Time points on averaged pages combine all 32 IFs in 4 s bins. Frequency points combine all valid times within the scan for each IF. Fine time pages plot each integration (about 0.4 s), IF and hand at its actual timestamp.')
        page.para('Fine spectra preserve one scan-level point per observed hand and channel. In cleaned coverage, channel selections suppress the matching channel and hand. A time cut can make the residual scan average unknowable: withhold the affected diagnostic SPW/hand. Conversely, withhold a coarse IF/hand when a selected fine channel contributes to that unresolved export sample. Withheld samples are display exclusions, not extra CASA flags. Marker centers from the original PostScript are calibrated against the actual tick marks on each baseline page. There are 116 channels per IF at 0.5 MHz spacing. Amplitudes and phases reconstructed from those coordinates are approximate. These spectra cannot locate a feature in time within its scan.')
        page.para('Nine baseline-scan selections have rows but zero usable samples: AX-GL, AX-KT and GL-KT in scans 4, 6 and 8. These appear as empty panels. Of 240 usable spectra, 218 contain four hands, 20 have RR/RL only and two have RR/LR only. The science fringe log independently reports interpolation difficulties in these early scans; it cannot by itself identify the cause of each missing visibility.')
        page.para('Station set: AA, AX, GL, KT, MG, NN and PV. Coverage counts use the stations present in each scan and exclude autocorrelations. Cleaned coverage occupies '+str(plot_count)+' pages. Candidate details and individual flag commands follow.')
        page.para(f'The index gives first and last recorded UVFITS integration centers. Original scan IDs are matched through list.obs. The next {evidence_pages} pages show up to two examples per command; the index points to the subsequent cleaned coverage.')
        front_count=page.n
        shift=front_count+evidence_pages+1
        lookup={key:value+shift for key,value in lookup.items()}
        for s,group in byscan.items():
            pg=lookup[s,group[0]['station1']+'-'+group[0]['station2']]
            page.c.beginForm('range'+str(s));page.line(f'{pg}–{pg+2*math.ceil(len(group)/6)-1}',0,0,10);page.c.endForm()
        first=shift+plot_count
        page.close()
        notes=Sheet(back,first-1)
        notes.page('Interpretation and selection criteria','Channel and SPW indices are zero-based. Time offsets are relative to the nominal scan anchors shown on plot pages.')
        notes.heading('Time and phase')
        notes.para('NN-PV, scan 2: RR/LL collapse to about 2% of their normal amplitudes between 25 and 64 s. Only 18% of individual parallel-hand phases lie within 30 degrees of zero in the early interval, versus about 95-96% after 72 s. Other available partners do not establish a single responsible endpoint. Retain the baseline-specific candidate.')
        notes.para('The time screen marks two or more 4 s bins below 0.2 times the scan median in both parallel hands on coherent baselines, and upward excursions above 2 times the hand median and 6 robust standard deviations. Phase-step candidates exceed 55 degrees between adjacent coherent bins, using the wrapped phase difference. Coherence here is the modulus of the weighted complex mean divided by the weighted mean modulus. A single jump spanning two bins does not establish which side is bad.')
        notes.para('A fitted slope required at least eight contiguous IFs with coherence above 0.3 in each scan half. Fits had to agree in sign and within 50% in slope, span over 25 degrees in each half, and leave less than 18 degrees rms residual. No parallel-hand slope met all criteria. Lower-SNR slopes and structure within an IF can still escape this test. Weak cross-hand phase scatter alone does not warrant flagging.')
        notes.heading('Frequency and antenna attribution')
        notes.para('Window candidates compare each interior IF to its two neighbors on a coherent parallel hand. A ratio outside 0.55-1.5 or a phase displacement above 35 degrees prompts review. Neighbor ratios can be biased by a single bad window. The export recommendations for recurring broad distortions select IF 28 on the affected AA-NN and NN-PV products. NN-PV scan 2 also has independent split-scan confirmation in RL.')
        notes.para('For narrow peaks use the within-window hand median and 1.4826 times the median absolute deviation. The paired screen requires RR above 2 times and LL above 1.5 times their medians, both above 3 robust deviations. A single-hand peak requires a ratio above 3 and more than 10 robust deviations. Include contributing hands above 1.5 times the median and 3 deviations. Only channel locations recurring in at least three scans and three distinct baselines receive proposed commands.')
        notes.para('The earlier bandpass inspection identified a drop in NN SPW 28 channels 97-115 and a feature at AX channel 97. NN involvement on six different partners and the absence of the channel-97 peak on controls without NN favor NN in these M87 data. For RR and LL, group corroborating partners in the same scan at NN. RL and LR depend on the ordered endpoints; commands preserve the actual stored product and baseline. Shared channel-edge peaks are restricted to each positive hand and baseline.')
        notes.heading('Candidate ledger')
        notes.para(', '.join(f'{n:,} {k}' for k,n in sorted(perkind.items()))+'. Each row below gives an averaged/fine plot-page pair, baseline, selected hand(s), measurement and disposition. For channels, peer counts give simultaneous baselines with the same channel peak that touch either endpoint (shared) or neither endpoint (other). For time and IF candidates, peers match the event type and overlap in time or match the window. Counts are supporting context, not proof of causality.')
        entries=[]
        for s,group in byscan.items():
            byb=findings[s]
            for r in group:
                b=r['station1']+'-'+r['station2'];pg=lookup[s,b]
                for e in byb[b]:
                    kind=e['kind']; pp='/'.join(e['pols'])
                    def matches(o):
                        if o['kind']!=kind:return False
                        if 'lo' in e:return o['lo']<e['hi'] and o['hi']>e['lo']
                        return (e.get('spw'),e.get('chan'))==(o.get('spw'),o.get('chan'))
                    others=[k for k,vs in byb.items() if k!=b and any(matches(o) for o in vs)]
                    shared=sum(bool(set(b.split('-'))&set(k.split('-'))) for k in others)
                    if kind=='channel peak':
                        sel=f"{e['spw']}:{e['chan']}"
                        detail=f"{sel}  {e['ghz']:.6f} GHz   "+'/'.join(f'{v:.1f}' for v in e['ratios'])+'x'
                        decision='native flag' if (s,b,sel) in narrow else 'review'
                    elif 'lo' in e:
                        value=f"{e['degrees']:+.0f} deg" if 'degrees'in e else f"{e['ratio']:.2f}x"
                        detail=f"{kind}   {e['lo']:g}-{e['hi']:g} s   {value}"
                        decision='time flag' if kind=='coherent amplitude loss' else 'review'
                        if s==20 and 'PV' in b and e['lo']==0:decision='opening ref.'
                    else:
                        detail=f"IF {e['spw']}   {e['ratio']:.2f}x   {e['degrees']:+.0f} deg"
                        decision='export flag' if e['spw']==28 and b in ('AA-NN','NN-PV') else 'review'
                    entries.append((s,pg,b,pp,detail,f'{shared}/{len(others)-shared}',decision))
        for i in range(0,len(entries),46):
            notes.page('Visibility candidate ledger',f'Entries {i+1}-{min(i+46,len(entries))} of {len(entries)}   /   ratios follow the listed order of polarizations')
            xs=[40,72,136,195,300,656,726]
            for x,v in zip(xs,['Scan','Pages','Baseline','Hands','Measurement','Peers S/O','Action']):notes.line(v,x,notes.y,9,'Helvetica-Bold',TEAL)
            notes.y-=18
            for s,pg,b,pol,detail,peers,action in entries[i:i+46]:
                for x,v in zip(xs,[str(s),f'{pg}/{pg+1}',b,pol,detail,peers,action]):notes.line(v,x,notes.y,9)
                notes.y-=16
        notes.page('CASA flagging selections','Proposed commands only   /   input UVFITS and science products were opened read-only')
        notes.heading('Choose the working Measurement Set')
        notes.para('M87_calibrated.ms refers to a new working MS imported from M87_calibrated.uvf with importuvfits and antnamescheme="old". It has one output channel per SPW. The following export calls were executed in order on a disposable full import, with flagbackup=False for verification. Independent station, UTC, polarization and SPW masks predicted every changed FLAG cell. All '+str(len(audit))+' calls matched exactly, with '+f"{sum(z['changed'] for z in audit):,}"+' additional flags across the tested copy. The printed calls use the normal CASA backup default.')
        notes.para('channelized_working_copy.ms is a placeholder for a working copy of the original 116-channel VLBI.ms with the original scan IDs and SPW/channel grid. The original MS was unavailable here. Channel indices and field/scan times were checked against list.obs and the diagnostic spectra. The native commands have not been executed on that MS. They are alternatives for data at that resolution. Do not apply native-channel indices to the one-channel export.')
        notes.para('First come the station time selections and NN selections supported by independent partners. The residual commands cover the specific baselines and hands that passed review. Some station-associated rows deliberately name partners. For example, NN&AA,AX,GL limits the selection to the confirmed partners. The complete plan expands back to the exact baseline/hand/channel candidate set in each scan.')
        notes.para('For isolated phase steps and time peaks with weak partner evidence, inspect or recalibrate before discarding samples. In scan 20, keep the opening PV reference interval. The proposed time flag starts 8 s into that scan. Confirm all selections against the intended edition of the working MS before applying them.')
        ordering=lambda p: (0 if '&' not in p['kwargs']['antenna'] else 1 if ',' in p['kwargs']['antenna'] else 2 if p['target']=='export' else 3,p['scan'],p['kwargs']['antenna'])
        ordered=sorted(plans,key=ordering)
        for i in range(0,len(ordered),12):
            notes.page('Individual CASA commands',f'Selections {i+1}-{min(i+12,len(ordered))} of {len(ordered)}   /   executed by the analyst only on the intended working MS')
            for n,p in enumerate(ordered[i:i+12],i+1):
                kw=p['kwargs'];target='M87_calibrated.ms' if p['target']=='export' else 'channelized_working_copy.ms'
                notes.line(f"{n:03d}   Scan {p['scan']}   /   {p['reason']}",42,notes.y,9,'Helvetica-Bold',TEAL);notes.y-=13
                lines=[f"flagdata(vis='{target}', mode='manual', field='M87',"]
                args=[f"{k}='{v}'" for k,v in kw.items()]
                current='         '
                for j,arg in enumerate(args):
                    token=arg+(', ' if j<len(args)-1 else ')')
                    if len(current)+len(token)>118:
                        lines.append(current.rstrip());current='         '
                    current+=token
                lines.append(current.rstrip())
                for ln in lines:notes.line(ln,42,notes.y,8.5,'Courier');notes.y-=11
                notes.y-=10
        notes.page('Require all four polarizations','UVFITS export only  /  simultaneous integration, spectral window and baseline  /  original scan IDs')
        notes.para(f"Across all 249 selections, {counts['complete']:,} cells contained all four valid hands, {counts['partial']:,} had partial coverage and {counts['empty']:,} were already empty. Positive finite weights and finite complex values determine validity before averaging. The plot bar projects the partial cells onto time or SPW. Frequency bars refer to the exported IF even on the channel-resolved page.")
        notes.para("A station contributes the first letter of the correlation when it is first in the ordered baseline and the second letter when it is second. In these selections the surviving products use its R feed. On evidence plots the missing-hand labels describe input data. Bars in the cleaned atlas mark removed or withheld support.")
        positions = (42, 100, 172, 270, 440, 550)
        for x, title in zip(positions, ('Scan', 'Baseline', 'Missing hands', 'SPWs', 'Partial cells', 'Plot pages')):
            notes.line(title, x, notes.y, 10, 'Helvetica-Bold', TEAL)
        notes.y -= 18
        for row in fullness['details']:
            pg = lookup[row['scan'], row['baseline']]
            values = (str(row['scan']), row['baseline'], row['missing'], row['spw'], f"{row['cells']:,}", f"{pg}/{pg+1}")
            for x, value in zip(positions, values):
                notes.line(value, x, notes.y, 9, 'Courier')
            notes.y -= 16
        notes.y-=6
        notes.para("The scan index includes 124 integration records stamped at or within 2 milliseconds beyond the observing log's rounded stop times. Each record was matched to exactly one scan. The earlier quality findings and their 580 proposed commands retain their original selections.")
        for title,items,caption in [
            ('Require all four hands in the original export',fullness['commands'],
             f"These station selectors cover every observed partial cell. CASA added {checked['fresh']['new_flags']:,} flags on a fresh disposable import and preserved every complete cell."),
            ('Complete the existing export quality flags',fullness['closure'],
             f"Use each complementary-hand call only after its matching export quality flag. With all 23 quality calls already applied, this category plus the preceding station calls added {checked['quality']['new_flags']:,} flags. The final mask matched the expected mask in every cell.")]:
            offset=len(ordered)+(len(fullness['commands']) if items is fullness['closure'] else 0)
            for i in range(0,len(items),10):
                notes.page(title,f"Additional CASA selections {i+1}-{min(i+10,len(items))} of {len(items)}  /  imported M87_calibrated.ms")
                notes.para(caption)
                for number,p in enumerate(items[i:i+10],offset+i+1):
                    kw=p['kwargs']
                    notes.line(f"{number:03d}   Scan {p['scan']}   /   {p['reason']}",42,notes.y,9,'Helvetica-Bold',TEAL);notes.y-=14
                    for line in ["flagdata(vis='M87_calibrated.ms', mode='manual', field='M87',",
                                 f"         antenna='{kw['antenna']}', timerange='{kw['timerange']}'" +
                                 (',' if 'spw' in kw or 'correlation' in kw else ')')]:
                        notes.line(line,42,notes.y,9,'Courier');notes.y-=13
                    extra=[f"{k}='{kw[k]}'" for k in ('spw','correlation') if k in kw]
                    if extra:
                        notes.line('         '+', '.join(extra)+')',42,notes.y,9,'Courier');notes.y-=13
                    notes.y-=14
        notes.close()
        writer=PdfWriter();writer.append(front,outline_item='Summary and coverage')
        for s in byscan:
            if evidence_counts[s]:
                part=ROOT/'review_plots'/f'evidence{s}.pdf'
                assert len(PdfReader(part).pages)==math.ceil(evidence_counts[s]/3)
                writer.append(part,outline_item=f'Command evidence / scan {s}')
        for s in byscan:
            part=ROOT/'review_plots'/f'clean{s}.pdf'
            assert len(PdfReader(part).pages)==2*math.ceil(len(byscan[s])/6)
            writer.append(part,outline_item=f'Scan {s}')
        writer.append(back,outline_item='Interpretation, candidate ledger and commands')
        writer.add_metadata({'/Title':'M87 calibrated visibility inspection','/Author':model})
        temp=dest.with_suffix('.writing.pdf')
        with temp.open('wb') as stream:writer.write(stream)
        temp.replace(dest)
        print(len(writer.pages),'pages;',len(entries),'entries;',len(plans),'flag calls')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=Path('M87_revised_visibility_inspection.pdf'))
    ap.add_argument('--model',required=True)
    args=ap.parse_args();emit_report(args.output,args.model)
