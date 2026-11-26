# Repeating the CASA single-band fringe-table inspection

Use the active reduction's `calibration_tables/ff_sb.t` and write the PDF into its `inspection/` directory. For e26m17-1-b3 the table is a CASA Fringe Jones calibration product. Record the track, table path, CASA version, analysis time with time zone and model identity in the PDF. For this analysis the recorded model was GPT-6.2 Astra High (model ID gpt-6.2-astra, reasoning effort high). On future runs check the analysis turn’s model and effort in the chat metadata before recording them. Keep the observing date separate from the analysis timestamp.

## Extract the active solutions

Use the Intel CASA interpreter in `~/Applications/CASA-6.6.6-Intel.app/Contents/MacOS/python3` for this installation. The following extraction can run from a temporary directory. Pass the absolute table path and the path of a temporary NPZ file as its two arguments.

```python
from pathlib import Path
from casatools import table
import numpy as np
import sys
root=Path(sys.argv[1]); out={}
def getrows(sub,cols):
 t=table();t.open(str(root/sub),nomodify=True,lockoptions={'option':'usernoread'})
 try:
  for col,n in cols.items():out[n]=t.getcol(col)
  if not sub:
   print(t.getkeywords().keys(),t.getcolkeywords('FPARAM')); print({k:t.getkeyword(k) for k in ['VisCal','ParType','PolBasis'] if k in t.keywordnames()})
  if sub=='SPECTRAL_WINDOW':
   out['freq']=np.array([np.mean(t.getcell('CHAN_FREQ',i)) for i in range(t.nrows())])/1e9
 finally:t.close()
getrows('',{k:k for k in ['FPARAM','FLAG','SCAN_NUMBER','FIELD_ID','ANTENNA1','SPECTRAL_WINDOW_ID','TIME']})
getrows('FIELD',{'NAME':'sources'});getrows('ANTENNA',{'NAME':'ants'});getrows('SPECTRAL_WINDOW',{})
print(out['sources'],out['ants'],out['freq'],np.unique(out['FIELD_ID']),out['FPARAM'].shape)
np.savez(sys.argv[2],**out)
```

## Validate the arrays before plotting

1. Confirm `VisCal` is Fringe Jones and `ParType` is Float. In this reduction `FPARAM` and `FLAG` both have shape (8, 1, 7168). The axes are parameter, solution channel, table row. Verify the layout for any other table or CASA version before applying these indices.
2. Map each row's antenna, field and SPW IDs through the corresponding subtables. Confirm field assignments against `list.obs` scan numbers. Check the correlation order there: this track uses circular feeds in RR, RL, LR, LL order. The caltable PolBasis keyword here says unknown. The pipeline's own FF_SB plots label the two solutions R and L.
3. Work in zero-based indices. R phase and delay are FPARAM slots 0 and 1. L phase and delay are slots 4 and 5. Delay is in ns. Convert phase from radians to degrees and wrap with `(np.rad2deg(phi) + 180) % 360 - 180`. Keep native signed delays. Exclude non-finite values and independently apply the matching parameter's FLAG. Retain counts by panel and hand.
4. Set each SPW's x coordinate to the arithmetic mean of its channel frequencies in Hz divided by 1e9. There is one fitted delay and phase per solution hand per SPW row. Check for duplicates in antenna / field / scan / SPW and retain valid time-dependent rows. Inspect the pipeline log for interpolation and reference changes before interpreting duplicates or identical values.

## Screen the delays

For each antenna/scan/hand, compare valid delays across SPWs with their median. When fewer than eight SPWs are available, use all finite unflagged delays for that antenna and hand across scans. Select absolute deviations exceeding max(10 ns, 6 × 1.4826 × MAD) using the same comparison sample. Save one Boolean selection mask keyed to the original parameter and table row. Do not recompute the rule after removing points. Group selected entries by antenna, hand, SPW, value and scans, retaining source assignments.

## Lay out the report

1. Begin with the table explanation, observation and analysis timestamps, CASA version, model identity, units, symbol key, usable counts and axis conventions.
2. For each antenna, start with two delay pages in immediate succession. Both have four single-column source panels, all scans overlaid. Show finite unflagged entries on the first page and circle selected entries. Exclude exactly the saved selection mask on the second page, maintain the frequency range and rescale the delay axis to the remaining values. Use linear scaling on the filtered page. A symmetric logarithmic scale with a ±50 ns linear core accommodates the largest delays on the first page.
3. Follow with phase pages for the same antenna. Sort scan IDs numerically and split into groups of eight, arranged in four rows and two columns, reading across rows. Give each panel its scan ID, source, and usable R/L counts. Retain a labeled empty panel if a scan has no usable phase for the antenna. Leave any unused panels at the end blank. Before drawing any points, collect all table rows for this antenna and scan. For an array flattened to FLAG[parameter, row], count R delay flags with FLAG[1, rows].sum() and L delay flags with FLAG[5, rows].sum(). If either count is positive, omit both phase series for the entire panel. Label it with the scan, source, and each hand’s flagged delay count over its row count. Otherwise draw the finite unflagged phases. Use the stored CASA delay flags for this decision. An outlier identified only by the analytical delay screen does not suppress the phase panel. Use a common frequency range and common phase limits with ticks at −180, −90, 0, 90 and 180 degrees.
4. Use blue open circles (#0072B2) for R and orange plus signs (#D55E00) for L throughout. Identify frequency in GHz, delay in ns and phase in degrees. Keep each page exclusive to one antenna.
5. After all antenna pages, list the outliers, then print executable CASA flagging commands for exactly those entries. End with notes on sparse scans, phase wrapping, interpolation and reference behavior. Distinguish repeat table values from independent detections.

## Formal CASA flagdata commands

Run from the reduction directory in CASA 6.6.6.18. The four clip commands below select the signed R delay (Sol2) within the specified ranges. On a fresh copy, comparing every FLAG element before and after gave exactly 30 new flags: AX 7 + 7, GL 7 and KT 9.

```python
from shutil import copytree
from casatasks import flagdata
vis = 'calibration_tables/ff_sb.review.t'
copytree('calibration_tables/ff_sb.t', vis)

flagdata(vis=vis, mode='clip', antenna='AX', spw='14', scan='3~9',
         datacolumn='FPARAM', correlation='REAL_Sol2', clipoutside=False,
         clipminmax=[807.15, 807.17], flagbackup=True)

flagdata(vis=vis, mode='clip', antenna='AX', spw='18', scan='3~9',
         datacolumn='FPARAM', correlation='REAL_Sol2', clipoutside=False,
         clipminmax=[848.19, 848.21], flagbackup=True)

flagdata(vis=vis, mode='clip', antenna='GL', spw='5', scan='3~9',
         datacolumn='FPARAM', correlation='REAL_Sol2', clipoutside=False,
         clipminmax=[20.04, 20.06], flagbackup=True)

flagdata(vis=vis, mode='clip', antenna='KT', spw='29', scan='1~9',
         datacolumn='FPARAM', correlation='REAL_Sol2', clipoutside=False,
         clipminmax=[-989.48, -989.46], flagbackup=True)
```

NN SPW 11, scans 21–32: the L delay occupies FPARAM slot 5 (zero-based). CASA rejected REAL_SOL6, and REAL_ALL clipping missed all 12 L-delay entries. The manual command below flags the entire solution row. In this table it added 96 flags: the 12 listed L delays plus 84 other values across both hands. Run it only if you intend to exclude the complete NN solutions.

```python
# flagdata(vis=vis, mode='manual', antenna='NN', spw='11',
#          scan='21~32', flagbackup=True)
```

With only the four clip commands, the review copy retains the 12 NN outliers. The filtered plots on the preceding pages exclude all 42 outliers analytically. For a different table or CASA version, repeat the test on a fresh copy and compare the complete FLAG cubes by parameter, antenna, SPW and scan. [CASA flagdata documentation](https://casadocs.readthedocs.io/en/stable/api/tt/casatasks.flagging.flagdata.html)

## Verify the output

For this reduction the PDF is 46 pages: one introduction, seven six-page antenna blocks (two delay pages and four phase pages per antenna), one outlier list, one command page and final notes. Check all 224 antenna/scan phase panels. For this active table expect 27 omitted panels (AX, GL and KT, each in scans 1–9) and 197 eligible panels. Confirm the 27 contain no phase points, and that the same scans remain eligible at AA, MG, NN and PV. The original delay totals are 6,493 R and 6,422 L. Removing 30 R and 12 L entries leaves 6,463 R and 6,410 L. Verify the formal clip commands independently: the changed FLAG cells must equal the 30 R-delay selections. If testing the optional NN manual command, compare its 96 additional changes separately. Reopen the PDF, render each page, and check the units, legends, commands, panel titles and margins. Deliver the PDF and this guide in the reduction's inspection directory.
