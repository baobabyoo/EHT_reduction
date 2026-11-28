# Advising a human on an rPICARD rerun

Use the [inspection PDF writing and layout guide](../inspection_pdf_style.md) for the opening survey, reader-facing language, typography, code blocks and rendered-page checks.

Use this procedure during the calibration-correction branch of the [overall workflow](../flaggings/Overall_workflow.md). A request for advice authorizes inspection and a proposed change. Editing inputs, applying flags and executing tasks are separate decisions for the human analyzer.


## When an inspection finding qualifies

### 1. Qualified situations in the inspection of delay and passband solution
- When the phase solutions of an antenna in the complex passband calibration table (over the frequency domain) are either close to exactly zero or are largely scattered from zero (e.g., by comparably larger than 10 degrees), it might be because the signal-to-noise of the observations only marginally supports the derivation of the complex passband calibration solution. In this case, a human analyzer may consider re-running rPICARD by skipping the derivation of the passband solution for that specific antenna. If the complex passband calibration solutions for all antennae are like that, then a human analyzer may skip the step of deriving the complex passband calibration solution when re-running rPICARD.

### 2. Qualified situations in the inspection and flagging of complex visibility

### 3. Actions

When the human requests rerun advice, or in the qualified situations strictly restricted to what has been mentioned above, include a proposal in the PDF summary of data inspection only if the following are established together:

- Measured evidence and a suitable comparison demonstrate a consequence for calibration or the delivered science product.
- The actual run settings, logs or table metadata support a specific cause and a change at an identifiable task. If a narrower flag addresses the finding, document what additional benefit requires reprocessing before recommending a rerun.
- The proposed change has a defined scope and a before/after test that can distinguish improvement from lost coverage or another cost.

When these conditions are unmet, report the finding in the ordinary inspection notes and identify the next discriminating check. Omit the rerun proposal section. A proposal is advice for human review; it does not authorize execution.

In an inspection report, first summarize the findings across the inspected products and array. Whenever recommending a rerun, open the rerun discussion with one or two sentences naming the eligibility condition and the observation-specific measurement and comparison that triggered it. Apply this order in the inspection PDF and in advice to the analyzer. Give the recommendation, scope, interpretation and commands after the trigger.

## 1. Establish the evidence

Identify the reduction run, source product and diagnostic, and give the affected antenna or baseline, hand, scan/UTC and SPW/channel as applicable. Quote a measurement with its units or a valid/total count and compare it with neighboring samples, other scans or an independent baseline. Explain the consequence for calibration or the science product. Check existing flags, phase wrapping, reference changes and export resolution when they could explain the finding. For flag candidates, use the [calibration-table](../flaggings/delaypassbandflag_guide.md) or [visibility](../flaggings/visflag_guide.md) procedure as appropriate.

Name the earliest task that could explain the observation and distinguish the measurement from the proposed cause. If the evidence supports an isolated flag, use that scope. If several causes remain plausible, specify the diagnostic that would distinguish them and defer the parameter change.

## 2. Reconstruct the run

Read the observation’s picard.out, launch arguments, pipeline version, active input/*.inp, and relevant table metadata. Compare observation.inp with input.orig/observation.inp when available. The supplied process_eht driver snapshots input on first use; its all_sci.py helper later changes science and calibrator assignments. An existing input.orig is not automatically restored. Check for template-copy options, cached fringe parameters, upstream tables and any previous flags affecting the proposed task. Record the state needed for the calibrator or science pass in question.

### Identify what the host actually ran

Use the calibrator-pass and science-pass `command_line_arguments.txt` records to recover task order, switches and resource settings. Check the matching `completed_calibration_steps.list` and applied-table lists in the log. A task catalogue only identifies the installed numbering. If the record contains one task per invocation, show how to omit the individual invocation. If the verified host driver groups tasks, show the exact old and new ranges in both branches. Preserve the lower endpoint, shell redirection, science handoff and later task selections used by this observation. In particular, check the independent scalar passband stage. The distributed driver and the observation may use different ranges.

Name the launcher, path, branch and line numbers only where verified. For an unavailable host wrapper, print the recorded task arguments, explain how to locate the editable line in a trial copy, and identify the invocation or swap list to recover from job history. A recorded invocation of picard inside the run does not establish how the outer driver was started.

Stage a separate trial from the reference starting inputs and flags. Verify availability of raw data, external tables, mount information and the matching environment on the host. Preserve relative paths to helper scripts when copying a driver. For a skipped solve, check both whether the table exists and whether a later application step actually used it. Compare reference and trial on common samples, then count the full coverage independently. Record which files came from the archive and which still need host confirmation.

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

### Example: array-wide trial prompted by noisy AX complex passband phases

If the eligibility conditions above are met and the human is considering an array-wide comparison, check that task 15 is `task_complex_bandpass` in the installed version. In the supplied `casaeht/bin/process_eht`, the first changed line below belongs to the polarization-swap branch and the second to the ordinary branch. Show this edit for a trial copy of the working driver:

```diff
-        picard -n $maxcores -prdfsmq b,c,7~15 >> picard.out
+        picard -n $maxcores -prdfsmq b,c,7~14 >> picard.out
     else
-        picard -n $maxcores -prlfsmq b,c,7~15 > picard.out
+        picard -n $maxcores -prlfsmq b,c,7~14 > picard.out
```

Preserve the working range’s lower endpoint. If the workshop configuration already uses `8~15`, shorten it to `8~14` in both branches. Task 14 still runs, and the scalar amplitude passband retains its own task selection.

In both the PDF opening findings and the proposal’s **Rerun scope**, state explicitly: **“The finding concerns AX. This trial skips the complex passband solve for every antenna in the array.”** If the human requires an AX-only test, identify and verify a station-specific method before proposing an edit. The task-range change above cannot isolate AX.

Use a fresh trial directory with the reference run’s starting inputs and flags. The driver’s cleanup leaves an existing `calibration_tables/bpass_complx.t` in place. Verify in the trial log that task 15 was skipped and check the downstream calibration records for reuse of an earlier complex passband table. Compare the same calibrator scans, hands and channels in both reductions. Report residual phase scatter, coherent amplitude and valid coverage on AX baselines and on baselines without AX before recommending adoption.

## 5. Define acceptance before execution

Compare the same scans, hands, stations and frequency ranges before and after, with a control where available. Specify an observable benefit and a possible cost. For example, assess both recovered fringe detections and delay scatter when considering a lower SNR threshold. State what would support keeping the result, reverting the change or investigating further. Record the human decision, any execution and the verified outcome separately in the observation handoff.

## Present the proposal in the inspection PDF

Mention each eligible proposal in the opening findings with its evidence figure and page number. Include the measured data and comparison together in an annotated figure in that same PDF. An existing diagnostic panel can serve as the evidence figure. Keep its selection, units, and averaging explicit in the caption. Label any candidate-masked view as a preview; only an actual rerun can supply a measured post-rerun result.

Follow the product guide for placement. For passbands, place Verification and Scope and the complete controlled-trial instructions before the first plot. For other products, use the location specified in their inspection guides. Use a section titled **Proposed rPICARD rerun — awaiting human review**, separate from executable CASA flag lists. Present each proposal in this order:

1. **Finding and evidence.** Cite the figure and page, measured discrepancy, comparison and impact.
2. **Interpretation.** State the supported cause, remaining uncertainty, and why reprocessing is warranted.
3. **Exact change.** Give the working file path and current and replacement assignments, or identify the existing invocation if no edit is necessary. Apply the driver exception in section 4 where relevant.
4. **Rerun scope.** Identify the earliest affected task, prerequisites and products to refresh. Include the command only when verified for the installed version.
5. **Human decision and verification.** Mark the proposal pending. Specify the before/after measurement, control and criterion for keeping or reverting the change.

In the human trial instructions, give the working directory, the file and verified line numbers or exact text to locate, the old and replacement lines as a code block, and the Linux commands in separate copyable blocks. State which host paths, launch arguments, and starting inputs require confirmation. Distinguish archived task arguments from an unverified top-level launcher. Check the evidence and proposal page references against the final pagination.
