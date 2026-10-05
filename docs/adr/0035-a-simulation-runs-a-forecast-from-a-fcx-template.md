# 0035: A Simulation runs a forecast from a `.FCX` template

Status: accepted (2026-10-04). Extends 0022, and reverses its "a Simulation does not run forecasts" rule.

## Context

ADR 0022 lets `run()` run a forecast FileX (`.FCX`) in DSSAT's forecast mode (Y). A Simulation
rejected `.FCX` templates, so a user could not forecast with their own weather data (GAPS F12,
UFAC2301). DSSAT-CSM v4.8.6.0 (`Weather/ModForecast.f90`) uses observed weather from the start date
to the day before the forecast date (SIMDATES FODAT). After that it runs one season per historical
year, from (start year - NYERS) to (start year - 1), each from the start day of year. Only run mode Y
decides that a run is a forecast. A missing FODAT makes DSSAT use the day after the last weather
record, and a FODAT before the start date stops DSSAT.

## Decision

A Simulation whose FileX template is a `.FCX` is a forecast. It runs in mode Y through the batch
file `run()` already writes, in the simulation folder. Experiment data `controls.forecast_date`
edits FODAT, and is a check problem on any other template. The checks report a missing forecast
date, a forecast date before the start date, observed weather that doesn't cover start to forecast
date - 1, and historical weather that doesn't cover the NYERS ensemble seasons (the existing season
coverage rule, started NYERS years earlier). They also report WTHER other than M, a climate file
source, and a sequence. The result is the usual one: each summary row is one historical weather year.

## Considered options

- A `forecast_date` key that turns any template into a forecast: rejected. It is a hidden mode
  switch, and ADR 0022 already recognises a forecast by `.FCX`.
- Letting DSSAT default a missing FODAT: rejected. The last record depends on how dssatlab splits
  weather files, which the user can't see.
- A separate forecast result class: rejected (one stateful class rule).

## Consequences

- Forecasts from a FileX built from scratch, climate or generated ensembles (WTHER S/W/G),
  FSTRYR/FENDYR ranges and ensemble statistics are still out of scope.
