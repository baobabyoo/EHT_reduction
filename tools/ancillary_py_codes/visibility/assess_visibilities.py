"""Screen all cached baseline/scan selections. Findings are candidates for review.

Usage: python assess_visibilities.py M87_checkpoints M87_visibility_coverage.csv
The output per scan is a JSON list. Times are seconds from original scan start.
Frequency indices are zero-based. Observations below these screens can still be
evaluated in the paired plots. Run after completing both checkpoint collectors.
"""
import argparse
import csv
import json
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

POLS=['RR','LL','RL','LR']


def runs(indices):
    return np.split(indices,np.flatnonzero(np.diff(indices)>1)+1) if len(indices) else []


def robust_scatter(data,axis=None):
    if axis is None and not np.isfinite(data).any():
        return np.nan
    return 1.4826*np.nanmedian(abs(data-np.nanmedian(data,axis=axis,keepdims=True)),axis=axis)


def screen(row,uv,channel):
    key=row['station1']+'-'+row['station2']
    avg=uv[key+'_avg']
    spec=uv[key+'_spectrum']
    t=uv['bin_centers']
    events=[]
    def record(kind,hands,**detail):
        events.append(dict(kind=kind,pols=[POLS[i] for i in hands],**detail))
    # Per-bin signal coherence guards against interpreting low-SNR phase wraps.
    raw=uv[key+'_v']
    weight=uv[key+'_w']
    seconds=uv[key+'_t']
    # Preserve the quality review's original half-open interval. The separate
    # completeness review includes exported integrations at rounded scan ends.
    in_review=seconds < float(uv['duration'])
    if not in_review.all():
        raw,weight,seconds=raw[in_review],weight[in_review],seconds[in_review]
        from collect_visibility_samples import weighted_mean
        spec=weighted_mean(raw,weight,0)
        avg=avg.copy()
        last=seconds>=t[-1]-2
        avg[-1]=weighted_mean(raw[last],weight[last],(0,1))
    coherence=np.full(avg.shape,np.nan)
    for i,mid in enumerate(t):
        m=(seconds>=mid-2)&(seconds<mid+2)
        scalar=np.nansum(abs(raw[m])*weight[m],axis=(0,1),dtype=float)
        total=weight[m].sum(axis=(0,1),dtype=float)
        np.divide(abs(avg[i])*total,scalar,out=coherence[i],where=scalar>0)
    median=np.nanmedian(abs(avg),axis=0)
    level=abs(avg)/np.where(median>0,median,np.nan)
    if np.isfinite(level[:,:2]).all(axis=1).sum()>=8 and np.all(np.nanmedian(coherence[:,:2],axis=0)>.45):
        for ids in runs(np.flatnonzero(np.all(level[:,:2]<.20,axis=1))):
            if len(ids)>=2:
                record('coherent amplitude loss',[0,1],lo=float(t[ids[0]]-2),hi=float(t[ids[-1]]+2),
                       ratio=float(np.nanmedian(level[ids,:2])))
    for p in (0,1):
        a=abs(avg[:,p])
        for ids in runs(np.flatnonzero((level[:,p]>2)&(a>median[p]+6*robust_scatter(a)))):
            record('time amplitude peak',[p],lo=float(t[ids[0]]-2),hi=float(t[ids[-1]]+2),ratio=float(np.nanmax(level[ids,p])))
        jumps=np.angle(avg[1:,p]*avg[:-1,p].conj(),deg=True)
        for i in np.flatnonzero((abs(jumps)>55)&(coherence[:-1,p]>.45)&(coherence[1:,p]>.45)):
            record('phase step',[p],lo=float(t[i]-2),hi=float(t[i+1]+2),degrees=float(jumps[i]))
        # Fit on contiguous, adequately populated IF sequences; require similar delay in each half.
        half=[]
        for mask in (seconds<uv['duration']/2,seconds>=uv['duration']/2):
            h=np.nansum(raw[mask,:,p]*weight[mask,:,p],axis=0,dtype=np.complex128)
            denom=np.nansum(abs(raw[mask,:,p])*weight[mask,:,p],axis=0,dtype=float)
            half.append((np.angle(h),abs(h)/np.where(denom>0,denom,np.nan)))
        for group in runs(np.flatnonzero((half[0][1]>.3)&(half[1][1]>.3))):
            if len(group)<8: continue
            x=uv['freq'][group]; slopes=[]
            for angle,_ in half:
                y=np.rad2deg(np.unwrap(angle[group]))
                coef=np.polyfit(x-x.mean(),y,1)
                residual=y-np.polyval(coef,x-x.mean())
                if np.std(residual)>18: break
                slopes.append(coef[0])
            if len(slopes)==2 and slopes[0]*slopes[1]>0 and min(abs(np.array(slopes)))*np.ptp(x)>25 and abs(slopes[0]-slopes[1])<.5*abs(np.mean(slopes)):
                record('repeatable phase slope',[p],first=int(group[0]),last=int(group[-1]),deg_per_ghz=float(np.mean(slopes)))
        for i in range(1,len(spec)-1):
            ratio=abs(spec[i,p])/np.mean(abs(spec[[i-1,i+1],p]))
            phase=np.angle(spec[i,p]*np.conj(np.mean(spec[[i-1,i+1],p])),deg=True)
            if np.nanmedian(coherence[:,p])>.45 and (ratio>1.5 or ratio<.55 or abs(phase)>35):
                record('IF excursion',[p],spw=i,ratio=float(ratio),degrees=float(phase))
    if key in channel:
        freq=channel['frequency']; amp=channel[key][0]
        windows=amp.reshape(len(spec),-1,4)
        for i,values in enumerate(windows):
            ref=np.nanmedian(values,axis=0)
            scale=robust_scatter(values,axis=0)
            ratio=values/np.where(ref>0,ref,np.nan)
            z=(values-ref)/np.where(scale>0,scale,np.nan)
            # A paired peak or an exceptionally isolated single-hand peak.
            pair=(ratio[:,0]>2)&(ratio[:,1]>1.5)&(z[:,0]>3)&(z[:,1]>3)
            single=(ratio>3)&(z>10)
            for j in np.flatnonzero(pair|np.any(single,axis=1)):
                hands=np.flatnonzero((z[j]>3)&(ratio[j]>1.5))
                record('channel peak',hands,spw=i,chan=int(j),ghz=float(freq[i*len(values)+j]),
                       ratios=[round(float(ratio[j,k]),2) for k in hands])
    return events


def main(root,coverage):
    dest=root/'findings';dest.mkdir(exist_ok=True)
    inventory=defaultdict(list)
    with coverage.open() as stream:
        for row in csv.DictReader(stream): inventory[int(row['scan'])].append(row)
    for scan,rows in inventory.items():
        with np.load(root/'uv'/f'scan{scan}.npz') as uv,np.load(root/'channels'/f'scan{scan}.npz') as ch:
            result={r['station1']+'-'+r['station2']:screen(r,uv,ch) for r in rows}
        (dest/f'scan{scan}.json').write_text(json.dumps(result,allow_nan=False))
        print(scan,sum(map(len,result.values())),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('coverage',type=Path)
    args=p.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        main(args.root,args.coverage)
