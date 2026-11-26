"""Extract finite unflagged passband samples with read-only CASA handles."""
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
import sys
import numpy as np
from casatools import table

root, kind, output = sys.argv[1:]
@contextmanager
def opened(sub=''):
    tb = table()
    tb.open(str(Path(root)/sub), nomodify=True, lockoptions={'option':'usernoread'})
    try:
        yield tb
    finally:
        tb.close()

with opened('ANTENNA') as tb:
    names = np.asarray(tb.getcol('NAME'), dtype=str)
with opened('SPECTRAL_WINDOW') as tb:
    freq = [tb.getcell('CHAN_FREQ', i)/1e9 for i in range(tb.nrows())]
    widths = [np.abs(tb.getcell('CHAN_WIDTH', i))/2e9 for i in range(tb.nrows())]
samples = defaultdict(list)
with opened() as tb:
    if tb.getkeyword('VisCal') != 'B Jones':
        raise ValueError('Expected a CASA B Jones calibration table')
    ants, refs, windows = (tb.getcol(k) for k in ('ANTENNA1','ANTENNA2','SPECTRAL_WINDOW_ID'))
    scans = tb.getcol("SCAN_NUMBER")
    active = np.unique(ants)
    selectors = []
    for a in active:
        if a in refs and not np.all(refs[ants==a] == a):
            raise ValueError('Ambiguous calibration antenna selector for ' + names[a])
        selectors.append(names[a] + ('&&&' if a in refs else ''))
    for row, (a,w) in enumerate(zip(ants,windows)):
        z = tb.getcell('CPARAM',row)
        flags = tb.getcell('FLAG',row)
        if z.shape != (2,len(freq[w])) or flags.shape != z.shape:
            raise ValueError('Expected two hands with native channel frequencies')
        for hand in range(2):
            channels = np.flatnonzero(~flags[hand] & np.isfinite(z[hand]))
            v = z[hand, channels]
            value = np.angle(v) if kind=='phase' else np.abs(v)
            samples[a,hand,w].append(np.column_stack((channels,value,np.abs(v),np.full(len(v),scans[row]))))

data = dict(names=names[active], selectors=np.array(selectors),
            bands=np.array([(w,np.min(freq[w]-widths[w]),np.max(freq[w]+widths[w])) for w in np.unique(windows)]))
for i,a in enumerate(active):
    for h in range(2):
        blocks = []
        for w in np.unique(windows):
            rows = samples.get((a,h,w))
            if rows:
                values, counts = np.unique(np.concatenate(rows),axis=0,return_counts=True)
                ch = values[:,0].astype(int)
                blocks.append(np.column_stack((np.full(len(ch),w),ch,freq[w][ch],values[:,1],counts,values[:,2],values[:,3])))
        data[f'p{i}_{h}'] = np.concatenate(blocks) if blocks else np.empty((0,7))
np.savez(output, **data)
