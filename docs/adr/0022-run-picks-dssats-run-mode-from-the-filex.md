# 0022: run() picks DSSAT's run mode from the FileX

Status: accepted (2026-10-02). Amends 0012 ("`run()` mode A, no batch file").

## Context

`run()` started DSSAT in mode A (all treatments) or C (one treatment). DSSAT_Test course cases
showed this is wrong for two kinds of FileX: a sequence FileX (`.SQX`, MSKB8902) run in mode A
gives each rotation component as an independent season, hundreds of rows instead of 55, and a
forecast FileX (`.FCX`, UFAC2301) run in mode A gives -99 results. The DSSAT Shell runs them in
modes Q and Y through a batch file. A Simulation already runs a sequence treatment in mode Q.

## Decision

- `run()` uses mode Y with a batch file for a FileX with the `.FCX` extension: one batch row per
  treatment run. Forecast cannot be recognised from FileX content, and `.FCX` is DSSAT's
  forecast FileX extension.
- Otherwise `run()` uses mode Q with a batch file when a treatment it runs is a sequence (several
  TREATMENTS rows for one number, read as in 0018): one batch row per rotation component. This is
  the same reading a Simulation uses, so both agree on what a sequence is whatever the extension.
  Mode Q runs one continuous batch, so with no treatment selected `run()` refuses a FileX that has
  a sequence and more than one treatment number and asks for `treatment=n`.
- Modes Q and Y need the FileX name to be exactly 12 characters (8.3): DSSAT 4.8 crashes on a
  shorter name in a batch file (probe 2026-10-02). `run()` refuses other lengths before running.
- Otherwise mode A or C, as before.
- `run()` writes `DSSBatch.v48` into the FileX folder and refuses to run when one already exists
  there, instead of overwriting a user's file. It writes the batch file after taking the
  before-run file list, so the file is moved into the run directory with the outputs whether DSSAT
  succeeds or fails, and deletes it if DSSAT cannot be started.
- A Simulation does not run forecasts: its check reports a `.FCX` FileX and points to `run()`.

## Alternatives considered

- Mode by extension only (`.SQX` -> Q), like the DSSAT Shell. Rejected: a sequence in another
  FileX would run as wrong independent seasons, and run() and Simulation would disagree.
- A `mode=` keyword on `run()`. Rejected: the user would have to know DSSAT's letters, and the
  wrong letter gives silent wrong results.

## Consequences

- `run()` on a sequence or forecast FileX gives the rows the DSSAT Shell gives; other FileX run
  exactly as before.
- Forecasting from a Simulation (observed weather to FODAT plus historical years) stays for the
  yield-forecast release.
