"""CASA Python subprocess; all table handles open read-only."""
import sys
from pathlib import Path
from contextlib import contextmanager
import numpy as np
from casatools import table

path, out, op, field = sys.argv[1:5]


@contextmanager
def opened(name):
    tb = table()
    tb.open(str(Path(path) / name), nomodify=True)
    try:
        yield tb
    finally:
        tb.close()


with opened("FIELD") as tb:
    fields = list(tb.getcol("NAME"))
if not field and len(fields) == 1:
    field = fields[0]
if fields.count(field) != 1:
    raise ValueError("Specify a unique --field from " + str(fields))
with opened("ANTENNA") as tb:
    ants = tb.getcol("NAME")
    stations = tb.getcol("STATION")
    if all(a.isdigit() for a in ants) and all(stations) and len(set(stations)) == len(stations):
        ants = stations
with opened("") as tb:
    expr = "FIELD_ID==%d && ANTENNA1!=ANTENNA2" % fields.index(field)
    if op == "index":
        q = tb.query(expr)
        a, b, s = [q.getcol(k) for k in ("ANTENNA1", "ANTENNA2", "SCAN_NUMBER")]
        times = q.getcol("TIME") - 40587 * 86400.0
        bounds = [(i, times[s == i].min(), times[s == i].max()) for i in np.unique(s)]
        q.close()
        combos = np.unique(np.column_stack((a, b, s)), axis=0)
        np.savez(
            out,
            field=field,
            bounds=bounds,
            antennas=np.asarray(ants,dtype=str),
            scans=combos[:, 2],
            pairs=[ants[i] + "&" + ants[j] for i, j, _ in combos],
        )
    else:
        scan, pair = sys.argv[5:7]
        a, b = [list(ants).index(x) for x in pair.split("&")]
        selection = expr + " && SCAN_NUMBER==%d && ANTENNA1==%d && ANTENNA2==%d" % (int(scan), a, b)
        q = tb.query(selection)
        dd = q.getcol("DATA_DESC_ID")
        times = q.getcol("TIME")
        t = np.unique(times)
        blocks = []
        for d in np.unique(dd):
            sub = tb.query(selection + " && DATA_DESC_ID==%d" % d)
            with opened("DATA_DESCRIPTION") as desc:
                sp = int(desc.getcell("SPECTRAL_WINDOW_ID", int(d)))
                pol = int(desc.getcell("POLARIZATION_ID", int(d)))
            with opened("SPECTRAL_WINDOW") as spws:
                freq = spws.getcell("CHAN_FREQ", sp) / 1e9
            with opened("POLARIZATION") as pols:
                codes = pols.getcell("CORR_TYPE", pol)
            col = "CORRECTED_DATA" if "CORRECTED_DATA" in sub.colnames() else "DATA"
            z = sub.getcol(col).T
            wt = (
                sub.getcol("WEIGHT_SPECTRUM").T
                if "WEIGHT_SPECTRUM" in sub.colnames() and sub.iscelldefined("WEIGHT_SPECTRUM", 0)
                else sub.getcol("WEIGHT").T[:, None, :]
            )
            valid = (
                ~sub.getcol("FLAG").T
                & ~sub.getcol("FLAG_ROW")[:, None, None]
                & np.isfinite(z)
                & np.isfinite(wt)
                & (wt > 0)
            )
            ix = np.searchsorted(t, sub.getcol("TIME"))
            if len(set(ix)) != len(ix):
                raise ValueError("Multiple rows per baseline, DDID and timestamp")
            v = np.zeros((len(t), len(freq), 4), np.complex64)
            w = np.zeros(v.shape, np.float32)
            for i, code in enumerate(codes):
                if code not in (5, 6, 7, 8):
                    raise ValueError("Expected circular correlations")
                j = {5: 0, 8: 1, 6: 2, 7: 3}[code]
                v[ix, :, j] = np.where(valid[:, :, i], z[:, :, i], 0)
                w[ix, :, j] = np.where(valid[:, :, i], wt[:, :, i], 0)
            blocks.append((sp, freq, v, w))
            sub.close()
        q.close()
        np.savez(
            out,
            t=t - 40587 * 86400.0,
            f=np.concatenate([b[1] for b in blocks]),
            spw=np.concatenate([np.full(len(f), s) for s, f, _, _ in blocks]),
            ch=np.concatenate([np.arange(len(b[1])) for b in blocks]),
            v=np.concatenate([b[2] for b in blocks], axis=1),
            w=np.concatenate([b[3] for b in blocks], axis=1),
        )
