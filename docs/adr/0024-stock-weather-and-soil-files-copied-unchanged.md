# 0024: Stock weather and soil files are copied unchanged and checked by a narrow read

Status: accepted (2026-10-03).

## Context

`run()` always generated the weather file from weather data, with DATE SRAD TMAX TMIN RAIN only.
The DSSAT_Test course cases UFGA7601 and UFGA7609 then give a different yield than DSSAT's own
run (T1 HWAM 4305 against 4348): the stock `UFGA7601.WTH` carries a daily PAR column that the
generated file drops. Putting the stock file back gives the reference result. Soil had the same
gap: `soil=` took only soil-template data.

## Decision

`weather=` also accepts a `.WTH` path (or a list of them) and `soil=` a `.SOL` path, for a copied
FileX. `run()` copies each file's content unchanged into the simulation folder (a weather file under its
upper-case name, which DSSAT on Linux opens; a soil file under its own name). The
checks read only what they need: for weather the station (the file name's first four characters,
as DSSAT looks it up), the `@ INSI` coordinates, and DATE SRAD TMAX TMIN RAIN by header column, fed
into the same checks as weather data; for soil the profile IDs and the file name DSSAT reads for
the FileX's ID_SOIL. A `-99` in a required weather column is a problem, as in weather data. The
weather template also gains an optional daily `par` column, written only when present.

## Alternatives considered

- Convert the stock file to weather data rows and write it again. Rejected: loses PAR and every
  other column, the cause of the course mismatch.
- A full weather and soil file parser. Rejected: AGENTS.md keeps file reading narrow; the checks
  need four columns and the profile IDs.
- Copy without checking. Rejected: a missing year or a wrong station would show up only as a
  `WARNING.OUT` after the run.

## Consequences

- A Simulation built from a stock file runs DSSAT on exactly the file DSSAT's own run uses.
- Stock files need a copied FileX; a FileX template still takes weather and soil data.
- Stock files with `-99` in SRAD, TMAX, TMIN or RAIN are rejected; no gap filling.
