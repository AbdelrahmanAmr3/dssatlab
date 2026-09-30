# 0005: Experiment data is one YAML that edits a copy of an existing FileX

Status: accepted (2026-09-30)

## Context

v0.3.2 lets a user change planting, irrigation and fertilizer. v0.6 adds cultivar, initial
conditions and simulation controls. The long-term direction is building a FileX from Python,
but each FileX section has crop-specific columns and codes, and only some are proven on real
DSSAT.

## Decision

All user-supplied FileX content is **experiment data**: one per-treatment YAML (or dict) with a
section per thing the user may change. It is applied to a copy of a FileX the user already has,
by adding a level and repointing the selected treatment; the original is never changed.
Sections the user omits keep the FileX's own level. Creating a FileX from nothing is deferred.

## Alternatives considered

- A separate argument and template per section (cultivar, initial conditions, controls).
  Rejected: they are written by the same add-a-level-and-repoint step, and users would fill in
  four files for one treatment.
- Building the FileX from scratch now. Rejected: it needs a template, checks and real-DSSAT
  proof for every section, including `TREATMENTS` and `FIELDS`, for little extra value while
  users already have a FileX.

## Consequences

- A new section means its template comment, its check and its FileX writer change together.
- The YAML stays additive, so management-only files keep working.
- FileX-from-scratch stays the intended later direction and is a new decision when taken.
