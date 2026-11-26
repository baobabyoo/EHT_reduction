---
name: eht-reduction
description: Inspect EHT rPICARD pipeline logs, CASA fringe-delay and bandpass tables, and calibrated VLBI visibilities. Use the EHT reduction project guides to prepare diagnostic reports, review CASA flag candidates and resume an observation from its inspection handoff.
---

## Start or resume

Locate the project by its README.md and tools/instructions/Markdowns directory. Resolve paths from that root even when the skill was installed elsewhere. Select the requested observation by inspecting data/ recursively for the named UVFITS, calibration_tables or picard.out. Examples, working observations and workflow tests may share filenames. Confirm the target, band and reduction run before using its files. If the project is unavailable, request its checkout path. Read the observation's inspection/HANDOFF.md when present.

Inventory the actual input paths and record which file supplies each quantity, its units, timestamps, scan IDs and flags. Match diagnostics to the science run. Take scan IDs and bounds directly from stored metadata where available; distinguish measured first/last integrations from scheduled boundaries. Inspect original inputs read-only. Resolve obsolete paths in historical scripts before any application of flags.

## Choose the procedure

All guide names below are relative to tools/instructions/Markdowns/. Use the shared code index at tools/ancillary_py_codes/README.md. Run tools by their actual paths with outputs and checkpoints in the observation's inspection directory.

- **Pipeline inspection.** Start with picard.out and its matching diagnostics directory. Record the stage, affected data, evidence and consequence of unusual events. Use the project's CASA_rPICARD data inspection slides in tools/instructions/PDFs/ for its inspection sequence.
- **Delay.** Follow ff_sb_inspection.md for ff_sb.t. Respect per-solution flags, report delay in ns and phase in degrees, and use its scan eligibility rule when showing phases. Record antenna, scan, SPW and receptor for a candidate.
- **Passband.** Follow all_antennas_bandpass_inspection.md. Use bpass_complx.t for phase and bpass_scalar.t for amplitude. Inspect each receptor and antenna across SPWs. Compare candidate jumps or excursions with neighbors, annotate evidence, and distinguish wrapped phase from a physical discontinuity.
- **Visibility.** Use visflag_guide.md for the review stages and visibility_inspection_guide.md for provenance, figures and page design. Inspect UVFITS axes and frequency metadata; verify the dimensions of any matching MS or channel-resolved diagnostic. Plot individual channels at their measured frequencies. Report missing spectra and the actual resolution where only IF averages exist. Compare independent baselines before proposing an antenna-wide flag. Identify incomplete polarization by affected products, time and SPW. Use the guide's RR/red, RL/green, LR/blue, LL/dark-slate convention. Lead with measured findings and controls, then a scan inventory. Present annotated command evidence followed by all observations with proposed selections masked before averaging.
- **Interactive review.** Read tools/ancillary_py_codes/visflag_widget/README.md. Launch app.py from the observation directory with the actual input and an explicit review output. PDF or ASCII input opens a command queue; --examine also permits browsing all data. Keep proposed selections, reviewer approvals and confirmed CASA application distinct. Export individual formal CASA calls targeting the verified ordinary MS or loaded calibration table. Confirm selection semantics and channel mapping on that target before application. Preserve the UVFITS.

## Close or pause

Record input and output paths relative to the observation, verified dimensions, missing coverage, substantive findings and their evidence, and the next actionable step in inspection/HANDOFF.md. Record whether commands were proposed, approved, applied or independently verified, including the target of any test. Approval in a rehearsal applies only to that rehearsal. Before reusing a checkpoint verify its inputs and selection settings. Use the M87 example for style; derive measurements, flag commands and provenance anew.
