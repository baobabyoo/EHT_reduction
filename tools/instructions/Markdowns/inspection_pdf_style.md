# Writing inspection PDFs for a human analyzer

Use this guide for the opening findings, evidence captions, verification notes, rerun advice and command appendices in delay, passband and visibility reports. The product inspection guide controls the science, figure layout and polarization colors. The [rerun advice guide](AI_advices/rpicard_rerun_advice.md) controls eligibility. The rules here govern how the analyzer reads the resulting report. Apply them to the rendered PDF as well as to the text drafted in chat.

## Start with the whole inspection

1. Identify the observation, date, scope and actual input files. Give each table or visibility product a short description. Put the primary inputs on the first page.
2. Lead with “What to inspect first” or an equally direct heading. Give each major product or issue class a short finding. For a passband report, cover both phase and scalar amplitude before pursuing one antenna. For a delay or visibility report, use the relevant dimensions of that inspection. Report unremarkable results briefly when they supply a useful comparison.
3. For each finding, identify where it occurs, one measurement with its unit or meaningful count, and a comparison. Say whether it recurs across hands, scans, SPWs or antennas. Distinguish rows, distinct channel positions, affected scans and independent measurements. Name the genuinely useful control. Explain the meaning of a unity correction or a missing solution when reporting one.
4. Only after this overview, introduce an eligible rerun issue. The **first sentences of the rerun discussion** identify the measured symptom and its demonstrated consequence. Then state the proposed experiment and the breadth of the change. General inspection findings may precede the trigger. The trigger precedes the recommendation, interpretation and launch instructions.
5. A first page can carry a short decision and links or page numbers. If the evidence needs more space, continue on the next page. Keep Verification and Scope and the full passband trial guide ahead of the first plot. Retain the figure order and science-specific sections required by the product guide.

### Worked example of the order

For e26m17-1-b3, first describe the concentration of phase candidates on KT and MG, the isolated excursions on AX, and the zero corrections on GL, NN and PV. Next describe the amplitude selections, the channel positions common to all station/hand combinations and the repeated spectra that affect the counts. Cite the applicable antenna plots.

Open the rerun discussion with what happened to signal averaged across the suspect channels when the stored phase correction was mathematically reversed. Give a calibrator measurement on AA–MG or AA–KT and the matched controls, then say whether the second calibrator showed the same behavior. Explain that a full reduction can change later fringe solutions and flags. Only then recommend a controlled trial and emphasize **every antenna in the array**. Derive numbers, antenna names and scope anew for every observation.

## Write for the person making the decision

- Start paragraphs with their subject and action. Prefer “On KT, neighboring channels differ in phase” to “The noisy-solution criterion is satisfied.” Prefer “Remove the task 15 invocation from the trial copy” to “Modify the task selection as appropriate.”
- Introduce a metric where it first changes the conclusion. For example, coherence here measures how much signal survives averaging channels with different phases. Put the exact formula and weighting in the methods. Give source, baseline, hand, frequency range and units with the evidence or refer to the labeled figure.
- Mark the boundary between observation and inference in the verb. Use “the table stores,” “the calibrated data show,” “the calculation predicts,” and “the proposed trial would test.” Reserve “the trial improved” for a measured new reduction. When source documentation omits a host command or setting, tell the reader precisely what to find and where to look.
- Use second-person imperatives in the run guide and factual statements in the findings. Use one action or decision per heading. Follow each important check with the expected result and what a contrary result would mean.
- Put the preferred, observation-specific route first. Introduce an alternative with a real condition, such as **If the working launcher uses grouped task ranges**. Keep mutually exclusive launch commands in separate blocks. Explain which one the analyzer should use.
- Use selective bold within paragraphs for a decisive measurement, the file to edit, line numbers, the affected scope or an acceptance condition. One or two short phrases usually suffice. Put literal filenames, options, parameter values and shell variables in inline monospace on a pale neutral background.

## Translate the preview into a PDF

Use the preview’s hierarchy directly. Create selectable text and vector or high-resolution scientific figures. White pages, dark text and whitespace carry the structure. Use background panels for literal commands and edits. Omit simulated browser buttons, copy icons and controls a PDF reader cannot use.

| Element | Rendering target |
| --- | --- |
| Page title | About 21–26 pt, bold, near black. Use a short title that fits at reading size. |
| Step or finding heading | About 15–18 pt, bold. Use numbered action headings in the actual order of execution. Keep headings with their first paragraph or block. |
| Body | About 12–14 pt with 16–20 pt line spacing on a 10-inch-wide page. Left align. Use short paragraphs, generous margins and space between sections. |
| Inline code | Real monospace, near body size, with a light gray background. Keep an option or short filename together when practical. |
| Command panel | Light neutral fill such as #F4F4F4, subtle edge such as #E4E4E4, rounded corners, 10–14 pt padding. Label the block **Bash**, **Diff** or **CASA** above the literal text. |
| Code | Usually 11–12 pt monospace with approximately 1.3× line height. A dense command appendix may use 10–11 pt. Introduce a valid continuation or a new page before reducing text further. |
| Navigation | Quiet footer with observation and page number. Give page references beside findings. Add bookmarks for guides, evidence and commands in a long document. Use blue for genuine links with meaningful labels. |

### Color has a specific job

- Use dark neutral prose and headings, for example #212528. Reserve muted gray (#525963) for secondary information and comments. A reported problem must remain clear in plain text.
- For Bash, color command names, options and variables violet (#5C36A3), quoted strings dark green (#21663A), control keywords or operators berry (#A23061), and numeric literals burnt orange (#9F4818). Keep punctuation recognizable. Highlight the literal source without adding spaces, escaping dollars or changing quotation marks.
- In a **Diff** panel, render the full removed line in dark red (#A12B29) with its literal leading minus. Render the full added line in dark green (#21663A) with its leading plus. Context stays dark neutral. Name the file, branch and verified line numbers in the adjacent prose. Put commands intended for execution in their own Bash or CASA panels.
- Retain the established scientific color and marker meanings in plots and legends. Red and green in an edit block describe removal and addition only. Never repurpose a polarization color as the sole indication of a flag. Pair plot color with a marker, outline, label or span as appropriate. Check readability in grayscale.

## Build each operating step

1. State the host, shell and working directory before the command. Define variables before first use. Say which commands share one shell session. Tie archived paths to the observed run and identify paths the analyzer must confirm.
2. State the file to edit, whether it is a trial copy, and how to locate the exact command if line numbers vary. Show before and after with indentation, shell redirects, lower endpoints, options and comments preserved where relevant. Treat an execution log as evidence of what ran.
3. Place the short instruction immediately above the corresponding block. Group related commands with whitespace or a useful comment. Preserve ASCII quotes, minus signs, backslashes, dollar signs and newlines. Use literal selectable text throughout. For CASA, preserve one complete approved or proposed call per item and identify the table, antenna or baseline, hand and relevant selection.
4. Keep the block, its condition and expected result together. If space runs out, break between complete actions and repeat the relevant directory or condition on the continuation page. Avoid clipping a line or allowing a visual wrap that changes a shell command when selected and pasted.
5. Verify both execution and scientific outcome. Identify a log or completed-task record, what a stale product would look like, and the same-data comparison required to keep the trial. Compare coverage independently so a higher median cannot hide lost data.

## Release check for the rendered artifact

- Read page one cold. Can an analyzer identify the observation, both input products where applicable, the main findings across the dataset, the comparison and where to inspect them? Does the specific rerun issue come after the survey? Is the measured trigger before the recommendation?
- Render the pages as images. Inspect page one, each guide page, the densest command sheet and representative figure pages. At ordinary reading size, check bold emphasis, panel labels, syntax colors, line spacing, edges, legends and page breaks. A text-extraction check alone cannot show a clipped line or an unreadable color.
- Extract the final PDF with pypdf using the default plain-text mode (call `page.extract_text()` with no arguments). Require each complete extracted Bash block to match its source exactly, including indentation, spaces, line breaks, continuations and redirects. Compare the strings without trimming or normalizing whitespace. Syntax highlighting can look correct while the extractor puts each colored token or letter on a separate line. Keep each code line in one PDF text object and change fill color in place, or use a single-color line if necessary. Verify the re-extracted text after rendering. Pass each matching extracted block directly to `bash -n` on standard input and require a zero exit status. This checks syntax without executing the commands.
- Use the review widget to import every proposed CASA `flagdata` call from the final PDF with all intended targets loaded. Compare the imported queue with the corresponding ASCII proposal file. Require the same call count and order, with an exact match for every argument and selector in each corresponding call. Confirm that the widget skipped or excluded zero calls. Perform this check without executing the calls or applying flags.
- Verify every page reference and bookmark against final pagination. Check that the evidence, captions and commands still agree on antenna, scan, SPW/channel indices, hand and units. When a change is editorial, confirm the underlying figure pages and numerical selections are preserved.
- Read the finished guide as if working at the Linux terminal. The analyzer should know what to type, which route applies, what requires host confirmation, what success looks like and which actions are still proposals.
