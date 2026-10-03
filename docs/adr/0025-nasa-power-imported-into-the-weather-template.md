# 0025: A NASA POWER file is imported into the weather template, not read as weather

Status: accepted (2026-10-03).

## Context

Many users get daily weather from NASA POWER as a CSV. Until now they had to rename its columns,
add station values and change its missing marker by hand before the weather template accepted it.
The weather template is the one shape the checks read; other shapes are "never guessed at".

## Decision

`import_nasa_power(source, path, *, station, latitude=None, longitude=None, elevation=None)`
reads a POWER daily point CSV (the header block, dates as YEAR+DOY or YEAR+MO+DY,
ALLSKY_SFC_SW_DWN, T2M_MAX, T2M_MIN and PRECTOTCORR or PRECTOT) and writes a new weather template
CSV. Coordinates come from the header unless a keyword gives them. POWER's -999 becomes -99, so
the weather checks report the missing day; nothing is filled, converted or range-checked by the
importer. The user then passes the written CSV as `weather=`.

## Alternatives considered

- Accept a POWER file as `weather=` and detect it. Rejected: a second weather input shape, guessed
  from content; the user never sees what DSSAT gets.
- A column mapping for any CSV. Rejected: a rename the user does in one line; it invites unit
  conversion, which AGENTS.md does not allow.
- Download from POWER. Rejected: new network access, and the user's file is the record.
- Import POWER PAR. Rejected: POWER gives it in W/m2, so it needs a conversion.

## Consequences

- One function and one module (`power.py`); the weather template and its checks do not change.
- A POWER file with missing days fails `check()` like any template with -99 values.
