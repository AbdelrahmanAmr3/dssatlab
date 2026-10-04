# 0020: Automatic management as controls fields, events checked against the irrigation code

Status: accepted (2026-10-02). Extends 0019's simulation options.

## Context

The DSSAT_Test course cases (gap row F3) use automatic irrigation (IRRIG A or F with IMDEP, ITHRL,
ITHRU, IMETH, IRAMT, IREFF), irrigation in days after planting (IRRIG D, IDATE as a day count),
irrigation efficiency EFIR .75 and automatic planting (PLANT A). dssatlab wrote IRRIG R and EFIR 1
and had no way to set the automatic blocks of a controls level.

DSSAT does not fail when the events and the IRRIG code disagree: under D it reads a date like 76126
as a day count, and under A, F or N it ignores reported events. The run exits 0 with wrong results.

## Decision

- The IRRIG and PLANT codes and the automatic irrigation and planting values are new `controls`
  fields (`irrigation_management`, `planting_management`, `auto_irrigation_*`, `auto_planting_*`),
  written like 0019's options: the treatment's controls level is copied, automatic blocks included,
  and only named columns change. They live in SIMULATION CONTROLS in the FileX, so they live in
  `controls` in experiment data, not in the `irrigation` or `planting` sections.
- An irrigation event has a `date` or `days_after_planting`, never both, and one list uses one
  kind. The checks read the effective IRRIG code (the `controls` field, else the treatment's level)
  and reject events DSSAT would misread or ignore: D needs day events, R/P/W need date events,
  A/F/N need no events. They never change the code for the user.
- `irrigation` may also be a dict `{efficiency: ..., events: [...]}` to set EFIR; the list form
  stays valid and writes EFIR 1.

## Consequences

- Rotation components keep date events in list form; their IRRIG belongs to the treatment.
- Fertilizer and residue in days after planting, the IROFF stop stage and the automatic nitrogen,
  residue and harvest blocks stay out until a roadmap item names them.
