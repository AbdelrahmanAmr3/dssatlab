# 0013: Sequences run in DSSAT's sequence mode (Q) through a batch file dssatlab writes

Status: accepted (2026-10-01). Amends 0012.

## Context

A DSSAT Shell user runs a sequence analysis: crops grown one after another on the same field for
several years, with the soil carried from one crop to the next. In a FileX a sequence is one
treatment number with several TREATMENTS rows, told apart by the R column (rotation component).

Measured on DSSAT 4.8.5 while planning v0.13 with `UFGA7804.SQX` (bean, fallow, bean, fallow,
soybean, fallow):

- Only mode Q runs a sequence. Mode C (what a Simulation uses) runs the first component alone for
  NYERS years; mode A (`run()`) runs every row as its own experiment. Both give results without
  an error.
- Mode Q needs a batch file. DSSAT reads TRTNO, RP and SQ from each line and runs the TREATMENTS
  row with N = TRTNO and R = SQ. It cycles through the lines, starting each component the day
  after the previous one ended, until start + NYERS years (NYERS of the first component) have
  passed.
- Mode Q takes the FileX name as the 12 characters before the first blank of the line: a shorter
  name crashes DSSAT.
- Summary.OUT gets one row per component run (`R#`, `CR`), SoilWat.OUT and Weather.OUT one block
  over the whole sequence; the existing readers work unchanged.
- Weather ending before the sequence does stops DSSAT with exit code 99 and ERROR.OUT.

0012 decided dssatlab writes no batch file, because seasons need none.

## Decision

- A Simulation whose treatment number has several TREATMENTS rows is a sequence. `run()` writes
  `DSSBatch.v48` into the simulation folder, one line per component, and runs
  `<executable> Q DSSBatch.v48` there. No new public name.
- `run()` (one FileX, modes A and C) is unchanged.
- Checks before the run: a 12-character FileX filename, distinct R values, one field for every
  component, NREPS 1, and weather covering the start through the sequence's last day.
- Experiment data for a sequence takes only controls `years` and `start_date` until a later
  release adds experiment data per rotation component.

## Alternatives considered

- A `sequence=True` flag or a `run_sequence()` function. Rejected: the FileX already says it is a
  sequence; a flag can disagree with it, and a function repeats Simulation's folder, weather and
  soil handling.
- Chaining single runs in Python and passing the end soil state as the next initial conditions.
  Rejected: it re-implements what DSSAT does in mode Q.

## Consequences

- Run modes now are C (Simulation), Q (Simulation of a sequence) and A (`run()`).
- A sequence FileX needs an 8.3 filename, as DSSAT's own files have.
- `summarize_seasons()` groups by rotation component as well, so a sequence's bean, fallow and
  soybean runs are not averaged together.
