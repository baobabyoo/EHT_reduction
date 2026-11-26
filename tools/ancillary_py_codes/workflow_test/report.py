"""Generate paired averaged/native plots and the pass-specific flag appendix."""
import csv,json,math,sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
from textwrap import wrap

stage=int(sys.argv[1]); tag=['initialflag','2ndflag'][stage-1]
C=Canvas('M87_'+tag+'_summary.pdf',pagesize=(880,965),pageCompression=1)
C.setTitle('M87 visibility inspection / '+tag)
R=Path('M87_checkpoints')
def read(p):return json.loads(Path(p).read_text())
cov=read('coverage.json');events=read('candidates.json')
actions=read('initial.json' if stage==1 else 'residual.json')
partial=read(R/'full_pol_plan.json')['details']
scans=defaultdict(list)
for r in csv.DictReader(open('M87_visibility_coverage.csv')):scans[int(r['scan'])].append(r)
colors=['#EE2C2C','#314F4F','#2E8B57','#0000FF'];hands=['RR','LL','RL','LR']
rgb=np.array([tuple(bytes.fromhex(c[1:])) for c in colors],np.uint8)
def label(x,y,s,n=10,font='Helvetica',color='#21383f'):
    C.setFillColor(HexColor(color));C.setFont(font,n);C.drawString(x,y,s)
def header(title,sub):
    label(40,925,title,20,'Helvetica-Bold');label(40,899,sub,10)
    label(40,18,f'M87_calibrated.uvf     /     {tag}     /     Page {C.getPageNumber()}',8)
def totals(key):return sum(r[key] for r in cov)
header('M87 visibility inspection / '+('initial flags' if stage==1 else 'second pass'),
       'M87_calibrated.uvf   |   17 March 2026   |   15 scans   |   249 baseline-scan pairs')
y=853
for text in [
    f"This pass displays {(totals('before') if stage==1 else totals('before')-totals('first')):,} valid complex samples. Its {len(actions)} four-hand CASA selections cover {totals('first' if stage==1 else 'second'):,} additional samples.",
    ('The strongest sustained loss starts 8 seconds into scan 20 on the AA-PV and NN-PV baselines. The opening signal is the reference for the drop. Scan 23 has a shorter coincident loss on AA-MG and KT-MG. The proposed UTC selections cover only the corroborating partners. NN has low IF 11 amplitudes on its AA and PV baselines in scans 23 and 24.' if stage==1 else 'Five isolated amplitude dips on AA-AX and one phase excursion on AA-PV remain after initial masking. No simultaneous partner passed the same test at those samples. Each proposal therefore covers one baseline, integration and exported IF, affecting four complex samples.'),
    ('Four-hand completeness was checked before averaging. In 38,260 integration-by-IF cells two hands were valid. Twelve station selectors on AX, GL and KT cover those cells. Labels on the plots give the missing hands and SPWs. Other windows can still contribute those colors.' if stage==1 else 'Each dip was below 40% of the local bracketing amplitude in both RR and LL and more than six robust scatter estimates below the scan/IF median. The AA-PV phase excursion exceeded 65 degrees and eight times the median angular deviation in both parallel hands. Their mean unit-phasor lengths exceeded 0.94.'),
    'The only visibility input is the calibrated UVFITS export, with 32 windows and one channel per window. Each group has an averaged page followed by a native page. The native spectra use the actual exported IF frequencies; within-window structure is unresolved. Channel 0 denotes the sole exported channel. Verify the SPW and channel mapping before using these commands on any differently channelized MS.',
    'The example PDF supplied the original scan IDs and rounded scan intervals. These bounds assigned every export record to exactly one scan. All displayed measurements, candidates and proposals were recalculated from the UVFITS. No observing log, original channelized MS or scan-resolved spectral diagnostic files were supplied.',
    'Time averages use four-second bins and all selected IFs. Spectra average over scan time per IF. Both use positive finite weights on complex data. Upper panels show 1000 times the stored amplitude (UNCALIB), lower panels show degrees. Magenta outlines mark valid samples or bins affected by this pass. Amber spans identify additional initial candidates.',
    'Selections use UTC, named stations or baselines, and spectral windows as needed. All four products are included. Approval was assumed under the requested test. Masks were verified against raw UVFITS samples through the local widget selectors. No CASA task was run on a science MS.',
    'Prepared by Codex (GPT-6 family). Exact variant, reasoning level and usage unavailable. '+datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds')]:
    for line in wrap(text,110):label(42,y,line,12);y-=17
    y-=12
C.showPage()
header('Scan index','Numbers are physical plot pages. Counts are newly selected valid samples in this pass.')
pg=3
for j,(s,rr) in enumerate(scans.items()):
    last=pg+2*math.ceil(len(rr)/6)-1
    n=sum(x['first' if stage==1 else 'second'] for x in cov if x['scan']==s)
    label(45,856-30*j,f"Scan {s:2}      {rr[0]['start_utc']} UTC      {len(rr):2} baselines      Pages {pg}-{last}      {n:,} samples",11)
    pg=last+1
C.showPage()

def pair(x,y,coord,val,mark,limits,is_time,spans):
    width,height=220,64
    ok=np.isfinite(val);coord=np.broadcast_to(coord,val.shape)
    for j,arr in enumerate((abs(val)*1000,np.angle(val,deg=True))):
        valid=ok if not j else ok&(abs(val)>0)
        lo,hi=(-180,180) if j else (0,max(1.e-9,float(arr[ok].max())*1.04) if ok.any() else 1.)
        bottom=y-j*(height+6)
        W,H=480,145;pixels=np.full((H,W,3),255,np.uint8)
        for a,b in spans:
            l,r=np.clip((np.array([a,b])-limits[0])/np.ptp(limits)*(W-1),0,W-1).astype(int)
            pixels[:,l:r+1]=[252,240,220]
        for k in (0,2,3,1):
            good=valid[...,k]
            ix=np.clip((coord[...,k][good]-limits[0])/np.ptp(limits)*(W-1),0,W-1).astype(int)
            iy=np.clip((hi-arr[...,k][good])/(hi-lo)*(H-1),0,H-1).astype(int)
            hit=mark[...,k][good]
            for dx,dy in ((-2,0),(2,0),(0,-2),(0,2)):
                pixels[np.clip(iy[hit]+dy,0,H-1),np.clip(ix[hit]+dx,0,W-1)]=[173,41,139]
            pixels[iy,ix]=rgb[k];pixels[iy,np.minimum(ix+1,W-1)]=rgb[k]
        C.drawImage(ImageReader(Image.fromarray(pixels)),x,bottom,width,height)
        C.setStrokeColorRGB(.65,.70,.71);C.setLineWidth(.4);C.rect(x,bottom,width,height)
        for frac in [0,.5,1]:
            a=lo+frac*(hi-lo);label(x-32,bottom+frac*(height-4),str(int(a)) if j else f'{a:.2g}',6)
        if not valid.any():label(x+68,bottom+28,'No valid samples',8)
    for frac in [0,.5,1]:
        a=limits[0]+frac*np.ptp(limits);label(x+frac*(width-20),bottom-10,f'{a:.0f}' if is_time else f'{a:.2f}',7)
    label(x+65,bottom-21,'Time from scan start (s)' if is_time else 'Frequency (GHz)',7)

for s,rr in scans.items():
    with np.load(R/'uv'/f'scan{s}.npz') as u,np.load(R/f'masks{s}.npz') as masks:
        f=u['freq'];bins=u['bin_centers'];data={}
        for r in rr:
            b=r['station1']+'-'+r['station2'];v=np.nan_to_num(u[b+'_v']);w=u[b+'_w'];t=u[b+'_t'];m=masks[b]
            if stage==2:w=np.where((m&1)[:,:,None],0,w)
            marked=((m&stage)!=0)[:,:,None]&(w>0)
            z=np.where(w>0,v,np.nan);wv=v*w
            den=w.sum(0,dtype=float);spec=wv.sum(0,dtype=complex)/np.where(den,den,np.nan)
            avg=[];hits=[]
            for i,mid in enumerate(bins):
                take=(t>=mid-2)&(t<mid+2+(.011 if i==len(bins)-1 else 0))
                den=w[take].sum((0,1),dtype=float)
                avg.append(wv[take].sum((0,1),dtype=complex)/np.where(den,den,np.nan))
                hits.append(marked[take].any((0,1)))
            data[b]=z,marked,t,np.array(avg),np.array(hits),spec
        for st in range(0,len(rr),6):
            for native in (False,True):
                header(f"Scan {s}   /   "+('Native exported samples' if native else 'Weighted complex averages'),
                       rr[0]['start_utc']+' UTC   /   amplitude x 1000 above phase (degrees)   /   magenta: proposed flag    amber: initial candidate')
                for j,k in enumerate((0,2,3,1)):label(620+j*48,925,hands[k],10,'Helvetica-Bold',colors[k])
                for pos,r in enumerate(rr[st:st+6]):
                    b=r['station1']+'-'+r['station2'];z,m,t,a,h,spec=data[b]
                    for freq in (False,True):
                        row=2*(pos//3)+freq;x=44+284*(pos%3);y=788-row*207
                        label(x,y+80,b+f'   /   Scan {s}   /   '+('Frequency' if freq else 'Time'),10,'Helvetica-Bold')
                        if stage==1:
                            for e in partial:
                                if e['scan']==s and e['baseline']==b:label(x,y+69,f"{e['missing']} missing in SPWs {e['spw']}",7,color='#862566')
                        coord=(f[None,:,None] if freq else t[:,None,None]) if native else (f if freq else bins)[:,None]
                        val=z if native else (spec if freq else a);mark=m if native else (m.any(0) if freq else h)
                        spans=[]
                        if stage==1:
                            for e in events[str(s)][b]:
                                if not freq and 'lo' in e:spans.append((e['lo'],e['hi']))
                                if freq and 'spw' in e:spans.append((f[e['spw']]-.012,f[e['spw']]+.012))
                                if freq and 'first' in e:spans.append((f[e['first']],f[e['last']]))
                        pair(x,y,coord,val,mark,(f.min()-.03,f.max()+.03) if freq else (0.,240.01),not freq,spans)
                C.showPage()
    print(s,flush=True)

if stage==1:
    lines=[]
    for s,entries in events.items():
        for b,ev in entries.items():
            for e in ev:
                where=f"{e['lo']:.3f}-{e['hi']:.3f}s" if 'lo' in e else f"IF {e['spw']}" if 'spw' in e else f"IF {e['first']}-{e['last']}"
                measure=' '.join(f'{k} {e[k]:.2f}' for k in ('ratio','degrees','deg_per_ghz') if k in e)
                lines.append(f"{s:>2}   {b:7}  {','.join(e['pols']):7}   {e['kind']:28}  {where:20}  {measure}")
    for st in range(0,len(lines),49):
        header('Initial candidate ledger','Individual measurements. The CASA appendix contains the selections proposed for flagging.')
        for j,line in enumerate(lines[st:st+49]):label(40,864-16*j,line,9,'Courier')
        C.showPage()
for st in range(0,len(actions),6):
    header('Individual CASA commands','All four hands   /   ordinary M87_calibrated.ms target   /   UTC')
    y=855
    for a in actions[st:st+6]:
        label(40,y,f"Scan {a['scan']}    /    {a['reason']}",10,'Helvetica-Bold');y-=17
        items=list(a['k'].items())
        for j,(k,v) in enumerate(items):
            label(43,y,('flagdata(' if j==0 else '         ')+k+'='+repr(v)+(',' if j+1<len(items) else ')'),9,'Courier');y-=13
        y-=15
    C.showPage()
C.save()
