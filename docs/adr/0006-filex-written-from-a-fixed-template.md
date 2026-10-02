# 0006: A FileX can be written from a fixed template, one field and one treatment

Status: accepted (2026-09-30)

## Context

ADR 0005 kept "FileX from scratch" as the intended later direction. The Colab user test of
v0.6.0 showed the cost of not having it: a user with their own weather and soil must still find
an existing FileX, and its station (`WSTA`) and soil ID (`ID_SOIL`) decide what their data must
be called. A user of the shell DSSAT can start from nothing.

## Decision

A **FileX template** (a separate YAML, not extra keys in the experiment data) lets dssatlab
write a FileX for exactly one field, one treatment and one crop. Station, coordinates and
elevation come from the checked weather data, and the soil profile ID comes from the checked
soil data; the template has no separate fields for them. The crop model is fixed per crop.
A `Simulation` takes either a FileX path or a FileX template, never both and never neither.
Crops are added only after a real-DSSAT run proves them.

## Alternatives considered

- Keep editing copies of an existing FileX only. Rejected: the FileX decides the site, so the
  user's own data must borrow another experiment's names.
- Extra keys in the experiment YAML that switch to writing a FileX. Rejected: the same file
  would mean two different things depending on which keys it holds.
- Multi-field or multi-treatment FileX. Rejected for now: each needs its own checks and proof.

## Consequences

- A new FileX section changes its template comment, its check and its writer together (as in ADR 0005).
- Model selection stays deferred; the model code is written by the template.
- AGENTS.md's "FileX from scratch is not allowed" is lifted for this case only.
