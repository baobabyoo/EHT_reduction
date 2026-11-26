"""Read fringe solutions and export approved CASA flagdata calls."""
import ast
from functools import lru_cache
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import numpy as np
from calibration_import import ImportedReview, scan_mask
from selections import Journal, command as format_call, frequencies

HERE = Path(__file__).resolve().parent


def command(key, table):
    antenna, scan, spw, hand, parameter = key
    if hand != 'R':
        raise ValueError('CASA flagdata cannot select a single L parameter in this fringe table')
    selector = {'phase': 'REAL_Sol1', 'delay': 'REAL_Sol2'}[parameter]
    return (f"flagdata(vis={str(table)!r}, mode='clip', antenna={antenna!r}, "
            f"scan={str(scan)!r}, spw={str(spw)!r}, datacolumn='FPARAM', "
            f'correlation={selector!r}, clipoutside=False, clipminmax=[-1e30, 1e30], flagbackup=True)')


class FringeJournal(Journal):
    def contents(self, steps):
        table = self.data['identity']['table']
        lines = []
        for step in steps:
            if 'lines' in step:
                lines.extend(step['lines'])
            elif 'calls' in step:
                lines.extend(format_call(k) for k in step['calls'])
            else:
                lines.extend(command(key, table) for key in step['keys'])
        return ''.join(line + '\n' for line in lines).encode('utf-8')

    def sync(self):
        # Older sessions embedded the CASA table helper in the approved file.
        if self.out.exists() and self.out.read_bytes().startswith(b'"""Apply individually approved flags'):
            raise ValueError('This output uses the older Python helper. It and its review history '
                             'are preserved. Use a new --output filename for formal CASA commands.')
        super().sync()


class Fringe:
    def __init__(self, args):
        path = Path(args.vis).resolve()
        output = Path(args.output)
        if Path.cwd() == HERE and not output.is_absolute():
            output = path.parent.parent / output
        output = output.resolve()
        if output == path or path in output.parents:
            raise ValueError('Choose an output file outside the calibration table')
        with TemporaryDirectory() as tmp:
            cache = Path(tmp) / 'solutions.npz'
            run = subprocess.run([args.casa_python, str(HERE/'fringe_reader.py'), str(path), str(cache)],
                                 capture_output=True, text=True, cwd=tmp)
            if run.returncode or not cache.exists():
                raise ValueError('CASA table read failed: ' + (run.stderr + run.stdout)[-2000:])
            with np.load(cache) as data:
                d = dict(data)
        self.raw = {}
        self.points = {}
        self.path = str(path)
        self.groups = {}
        self.scan_spws = {}
        self.delay_flags = {}
        self.delay_totals = {}
        self.sources = {}
        self.band = [float(min(d["GHz"])), float(max(d["GHz"]))]
        for row, aid in enumerate(d['ANTENNA1']):
            ant = str(d['ANTENNA'][aid])
            scan = int(d['SCAN_NUMBER'][row])
            spw = int(d['SPECTRAL_WINDOW_ID'][row])
            group = self.groups.setdefault((ant, scan), [])
            position = (ant, scan)
            self.scan_spws.setdefault(position, set()).add(spw)
            self.sources.setdefault(position, set()).add(str(d['FIELD'][d['FIELD_ID'][row]]))
            self.delay_totals[position] = self.delay_totals.get(position, 0) + 2
            self.delay_flags[position] = self.delay_flags.get(position, 0) + int(d['FLAG'][[1,5],0,row].sum())
            for slot, hand, name in [(0,'R','phase'), (1,'R','delay'), (4,'L','phase'), (5,'L','delay')]:
                key = (ant, scan, spw, hand, name)
                if key in self.points:
                    raise ValueError(f'Ambiguous solution rows for {key}')
                value = float(d['FPARAM'][slot,0,row])
                valid = np.isfinite(value) and not d['FLAG'][slot,0,row]
                cmd = command(key, path) if hand == 'R' and abs(value) < 1e30 else None
                if name == 'phase':
                    value = (np.degrees(value) + 180) % 360 - 180
                self.points[key] = bool(valid and cmd)
                if valid and hand=="R":
                    self.raw[key] = float(d["FPARAM"][slot,0,row])
                if valid:
                    group.append(dict(key=key, freq=float(d['GHz'][spw]), value=value,
                                      source=str(d['FIELD'][d['FIELD_ID'][row]]), cmd=cmd))
        self.imported = ImportedReview(args,[path],output,self.parse)
        self.log = FringeJournal(output, {'table': str(path),**self.imported.identity}, args.overwrite)

    def parse(self, text):
        keys = []
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            call = ast.parse(line.strip(), mode='eval').body
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != 'flagdata' or call.args:
                raise ValueError('Expected one formal flagdata call per line')
            kw = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
            if len(kw) != len(call.keywords) or kw.get('vis') != self.path:
                raise ValueError('Use the loaded table path and unique keyword arguments')
            parameter = {'REAL_Sol1': 'phase', 'REAL_Sol2': 'delay'}.get(kw.get('correlation'))
            if parameter is None:
                raise ValueError('Choose REAL_Sol1 for R phase or REAL_Sol2 for R delay')
            required={'vis','mode','antenna','datacolumn','correlation','clipminmax','clipoutside','flagbackup'}
            if (set(kw)-{'spw','scan'}!=required or kw['mode']!='clip' or kw['datacolumn']!='FPARAM'
                or type(kw['clipoutside'])!=bool or kw['flagbackup'] is not True):
                raise ValueError('Use an FPARAM clip selection with flag backup')
            lo,hi=kw['clipminmax']
            if not np.isfinite([lo,hi]).all() or lo>hi:
                raise ValueError('Invalid clip limits')
            ant=kw['antenna']
            rows=[k for k in self.raw if k[0]==ant and k[4]==parameter]
            if not rows and not any(a==ant for a,_ in self.groups):
                raise ValueError('Unknown antenna')
            scans=np.array([k[1] for k in rows])
            spws=np.array([k[2] for k in rows])
            mask=scan_mask(scans,kw.get('scan','')) & frequencies(spws,np.zeros(len(rows)),kw.get('spw',''))
            for i in np.flatnonzero(mask):
                key=rows[i]
                if (lo<=self.raw[key]<=hi) != kw['clipoutside'] and key not in keys:
                    keys.append(key)
        return keys

    @lru_cache(maxsize=1024)
    def command_keys(self, line):
        return self.parse(line)

    def approved_commands(self):
        rows=[]
        for index,step in enumerate(self.log.data['steps']):
            calls=step.get('calls')
            if calls is None:
                lines=[command(key,self.path) for key in step['keys']]
            else:
                lines=[format_call(k) for k in calls]
            for offset,line in enumerate(lines):
                keys=self.command_keys(line)
                rows.append(dict(uid=f'{index}.{offset}',line=line,keys=keys,
                                 antenna=keys[0][0] if keys else ''))
        return sorted(rows,key=lambda r:r['antenna'])

    def api(self, action, q):
        if action == 'state':
            return dict(groups=list(self.groups), table=self.log.data['identity']['table'], out=str(self.log.out))
        if action in ('points', 'delays'):
            approved = [key for step in self.log.data['steps'] for key in step['keys']]
        if action == 'delays':
            positions = [pos for pos in self.groups if pos[0] == q['ant']]
            if self.imported.entries and not self.imported.examine:
                index = len(self.log.data['steps'])
                if index < len(self.imported.entries):
                    spec = self.imported.entries[index]['scan']
                    keep = scan_mask(np.array([scan for _,scan in positions]), spec)
                    positions = [pos for pos,selected in zip(positions,keep) if selected]
            points = [p for pos in positions for p in self.groups[pos] if p['key'][4]=='delay']
            sources = sorted(set().union(*(self.sources[pos] for pos in positions)))
            return dict(points=points, sources=sources, band=self.band, approved=approved,commands=self.approved_commands())
        if action == 'points':
            position = (q['ant'], int(q['scan']))
            return dict(points=self.groups[position], spws=sorted(self.scan_spws[position]), flagged_delays=self.delay_flags[position],
                        total_delays=self.delay_totals[position],
                        sources=sorted(self.sources[position]), band=self.band, approved=approved,commands=self.approved_commands())
        keys = self.parse(q['text'])
        if action == 'approve':
            if not keys:
                raise ValueError('Select at least one solution')
            calls=[{kw.arg:ast.literal_eval(kw.value) for kw in ast.parse(line.strip(),mode='eval').body.keywords}
                   for line in q['text'].splitlines() if line.strip() and not line.lstrip().startswith('#')]
            lines=[line.strip() for line in q['text'].splitlines() if line.strip() and not line.lstrip().startswith('#')]
            self.log.add(dict(keys=keys,calls=calls,lines=lines,reason=q['reason'].strip() or 'Approved fringe solution'))
        elif action != 'preview':
            raise ValueError('Unknown action')
        return dict(keys=keys)
