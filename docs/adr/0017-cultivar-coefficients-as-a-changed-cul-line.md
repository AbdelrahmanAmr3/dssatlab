# 0017: Cultivar coefficients written as a changed .CUL line with a new VAR#

Status: accepted (2026-10-01). Builds on 0005 and 0016; completes 0016's deferred coefficient sweep.

## Context

Sensitivity work varies a cultivar coefficient (P1, G2 ...) and compares the results. Until now
the experiment data cultivar section only chose a cultivar code; the crop's .CUL was copied into
the simulation folder unchanged. DSSAT reads the .CUL from the FileX folder (verified on 4.8.5:
a line inserted there under a new VAR# changed HWAM and anthesis as expected).

## Decision

- The cultivar section takes an optional `coefficients` dict: .CUL header names after `ECO#` to
  numbers.
- dssatlab copies the source cultivar's line, replaces only those fixed-width fields
  (right-aligned, no rounding, no exponent), gives it the first free VAR# `DLnnnn` in that file,
  inserts it right after the source line in the simulation folder's .CUL copy, and writes the
  CULTIVARS level with the new code. The source .CUL is never changed.
- Sweeps need nothing new: a `cultivar` factor whose values carry coefficients.
- Rotation components reject `coefficients`; .ECO and .SPE stay unchanged.

## Alternatives considered

- Editing the source line in place. Rejected: the same code would mean different cultivars in
  different folders, and a FileX elsewhere still pointing at it would silently change.
- A separate `cultivar_coefficients` section or a public .CUL writer. Rejected: two places that
  must agree on crop and code, or files the user manages by hand.
- A dssatlab table of coefficient names per model. Rejected: duplicates DSSAT's own headers.
