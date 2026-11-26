"""Run with the calibration_tables directory and CASA's Python executable."""
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from bandpass import Bandpass, KINDS

# Independent CASA-side comparison includes every row, hand and channel.
VERIFY = """
import sys,numpy as np
from casatasks import flagdata
from casatools import table
from pathlib import Path
root=Path.cwd()
tb=table()
def read(p):
    tb.open(str(p))
    try:
        return [tb.getcol(k) for k in ('FLAG','CPARAM','ANTENNA1','SPECTRAL_WINDOW_ID')]
    finally:
        tb.close()
exec((root/'commands.py').read_text())
for filename in ('bpass_complx.t','bpass_scalar.t'):
    before,z,a,w=read(Path(sys.argv[1])/filename)
    after=read(root/filename)[0]
    expected=before.copy()
    if filename=='bpass_complx.t':
        v=np.angle(z)
        expected[0]|=(a==0)[None,:] & (v[0]<np.deg2rad(-20))
        expected[1]|=(a==1)[None,:] & (v[1]>np.deg2rad(-5))
    else:
        v=np.abs(z)
        expected[0]|=(a==0)[None,:] & (v[0]>0.995)
        expected[1]|=(a==1)[None,:] & (v[1]<0.85)
        expected[1,55,:]|=(a==0)&(w==4)
        expected[0]|=((a==1)&(w==4))[None,:]
    assert np.array_equal(after,expected),(filename,np.count_nonzero(after!=expected))
    print(filename,'new flags',np.count_nonzero(after!=before))
"""

def check(source,casa):
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for name in KINDS:
            shutil.copytree(source/name, root/name)
        args=SimpleNamespace(vis=root/'bpass_complx.t',other_table=root/'bpass_scalar.t',
                             casa_python=casa,output=root/'commands.py',overwrite=False)
        review=Bandpass(args)
        lines=[]
        for kind,hand,ant,operation,v in [('phase',0,'AA','below',-20),('phase',1,'AX','above',-5),
                                          ('amplitude',0,'AA','above',0.995),('amplitude',1,'AX','below',.85),
                                          ('amplitude',1,'AA','channel',0),('amplitude',0,'AX','spw',0)]:
            q=dict(kind=kind,hand=hand,ant=ant,operation=operation,value=v,spw=4,channel=55)
            line=review.api('make',q)['line']
            lines.append(line)
            view=review.api('view',dict(ant=ant,text=line))['panels']
            after=review.api('view',dict(ant=ant,text=line,after=True))['panels']
            idx=next(i for i,p in enumerate(view) if p['kind']==kind and p['hand']==hand)
            assert len(view)==4 and len(view[idx]['bands'])==32
            assert view[idx]['selected']>0,(q,view[idx]['selected'])
            assert view[idx]['count']-after[idx]['count']==view[idx]['selected']
        review.api('approve',dict(text='\n'.join(lines),reason='Copy test'))
        assert args.output.read_text().splitlines()==lines
        (root/'verify.py').write_text(VERIFY)
        subprocess.run([casa,str(root/'verify.py'),str(source)],cwd=root,check=True)
        for name,kind in KINDS.items():
            args.vis=root/name
            args.other_table=None
            args.output=root/(kind+'.py')
            single=Bandpass(args)
            panels=single.api('view',dict(ant='AA'))['panels']
            assert [(p['kind'],p['hand']) for p in panels]==[(kind,0),(kind,1)]
        print('Paired and single input checks passed')

if __name__=='__main__':
    check(Path(sys.argv[1]).resolve(),str(Path(sys.argv[2]).expanduser().absolute()))
