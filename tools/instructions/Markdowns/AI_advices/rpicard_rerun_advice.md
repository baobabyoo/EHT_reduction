# Advising a human on an rPICARD rerun

Use this procedure during the calibration-correction branch of the [overall workflow](../flaggings/Overall_workflow.md). A request for advice authorizes inspection and a proposed change. Editing inputs, applying flags and executing tasks are separate decisions for the human analyzer.

## 1. Establish the evidence

Identify the reduction run, source product and diagnostic, and give the affected antenna or baseline, hand, scan/UTC and SPW/channel as applicable. Quote a measurement with its units or a valid/total count and compare it with neighboring samples, other scans or an independent baseline. Explain the consequence for calibration or the science product. Check existing flags, phase wrapping, reference changes and export resolution when they could explain the finding. For flag candidates, use the [calibration-table](../flaggings/delaypassbandflag_guide.md) or [visibility](../flaggings/visflag_guide.md) procedure as appropriate.

Name the earliest task that could explain the observation and distinguish the measurement from the proposed cause. If the evidence supports an isolated flag, use that scope. If several causes remain plausible, specify the diagnostic that would distinguish them and defer the parameter change.

## 2. Reconstruct the run

Read the observation’s picard.out, launch arguments, pipeline version, active input/*.inp, and relevant table metadata. Compare observation.inp with input.orig/observation.inp when available. The supplied process_eht driver snapshots input on first use; its all_sci.py helper later changes science and calibrator assignments. An existing input.orig is not automatically restored. Check for template-copy options, cached fringe parameters, upstream tables and any previous flags affecting the proposed task. Record the state needed for the calibrator or science pass in question.

## 3. Propose the smallest input edit

Use the actual observation’s working input directory. Choose observation.inp for source roles and MS identity, array.inp for reference preferences and search ranges, array_finetune.inp for solver tuning, flagging.inp for flagging controls, or constants.inp for export averaging and cache controls. Verify the key and its documented semantics in the installed version.

Give the observation-relative path, the exact current assignment, and its complete replacement as a minimal diff. Name the scope and any unaffected data that the edit would also touch. If an input change is unnecessary, identify the existing task or selection that addresses the finding.

**Conditional example.** Suppose the calibrated MS contains native spectral channels, the exported UVFITS has one frequency per SPW, and the active constants.inp documents and uses full-SPW averaging. To retain channels in the export, propose this change only after confirming those observations:

```diff
# input/constants.inp
-avg_final_channel = 999999
+avg_final_channel = False
```

Identify the export task that uses the setting and the calibrated MS it needs. Compare the regenerated channel counts and frequencies against that MS. This test addresses export resolution and requires no new fringe solution.

## 4. Specify rerun scope and exceptions

Give the working directory, earliest affected task, prerequisites, downstream tasks/products to refresh, and the exact human-run command after checking the installed task map and quickmode syntax. Identify what the command overwrites, resets, or reuses. Retain the original log, settings and comparison products before a rerun. If the installed version or required state is unknown, list what must be confirmed before giving an executable command.

Prefer working input edits or an existing supported invocation. Suggest a change to casaeht/bin/process_eht only after explaining why neither can implement the required task sequence. Quote the actual old and new command lines in every applicable execution branch and explain the calibration consequence. For example, the training workshop discusses skipping ANTAB-dependent steps when ANTAB is unavailable. Verify actual ANTAB availability and the installed task numbering; omitting those steps affects the absolute amplitude scale. A training example alone does not justify changing a driver.

## 5. Define acceptance before execution

Compare the same scans, hands, stations and frequency ranges before and after, with a control where available. Specify an observable benefit and a possible cost. For example, assess both recovered fringe detections and delay scatter when considering a lower SNR threshold. State what would support keeping the result, reverting the change or investigating further. Record the human decision, any execution and the verified outcome separately in the observation handoff.

**Recommendation template:** Finding and comparison → source of evidence → proposed cause and uncertainty → exact file edit → task scope, prerequisites and command → before/after test and rollback criterion → human decision.
