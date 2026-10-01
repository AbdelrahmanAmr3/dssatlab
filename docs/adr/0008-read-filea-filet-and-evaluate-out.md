# 0008: Read DSSAT's FileA/FileT and Evaluate.OUT, still write nothing for DSSAT

Status: accepted (2026-09-30). Amends 0007.

## Context

0007 kept dssatlab away from FileA/FileT and `Evaluate.OUT`. Users who already have DSSAT
experiments (every shipped experiment, and anything made in GBuild) hold their measurements in
FileA/FileT and expect DSSAT's own evaluation table, as the DSSAT Shell shows it.

Measured on DSSAT 4.8.5 while building v0.9: DSSAT fills `Evaluate.OUT`'s measured columns only in
some runs. CERES-Maize run in mode A (`run()`, all treatments) with the FileA beside the FileX fills
them. Mode C (one treatment, what a Simulation uses) never does: `CSM.for` sets the FileA path
`PATHEX` to blank only in mode A and leaves it unset in mode C. CROPSIM wheat (CSCER048) leaves them
-99 even in mode A, because it builds its own FileA path.

## Decision

- `read_dssat_observed(path)` reads a FileA or FileT into observed data rows, so `evaluate()`,
  `plot_observed()` and `to_dataframe()` take them unchanged. Only the columns the comparison
  supports are kept; `-99` cells and rows with no measurement are left out. Short dates follow
  DSSAT's own rules, anchored on the treatment's simulation start in the FileX beside the file.
- `read_dssat_evaluation(run_dir)` and `RunResult.dssat_evaluation()` read `Evaluate.OUT` as rows,
  with `-99` as None, whatever DSSAT filled.
- The simulation folder does not copy FileA/FileT: in mode C it would change nothing. Switching a
  Simulation to batch mode (B), where DSSAT takes the path from the batch file, would change every
  Simulation run, so it waits for seasonal analysis (v0.12), which brings a batch file anyway.
- The Evaluation is still computed in Python (0007). Nothing is written for DSSAT.

## Alternatives considered

- Write FileA/FileT from the observed data CSV. Rejected: a second fixed-width writer to prove on
  real DSSAT, for users who can already use the CSV.
- Keep every FileA/FileT column. Rejected: shipped files always hold columns `evaluate()` cannot
  compare (GN%M, VN%D, SW1D), so the direct route would always fail.

## Consequences

- dssatlab's Evaluation and DSSAT's evaluation can be compared side by side where DSSAT fills it
  (maize `run()` with the FileA beside the FileX). Everywhere else,
  `evaluate(results, read_dssat_observed(path))` is the comparison that works.
- A FileA/FileT with bare day-of-year or 2-digit-year dates needs its FileX beside it.
