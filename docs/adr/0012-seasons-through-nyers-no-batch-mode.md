# 0012: Seasonal analysis sets NYERS in the controls level; no batch file, no new run mode

Status: accepted (2026-10-01). Amends 0008.

## Context

A DSSAT Shell user runs a seasonal analysis: the same experiment over many weather years, then
compares the yearly results. DSSAT keeps the number of seasons in the simulation controls level
(NYERS). The DSSAT Shell runs seasonal experiments in batch mode N.

Measured on DSSAT 4.8.5 while planning v0.12: a two-treatment maize FileX with NYERS 9 and ten
years of weather in one weather file gives 9 Summary rows per treatment, with identical results in
mode C (one treatment, what a Simulation uses), mode A (all treatments, `run()`), and modes N and B
through a batch file. Each season starts on the same day of year in the next year (Feb 29 in leap
years), and planting and fertilizer dates move with it. One weather file holding every year and
one file per year give the same results.

0008 deferred switching a Simulation to batch mode, so DSSAT would fill `Evaluate.OUT`'s measured
columns, to this release, assuming seasonal analysis needed a batch file anyway.

## Decision

- Experiment data controls take `years`, a positive integer. It is written as NYERS into the copied
  controls level of the selected treatment, like the other controls. A FileX that already has
  NYERS above 1 runs as before.
- Run modes stay as they are: a Simulation runs mode C and `run()` mode A. dssatlab writes no batch
  file.
- Checks require weather data covering the start day of every season. Gaps after a season starts
  are still caught after the run by the `WARNING.OUT` scan.
- `summarize_seasons()` computes the statistics over seasons in Python from Summary rows.
- `Evaluate.OUT` stays as 0008 describes it: no batch mode for a Simulation.

## Alternatives considered

- Batch file and mode N, as the DSSAT Shell does. Rejected: identical results for a second command
  shape and a batch file writer.
- One FileX per year. Rejected: more runs, and it bypasses DSSAT's own season handling.
- A `years=` keyword on Simulation and run_treatments, or a FileX template key. Rejected: a second
  place to say what the controls level already holds.

## Consequences

- Every Summary-reading function already handles several rows per treatment; Summary rows tell the
  seasons apart by RUNNO and dates.
- `evaluate()` keeps rejecting several Summary rows for one treatment; observed data per season is
  out of scope.
