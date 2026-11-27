# Finding and running the inspection code

Start at the EHT_reduction project root. Observations live under `data/rpicard/`. Use a separate working directory inside each observation so coverage files, checkpoints and reports belong to the observation that produced them.

| Folder | Contents |
|---|---|
| `visibility/` | The 13 Python scripts from the reference observation’s inspection directory, plus its single-baseline JSON example. Use this folder for coverage indexing, sample extraction, diagnostic spectra, plotting and report verification. |
| [visflag_widget/](visflag_widget/README.md) | Interactive delay, bandpass and visibility flag review. Launch the shared app from the observation directory, for example `python3 "$project/tools/ancillary_py_codes/visflag_widget/app.py" M87_calibrated.uvf`. |
| `workflow_test/` | The historical analysis, approval, reporting and verification drivers from the M87 workflow test. They assume that test’s files and working directory. |
| `../instructions/Markdowns/flaggings/` | The visibility inspection guide and the separate delay and bandpass inspection guides. |

The old script names directly under ancillary_py_codes are relative links so existing paths still work. Edit the files in the named subfolders.

## Start another visibility inspection

From the project root, substitute the observation, UVFITS filename and matching rPICARD diagnostics directory below. Use a Python environment with NumPy, Astropy and Matplotlib. The reference indexer expects a single-source random-groups UVFITS export with AIPS antenna metadata. Check the source, correlation order, channel dimensions, frequency setup and observing dates against the new file before using the reference collectors.

```bash
project="$PWD"
tools="$project/tools/ancillary_py_codes/visibility"
obs="$project/data/rpicard/YOUR_OBSERVATION"
uv="$obs/TARGET_calibrated.uvf"
diag="$obs/diagnostics_YOUR_RUN"
mkdir -p "$obs/inspection"
cd "$obs/inspection" || exit 1
python3 "$tools/index_visibility.py" "$uv" "$diag/list.obs" coverage.csv
python3 "$tools/collect_visibility_samples.py" "$uv" coverage.csv checkpoints/uv
python3 "$tools/collect_channel_spectra.py" "$uv" "$diag/PLOTS_VISIBILITIES" "$diag/list.obs" checkpoints/channels
python3 "$tools/assess_visibilities.py" checkpoints coverage.csv
```

The indexer uses stored scan IDs when available and falls back to matching source and UTC intervals in list.obs. The channel collector reads vector spectral diagnostics and checks their SPW metadata against the export. If the diagnostics are unavailable, record the missing spectra and restrict frequency claims to the resolution actually present in the visibility file. Start fresh checkpoints when changing inputs.

## Continue to review and reporting

Use [the visibility flagging workflow](../instructions/Markdowns/flaggings/visflag_guide.md) for proposal filenames, output location and the two human review passes. Follow [the visibility inspection guide](../instructions/Markdowns/flaggings/visibility_inspection_guide.md) for selection, averaging, evidence pages, residual plots and QA. Use the scripts from the shared tools folder and keep the observation’s inspection directory as the working directory. Before running the flag planners, polarization checks, report assembler or export checks for a new target, review their M87-specific paths, selections, measurements and narrative. Derive those values from the new observation. The sample JSON illustrates the preview format and contains measurements for one M87 baseline.

For calibration tables, start with [delay inspection](../instructions/Markdowns/flaggings/ff_sb_inspection.md) or [bandpass inspection](../instructions/Markdowns/flaggings/all_antennas_bandpass_inspection.md).
