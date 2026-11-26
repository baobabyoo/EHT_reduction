"""Cache UVFITS integrations and coherent averages for an indexed visibility run.

Usage: python collect_visibility_samples.py ../M87_calibrated.uvf M87_visibility_coverage.csv M87_checkpoints/uv
Arrays have axes time, IF, hand. Pols are explicitly stored as RR, LL, RL, LR.
Invalid samples retain zero weight and have NaN complex values in the cache.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.time import Time


def weighted_mean(v,w,axes):
    weight=w.sum(axis=axes,dtype=float)
    total=(np.where(w>0,v,0)*w).sum(axis=axes,dtype=np.complex128)
    return np.divide(total,weight,out=np.full(total.shape,complex(np.nan,np.nan)),where=weight>0)


def collect(path,coverage,out):
    out.mkdir(parents=True,exist_ok=True)
    scans=defaultdict(list)
    with coverage.open() as stream:
        for row in csv.DictReader(stream):
            scans[int(row['scan'])].append(row)
    with fits.open(path,memmap=True) as h:
        hdr=h[0].header
        g=h[0].data
        from index_visibility import stored_scans
        ids=stored_scans(g)
        times=g.par('DATE')
        baseline=g.par('BASELINE').astype(int)
        numbers=dict(zip(h['AIPS AN'].data['ANNAME'],h['AIPS AN'].data['NOSTA']))
        pol_codes=hdr['CRVAL3']+(np.arange(hdr['NAXIS3'])+1-hdr['CRPIX3'])*hdr['CDELT3']
        order=[list(pol_codes).index(code) for code in (-1,-2,-3,-4)]
        centers=(hdr['CRVAL4']+(1-hdr['CRPIX4'])*hdr['CDELT4']+h['AIPS FQ'].data['IF FREQ'][0])/1e9
        if len(np.unique(g.par('FREQSEL')))!=1 or hdr['NAXIS4']!=1:
            raise ValueError("Expected one frequency setup and one channel per IF")
        day=hdr['DATE-OBS'][:10]
        for scan,rows in scans.items():
            start,end=Time([day+'T'+rows[0][k] for k in ('start_utc','end_utc')]).jd
            seconds=(times-start)*86400
            duration=round((end-start)*86400,3)
            bins=np.arange(0,duration,4.)
            arrays=dict(freq=centers,pols=np.array(['RR','LL','RL','LR']),bin_centers=bins+2,duration=duration)
            for r in rows:
                a,b=r['station1'],r['station2']
                key=a+'-'+b
                in_scan=(ids==scan) if ids is not None else (times>=start)&(times<=end+.01/86400)
                mask=in_scan&(baseline==256*numbers[a]+numbers[b])
                data=g.data[mask,0,0,:,0,:,:][:,:,order,:]
                good=np.isfinite(data).all(axis=-1)&(data[...,2]>0)
                if int(good.sum())!=int(r['valid']) or len(data)!=int(r['integrations']):
                    raise ValueError('Coverage mismatch '+key)
                v=np.where(good,data[...,0]+1j*data[...,1],complex(np.nan,np.nan))
                w=np.where(good,data[...,2],0.)
                t=seconds[mask]
                averages=[]
                for edge in bins:
                    use=(t>=edge)&(t<(edge+4+(.011 if edge==bins[-1] else 0)))
                    averages.append(weighted_mean(v[use],w[use],(0,1)))
                for field,value in [('v',v),('w',w),('t',t),('avg',averages),('spectrum',weighted_mean(v,w,0))]:
                    arrays[key+'_'+field]=value
            dest=out/f'scan{scan}.npz'
            tmp=dest.with_suffix('.tmp.npz')
            np.savez_compressed(tmp,**arrays)
            tmp.replace(dest)
            print('scan',scan,len(rows),'baselines',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('uvfits','coverage','out'):
        p.add_argument(name,type=Path)
    args=p.parse_args()
    collect(args.uvfits,args.coverage,args.out)
