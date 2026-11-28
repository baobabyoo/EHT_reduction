<!-- This guide introduces a workflow for inspecting and flagging delay and passband solutions -->

Use this guide when reviewing rPICARD calibration solutions for one reduction run. Codex proposes flags. A human reviews them in the widget. Each exported CASA command must target the actual calibration table and the affected solution hand (R or L). Keep delay and passband reviews in separate files. The two passband tables may share one review file because each call names its target table.

Read the [PDF writing and layout guide](../inspection_pdf_style.md) for both reports. Give each its own opening findings. In the delay report, describe how much phase can be shown after accounting for the stored delay and phase flags. In the passband report, cover both tables before discussing any proposed rerun.

## Step 1. Codex flagging

1. **Identify the inputs.** From the requested observation directory, locate the active `calibration_tables/ff_sb.t`, `bpass_complx.t` and `bpass_scalar.t` (all under `calibration_tables/`). Open them read-only. Read antenna, field, stored scan number, SPW, channel frequencies and existing flags from each table. Verify the receptor and parameter mapping for this reduction. Record the input paths and CASA version.
2. **Inspect delay solutions.** Follow the [single-band delay inspection guide](ff_sb_inspection.md). For each antenna, compare R and L delays in ns across SPWs, with one source per panel and all its scans overlaid. Identify each candidate by antenna, scan, SPW, hand and parameter. Confirm it in the single-scan view. Show the same delay panels before and after excluding candidates. Plot phase wherever that hand and SPW have finite, unflagged phase and delay on the same solution row. Label the affected hand, parameter and SPWs for omitted points. Keep a labeled empty panel when none qualify. An analytical delay outlier alone does not suppress its phase.
3. **Inspect passband solutions.** Follow the [passband inspection guide](all_antennas_bandpass_inspection.md). For each antenna and hand, plot complex-table phase in degrees and scalar-table gain amplitude at the native channel frequencies in GHz. Compare neighboring valid channels within each SPW. Use circular phase differences so a wrap at ±180° does not look like a jump. Highlight outliers, jumps and affected channel ranges on paired before/after pages. Record near-zero phase in the notes and highlight any actual excursions. Check whether repeated spectra are copies of the same solution before citing recurrence as evidence.
4. **Produce proposals.** Save separate delay and passband PDFs and matching ASCII lists in the observation’s `inspection/` directory. Suggested stems are `delay_Codexflag` and `passband_Codexflag`, with suffixes `_summary.pdf` and `_commands.py`. Give the measured evidence and scope for each proposed flag in the PDF. Write one standalone, literal CASA `flagdata(...)` call per line in the ASCII file. Combine selections only when the result covers exactly the intended table entries.
5. **Verify the selection.** Test the proposed calls on disposable table copies with only the target paths redirected. Compare the complete resulting FLAG array with the original flags OR the proposed mask. For Fringe Jones, verify which FPARAM slots CASA can address. The documented CASA 6.6.6 setup supports exact widget flags for R phase and R delay; report L candidates separately when exact selection is unavailable. For passbands, check hand, channel and scan scope. CASA phase clip thresholds use radians; the plots use degrees.

## Step 2. Human flagging

**First pass — review the proposals.** Start in the observation directory with the widget environment active. The commands below use the checkout’s shared app. If the widget cannot find CASA, add `--casa-python /path/to/CASA/python3`. Run one session at a time.

```bash
app="$(git rev-parse --show-toplevel)/tools/ancillary_py_codes/visflag_widget/app.py"
delay=calibration_tables/ff_sb.t
phase=calibration_tables/bpass_complx.t
amp=calibration_tables/bpass_scalar.t

python3 "$app" "$delay" --commands inspection/delay_Codexflag_commands.py --output inspection/delay_Codexflag_commands_approved.py
python3 "$app" "$phase" "$amp" --commands inspection/passband_Codexflag_commands.py --output inspection/passband_Codexflag_commands_approved.py
```

Check the highlighted points against the reason and editable command. Use **Show after flagging** to see its effect, then approve, edit or skip. Approval exports a call; the observation tables remain read-only during review.

**Second pass — examine all solutions.** Import the first-pass approvals with `--examine`. Review each antenna, including those with no proposal. If the first pass produced an empty list, launch with the table arguments and a fresh output name alone.

```bash
python3 "$app" "$delay" --commands inspection/delay_Codexflag_commands_approved.py --examine --output inspection/delay_humanflag_commands.py
python3 "$app" "$phase" "$amp" --commands inspection/passband_Codexflag_commands_approved.py --examine --output inspection/passband_humanflag_commands.py
```

- **Delay.** Start with the all-scan delay overview, then use **Delay and phase** to check the scan and hand behind an excursion. Pick outliers or use the form when points overlap.
- **Passband.** **Pick channel** selects a channel; **Pick SPW** selects a whole window. **Clip above** and **Clip below** act across all SPWs and solution rows of the chosen table, antenna and hand, even when zoomed. Restrict the editable command if the evidence supports only particular channels or scans, then check the highlight again.
- **Finish.** Confirm that the final ASCII lists include the retained first-pass selections and any additions. Keep the review journals with them. Before applying a revised list, repeat the copy check for its final selections. Record the tables actually flagged, the verification result, and any unresolved candidates in the rPICARD report. If recalibration is needed, inspect the regenerated solutions before using them downstream. See the [overall workflow](../../../../Overall_workflow.md) and [widget instructions](../../../ancillary_py_codes/visflag_widget/README.md).
