# Inspect rPICARD complex and scalar passbands

This procedure produced the seven-antenna inspection (AA, AX, GL, KT, MG, NN, PV) for e26m17-1-b3. It works from the active CASA tables in the reduction’s calibration_tables directory. Write a new PDF and this guide in inspection/. Record the observation, reduction, table versions or paths, antenna list, CASA version and analysis time. For this report the model was GPT-6.2 Astra High.

## Read the solutions

1. In the matching CASA Python environment, open bpass_complx.t and bpass_scalar.t read-only with casatools.table. Read ANTENNA/NAME, FIELD/NAME and each SPECTRAL_WINDOW/CHAN_FREQ array independently for each table. Resolve station names before selecting rows. In the main table read ANTENNA1, SPECTRAL_WINDOW_ID, FIELD_ID, SCAN_NUMBER, TIME, CPARAM and FLAG. Use the saved channel frequencies (Hz divided by 1e9); a solution channel index is local to its SPW.
2. Confirm hand order from observation metadata and diagnostic legends. Here hand indices 0 and 1 correspond to R and L. CPARAM and FLAG have axes [hand, solution channel, row]. This reduction has 116 native channels in each of 32 SPWs. For another reduction handle each row separately if its channel shape differs.
3. For complex bandpass display angle(CPARAM) in degrees on a signed ±180° axis. For scalar bandpass display abs(CPARAM), a dimensionless gain. Check the settings for phase-only solving, gap filling and normalization. Group by actual table times and fields. Report a unity spectrum as a stored unity correction; interpreting whether it was fitted or substituted requires processing evidence.
4. Inventory rows, existing flags and non-finite samples per antenna and hand. Record scan and source coverage separately for the two tables. For the present dataset the complex table labels all station spectra as 3C279 scan 3. Scalar entries span four sources. All scalar spectra repeat exactly from scan to scan within each antenna/SPW. Count every row but draw a coincident spectrum once only after verifying identical values and masks. In another run overlay genuinely different spectra or facet them by time. Avoid assuming all available scans contain independent solves.

## Select review candidates

Start with finite, unflagged entries. Work within a single table row, hand and SPW. The numerical cuts below are review criteria for this pass. Reassess them against local noise, calibration settings and spectral structure on each dataset.

| Quantity | Value outlier | Adjacent-channel jump | Endpoint to mark |
|---|---|---|---|
| Phase | Absolute wrapped phase above 60° | Absolute circular difference above 60° | Larger absolute wrapped phase |
| Amplitude | Gain below 0.5 or above 1.5 | Absolute gain difference above 0.35 | Larger absolute distance from unity |

Use degrees(angle(z_next × conjugate(z_previous))) for circular phase differences. Require both endpoints to be valid, finite and directly adjacent. Do not bridge a flagged channel or SPW boundary. Break exact endpoint ties toward the higher index. Keep separate masks for outliers, jump endpoints, overlap and their union. Inspect before classifying a jump as a bad channel: a sustained offset, band edge, smooth phase ramp, poor fit, or isolated spike can produce different signatures. A jump identifies a boundary; the chosen endpoint is a candidate for review.

## Make the comparison pages

- Allocate two consecutive pages per antenna. For each page draw exactly two two-panel figures, one for R and one for L. In each figure put phase above amplitude against native frequency in GHz. Label axes, polarization, SPW boundaries and units. Use the same limits and tick locations on both pages. Do not pair scalar and complex rows as if observed simultaneously.
- On the first page show all stored finite values, mark prior flags separately and distinguish new value outliers, jump-only endpoints and overlap using different symbols. On the next page use the original entry mask with the union of new candidates removed. Leave real coverage gaps visible. For non-finite entries that cannot be drawn, give a count.
- Include station/SPW/channel examples, the reason for each selection and the observed comparison. Report both the total entries and the distinct spectral channels, especially when spectra repeat by scan. Distinguish the effects of masking from evidence that a recalibrated observation has improved.

### Identify input tables and annotate noteworthy features

On the first page, show the exact input table paths relative to the reduction directory. Label which quantity each provides: phase from calibration_tables/bpass_complx.t and gain amplitude from calibration_tables/bpass_scalar.t. Update the paths when a different table version is used.

Mark noteworthy excursions directly on the affected antenna and hand panels. Use native CHAN_FREQ values to place a labeled vertical guide at an isolated channel or a shaded band over a cluster. Give the SPW and channel or channel range. Keep the guides at identical frequencies on the before and after pages. A guide denotes the location of the finding; only the verified candidate mask excludes a value. Describe zero or nearly zero phase in the closing notes without highlighting the flat trace. Mark genuine excursions within such spectra.

For this reduction, highlight AA R in SPW 28 channels 86–89; AX in both hands at SPW 6 channel 115 and SPW 28 channel 97; the KT R cluster in SPWs 15–16, MG R in SPWs 14–16, and both stations’ L clusters in SPW 2. On scalar panels mark the 40 SPW/channel locations shared by all seven stations in both hands with short ticks along the lower edge. Label representative common dips, the deep edge channel, and NN’s extended SPW 28 drop at channels 97–115. Derive the selections afresh for other observations. Render the final PDF and check the labels against the native frequency coordinates and the first-page table names.

## Produce and test formal CASA commands

Generate standalone flagdata calls, one per selection, writing out every call with its actual arguments. The example below was executed with CASA 6.6.6.18 on disposable copies and verified against the complete FLAG cubes. Run the setup from the reduction directory with new destination names. For new data regenerate all selections, including scan restrictions, channel ranges and value bounds. If a candidate is present only in a subset of scans, restrict the command to those rows. This example uses all available scalar scan rows because the spectra and candidate masks were identical across them.

The first call for each hand uses clipoutside=True to select outlying values. CASA ARG clip limits are in radians, while the plots use degrees. For jump-only candidates the second call identifies exact SPW/channel ranges and uses clipoutside=False over a modulus interval covering the selected entries. Confirm that the interval includes the intended moduli in the new data. Keep verification separate from the flagging calls: read the complete original and modified cubes and assert that the tested copy equals original flags OR the candidate mask. Include all other antennas in this comparison. GL, NN and PV contain only unity corrections in the phase table and require no phase command. On this snapshot 39 calls produced exactly 295 new phase flags and 16,246 new amplitude flags. For the cross-station check, intersect the distinct amplitude SPW/channel selections across all seven stations and both hands; 40 channel positions are common to all 14 sets.


For this dataset the calibration tables use AA as the second antenna ID. Use the verified AA&&& selector to isolate the AA/AA calibration rows. A bare AA selector in a test selected other stations and missed the intended AA flags. Inspect ANTENNA1 and ANTENNA2 and retest on fresh copies for other datasets.

The all-station screen found 40 scalar SPW/channel pairs common to all seven antennas in both hands. To repeat this check, deduplicate each antenna/hand mask over rows (keeping SPW and channel), then intersect the 14 sets. Report repeated scan counts separately from distinct affected channels. The individual commands below reproduce the masks for this particular reduction.

```python
from shutil import copytree
from casatasks import flagdata
complx = 'calibration_tables/bpass_complx.all.review.t'
scalar = 'calibration_tables/bpass_scalar.all.review.t'
copytree('calibration_tables/bpass_complx.t', complx)
copytree('calibration_tables/bpass_scalar.t', scalar)

# AA R complx
flagdata(vis=complx, mode='clip', antenna='AA&&&', scan='3',
         datacolumn='CPARAM', correlation='ARG_Sol1',
         clipminmax=[-1.0471975512, 1.0471975512], clipoutside=True, flagbackup=True)

# AX R complx
flagdata(vis=complx, mode='clip', antenna='AX', scan='3',
         datacolumn='CPARAM', correlation='ARG_Sol1',
         clipminmax=[-1.0471975512, 1.0471975512], clipoutside=True, flagbackup=True)

# AX L complx
flagdata(vis=complx, mode='clip', antenna='AX', scan='3',
         datacolumn='CPARAM', correlation='ARG_Sol2',
         clipminmax=[-1.0471975512, 1.0471975512], clipoutside=True, flagbackup=True)

# KT R complx
flagdata(vis=complx, mode='clip', antenna='KT', scan='3',
         datacolumn='CPARAM', correlation='ARG_Sol1',
         clipminmax=[-1.0471975512, 1.0471975512], clipoutside=True, flagbackup=True)

flagdata(vis=complx, mode='clip', antenna='KT', scan='3',
         spw=('3:98,8:58;81~82;86;94;96~97,15:5;7;28;65,'
              '16:21~22;49;59;61;71;74~75,17:100,20:73,21:42;63,23:89,'
              '27:64;89'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# KT L complx
flagdata(vis=complx, mode='clip', antenna='KT', scan='3',
         datacolumn='CPARAM', correlation='ARG_Sol2',
         clipminmax=[-1.0471975512, 1.0471975512], clipoutside=True, flagbackup=True)

flagdata(vis=complx, mode='clip', antenna='KT', scan='3',
         spw=('2:5;39;41~42;53;68,15:89~90;104,16:22;24;69;73;82;103,'
              '18:87;107,20:56;60;65;69;105;108,21:17;64;88;108,22:105,'
              '23:100,29:51;54'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# MG R complx
flagdata(vis=complx, mode='clip', antenna='MG', scan='3',
         datacolumn='CPARAM', correlation='ARG_Sol1',
         clipminmax=[-1.0471975512, 1.0471975512], clipoutside=True, flagbackup=True)

flagdata(vis=complx, mode='clip', antenna='MG', scan='3',
         spw=('5:97,6:92,12:71,13:106,14:0;6;9;43;57;65,15:9;26;28;37;82,'
              '16:15;20~21;32;39;42;52~53;64;67;79,20:108'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# MG L complx
flagdata(vis=complx, mode='clip', antenna='MG', scan='3',
         datacolumn='CPARAM', correlation='ARG_Sol2',
         clipminmax=[-1.0471975512, 1.0471975512], clipoutside=True, flagbackup=True)

flagdata(vis=complx, mode='clip', antenna='MG', scan='3',
         spw=('2:35;44;49;57;109,21:8;17;86,30:98'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# AA R scalar
flagdata(vis=scalar, mode='clip', antenna='AA&&&',
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='AA&&&',
         spw=('4:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# AA L scalar
flagdata(vis=scalar, mode='clip', antenna='AA&&&',
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='AA&&&',
         spw=('4:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# AX R scalar
flagdata(vis=scalar, mode='clip', antenna='AX',
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='AX',
         spw=('4:115,9:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# AX L scalar
flagdata(vis=scalar, mode='clip', antenna='AX',
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='AX',
         spw=('4:115,9:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# GL R scalar
flagdata(vis=scalar, mode='clip', antenna='GL',
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='GL',
         spw=('10:115,15:115,20:115,26:115'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# GL L scalar
flagdata(vis=scalar, mode='clip', antenna='GL',
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='GL',
         spw=('4:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# KT R scalar
flagdata(vis=scalar, mode='clip', antenna='KT',
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='KT',
         spw=('4:115,9:115,10:115,15:115,20:115,26:115'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# KT L scalar
flagdata(vis=scalar, mode='clip', antenna='KT',
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='KT',
         spw=('10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# MG R scalar
flagdata(vis=scalar, mode='clip', antenna='MG',
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='MG',
         spw=('4:115,5:115,10:115,15:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# MG L scalar
flagdata(vis=scalar, mode='clip', antenna='MG',
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='MG',
         spw=('9:115,10:115,15:115,20:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# NN R scalar
flagdata(vis=scalar, mode='clip', antenna='NN',
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='NN',
         spw=('4:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# NN L scalar
flagdata(vis=scalar, mode='clip', antenna='NN',
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='NN',
         spw=('4:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# PV R scalar
flagdata(vis=scalar, mode='clip', antenna='PV',
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='PV',
         spw=('5:115,10:115,15:115,20:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol1',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)

# PV L scalar
flagdata(vis=scalar, mode='clip', antenna='PV',
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.5, 1.5], clipoutside=True, flagbackup=True)

flagdata(vis=scalar, mode='clip', antenna='PV',
         spw=('10:115,15:115,26:115,31:115'),
         datacolumn='CPARAM', correlation='ABS_Sol2',
         clipminmax=[0.0, 2.0], clipoutside=False, flagbackup=True)
```

## Record usage and verify the report

Use model and reasoning effort from the analysis turn metadata. Take the last chat token-counter sample before the green light and the latest available sample before final PDF generation. Record the timestamp of the latter and the differences in cumulative input, cached input (included in input) and output tokens. For the rounded five-hour and weekly account meters, check for matching reset times before subtracting used percentages. Report the change in percentage points and identify it as account-wide. Exact attribution of a quota percentage to this job is unavailable if other activity shares that meter. Render the completed PDF and check both polarization pairs, before/after alignment, coverage, and readable standalone command calls.
