# 0002: pandas is accepted but never required

Status: accepted (2026-09-29)

## Context

Up to v0.2 the package has zero runtime dependencies, which keeps installation trivial on
Windows, Linux and a fresh Colab runtime. The next phase converts a user's own data (first
weather) into DSSAT files. Users hold that data in pandas DataFrames.

## Decision

The package still installs and works without pandas. Where a table is expected, a plain
Python form (rows or a path to a CSV file) is always accepted, and a DataFrame is accepted
too when the user already has pandas. The checks run on plain rows, so they behave the same
either way. pandas is never listed as a required dependency.

## Alternatives considered

- Plain Python only. Rejected: it makes the common case (a DataFrame) awkward.
- pandas as a required dependency. Rejected: it adds a large install to every user,
  including those who only call `connect()` or `run()`.

## Consequences

- Reading a DataFrame must not import pandas unless the user passes one.
- Both input forms need tests. A pandas-specific test may be skipped when pandas is absent.
- If pandas ever becomes required, that is a new decision that supersedes this one.
