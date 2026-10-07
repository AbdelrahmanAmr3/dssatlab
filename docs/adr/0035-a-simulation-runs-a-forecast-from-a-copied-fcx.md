# 0035: A Simulation runs a forecast from a copied `.FCX`

Status: accepted (2026-10-04). Extends 0022, and reverses its "a Simulation does not run forecasts" rule.

## Context

ADR 0022 lets `run()` run a forecast FileX (`.FCX`) in DSSAT's forecast mode (Y). A Simulation
rejected a `.FCX` FileX, so a user could not forecast with their own weather data (GAPS F12,
UFAC2301). DSSAT-CSM v4.8.6.0 (`Weather/ModForecast.f90`) uses observed weather from the start date
to the day before the forecast date (SIMDATES FODAT). After that it runs one season per historical
year, from (start year - NYERS) to (start year - 1), each from the start day of year. Only run mode Y
decides that a run is a forecast. A missing FODAT makes DSSAT use the day after the last weather
record, and a FODAT before the start date stops DSSAT.

## Decision

A Simulation whose FileX (copied into the simulation folder) is a `.FCX` is a forecast. It runs in mode Y through the batch
file `run()` already writes, in the simulation folder. Experiment data `controls.forecast_date`
edits FODAT in the copy, and is a check problem on any other FileX. The checks report a missing forecast
date, a forecast date before the start date, observed weather that doesn't cover start to forecast
date - 1, and weather that doesn't reach back to the first historical season start (start day of year
in start year - NYERS). For a forecast that one contiguous range, from the first historical season
start to forecast date - 1, replaces the normal season coverage rule; it is a conservative input
check, and the WARNING.OUT scan after the run stays the backstop. They also report WTHER other than M,
a climate file source, and a sequence. The result is the usual one: each summary row is one historical weather year.

Stock `.WTH` coverage follows the files DSSAT selects in mode Y, from the first
historical season start through forecast date - 1, using the shared stock-weather
gap check, only for uniform station layouts: all annual one-year files, or one
single multi-year file. Supplied files and installed WED candidates count toward
the layout, with supplied names taking priority. Mixed or unproven layouts skip
forecast coverage; stock structure checks and the `WARNING.OUT` missing-weather
scan remain the backstop. FODAT and its override use four-digit years without
the FileX date century restriction (#324).

## Considered options

- A `forecast_date` key that turns any FileX into a forecast: rejected. It is a hidden mode
  switch, and ADR 0022 already recognises a forecast by `.FCX`.
- Letting DSSAT default a missing FODAT: rejected. The last record depends on how dssatlab splits
  weather files, which the user can't see.
- A separate forecast result class: rejected (one stateful class rule).

## Consequences

- Forecasts from a FileX built from scratch (a FileX template), climate or generated ensembles (WTHER S/W/G),
  FSTRYR/FENDYR ranges and ensemble statistics are still out of scope.

## Real-DSSAT proof

Manual SPEC v0.22 (a)-(d), Windows `C:\DSSAT48\DSCSM048.EXE`, DSSAT
4.8.5.017, UFAC2301.FCX treatments 1 and 2, on 2026-10-04:

- (a) The 8,903 daily UFAC9925.WTH rows (1999-01-01 through 2023-05-17),
  passed as weather data, produce one generated multi-year `.WTH` per Simulation.
  All 46 Summary rows match `ref/UFAC2301.OSU` and `run()` with unchanged stock
  weather on HWAM and MDAT; no missing-weather warning and no missing HWAM.
- (b) `controls.forecast_date` 2023-05-10 / 2022-06-24 matches an independently
  hand-edited stock `.FCX` on HWAM and MDAT in all 46 rows.
- (c) `controls.years: 5` gives five rows per treatment, WYEAR 2018..2022 and
  2017..2021 in order, matching the corresponding baseline tails on HWAM and MDAT.
- (d) Weather trimmed to 2023-05-16 / 2022-06-30 (forecast date minus one day)
  matches all 46 baseline rows on HWAM and MDAT, without missing-weather warnings.

Evidence is retained locally under `.work/e2e-v022/`: `prove.py`, `results.json`
with every compared row and source SHA-256 hashes, and run directories with
DSSAT outputs and batch files. Source inputs and the executable remain unchanged.
Forecasts from scratch are still outside this proof. No Linux real-DSSAT proof
was run.
