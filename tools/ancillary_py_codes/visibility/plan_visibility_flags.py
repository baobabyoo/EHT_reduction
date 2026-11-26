"""Build the reviewed CASA selections and their coverage audit from the M87 screening output.

Run in inspection/: python3 plan_visibility_flags.py. The M87-specific time and broad-IF
decisions below follow cross-baseline review; reassess them before using other data.
"""
import csv
import json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path

ROOT=Path('M87_checkpoints')
POLS=['RR','LL','RL','LR']


def build():
    rows=list(csv.DictReader(open('M87_visibility_coverage.csv')))
    scans=sorted({int(r['scan']) for r in rows})
    start={int(r['scan']):datetime.strptime('2026-03-17T'+r['start_utc'],'%Y-%m-%dT%H:%M:%S.%f') for r in rows}
    findings={s:json.loads((ROOT/'findings'/f'scan{s}.json').read_text()) for s in scans}
    actions=[]
    def add_time(s,antenna,hands,lo,hi,reason,spw=None):
        # Include actual integrations in the half-open reviewed interval.
        fmt=lambda t:(start[s]+timedelta(seconds=t)).strftime('%Y/%m/%d/%H:%M:%S.%f')[:-3]
        kw=dict(antenna=antenna,timerange=fmt(lo)+'~'+fmt(hi-.001),correlation=','.join(hands))
        if spw is not None:kw['spw']=spw
        actions.append(dict(target='export',scan=s,reason=reason,kwargs=kw))
    add_time(20,'PV',['RR','LL'],8,240,'PV signal loss after the opening integrations')
    add_time(23,'MG',['RR','LL'],124,152,'MG dropout on AA and KT baselines')
    add_time(2,'NN&PV',['RR','LL'],25,64,'Early loss of coherent amplitude')
    for s in scans:
        for b in ['AA-NN','NN-PV']:
            events=[e for e in findings[s].get(b,[]) if e['kind']=='IF excursion' and e['spw']==28]
            if not events:continue
            hands=sorted({p for e in events for p in e['pols']},key=POLS.index)
            if s==2 and b=='NN-PV':hands.append('RL') # independent half-scan confirmation in preview
            add_time(s,b.replace('-','&'),hands,0,240,'Recurring IF 28 distortion; export-only selection','28:0')
    # Only well-repeated channels are proposed. Preserve exact observed baseline/hand coverage.
    occur=defaultdict(set)
    for s,baselines in findings.items():
        for b,events in baselines.items():
            for e in events:
                if e['kind']=='channel peak':occur[e['spw'],e['chan']].add((s,b))
    proposed={c for c,obs in occur.items() if len({s for s,b in obs})>=3 and len({b for s,b in obs})>=3}
    for s in scans:
        selection=defaultdict(set)
        for b,events in findings[s].items():
            for e in events:
                if e['kind']=='channel peak' and (e['spw'],e['chan']) in proposed:
                    for p in e['pols']:selection[e['spw'],e['chan'],p].add(b)
        original={(c,j,p,b) for (c,j,p),bs in selection.items() for b in bs}
        # At the two interior channels every triggering baseline touches NN across the run.
        # Group confirmed independent partners for parallel hands. Cross-hands stay oriented.
        grouped=defaultdict(set)
        for (c,j,p),bs in selection.items():
            if (c,j) in [(11,41),(28,97)] and p in ('RR','LL') and len(bs)>=2 and all('NN' in b.split('-') for b in bs):
                partners=sorted(set(b.replace('NN','').strip('-') for b in bs))
                grouped['NN&'+','.join(partners),p].add((c,j))
            else:
                for b in bs: grouped[b.replace('-','&'),p].add((c,j))
        compressed=defaultdict(list)
        for (ant,p),channels in grouped.items():compressed[ant,tuple(sorted(channels))].append(p)
        recovered=set()
        for (ant,channels),hands in sorted(compressed.items(),key=lambda z:(',' not in z[0][0],z[0])):
            hands.sort(key=POLS.index)
            a,partners=ant.split('&')
            recovered.update((c,j,p,'-'.join(sorted([a,b]))) for c,j in channels for p in hands for b in partners.split(','))
            kw=dict(antenna=ant,scan=str(s),spw=','.join(f'{i}:{j}' for i,j in channels),correlation=','.join(hands))
            actions.append(dict(target='channelized',scan=s,reason='Recurrent narrow peak',kwargs=kw))
        assert original==recovered
    (ROOT/'flag_plan.json').write_text(json.dumps(actions,indent=1))
    return actions


if __name__=='__main__':print(len(build()),'CASA selections')
