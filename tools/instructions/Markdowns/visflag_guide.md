<!-- This guide introduces a workflow for performing visibility flagging -->

Flag commands should be specified only with the following parameters: antenna (or baseline, only if the issue is not antenna-based), SPW:channel, timerange (or scan, if the entire scan is bad). Do not use clipping in the flagging. Flags should always be implemented for all four correlator products, RR, RL, LR, and LL.
Do not edit any .uvf files.

When producing the flag commands, the parameter, vis, should point to the visibility file we are analyzing, e.g., /Users/hyliu/Desktop/EHT2026/e26m17_rpicard/e26m17-1-b3/M87_calibrated.ms, instead of a working copy.



# Workflow (recommend to follow the flow below, step by step)
## Step 1. Codex flagging

If you are Codex, inspect the data under the directory that you're told to analyze, for example, /data/rpicard/e26m17/b3. Identify any integrations that are outliers (in terms of either phase, amplitude, or both) in the time domain, and identify where (e.g., at which integration) we are missing the data for any of the four polarizations: RR, LL, RL, LR. Also look into other problems that are troublesome in radio/submillimeter interferometric observations.

If you find multiple high-amplitude spikes associated with one antenna, try to incorporate those issues in one flag command instead of fragmenting them into multiple flag commands; if there is a cluster of high-scatter data (e.g., over a specific time period), they should also be flagged with one command (e.g., flagging a certain time period) instead of multiple flag commands. Likewise, if there are multiple SPWs in an antenna (or baseline) that appear as outliers in the amplitude or frequency domain, try to incorporate those issues in one flag command instead of fragmenting them into multiple flag commands.

Produce a version of the summary PDF in the format that is instructed in the file, visibility_inspection_guide.md (if you need an example, see M87_full_visibility_inspection.pdf).  The filename of this summary PDF should end with '_Codexflag_summary.pdf'. The visibility_inspection_guide.md should have instructed you to present plots to demonstrate flagged data, followed by the presentation of all data. When presenting flagged data in the plots, show those that can be attributed to antenna-based time-domain effects first, followed by those that can be attributed to antenna-based frequency-domain effects, followed by the other flaggings.

Collect all flag commands into an ASCII file ending with _Codexflag_commands.py. The PDF file and the .py file should be inside the directory of the data you are analyzing. 



## Step 2. Human flagging

This part should be executed with a human analyzer, not Codex. Use the visflag_widget tool to validate Codex's flagging in the following two steps. 
(1) When launching the tool, import the ASCII-format flag commands. The tool will only present the data that are relevant to your flag commands. Output your approved flag commands to another ASCII file ending with _Codexflag_commands_approved.py
(2) When launching the tool, import the ASCII file ending with _Codexflag_commands_approved.py, and use the --examine option when launching the tool. In this case, it will iterate over all available data, which allows you to include more flag commands. Output your final flag commands to another ASCII file ending with _humanlag_commands.py. In the 2nd step, my tips are (i) first look at frequency-binned data in the time domain, and then time-binned data in the frequency domain, and finally, try to identify the remaining issues. 

 
