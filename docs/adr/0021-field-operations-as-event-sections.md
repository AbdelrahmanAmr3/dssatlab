# 0021: Residue, tillage and harvest as event sections

Status: accepted (2026-10-02). Extends 0020's event checks.

## Context

Seven DSSAT_Test course cases (gap row F4) use residue applications (RESIDUES AND ORGANIC
FERTILIZER), tillage (TILLAGE AND ROTATIONS) and harvest details with a growth stage, component,
size group and by-product removal (HARVEST DETAILS). Three are sequences that put tillage and
harvest on fallow components, and one has two tillage rows on the same date. dssatlab had no way to
write any of the three sections, and rejected all experiment data for a fallow component.

As with irrigation, DSSAT exits 0 when events and the management code disagree: under RESID or
HARVS "D" it reads a date like 79170 as a day count, and under RESID "N" it ignores the events.

## Decision

- Three new experiment data sections, `residues`, `tillage` and `harvest`, each a list of event
  dicts written as one new level of its FileX section (MR, MT, MH), like `fertilizer`. Omitted
  optional fields are written as DSSAT's -99.
- Their events need non-descending dates; several events on one date are allowed (fertilizer and
  irrigation keep their one-event-per-date rule). Dates only, no days after planting.
- Treatment entries: residue events are checked against the effective RESID (`controls` `residue`,
  else the FileX level): "R" takes them, "D" and "N" reject them. A new `controls` field
  `harvest_management` sets HARVS; harvest events are rejected only under "D", because "M", "A"
  and "G" still read the stage and percents. Tillage has no code check. Codes are never changed
  for the user.
- Rotation components take the three sections too, without code checks; a fallow component takes
  only these three.
- One new module, `operations.py`, holds their field tables and checks.

## Consequences

- Days-after-planting residue and harvest, and the automatic residue and harvest blocks, stay out
  until a roadmap item names them.
