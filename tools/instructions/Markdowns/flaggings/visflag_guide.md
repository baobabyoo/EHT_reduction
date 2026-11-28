<!-- This guide introduces a workflow for performing visibility flagging -->

Flag commands should be specified only with the following parameters: antenna (or baseline, only if the issue is not antenna-based), SPW:channel, timerange (or scan, if the entire scan is bad). Do not use clipping in the flagging. Flags should always be implemented for all four correlator products, RR, RL, LR, and LL.
Do not edit any .uvf files.

Set `vis` in each proposed call to the verified path of the target measurement set. For an M87 UVFITS export, confirm the location and channel grid of the matching `M87_calibrated.ms` before using its path.



# Workflow (recommend to follow the flow below, step by step)
## Step 1. Codex flagging

If you are Codex, inspect the data under the directory that you're told to analyze, for example, `data/rpicard/e26m17/b3/` from the checkout root. Identify any integrations that are outliers (in terms of either phase, amplitude, or both) in the time domain, and identify where (e.g., at which integration) we are missing the data for any of the four polarizations: RR, LL, RL, LR. Also look into other problems that are troublesome in radio/submillimeter interferometric observations.

If you find multiple high-amplitude spikes associated with one antenna, try to incorporate those issues in one flag command instead of fragmenting them into multiple flag commands; if there is a cluster of high-scatter data (e.g., over a specific time period), they should also be flagged with one command (e.g., flagging a certain time period) instead of multiple flag commands. Likewise, if there are multiple SPWs in an antenna (or baseline) that appear as outliers in the amplitude or frequency domain, try to incorporate those issues in one flag command instead of fragmenting them into multiple flag commands.

Produce a version of the summary PDF in the format that is instructed in the file, visibility_inspection_guide.md (if you need an example, see [the archived M87 report](../../examples/M87_full_visibility_inspection.pdf)).  The filename of this summary PDF should end with '_Codexflag_summary.pdf'. The visibility_inspection_guide.md should have instructed you to present plots to demonstrate flagged data, followed by the presentation of all data. When presenting flagged data in the plots, show those that can be attributed to antenna-based time-domain effects first, followed by those that can be attributed to antenna-based frequency-domain effects, followed by the other flaggings.

Collect all flag commands into an ASCII file ending with _Codexflag_commands.py. The PDF file and the .py file should be inside the directory of the data you are analyzing. 



## Step 2. Human flagging

A human analyzer runs both passes. Start in the observation directory containing the visibility file and the Step 1 ASCII proposals, with the [widget environment](../../../ancillary_py_codes/visflag_widget/README.md) active. In the same shell, set the target basename to match the proposal filename. This example uses M87 and assumes the observation is inside the project checkout.

```bash
app="$(git rev-parse --show-toplevel)/tools/ancillary_py_codes/visflag_widget/app.py"
target=M87
vis="${target}_calibrated.uvf"
```

### Pass 1. Review the proposed commands

```bash
python3 "$app" "$vis" \
  --commands "${target}_Codexflag_commands.py" \
  --output "${target}_Codexflag_commands_approved.py"
```

The widget opens the matching scan and baseline for each proposal. Check the scan ID source, the highlighted samples and the reason. Use **Show after flagging** to preview the effect. Edit the command if needed, then click **Approve & append** or **Skip**. Close this session before starting the second pass.

### Pass 2. Examine all scans and baselines

```bash
python3 "$app" "$vis" --examine \
  --commands "${target}_Codexflag_commands_approved.py" \
  --output "${target}_humanlag_commands.py"
```

Inspect frequency-binned data versus time first, then time-binned data versus frequency. Check the native samples for features hidden by averaging. Matching first-pass commands appear as suggestions. Approve the selections you want in the final export, including retained proposals and any new selections. If the first pass yielded an empty list, omit the `--commands` argument and its filename to browse all data from scratch.

Keep each ASCII output with its companion `.review.json`. To resume, repeat the command for that pass with the same input and output. Approval saves CASA commands for later application to the intended measurement set.
