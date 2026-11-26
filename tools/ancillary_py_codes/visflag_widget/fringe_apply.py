"""Apply individually approved flags to an rPICARD single-band Fringe Jones table."""
from casatools import table
import numpy as np


def flag_solution(vis, antenna, scan, spw, hand, parameter):
    """Set one parameter flag on one uniquely identified solution row."""
    tb = table()
    tb.open(str(vis) + '/ANTENNA', nomodify=True)
    try:
        names = list(tb.getcol('NAME'))
        if names.count(antenna) != 1:
            raise ValueError('Expected a unique station named ' + antenna)
        station = names.index(antenna)
    finally:
        tb.close()
    slot = {'R': 0, 'L': 4}[hand] + {'phase': 0, 'delay': 1}[parameter]
    tb.open(str(vis), nomodify=False)
    try:
        if tb.getkeyword('VisCal') != 'Fringe Jones':
            raise ValueError('Expected Fringe Jones solutions')
        rows = np.flatnonzero((tb.getcol('ANTENNA1') == station) &
                              (tb.getcol('SCAN_NUMBER') == scan) &
                              (tb.getcol('SPECTRAL_WINDOW_ID') == spw))
        if len(rows) != 1 or tb.getcell('FLAG', int(rows[0])).shape != (8, 1):
            raise ValueError('Selection must identify exactly one single-band solution')
        tb.lock(write=True)
        flags = tb.getcell('FLAG', int(rows[0]))
        flags[slot, 0] = True
        tb.putcell('FLAG', int(rows[0]), flags)
        tb.flush()
    finally:
        tb.close()
