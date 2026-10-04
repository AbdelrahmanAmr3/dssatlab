# 0032: Generated weather from a climate file copied beside the FileX

Status: accepted (2026-10-04). Extends 0019 and 0024.

## Context

Simulation rejected every WTHER other than M, so seasonal course cases such as DTCM6401 (WTHER S,
ten seasons) and UFGA7874 (WTHER W, NREPS 10) could not run. Measured on Windows DSSAT 4.8.5.017 while
planning v0.21 (`.work/probe-v021/`): DTCM6401.SNX run in mode A with no `.WTH` and no `.CLI` in its
folder reads `DTCM.CLI` from DSSAT's climate folder (DSSATPRO `CLD`) and gives the course reference
Summary exactly. A changed `DTCM.CLI` placed beside the FileX changes the results: DSSAT prefers the
copy in the FileX folder. A Linux managed install has no `CLD` entry.

## Decision

`weather=` also accepts a `.CLI` path, alone or with `.WTH` paths. `run()` copies it unchanged,
under its upper-case name, into the simulation folder, as ADR 0024 does for stock weather files.
Each run treatment's controls level decides what it needs: WTHER M needs weather data as before;
W or S needs a climate file named after the FileX WSTA's first four characters, and no weather data.
Supplied input that no run treatment uses is a problem, not a warning. The checks read the climate
file narrowly: the `*CLIMATE` header, the `@ INSI` station and twelve monthly averages rows.
Controls gain `weather_source` (WTHER), `replicates` (NREPS) and `random_seed` (RSEED); replicates
above 1 need generated weather.

## Alternatives considered

- A new `climate=` parameter. Rejected: a second way to pass a copied input file; `weather=`
  already takes files by path.
- Look up the climate file in DSSAT's installation. Rejected: not portable to Linux managed installs
  and hides which file the run used.
- Generate the climate file from weather data. Rejected: that is computing climate statistics, a
  later WeatherMan-style feature.

## Consequences

- A Simulation can run seasonal and sequence analyses on generated weather with replicates.
- The narrow read cannot prove the climate file is complete for WGEN; DSSAT's own errors still
  surface through the run.
