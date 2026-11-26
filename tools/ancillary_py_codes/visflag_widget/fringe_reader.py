"""Read an rPICARD single-band CASA Fringe Jones table with CASA Python."""
import sys
from pathlib import Path
from contextlib import contextmanager
import numpy as np
from casatools import table

root = Path(sys.argv[1])

@contextmanager
def opened(name):
    tb = table()
    tb.open(str(root / name), nomodify=True, lockoptions={'option': 'usernoread'})
    try:
        yield tb
    finally:
        tb.close()

with opened('') as tb:
    if tb.getkeyword('VisCal') != 'Fringe Jones':
        raise ValueError('Expected a Fringe Jones calibration table')
    data = {k: tb.getcol(k) for k in ('ANTENNA1', 'SCAN_NUMBER', 'FIELD_ID', 'SPECTRAL_WINDOW_ID', 'FPARAM', 'FLAG')}
    if data['FPARAM'].shape[:2] != (8, 1) or data['FLAG'].shape != data['FPARAM'].shape:
        raise ValueError('Expected eight fringe parameters and one solution channel')
for name in ('ANTENNA', 'FIELD'):
    with opened(name) as tb:
        data[name] = np.asarray(tb.getcol('NAME'), dtype=str)
with opened('SPECTRAL_WINDOW') as tb:
    data['GHz'] = np.array([tb.getcell('CHAN_FREQ', i).mean()/1e9 for i in range(tb.nrows())])
np.savez(sys.argv[2], **data)
