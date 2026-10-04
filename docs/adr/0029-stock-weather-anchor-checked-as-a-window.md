# 0029: Stock $WEATHER files anchor FileX years; dssatlab checks the window

Status: accepted (2026-10-04).

## Context

ADR 0027 reads every FileX date with DSSAT's fixed rule (00-35 are 2000-2035, 36-99 are 1936-1999)
and deferred two cases. First, DSSAT-CSM v4.8.6.0 (InputModule/MAKEFILEW.f90, Utilities/DATES.for
Y4K_DOY) anchors FileX years to the first date F of the first weather file it opens, when that file
has a `$WEATHER` header and seven-digit dates: a date becomes the first matching year on or after F,
and DSSAT stops when the result is beyond F plus 99 years. Second, an experiment data date outside
1936-2035 was written as YYDDD and read back in another century (#266).

## Decision

- `filex._filex_date` stays the only FileX date reader, with the fixed rule. Inside [F, F + 99 years]
  the anchored and fixed readings agree, so the stock weather check adds one window check instead of
  a second reader: the simulation start and the fixed harvest date must lie in that window, else a
  problem names the date, F, the file and the anchor rule.
- F comes from the first file of DSSAT's own selection walk (`_walk_weather_files`), only when it has
  `$WEATHER` and seven-digit dates.
- `experiment._check_date` rejects dates outside 1936-01-01..2035-12-31, so every FileX date writer
  shares one range check. The anchor does not widen this range.

## Alternatives considered

- Pass the anchor into `_filex_date` and every caller on the stock path. Rejected: a second reading
  rule threaded through about ten callers, for no difference inside the window.
- Check every FileX date of the treatment against the window. Rejected: needs full FileX parsing.
  Other levels dated before F make DSSAT stop with an error, which fails the run loudly.

## Consequences

- Proven on real DSSAT in `.work/e2e28`.
- Dates in other levels (fertilizer, initial conditions, soil analysis, ...) are not window-checked.
