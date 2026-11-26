"""Build per-scan frequency checkpoints for the full visibility report.

Run from inspection/ with Python 3, NumPy and Astropy. Source and paths may be
passed on the command line. Each scan archive holds one amp/phase matrix per
baseline and the corresponding GHz grid. Rebuild a scan if its input changes.
"""
import argparse
import json
import mmap
import re
from pathlib import Path

import numpy as np
from astropy.io import fits
from diagnostic_spectrum import decode_page

NUM = r"[-.\d]+"
LINE = re.compile(rf"({NUM})\s+({NUM})\s+m\s+({NUM})\s+({NUM})\s+l")


def labels(group):
    tokens = iter(re.findall(r"\(([^()]*)\)Tj", group))
    result = []
    for value in tokens:
        if r"\32710" in value:
            coefficient = value.split(r"\32710")[0]
            result.append(float(coefficient or "1") * 10**int(next(tokens)))
        else:
            result.append(float(value))
    return result


def axes(half, frequency=False):
    # Read major ticks in the path immediately preceding each numeric label group.
    header = re.split(r"(?m)^"+NUM+" "+NUM+" "+NUM+" rg$",half,maxsplit=1)[0]
    parts = re.split(r"\bBT\b(.*?)\bET\b",header,flags=re.S)
    group = 1 if frequency else (3 if "(Amp [Jy])Tj" in header else 1)
    vals = labels(parts[group])
    lines = np.array(LINE.findall(parts[group-1]),float)
    x,y,x1,y1 = lines.T
    if frequency:
        select = (abs(abs(y1-y)-5.25)<.006)&(abs(x1-x)<.001)&(abs(y-y.max())<.01)
        coords = sorted(set(x[select]))
        vals = np.array(vals)/1000
    else:
        select = (abs(abs(x1-x)-5.25)<.006)&(abs(y1-y)<.001)&(abs(x-x.min())<.01)
        coords = sorted(set(y[select]),reverse=True)
    if len(coords)!=len(vals) or len(vals)<2:
        raise ValueError(f"Tick mismatch {coords} {vals}")
    predicted=np.interp(np.array(vals,float),[vals[0],vals[-1]],[coords[0],coords[-1]])
    if max(abs(predicted-coords))>.02:
        raise ValueError("Nonlinear or misidentified ticks")
    return [[coords[0],vals[0]],[coords[-1],vals[-1]]]


def collect(uvfits, directory, log, out):
    out.mkdir(parents=True,exist_ok=True)
    with fits.open(uvfits) as h:
        head=h[0].header
        source=head['OBJECT'].strip()
        centers=(head['CRVAL4']+h['AIPS FQ'].data['IF FREQ'][0])/1e9
        stations=[str(s).strip() for s in h['AIPS AN'].data['ANNAME']]
    spws=re.findall(r'^\s*(\d+)\s+\S+\s+(\d+)\s+GEO\s+([\d.]+)\s+([\d.]+)',log.read_text(),re.M)
    if len(spws)!=len(centers):
        raise ValueError('SPW count disagrees with observing log')
    nchan=int(spws[0][1]); spacing=float(spws[0][3])/1000
    for i,n,f0,width in spws:
        if int(n)!=nchan or float(width)/1000!=spacing or abs(float(f0)+(nchan-1)*spacing/2-centers[int(i)]*1000)>.002:
            raise ValueError("Nonuniform or mismatched frequency grid")
    pols=['RR','LL','RL','LR']
    manifest=out/"inventory.json"
    inventory=json.loads(manifest.read_text()) if manifest.exists() else []
    for file in sorted(directory.glob(f'{source}_scan*_plots_vs_freq.ps')):
        scan=int(re.search(r'scan(\d+)',file.name)[1])
        known=[r for r in inventory if r['scan']==scan and r.get('source_mtime')==file.stat().st_mtime_ns]
        if known and all(r['state']!='unresolved' for r in known) and (out/f'scan{scan}.npz').exists():
            continue
        arrays={}; info=[]
        with file.open('rb') as stream, mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as mm:
            pages=list(re.finditer(rb'^%%Page: (\d+) \d+',mm,re.M))
            for j,m in enumerate(pages):
                page=mm[m.start():pages[j+1].start() if j+1<len(pages) else len(mm)].decode('latin1')
                matches=[(a,b) for a in stations for b in stations if f'({a}{b})Tj' in page]
                if len(matches)!=1:
                    raise ValueError(f'Unexpected baseline labels in {file.name} page {j+1}: {matches}')
                a,b=matches[0]
                record=dict(scan=scan,baseline=f'{a}-{b}',page=j+1,file=file.name,source_mtime=file.stat().st_mtime_ns)
                info.append(record)
                if a==b:
                    record['state']='autocorrelation';continue
                if not re.search(r'\bc\s+f\b',page):
                    record['state']='empty';continue
                amp,phase=page.split(f'({a}{b})Tj')
                try:
                    config=dict(frequency_ghz=axes(amp,True),amplitude_jy=axes(amp),phase_deg=axes(phase),spacing_mhz=spacing,channels_per_if=nchan)
                    freq,am,ph=decode_page(page,dict(baseline=[a,b],channel_diagnostic=config),centers,pols)
                    arrays['frequency']=freq
                    arrays[f'{a}-{b}']=np.stack([am,ph]).astype('float32')
                    record.update(state='decoded',samples=int(np.isfinite(am).sum()))
                except (ValueError,IndexError,StopIteration) as error:
                    record.update(state='unresolved',error=str(error))
        checkpoint=out/f'scan{scan}.tmp.npz'
        np.savez_compressed(checkpoint,**arrays)
        checkpoint.replace(out/f'scan{scan}.npz')
        inventory=[r for r in inventory if r['scan']!=scan]
        inventory.extend(info)
        tmp_manifest=manifest.with_suffix('.tmp.json')
        tmp_manifest.write_text(json.dumps(inventory,indent=1))
        tmp_manifest.replace(manifest)
        print(scan,{k:sum(r['state']==k for r in info) for k in set(r['state'] for r in info)},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('uvfits','diagnostics','scanlog','out'):
        p.add_argument(name,type=Path)
    args=p.parse_args()
    collect(args.uvfits,args.diagnostics,args.scanlog,args.out)
