"""Plan exact four-hand completeness flags on the single-channel-per-IF export.

Run in inspection/. Broad station selectors are allowed only where the same
station feed is missing on at least two partners and no complete cell is touched.
The companion verifier checks the resulting calls against CASA's actual FLAG cube.
"""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timedelta

import numpy as np
from astropy.io import fits

ROOT=Path('M87_checkpoints')


def ranges(values):
    result=[]
    for group in np.split(values,np.flatnonzero(np.diff(values)>1)+1):
        if len(group):result.append(str(group[0]) if len(group)==1 else f'{group[0]}~{group[-1]}')
    return ','.join(result)


def plan():
    groups=defaultdict(list)
    for r in csv.DictReader(open('M87_visibility_coverage.csv')):
        groups[int(r['scan'])].append(r)
    day=fits.getheader('../M87_calibrated.uvf')['DATE-OBS'][:10]
    counts=Counter(); details=[]; commands=[]
    for scan,rows in groups.items():
        origin=datetime.strptime(day+' '+rows[0]['start_utc'],'%Y-%m-%d %H:%M:%S.%f')
        def utc(t):
            return (origin+timedelta(seconds=float(t))).strftime('%Y/%m/%d/%H:%M:%S.%f')[:-3]
        with np.load(ROOT/'uv'/f'scan{scan}.npz') as u:
            pols=list(u['pols'])
            names=[r['station1']+'-'+r['station2'] for r in rows]
            masks={b:(u[b+'_w']>0)@(1<<np.arange(4)) for b in names}
            times={b:u[b+'_t'] for b in names}
            fullspan=utc(0)+'~'+utc(float(u['duration'])+.010)
            groups_for_scan=defaultdict(list)
            for b,m in masks.items():
                counts['complete']+=int((m==15).sum());counts['empty']+=int((m==0).sum())
                for mask in set(np.unique(m))-{0,15}:
                    hit=m==mask
                    surviving=[p for i,p in enumerate(pols) if mask&(1<<i)]
                    count=int(hit.sum()); counts['partial']+=count; counts['valid_to_flag']+=count*len(surviving)
                    details.append(dict(scan=scan,baseline=b,missing='/'.join(p for p in pols if p not in surviving),
                                        spw=ranges(np.flatnonzero(hit.any(axis=0))),cells=count))
            for j in range(len(u['freq'])):
                partial={b for b,m in masks.items() if ((m[:,j]>0)&(m[:,j]<15)).any()}
                covered=set()
                for station in sorted({a for b in partial for a in b.split('-')}):
                    incident=[b for b in names if station in b.split('-')]
                    partners=[b for b in incident if b in partial]
                    if len(partners)<2 or set(partners)&covered or any((masks[b][:,j]==15).any() for b in incident):continue
                    feeds=set()
                    for b in partners:
                        end=b.split('-').index(station)
                        for mask in set(masks[b][:,j])-{0}:
                            feeds.update(p[end] for i,p in enumerate(pols) if mask&(1<<i))
                    if len(feeds)!=1:continue
                    covered.update(partners)
                    groups_for_scan[station,fullspan,'Observed station '+station+' '+next(iter(feeds))+' feed only'].append(j)
                for b in sorted(partial-covered):
                    m=masks[b][:,j]
                    indices=np.flatnonzero((m>0)&(m<15))
                    for g in np.split(indices,np.flatnonzero(np.diff(indices)>1)+1):
                        span=fullspan if not (m==15).any() else utc(times[b][g[0]]-.05)+'~'+utc(times[b][g[-1]]+.05)
                        marker=(b.replace('-','&'),span,'Residual baseline selection')
                        if j not in groups_for_scan[marker]:groups_for_scan[marker].append(j)
            for (ant,span,why),spws in groups_for_scan.items():
                commands.append(dict(scan=scan,reason=why,kwargs=dict(antenna=ant,timerange=span,spw=ranges(np.array(spws)))))
    commands.sort(key=lambda c:('&' in c['kwargs']['antenna'],c['scan'],c['kwargs']['antenna']))
    # After quality flags, complete sets can become partial. In those already
    # selected rows flag the complementary hands. Redundant writes are idempotent.
    closure=[]
    for p in json.loads((ROOT/'flag_plan.json').read_text()):
        if p['target']!='export':continue
        kw=p['kwargs'].copy()
        kw['correlation']=','.join(k for k in ('RR','RL','LR','LL') if k not in kw['correlation'].split(','))
        if kw['correlation']:closure.append(dict(scan=p['scan'],reason='After matching export quality flag',kwargs=kw))
    result=dict(counts=counts,details=details,commands=commands,closure=closure)
    (ROOT/'full_pol_plan.json').write_text(json.dumps(result,indent=1))
    print(dict(counts),len(commands),len(closure),len(details))


if __name__=='__main__':plan()
