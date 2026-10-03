# 0015: Experiment data per rotation component, keyed by R, with dates checked against the component's period

Status: accepted (2026-10-01). Extends 0005, 0013 and 0014; supersedes 0014's limit on
experiment data for a rotation.

## Context

Since v0.13 a sequence's experiment data takes only the controls years and start date. Every
FileX writer edits the first TREATMENTS row with the treatment number, so it cannot reach the
second or third rotation component. A DSSAT Shell user gives each crop in a rotation its own
fertilizer, irrigation, planting and cultivar in XBuild.

Measured on DSSAT 4.8.5 while planning v0.13.2 (maize, fallow, wheat, fallow; three cycles in
mode Q):

- A fertilizer or irrigation level per component applies in every cycle, its dates moved by whole
  years with the component, like its planting date.
- An event dated before its component starts (inside the previous fallow) or after it ends
  (after maturity, inside the next fallow) is skipped without any error or warning.

## Decision

- A sequence treatment's experiment data takes `rotation`, a dict keyed by the component's R
  number, beside `controls`. Each value takes `planting`, `cultivar`, `fertilizer` and
  `irrigation` with the same fields and checks as a single treatment. Fallow components take none.
  A cultivar keeps the component's crop.
- Each edit adds a new level and repoints only that component's row (N, R); a level other
  components share stays unchanged. The same writers serve copied and template sequences.
- Before anything is written, a planting date and every event date must lie in the component's
  period in the first cycle, worked out from the known dates: after the previous component's last
  known date (or on or after the simulation start for the first component), and not after its own
  harvest or fallow end date, else before the next component's first known date. A crop at
  maturity ends on a day only the run knows; that end is documented, not checked.

## Alternatives considered

- A list aligned with the components. Rejected: placeholders for untouched components, and a
  copied FileX's R numbers need not be 1..k.
- Compound treatment keys such as "1.3". Rejected: changes the treatments key every check,
  scenario and run_treatments relies on.
- A separate row-targeted writer per section. Rejected: three duplicated writers; one optional
  R match in the shared repoint helper does it.

## Consequences

- A copied FileX's component dates are read from its planting and harvest levels; a two-digit
  year resolves to the first matching year on or after the simulation start. An unreadable date
  gives no bound, and the report says the check was skipped.
- Initial conditions, controls and harvest per component stay out of experiment data.
