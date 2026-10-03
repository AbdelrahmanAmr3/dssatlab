# 0027: FileX dates are read with DSSAT's two-digit-year rule

Status: accepted (2026-10-03).

## Context

A FileX stores dates as YYDDD. dssatlab had three readers for them: SDATE took its century from the
years the weather covers (with an "ambiguous start year" error), inherited automatic planting dates
picked the nearest matching year, and the harvest and rotation checks used DSSAT's own rule. Every
review round found a case where two of these readers disagreed (#221, #226, #238).

## Decision

Every FileX date is read by one function, `filex._filex_date`, with DSSAT's rule (DSSAT-CSM v4.8.6.0,
Utilities/DATES.for, Y2K_DOY): years 00-40 are 2000-2040, 41-99 are 1941-1999. The weather never
chooses a FileX century. When the resolved date is not covered by the weather, the coverage check
says so and names the rule. Stock weather file records are a separate matter: their dates are
decoded only while walking DSSAT's file selection order, by the existing walker, whose century
handling is unchanged (original start for the first file, the advancing date at each rollover, the
previous record's year within a file).

## Alternatives considered

- Keep resolving SDATE from the weather years. Rejected: DSSAT does not, so a check could pass a run
  that DSSAT simulates in another century, and it kept disagreeing with the other readers.
- Reject every experiment data date outside 1941-2040. Deferred to its own issue: it touches every
  FileX writer.

## Consequences

- The "ambiguous start year" problem is gone; a start in the wrong century is a coverage problem.
- Each rule is proven on real DSSAT (`.work/e2e25`) before it is changed.
