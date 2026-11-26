"""Integration check. Pass a fringe table and a CASA Python executable."""
import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from fringe import Fringe, command

def check_copy(source, casa):
    reader = Path(__file__).with_name('fringe_reader.py').resolve()
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch).resolve()
        dest = root/'copy.t'
        shutil.copytree(source, dest)
        def snapshot(path):
            target = root/'test.npz'
            subprocess.run([casa, str(reader), str(path), str(target)], cwd=root, check=True,
                           capture_output=True)
            with np.load(target) as data:
                return dict(data)
        before = snapshot(source)
        args = SimpleNamespace(vis=dest, output=root/'approved.py', casa_python=casa, overwrite=False)
        review = Fringe(args)
        for aid, ant in enumerate(before['ANTENNA']):
            overview = review.api('delays', dict(ant=str(ant)))
            expected = set()
            for row in np.flatnonzero(before['ANTENNA1'] == aid):
                for slot, hand in ((1, 'R'), (5, 'L')):
                    value = before['FPARAM'][slot,0,row]
                    if np.isfinite(value) and not before['FLAG'][slot,0,row]:
                        key = (ant, int(before['SCAN_NUMBER'][row]), int(before['SPECTRAL_WINDOW_ID'][row]), hand, 'delay')
                        expected.add((key, before['FIELD'][before['FIELD_ID'][row]], float(value)))
            assert set(overview['sources']) == set(before['FIELD'][before['FIELD_ID']])
            assert len(overview['points']) == len(expected)
            assert {(p['key'], p['source'], p['value']) for p in overview['points']} == expected
        selected = []
        for ant, scan in review.groups:
            view = review.api('points', dict(ant=ant, scan=scan))
            points = view['points']
            rows = (before['ANTENNA'][before['ANTENNA1']]==ant) & (before['SCAN_NUMBER']==scan)
            delays = before['FLAG'][[1,5],0][:,rows]
            assert view['flagged_delays']==int(delays.sum()) and view['total_delays']==delays.size
            assert all(p['key'][:2]==(ant,scan) and p['cmd']==(command(p['key'], dest) if p['key'][3]=='R' else None) for p in points)
            if selected or len(points)<4:
                continue
            for par in ('phase','delay'):
                used_spws = {k[2] for k in selected}
                selected.append(next(p['key'] for p in points if p['key'][3:]==('R',par) and p['key'][2] not in used_spws))
        text = '\n'.join(command(k, dest) for k in selected)
        assert review.api('preview', dict(text=text))['keys']==selected
        review.api('approve', dict(text=text, reason='Fringe integration test'))
        assert args.output.read_text() == text + '\n'
        assert all(isinstance(st,ast.Expr) and st.value.func.id=='flagdata'
                   for st in ast.parse(text).body)
        runner = root/'run_test.py'
        runner.write_text('from casatasks import flagdata\n' + args.output.read_text())
        subprocess.run([casa, str(runner)], cwd=root, check=True)
        after = snapshot(dest)
        expect = before['FLAG'].copy()
        for ant,scan,spw,hand,par in selected:
            row = np.flatnonzero((before['ANTENNA'][before['ANTENNA1']]==ant)&
                                 (before['SCAN_NUMBER']==scan)&(before['SPECTRAL_WINDOW_ID']==spw))
            assert len(row)==1
            expect[(4 if hand=='L' else 0)+(par=='delay'),0,row]=True
        assert np.count_nonzero(expect!=before['FLAG'])==2
        assert np.array_equal(expect,after['FLAG'])
        assert np.array_equal(before['FPARAM'],after['FPARAM'],equal_nan=True)
        assert np.array_equal(before['FLAG'],snapshot(source)['FLAG'])
        print(len(review.groups),'antenna/scan views verified;',selected,'changed exactly two FLAG elements')

if __name__=='__main__':
    check_copy(Path(sys.argv[1]).resolve(), str(Path(sys.argv[2]).expanduser().absolute()))
