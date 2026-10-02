# 0016: Sweeps run as generated scenarios over experiment data sections

Status: accepted (2026-10-01). Builds on 0005 and on v0.5's scenarios.

## Context

A DSSAT Shell user varies planting date, N rate or irrigation over a grid in XBuild (treatment
factors) and compares the results in one table. dssatlab already runs named scenarios through
`run_treatments`, with all checks before any run and labelled results, but a user has to write
every combination by hand and the table carries only the scenario name.

## Decision

- `run_sweep` takes `factors`: a dict keyed by an experiment data section name, each value a dict
  of label to a complete section value. Labels are strings or numbers.
- Every combination (cartesian product, factor order then value order) becomes one scenario: the
  base experiment data with each factor's section set on every selected treatment, replacing that
  section whole. The scenario name is the labels joined by a space.
- The scenarios go through `run_treatments` unchanged: same checks, base first, stop on the first
  run failure.
- The result is one list of Summary rows with `scenario`, `treatment`, one column per factor
  (None in base rows) and `run_dir`.

## Alternatives considered

- Named factors with fixed meanings (planting_date, n_rate). Rejected: each needs its own rule
  (which event gets the rate, what happens to the emergence date) and a base section anyway.
- Dotted paths into experiment data. Rejected: ambiguous over event lists.
- Cultivar coefficient sweeps in the same release. Deferred to v0.14.1: they need a new .CUL writer
  and their own DSSAT proof.
