"""Script the same approval handler as the widget button, with blanket permission."""
from analyse import *
from types import SimpleNamespace
from app import Review
import hashlib

def main():
    out=Path('M87_approved_flags.py')
    review=Review(SimpleNamespace(vis='../M87_calibrated.uvf',pdf=None,commands='proposed.py',output=out,field=None,
                  scan_log='scan_times.txt',scan_gap=60,casa_python=None,native_ms=None,overwrite=True))
    state=review.state()
    while not state['done']:
        state=review.decide(dict(state,text=state['command'],reason=state['reason'],approve=True))
    approved=[a['k'] for step in review.steps for a in step['items']]
    first=json.loads(Path('initial.json').read_text()); second=json.loads(Path('residual.json').read_text())
    assert approved==[x['k'] for x in first+second]
    checked=json.loads(Path('coverage.json').read_text())
    audit=[]
    for s,rr in rows.items():
        u=load(s);masks={}
        for r in rr:
            b=r['station1']+'-'+r['station2'];d=data(u,b,s)
            m=applied(d,b,s,first);n=applied(d,b,s,second)
            masks[b]=m.astype(np.uint8)+2*n.astype(np.uint8)
            # Independently apply the widget's approved selections on original FITS samples.
            orig=review.primary.read(s,b.replace('-','&'));flag=np.zeros(orig['w'].shape,bool)
            assert np.array_equal(orig['w'],d['w'])
            for k in approved:
                sl=axes(k,orig,s,b.replace('-','&'),'M87')
                if sl is not None:flag[np.ix_(*sl)]=True
            good=orig['w']>0
            assert np.array_equal(flag&good,good&(m|n)[:,:,None])
            cm=next(x for x in checked if x['scan']==s and x['baseline']==b)
            assert np.count_nonzero(good&~flag)==cm['before']-cm['first']-cm['second']
        np.savez_compressed(root/f'masks{s}.npz',**masks)
        audit.append(s)
    print('Widget approvals',len(approved),'verified scans',audit)
if __name__=='__main__':main()
