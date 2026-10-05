# 0034: A climate file as a FileX template field's weather

Status: accepted (2026-10-04). Extends 0032; reverses its "templates keep measured weather" limit (#300).

## Context

ADR 0032 let a copied FileX run on generated weather (WTHER W or S) from a climate file passed in
`weather=`. A FileX template still required weather data rows for every field, because the template
takes each field's station and coordinates from those rows. A user with only a station's `.CLI` file
could not write a FileX from scratch.

## Decision

Each template field's weather is either weather data rows or exactly one `.CLI` path. For a climate
file, the field's station is the `@ INSI` value (already checked equal to the filename's first four
characters) and its FIELDS coordinates are the INSI row's LAT, LONG and ELEV. The template still
writes WTHER M; the run treatment needs experiment data `controls.weather_source` W or S to use a
climate-file field, and W or S with a data-rows field is a problem. `run()` copies the climate file
unchanged beside the FileX and writes no weather file for that station. This applies to single-crop,
crop-entry and rotation templates; replicates above 1 still need a sequence (a rotation template).

## Alternatives considered

- Switch WTHER to W or S automatically when a field has only a climate file. Rejected: an automatic
  repair, and W versus S is the user's choice.
- A separate `climate=` parameter. Rejected for the same reason as in 0032.

## Consequences

- Daily-weather coverage checks do not apply to a climate-file field; date order checks still do.
- Fields sharing a station must share the same source, as weather rows already must.

## Proof on real DSSAT

Windows DSSAT 4.8.5.017, UFGA station with the stock `UFGA.CLI`, a three-layer soil, `years: 3`,
`random_seed: 1234`. Linux was not run (no stock Linux DSSAT, ADR 0032 probe 6). Comparisons use the Summary
columns TRNO, CR, SDAT, HWAM, ADAT, MDAT, HDAT, R#, P# and ignore run timestamps.

| Check | Result |
|---|---|
| (a) maize template, WTHER W | 3 Summary rows, HWAM 736, 1360, 1609; a rerun is identical; seed 999 gives HWAM 1562, 1121, 888 |
| (b) same, WTHER S | 3 rows, HWAM 1291, 1368, 1223; rerun identical; seed 999 differs (1174, 1285, 1062) |
| (c) supplied `UFGA.CLI` with RTOT and PDW scaled by 0.3 | HWAM 458, 959, 1218 against the stock 736, 1360, 1609, so the copy is used and the stock file does not mask it |
| (d) rotation maize then fallow, W, `years: 2` | `replicates: 1` gives 4 rows; `replicates: 2` gives 8 rows with P# 1 and 2 |
| (e) crop-entry template, maize and wheat, W | treatment 1 CR MZ (HWAM 736, 1360), treatment 2 CR WH (HWAM 358, 175) |
