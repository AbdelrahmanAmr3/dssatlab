# 0014: A rotation in the FileX template, with dates checked by DSSAT's day-of-year rule

Status: accepted (2026-10-01). Extends 0006, 0010 and 0013.

## Context

v0.13 runs a sequence from an existing FileX (ADR 0013), so a user still needs a hand-made
sequence FileX. The FileX template writes one crop. A DSSAT Shell user builds a rotation in XBuild:
crops and fallows one after another, each with its own cultivar, planting and harvest.

Measured on DSSAT 4.8.5 while planning v0.13.1 with a template-style rotation FileX (maize, fallow,
wheat, fallow):

- It runs in mode Q with one TREATMENTS row and one cultivar, planting, harvest and controls level
  per component. A fallow is a cultivar row `FA IB0001`, a harvest level as its end, a blank model
  and no genotype file.
- DSSAT moves every component date forward by whole years, keeping its day of year, until it falls
  on or after the component's own start. A planting date before the previous component's end, or a
  last component ending on or after the first planting's day of year, costs a year without any
  error or warning.

## Decision

- The FileX template takes `rotation`, a list of 2 to 9 components, instead of one crop. A crop
  component has the crop, cultivar, planting and optional harvest date the single-crop template
  has; a fallow has only an end date. One sequence (treatment 1) on one field.
- Checks before anything is written: the first component is a crop, the last ends on a known date,
  the dates are in rotation order, and the last end's day of year is before the first planting's.
- The first component's NYERS is the rotation's cycle in years, so a bare template runs one whole
  cycle; controls `years` in experiment data overrides it.
- Experiment data for a rotation keeps v0.13's limit (controls years and start_date) until a later
  release adds experiment data per rotation component. (Superseded by 0015 in v0.13.2.)

## Alternatives considered

- A separate rotation template and writer. Rejected: a second template, loader and set of checks
  for the same crops and plantings.
- A list of single-crop FileX templates. Rejected: station, treatment name and soil keys repeated.
- Rotation dates as days of year or offsets. Rejected: users think in calendar dates; dssatlab
  converts them and checks them against DSSAT's day-of-year rule.

## Consequences

- A crop harvested at maturity can still mature after the next component's date in some weather
  year, and DSSAT then moves that date a year. This cannot be checked before the run; the guide
  says to end crops with a harvest date or leave a margin.
- The written FileX is a `.SQX`, named like DSSAT's own sequence files.
