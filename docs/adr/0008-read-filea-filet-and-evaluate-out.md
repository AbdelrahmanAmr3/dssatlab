# 0008: Read DSSAT's FileA/FileT and Evaluate.OUT, still write nothing for DSSAT

Status: accepted (2026-09-30). Amends 0007.

## Context

0007 kept dssatlab away from FileA/FileT and `Evaluate.OUT`. Users who already have DSSAT
experiments (every shipped experiment, and anything made in GBuild) hold their measurements in
FileA/FileT and expect DSSAT's own evaluation table, as the DSSAT Shell shows it. The simulation
folder did not copy FileA/FileT, so `Evaluate.OUT` there had -99 in every measured column.

## Decision

- `read_dssat_observed(path)` reads a FileA or FileT into observed data rows, so `evaluate()`,
  `plot_observed()` and `to_dataframe()` take them unchanged. Only the columns the comparison
  supports are kept; `-99` cells and rows with no measurement are left out. Short dates follow
  DSSAT's own rules, anchored on the treatment's simulation start in the FileX beside the file.
- `Simulation.run()` copies the FileA and FileT named after the FileX into the simulation folder,
  so DSSAT fills `Evaluate.OUT`. `read_dssat_evaluation(run_dir)` reads it as rows.
- The Evaluation is still computed in Python (0007). Nothing is written for DSSAT.

## Alternatives considered

- Write FileA/FileT from the observed data CSV. Rejected: a second fixed-width writer to prove on
  real DSSAT, for users who can already use the CSV.
- Keep every FileA/FileT column. Rejected: shipped files always hold columns `evaluate()` cannot
  compare (GN%M, VN%D, SW1D), so the direct route would always fail.

## Consequences

- dssatlab's Evaluation and DSSAT's evaluation can be compared side by side on the same data.
- A FileA/FileT with bare day-of-year or 2-digit-year dates needs its FileX beside it.
