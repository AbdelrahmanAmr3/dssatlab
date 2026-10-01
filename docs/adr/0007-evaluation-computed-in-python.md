# 0007: Evaluation is computed in Python, not through DSSAT's FileA and Evaluate.OUT

Status: accepted (2026-09-30), amended by 0008

## Context

Users want to compare simulated with measured values. DSSAT's own route is to write observed
averages (FileA) and time series (FileT) beside the FileX and read `Evaluate.OUT`, which DSSAT
fills only for certain run modes.

## Decision

dssatlab reads the user's observed data (CSV or DataFrame) and compares it with the parsed
Summary and Plant growth itself. Nothing is written for DSSAT and `Evaluate.OUT` is not read.
Observed data uses DSSAT's own column names and units, so the comparison needs no conversion.

## Alternatives considered

- Write FileA/FileT and read `Evaluate.OUT`. Rejected: a second fixed-width format to write and
  prove on real DSSAT, and the output depends on the run mode.
- Friendly variable aliases and unit converters. Rejected: they lead to unit conversion, which is out of scope.

## Consequences

- No new DSSAT file writer; the comparison is testable without DSSAT.
- A pair that cannot be compared (no simulated row, `-99`) is a check problem, never dropped.
- A user who needs DSSAT's own `Evaluate.OUT` statistics must run DSSAT by hand.
