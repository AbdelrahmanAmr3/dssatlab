# 0030: New cultivars written under the user's own code

Status: accepted (2026-10-04). Builds on 0017.

## Context

Course FileXs point at cultivars the installed .CUL does not have (UFGA7801: IB1000-IB1010,
KADO7701: IB0098); DSSAT stops with 99 (IPVAR). ADR 0017 only changes an existing cultivar and
renames it DLnnnn, so a FileX's own missing code can never exist.

## Decision

- The cultivar section takes two more optional fields, `ecotype` and `name`. A `code` missing from
  the crop's .CUL together with `ecotype` and `coefficients` is a new cultivar.
- A new cultivar must give every coefficient column after `ECO#` of the .CUL's first `@VAR#` table,
  with no defaults. The ecotype must exist in the crop's .ECO when the crop has one.
- dssatlab writes one line in the layout of that table's first cultivar line (EXPNO `.`, name
  defaulting to the code) at the end of the table in the simulation folder's .CUL copy, under the
  user's code. The source .CUL, .ECO and .SPE never change.
- DL0001-DL9999 stay reserved for changed cultivars. One new code used twice in a run must be
  defined identically. Rotation components reject new cultivars, as they reject coefficients.

## Alternatives considered

- A user-supplied .CUL file. Rejected: another input file with its own checks, and the user edits
  fixed-width columns by hand.
- `based_on` an existing cultivar plus changes. Rejected: that is ADR 0017's changed cultivar.
- Defaults for omitted coefficients. Rejected: a silent guess at a physiological value.
