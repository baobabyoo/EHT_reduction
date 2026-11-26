"""Run with CASA Python from a disposable full import.

Pass full_pol_plan.json, output JSON, and fresh or after-quality. For the latter
start with the original 23 export quality commands already applied. Never run
on the user's working MS. A .disposable_flag_test marker is required.
"""
import json,sys
from pathlib import Path
import numpy as np
from casatools import table
from casatasks import flagdata

if not Path('.disposable_flag_test').exists(): raise RuntimeError('Require a disposable MS')
plan=json.loads(Path(sys.argv[1]).read_text())
mode=sys.argv[3]
assert mode in ('fresh','after-quality')
vis='M87_calibrated.ms'
def flags():
    t=table();t.open(vis)
    try:return t.getcol('FLAG') | t.getcol('FLAG_ROW')[None,None,:]
    finally:t.close()
before=flags()
partial=before.any(axis=0)&~before.all(axis=0)
expected=before|partial[None,:,:]
if mode=='fresh':
    assert int(partial.sum())==plan['counts']['partial']
    assert int((expected&~before).sum())==plan['counts']['valid_to_flag']
calls=plan['commands']+(plan['closure'] if mode=='after-quality' else [])
for call in calls:
    flagdata(vis=vis,field='M87',mode='manual',flagbackup=False,**call['kwargs'])
after=flags()
result=dict(mode=mode,calls=len(calls),partial_before=int(partial.sum()),new_flags=int((after&~before).sum()),
            mismatches=int((expected!=after).sum()),partial_after=int((after.any(axis=0)&~after.all(axis=0)).sum()))
print(result)
assert result['mismatches']==0 and result['partial_after']==0
Path(sys.argv[2]).write_text(json.dumps(result,indent=1))
