"""Run inside disposable CASA work directory containing a fresh M87_calibrated.ms.
Arguments: path to flag_plan.json, output JSON. Modifies the disposable MS.
"""
from casatasks import flagdata
from casatools import table
from datetime import datetime
import json,sys
from pathlib import Path
import numpy as np

vis='M87_calibrated.ms'
if not Path('.disposable_flag_test').exists():
    raise RuntimeError('This verifier needs a disposable import. Place .disposable_flag_test in that directory.')
def columns(sub, names):
    tb=table();tb.open(vis+sub)
    try:return [tb.getcol(n) for n in names]
    finally:tb.close()
station,=columns('/ANTENNA',['STATION'])
pol,=columns('/POLARIZATION',['CORR_TYPE'])
sw,=columns('/DATA_DESCRIPTION',['SPECTRAL_WINDOW_ID'])
a,b,t,dd=columns('',['ANTENNA1','ANTENNA2','TIME','DATA_DESC_ID'])
plan=json.loads(Path(sys.argv[1]).read_text())
audit=[]
old,=columns('',['FLAG'])
epoch=datetime(1858,11,17)
for action in sorted([z for z in plan if z['target']=='export'],key=lambda z:('&' in z['kwargs']['antenna'])):
    kw=action['kwargs']; ant=kw['antenna'].split('&')
    ids=[list(station).index(n) for n in ant]
    mask=((a==ids[0])|(b==ids[0])) if len(ids)==1 else (((a==ids[0])&(b==ids[1]))|((a==ids[1])&(b==ids[0])))
    lo,hi=[(datetime.strptime(x,'%Y/%m/%d/%H:%M:%S.%f')-epoch).total_seconds() for x in kw['timerange'].split('~')]
    mask &= (t>=lo)&(t<=hi)
    if 'spw' in kw:mask &= sw[dd]==int(kw['spw'].split(':')[0])
    hands=np.isin(pol.ravel(),[dict(RR=5,RL=6,LR=7,LL=8)[p] for p in kw['correlation'].split(',')])
    wanted=old|(mask[None,None,:]&hands[:,None,None]);del mask
    flagdata(vis=vis,mode='manual',field='M87',flagbackup=False,**kw)
    new,=columns('',['FLAG'])
    mismatch=int((wanted!=new).sum())
    audit.append(dict(kwargs=kw,changed=int((new&~old).sum()),mismatch=mismatch))
    Path(sys.argv[2]).write_text(json.dumps(audit,indent=1))
    if mismatch:raise ValueError(f'Unexpected FLAG differences: {mismatch} / {kw}')
    print(len(audit),audit[-1]['changed'],flush=True)
    old=new
