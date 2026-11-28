# EHT reduction workflow

## 1. PolConvert

1. **Processing.** Run PolConvert with the default parameters to convert the polarization basis of the correlated data.
2. **Preliminary assessment.** Use Codex to inspect the PolConvert products and prepare an initial report.
3. **Human validation.** Review the conversion results and the actions proposed by Codex. If the results need correction, troubleshoot, rerun PolConvert, and review the updated products. Once accepted, use Codex to document resolved issues and remaining limitations in `<track-band>_polconvert_report.pdf` (for example, `e26m17-b3_polconvert_report.pdf`). Proceed to rPICARD.

## 2. rPICARD

1. **Calibration.** Run rPICARD with the default parameters to calibrate the cross-correlation data.
2. **Preliminary assessment.** Use Codex to prepare an initial report covering the delay table, complex and scalar passband tables, complex visibilities of the target source, gross fringe-fitting solutions, and short-timescale fringe-fitting solutions. For flag proposals, use [Codex delay and passband inspection](tools/instructions/Markdowns/flaggings/delaypassbandflag_guide.md#step-1-codex-flagging) for calibration-table entries and [Codex visibility inspection](tools/instructions/Markdowns/flaggings/visflag_guide.md#step-1-codex-flagging) for the target visibilities.
3. **Human validation.** Review the calibration results and the proposed actions. For delay and passband flags, follow the [two-pass calibration-table review](tools/instructions/Markdowns/flaggings/delaypassbandflag_guide.md#step-2-human-flagging). Keep the delay and passband lists separate and verify the final selections on table copies before applying them to the intended calibration tables.
   - **If calibration needs correction**, use the [rerun advice guide](tools/instructions/Markdowns/AI_advices/rpicard_rerun_advice.md) to document the evidence, exact input edit and verification plan. If the human approves the change, troubleshoot and rerun PolConvert or rPICARD as appropriate. Inspect the delay solutions first, followed by the passband solutions. If either shows an obvious problem, adjust the parameters or flags and rerun rPICARD before inspecting the complex visibilities. A partial rerun through production of the delay and passband tables lets the analyzer check the updated solutions.
   - **Before imaging**, follow the [two-pass visibility flag review](tools/instructions/Markdowns/flaggings/visflag_guide.md#step-2-human-flagging). First review the proposed ASCII commands in the widget. Then open the approved list with `--examine` to inspect all available data and export the final selections. Widget approval writes commands to a file. If flags are needed, verify their scan and SPW/channel selections against the intended measurement set (MS), apply the agreed commands, and check the affected data before and after flagging. If no additional flags are needed, record that decision. Rerun rPICARD if the flags can improve the quality of data calibration.
   - **On acceptance**, use Codex to summarize resolved issues and remaining limitations in `<track-band>_rpicard_report.pdf` (for example, `e26m17-b3_rpicard_report.pdf`). Identify the final flag list, whether its selections were applied and verified, and the exact dataset passed to imaging.

## 3. Imaging

1. **Perform imaging** using the dataset identified in the rPICARD report.
2. **Human validation.** Review the image and residuals for the intended science goal. If the evidence points to weighting or deconvolution, adjust the imaging settings and repeat imaging. If it points to a calibration or polarization-conversion problem, return to the relevant earlier stage and review its updated products. Once the human analyzer accepts the image, proceed to the final QA report.

## 4. Final report

With Codex's assistance, produce `<track-band>_QAfinal.pdf`. Summarize the main findings and remaining limitations from the PolConvert and rPICARD reports. Include the accepted image and identify its input dataset, restoring beam (major axis, minor axis, and position angle), and residual RMS with units.
