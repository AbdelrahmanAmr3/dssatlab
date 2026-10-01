# 0010: Template treatments are named in the FileX template and varied by experiment data

Status: accepted (2026-09-30)

## Context

ADR 0006 limited the FileX template to one field and one treatment. A DSSAT shell user builds an
experiment with several treatments in XBuild (a control, an N rate, an irrigated one) and runs them
together. Experiment data already adds cultivar, planting, irrigation, fertilizer, initial-condition
and control levels per treatment number, and a plan probe on real DSSAT showed that a template FileX
with several treatment rows, each varied by that writer, runs clean all at once and one at a time.

## Decision

The FileX template takes either `treatment_name` (one treatment, as before) or `treatments`, a list
of up to 99 names numbered 1..N in list order. Every treatment starts from the template's cultivar,
planting and harvest levels. Experiment data keyed by treatment number varies each treatment, and
the written FileX holds every treatment with its own experiment data applied. Each entry gets its own
new level; equal levels are not shared. A Simulation still runs one treatment; `run_treatments` takes
`filex_template=` to run them all. One field only.

## Alternatives considered

- Per-treatment sections inside the FileX template. Rejected: the experiment template's sections
  would live in two files with two sets of checks.
- Treatment count taken from the experiment data keys. Rejected: an unchanged control needs an empty
  entry, and the template alone would not say how many treatments the FileX has.
- Share equal levels between treatments, as XBuild does. Rejected for now: cosmetic, and it needs a
  comparison of levels that DSSAT does not require.

## Consequences

- Several fields (several stations or soil profiles) stay out until their own release (v0.11.1).
- Factorial generation (every N rate times every cultivar) is left to the user's Python or to sweeps.
