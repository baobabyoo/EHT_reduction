"""Index M87 scan/baseline coverage from the single-source CASA UVFITS export."""
import argparse
import csv
import re
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.time import Time


def stored_scans(groups):
    names={n.upper():n for n in groups.parnames}
    for name in ('SCAN_NUMBER','SCAN'):
        if name in names:
            ids=groups.par(names[name])
            if not np.all(np.isfinite(ids) & (ids==np.floor(ids))):
                raise ValueError('Invalid stored scan identifiers')
            return ids.astype(int)
    return None


def index(uvfits, scanlog, output):
    with fits.open(uvfits, memmap=True) as h:
        g = h[0].data
        stations = dict(zip(h['AIPS AN'].data['NOSTA'], h['AIPS AN'].data['ANNAME']))
        times = g.par('DATE')
        baseline = g.par('BASELINE').astype(int)
        source = h[0].header['OBJECT'].strip()
        day = h[0].header['DATE-OBS'][:10]
        pattern = r'(\d\d:\d\d:\d\d\.\d+)\s+-\s+(\d\d:\d\d:\d\d\.\d+)\s+(\d+)\s+\d+\s+' + re.escape(source) + r'\s'
        rows = []
        assigned=np.zeros(len(times),dtype=int)
        ids=stored_scans(g)
        if ids is None:
            intervals=re.findall(pattern,scanlog.read_text())
            provenance=str(scanlog)
        else:
            intervals=[]
            for scan in sorted(np.unique(ids),key=lambda s:times[ids==s].min()):
                stamps=Time([times[ids==scan].min(),times[ids==scan].max()],format='jd').isot
                intervals.append((stamps[0].split('T')[1],stamps[1].split('T')[1],scan))
            provenance='UVFITS scan parameter'
        for start, end, scan in intervals:
            lo, hi = Time([day+'T'+start, day+'T'+end]).jd
            mask = ids==int(scan) if ids is not None else (times >= lo) & (times <= hi + .01/86400)
            if not mask.any():continue
            measured=Time([times[mask].min(),times[mask].max()],format='jd').isot
            assigned += mask
            for code in np.unique(baseline[mask]):
                a,b = divmod(int(code),256)
                if a == b:
                    continue
                data = g.data[mask & (baseline == code)]
                good = np.isfinite(data).all(axis=-1) & (data[...,2]>0)
                rows.append([scan,start,end,stations[a],stations[b],len(data),good.sum(),good.size,provenance,*measured])
        if not np.all(assigned==1):
            raise ValueError('Some timestamps match zero or multiple scan intervals')
        if not rows:
            raise ValueError("No matching scan/baseline records")
        with output.open('w') as handle:
            w = csv.writer(handle)
            w.writerow(['scan','start_utc','end_utc','station1','station2','integrations','valid','total','scan_id_source','measured_start_utc','measured_end_utc'])
            w.writerows(rows)
        print(len(rows),'baseline-scan selections;',len(set(r[0] for r in rows)),'scans')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('uvfits','scanlog','output'):
        parser.add_argument(key,type=Path)
    args=parser.parse_args()
    index(args.uvfits,args.scanlog,args.output)
