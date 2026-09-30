# 0004: matplotlib is an optional extra, used only for plots

Status: accepted (2026-09-30)

## Context

v0.4 reads DSSAT's output files and lets the user plot them. Plotting needs a library, and
the package has no required runtime dependencies (ADR 0002 keeps pandas optional for the same
reason).

## Decision

matplotlib is an optional extra: `pip install dssatlab[plot]`. It is imported inside
`plot_plant_growth()` and nowhere else, so installing and running the package never needs it.
If it is missing, the function raises an error that says what to install. The reader
functions return plain rows and work without matplotlib or pandas.

## Alternatives considered

- No plotting in the package; the notebook shows how to plot the rows. Rejected: the owner
  wants visualizing to be easy from Python, and one small function does that.
- matplotlib as a required dependency. Rejected: it adds a large install to every user,
  including those who only call `connect()` or `run()`.

## Consequences

- The plot function has a deliberately tiny surface: one variable against date, one line per
  simulation. No styling options, no dashboards.
- Tests for plotting are skipped when matplotlib is absent.
- Adding another plotting library, or a richer plot API, is a new decision.
