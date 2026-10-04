# 0028: Soil analysis and environment modifications as new levels

Status: accepted (2026-10-03). Follows 0005 and 0021.

## Context

Six DSSAT_Test course cases use a FileX SOIL ANALYSIS section (gap row F7: soil phosphorus for
GAPL2004, SAWA0402, UFGA8281) or an ENVIRONMENT MODIFICATIONS section (gap row F8: UFGA7901,
UFGA8281, UFGA7609). dssatlab could write neither, so a FileX template Simulation could not set
soil phosphorus or change the weather by date. The phosphorus control (PHOSP) already existed.

DSSAT-CSM v4.8.6.0 reads soil analysis in `InputModule/IPSLIN.for` (IPSLAN) and uses a column only
when the first layer has a value. It reads environment events in `InputModule/IPENV.for` and
applies, each day, the last event dated on or before it (`Weather/WTHMOD.for`). Before the run it
copies the events to its input file with formats that keep one decimal place for most values
(`InputModule/optempy2k.for`, formats 90-94).

## Decision

- Two new experiment data sections, each written as one new level of its FileX section and
  pointed at by the treatment: `soil_analysis` (SA; a dict like `initial_conditions`, `"off"` for
  level 0) and `environment` (ME; a list of events, `[]` for level 0). Omitting a section keeps the
  FileX's own level.
- A soil analysis field set in a deeper layer must also be set in the first layer, because DSSAT
  would ignore the column without a message. Upper limits for bulk density, organic carbon and
  total nitrogen are IPSLAN's own errors.
- An environment change is one of add, subtract, multiply or replace, with a number that fits the
  FileX's 4-character cell; event dates are strictly ascending. dssatlab does not copy DSSAT's
  input-file rounding: the docs say DSSAT may round a change.
- Treatments only (copied FileX and FileX template). Rotation components don't take these
  sections, and sweeps may keep them in the base experiment data but can't vary them as factors.
- One module per section, `soil_analysis.py` and `environment.py`, as for the v0.6 sections.

## Consequences

- Soil without phosphorus data still fails in DSSAT under PHOSP "Y" (SPINIT): a DSSAT run error, not
  a dssatlab check.
- Environment events in rotation components and CO2 sweeps wait for a roadmap item.
