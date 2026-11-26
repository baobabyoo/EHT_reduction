"""Run in workflow_test. Only the two adjacent local code directories are imported."""
import csv,json,sys,warnings
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
sys.path[:0]=['../ancillary_py_codes','../visflag_widget']
from assess_visibilities import screen,runs
from selections import axes,utc,command
from outliers import time_ranges
from full_polarization import plan
warnings.filterwarnings('ignore',category=RuntimeWarning)
root=Path('M87_checkpoints')
rows=defaultdict(list)
for r in csv.DictReader(open('M87_visibility_coverage.csv')): rows[int(r['scan'])].append(r)
def load(scan):
    with np.load(root/'uv'/f'scan{scan}.npz') as data:return dict(data)
def origin(scan):
    return datetime.fromisoformat('2026-03-17T'+rows[scan][0]['start_utc']).replace(tzinfo=timezone.utc).timestamp()
def base():return dict(vis=str(Path('../M87_calibrated.ms').resolve()),mode='manual')
def data(u,b,s):
    return dict(t=origin(s)+u[b+'_t'],spw=np.arange(len(u['freq'])),ch=np.zeros(len(u['freq']),int),v=u[b+'_v'],w=u[b+'_w'])
def applied(d,b,s,actions):
    mask=np.zeros(d['w'].shape[:2],bool)
    for k in actions:
        if k['scan']!=s:continue
        sel=axes(k['k'],d,s,b.replace('-','&'),'M87')
        if sel is not None:
            t,f,h=sel;assert h.all();mask[np.ix_(t,f)]=True
    return mask
def action(s,a,reason,span,spw=''):
    k=dict(base(),antenna=a,timerange=span)
    if spw:k['spw']=spw
    return dict(scan=s,k=k,reason=reason)
def main():
    (root/'flag_plan.json').write_text('[]') # No previous quality selections.
    plan()
    pol=json.loads((root/'full_pol_plan.json').read_text())
    initial=[dict(scan=x['scan'],k=dict(base(),**x['kwargs']),reason='Partial polarization coverage. '+x['reason']) for x in pol['commands']]
    candidates={}; residual=[];coverage=[]
    for s,rr in rows.items():
        u=load(s);events={};nominations=defaultdict(list)
        for r in rr:
            b=r['station1']+'-'+r['station2']; ev=screen(r,u,{})
            events[b]=ev
            a=np.abs(u[b+'_avg'][:,:2]); ref=np.nanmedian(a,axis=0)
            for e in ev:
                if e['kind']=='coherent amplitude loss':
                    for t in np.arange(e['lo'],e['hi'],4):nominations['time',int(t),'loss'].append(b)
                if e['kind']=='IF excursion' and (e['ratio']<.45 or e['ratio']>2.5):
                    nominations['IF',e['spw'],'low' if e['ratio']<1 else 'high'].append(b)
            # Sustained in-scan losses and individual frequency-averaged integrations.
            if np.all(np.isfinite(ref)&(ref>0)):
                for g in runs(np.flatnonzero(np.all(a<.28*ref,axis=1))):
                    if len(g)>=2:
                        for i in g:nominations['time',int(4*i),'loss'].append(b)
            raw=u[b+'_v'][:,:,:2];wt=u[b+'_w'][:,:,:2]
            avg=np.nansum(raw*wt,axis=1)/np.where(wt.sum(1)>0,wt.sum(1),np.nan)
            amp=abs(avg);typ=np.nanmedian(amp,axis=0);spread=1.4826*np.nanmedian(abs(amp-typ),axis=0)
            spike=np.all((amp>4*typ)&(amp>typ+7*spread),axis=1)
            for i in np.flatnonzero(spike):
                tm=float(u[b+'_t'][i])
                ev.append(dict(kind='integration amplitude peak',pols=['RR','LL'],lo=tm-.001,hi=tm+.001,ratio=float(np.min(amp[i]/typ))))
                nominations['integration',round(tm,5),'peak'].append(b)
            # Detect a bright opening reference followed by a sustained drop in both parallel hands.
            for cut in range(2,9):
                head=a[:cut];tail=a[cut:]
                if np.all(np.nanmin(head,axis=0)>5*np.nanmedian(tail,axis=0)) and np.all(np.isfinite(head)):
                    # These opening integrations are the reference for the later dropout.
                    # Do not also classify their high amplitudes as independent spikes.
                    for key,partners in nominations.items():
                        if key[0]=='integration' and key[1]<cut*4 and b in partners:
                            partners.remove(b)
                    for t in range(cut*4,240,4):nominations['time',t,'loss'].append(b)
                    break
        candidates[s]=events
        station=defaultdict(list)
        for (domain,value,kind),pairs in nominations.items():
            left=set(pairs)
            for ant in sorted({a for b in pairs for a in b.split('-')},key=lambda a:-sum(a in b.split('-') for b in set(pairs))):
                bs=sorted(b for b in left if ant in b.split('-'))
                if len(bs)<2:continue
                partners=sorted(b.split('-')[1-b.split('-').index(ant)] for b in bs)
                supported=ant+'&'+','.join(partners)
                station[domain,kind,supported].append(value);left.difference_update(bs)
        for (domain,kind,ant),vs in station.items():
            start=origin(s)
            if domain=='integration':
                span=','.join(utc(start+t-.001)+'~'+utc(start+t+.001) for t in sorted(set(vs)))
                initial.append(action(s,ant,'Paired-hand integration peaks shared by station partners',span))
            elif domain=='IF':
                initial.append(action(s,ant,'Large scan-mean IF amplitude '+kind+' shared by at least two station partners',utc(start)+'~'+utc(start+240.01),','.join(str(i)+':0' for i in sorted(vs))))
            else:
                for g in runs(np.array(sorted(vs))//4):
                    end=(g[-1]+1)*4
                    initial.append(action(s,ant,'Simultaneous coherent parallel-hand loss on multiple partners',utc(start+4*g[0])+'~'+utc(start+end+(.01 if end==240 else -.00001))))
        # Independent second pass, restricted to usable samples after initial flags.
        # Store exact time/window candidates. Group matching partners and then ranges.
        hits=defaultdict(set)
        for r in rr:
            b=r['station1']+'-'+r['station2'];d=data(u,b,s);m=applied(d,b,s,initial)
            z=np.where((d['w']>0)&~m[:,:,None],d['v'],np.nan)
            a=abs(z[:,:,:2]);med=np.nanmedian(a,axis=0);mad=1.4826*np.nanmedian(abs(a-med),axis=0)
            local=(np.roll(a,1,axis=0)+np.roll(a,-1,axis=0))/2
            high=np.all((a>2.5*local)&(a>med+8*mad),axis=2)
            low=np.all((a<.4*local)&(a<med-6*mad)&(local>.75*med),axis=2)
            ph=z[:,:,:2];unit=ph/abs(ph);circ=np.nanmean(unit,axis=0)
            dev=abs(np.angle(unit*circ.conj(),deg=True));scale=np.nanmedian(dev,axis=0)
            excursion=np.all((abs(circ)>.94)&(dev>np.maximum(65,8*scale)),axis=2)
            for reason,arr in [('amplitude spike',high),('amplitude dip',low),('phase excursion',excursion)]:
                arr[[0,-1]]=False
                for t,f in zip(*np.where(arr)):hits[reason,round(d['t'][t],5),int(f)].add(b)
        grouped=defaultdict(set)
        for (reason,t,f),pairs in hits.items():
            left=set(pairs)
            for ant in sorted({a for b in pairs for a in b.split('-')},key=lambda a:-sum(a in b.split('-') for b in pairs)):
                partners=sorted(b for b in left if ant in b.split('-'))
                if len(partners)<2:continue
                sel=ant+'&'+','.join(b.split('-')[1-b.split('-').index(ant)] for b in partners)
                grouped[reason,sel,t].add(f);left.difference_update(partners)
            for b in left:grouped[reason,b.replace('-','&'),t].add(f)
        times=defaultdict(list)
        for (reason,ant,t),fs in grouped.items():times[reason,ant,tuple(sorted(fs))].append(t)
        alltimes=np.unique(np.concatenate([origin(s)+u[b+'_t'] for b in events]))
        for (reason,ant,fs),ts in times.items():
            ix=np.searchsorted(alltimes,np.array(ts)-.00001)
            assert np.max(abs(alltimes[ix]-ts))<.00002
            residual.append(action(s,ant,'Native two-parallel-hand '+reason,time_ranges(alltimes,ix),','.join(str(f)+':0' for f in fs)))
        for b in events:
            d=data(u,b,s);good=d['w']>0
            first=applied(d,b,s,initial);later=applied(d,b,s,residual)
            coverage.append(dict(scan=s,baseline=b,before=int(good.sum()),first=int(good[first].sum()),second=int(good[later&~first].sum())))
        print(s,len(initial),len(residual),flush=True)
    for name,obj in [('candidates',candidates),('initial',initial),('residual',residual),('coverage',coverage)]:
        Path(name+'.json').write_text(json.dumps(obj,indent=1))
    combined=initial+residual
    Path('proposed.py').write_text(''.join('# '+x['reason']+'\n'+command(x['k'])+'\n' for x in combined))
if __name__=='__main__':main()
