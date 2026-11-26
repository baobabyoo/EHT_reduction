"""Antenna-based inspection of rPICARD complex and scalar passbands."""
import ast
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
from selections import Journal, command, frequencies
from calibration_import import ImportedReview, scan_mask

KINDS = {'bpass_complx.t':'phase', 'bpass_scalar.t':'amplitude'}
HANDS = ('R','L')
LIMIT = 1e30


class CommandJournal(Journal):
    def contents(self, steps):
        return ''.join(command(k)+'\n' for step in steps for k in step['calls']).encode()


class Bandpass:
    def __init__(self, args):
        paths = [Path(p).resolve() for p in (args.vis,args.other_table) if p]
        self.tables = {}
        output = Path(args.output)
        if not output.is_absolute() and Path.cwd() == Path(__file__).resolve().parent:
            output = paths[0].parent.parent / output
        output = output.resolve()
        for path in paths:
            kind = KINDS[path.name]
            if kind in self.tables:
                raise ValueError('Supply one table of each kind')
            if output == path or path in output.parents:
                raise ValueError('Choose an output outside the calibration tables')
            with TemporaryDirectory() as tmp:
                cache = Path(tmp)/'samples.npz'
                reader = Path(__file__).with_name('bandpass_reader.py').resolve()
                run = subprocess.run([args.casa_python,str(reader),str(path),kind,str(cache)],
                                     cwd=tmp,capture_output=True,text=True)
                if run.returncode or not cache.exists():
                    raise ValueError('CASA passband read failed: '+(run.stderr+run.stdout)[-2500:])
                with np.load(cache) as data:
                    panels = {(str(a),h):data[f'p{i}_{h}'] for i,a in enumerate(data['names']) for h in range(2)}
                    self.tables[kind] = dict(path=str(path), panels=panels, bands=data['bands'].tolist(),
                                             selectors=dict(zip(data['names'].tolist(),data['selectors'].tolist())))
        self.ants = sorted(set.union(*(set(t['selectors']) for t in self.tables.values())))
        self.imported = ImportedReview(args,paths,output,self.parse)
        self.log = CommandJournal(output, {'passbands':sorted(map(str,paths)),**self.imported.identity},args.overwrite)

    def target(self, k):
        for kind,t in self.tables.items():
            if t['path'] == k['vis']:
                corr = self.correlation(kind)
                if k['correlation'] not in (corr+'1',corr+'2','ABS_Sol1','ABS_Sol2') or k['antenna'] not in t['selectors'].values():
                    break
                antenna = next(a for a,sel in t['selectors'].items() if sel==k['antenna'])
                return kind,antenna,int(k['correlation'][-1])-1
        raise ValueError('Use a loaded table, station selector and its matching ARG or ABS hand')

    @staticmethod
    def correlation(kind):
        return 'ARG_Sol' if kind=='phase' else 'ABS_Sol'

    def parse(self,text):
        calls=[]
        required={'vis','mode','antenna','datacolumn','correlation','clipminmax','clipoutside','flagbackup'}
        for line in text.splitlines():
            if not line.strip():
                continue
            expr=ast.parse(line.strip(),mode='eval').body
            if not isinstance(expr,ast.Call) or not isinstance(expr.func,ast.Name) or expr.func.id!='flagdata' or expr.args:
                raise ValueError('Use one literal flagdata call per line')
            k={x.arg:ast.literal_eval(x.value) for x in expr.keywords}
            if (len(k)!=len(expr.keywords) or set(k)-{'spw','scan'}!=required or k['mode']!='clip' or
                k['datacolumn']!='CPARAM' or type(k['clipoutside'])!=bool or k['flagbackup'] is not True):
                raise ValueError('Use the generated CPARAM clip arguments')
            if not isinstance(k.get('spw',''),str):
                raise ValueError('Specify SPW and channel selections as a string')
            limits=k['clipminmax']
            if not isinstance(limits,list) or len(limits)!=2 or not all(type(v) in (float,int) and np.isfinite(v) for v in limits) or limits[0]>limits[1]:
                raise ValueError('Supply two ordered finite clip limits')
            kind,a,h=self.target(k)
            self.mask(self.tables[kind]['panels'][a,h],k)
            if k not in calls:
                calls.append(k)
        return calls

    @staticmethod
    def mask(points,k):
        lo,hi=k['clipminmax']
        values=points[:,5] if k['correlation'].startswith('ABS') else points[:,3]
        inside=(values>=lo)&(values<=hi)
        return scan_mask(points[:,6],k.get('scan','')) & frequencies(points[:,0],points[:,1],k.get('spw','')) & (~inside if k['clipoutside'] else inside)

    def make(self,q):
        kind,a,h=q['kind'],q['ant'],int(q['hand'])
        t=self.tables[kind]
        if h not in (0,1):
            raise ValueError('Unknown hand')
        k=dict(vis=t['path'],mode='clip',antenna=t['selectors'][a],datacolumn='CPARAM',
               correlation=self.correlation(kind)+str(h+1))
        if q['operation'] in ('channel','spw'):
            w=int(q['spw'])
            if w not in {int(b[0]) for b in t['bands']}:
                raise ValueError('Unknown spectral window')
            k['spw']=str(w) if q['operation']=='spw' else f"{w}:{int(q['channel'])}" 
            limits=[-LIMIT,LIMIT]
            outside=False
        else:
            if q['operation'] not in ('above','below'):
                raise ValueError('Choose a clip direction')
            threshold=float(q['value'])
            if not np.isfinite(threshold):
                raise ValueError('Choose a finite threshold')
            if kind=='phase':
                threshold=float(np.deg2rad(threshold))
            limits=[-LIMIT,threshold] if q['operation']=='above' else [threshold,LIMIT]
            outside=True
        k.update(clipminmax=limits,clipoutside=outside,flagbackup=True)
        return k

    def api(self,action,q):
        approved=[k for s in self.log.data['steps'] for k in s['calls']]
        if action=='state':
            return dict(antennas=self.ants,paths=[t['path'] for t in self.tables.values()],out=str(self.log.out))
        if action=='make':
            return dict(line=command(self.make(q)))
        if action not in ('view','approve'):
            raise ValueError('Unknown passband action')
        calls=self.parse(q.get('text',''))
        if action=='approve':
            if not calls:
                raise ValueError('Choose a passband selection first')
            self.log.add(dict(calls=calls,reason=q.get('reason','')))
            return dict(out=str(self.log.out))
        result=[]
        inactive=set(q.get('unchecked',[]))
        ant=q['ant']
        for h in range(2):
            for kind in ('phase','amplitude'):
                if kind not in self.tables:
                    continue
                t=self.tables[kind]
                p=t['panels'].get((ant,h),np.empty((0,7)))
                available=np.ones(len(p),bool)
                marked=np.zeros(len(p),bool)
                for k in approved:
                    if command(k) not in inactive and self.target(k)==(kind,ant,h):
                        available &= ~self.mask(p,k)
                for k in calls:
                    if self.target(k)==(kind,ant,h):
                        marked |= self.mask(p,k)
                selected=int(p[marked&available,4].sum())
                if q.get('after'):
                    available &= ~marked
                data=p[available].copy()
                if kind=='phase':
                    data[:,3]=np.rad2deg(data[:,3])
                display=np.unique(np.column_stack((data[:,:4],marked[available])),axis=0)
                result.append(dict(kind=kind,hand=h,bands=t['bands'],points=display[:,:4].tolist(),
                                   hits=display[:,4].astype(int).tolist(),selected=selected,
                                   count=int(data[:,4].sum())))
        display = sorted(approved,key=lambda k:self.ants.index(self.target(k)[1]))
        return dict(panels=result,approved=[command(k) for k in display],
                    stations={command(k):self.target(k)[1] for k in display})
