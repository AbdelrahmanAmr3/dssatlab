# Sweeps

A **Sweep** runs every combination of a few **Factors** as scenarios over the
base inputs. Each Factor is an experiment data section with labelled, complete
section values. `run_sweep()` returns one table of Summary rows with the labels
in their own columns.

## Planting date by nitrogen rate

Use an existing `UFGA8201.MZX` and weather data covering its 1982 season:

```python
import dssatlab as dl

event = {"date": "1982-02-26", "material": "FE005", "application": "AP001", "depth": 5}
planting = {"method": "S", "distribution": "R", "population": 7.2, "row_spacing": 61, "depth": 5}
rows = dl.run_sweep(
    "UFGA8201.MZX", "weather.csv", treatments=[1],
    factors={
        "planting": {d: dict(planting, date=d) for d in ("1982-02-26", "1982-03-12")},
        "fertilizer": {n: [dict(event, n=n)] if n else [] for n in (0, 60, 120)},
    },
)
```

This runs treatment 1 seven times: the unchanged base, then two planting dates
by three nitrogen rates (0, 60 and 120 kg N/ha). `[]` means no fertilizer events.
The fertilizer date stays February 26 for both planting dates; the sweep does
not move event dates automatically.

## Factors and labels

`factors` must be a non-empty Python dict. Its keys are experiment data sections:
`planting`, `irrigation`, `fertilizer`, `cultivar`, `initial_conditions`,
`controls` or `rotation`. Each maps a non-empty dict of labels to complete
section values, using the same fields and checks as
[experiment data](experiment.md). For `rotation`, supply the whole section keyed
by rotation component R number, as in [sequence analysis](sequence.md).

A label must be a non-empty printable string or a finite integer or float;
booleans, `None`, NaN and infinity are rejected. Labels describe the values in
the results: numeric labels stay numbers, so nitrogen rate can be plotted directly.
Factors are supplied as a Python dict; there is no factors YAML or sweep template.

Combinations follow dict insertion order: factor order, then value order. In
the example, the February 26 combinations run at 0, 60 and 120, followed by the
March 12 combinations at 0, 60 and 120.

## Base inputs and section replacement

All arguments except `factors` mean the same as for
[`run_treatments()`](scenarios.md). Supply exactly one of `filex` or
`filex_template`; a FileX template requires soil data. `treatments=None` selects
all FileX treatments once in file order, or treatments 1..N for a template.
Pass a list such as `[1, 3]` to select a subset. Weather, soil and the DSSAT
executable are passed through as usual.

Base experiment data comes from `management`: a dict, a YAML path, or `None`
for no experiment data overrides. For each combination it is deep-copied, then
each factor's section **replaces that section whole** for every selected
treatment. Other sections, treatments and top-level keys stay unchanged.
Treatment keys such as `1`, `"1"` and `"01"` identify the same treatment. A
missing treatment entry is added under its integer number. No section fields
or event lists are partially merged. Original FileX, YAML and data files are
left untouched.

The unchanged base runs first under scenario `"base"`, with every factor column
set to `None`. Each combination then runs through `run_treatments()` as a scenario.
Its name is the labels converted to strings and joined by one space in factor
order, for example `"1982-03-12 60"`. This name is also written into the copied
FileX's treatment name (`TNAME`/`TNAM`). **Keep labels short:** the joined name must
fit that FileX's treatment name column. Checks reject names that are too long,
duplicate joined names, and the reserved name `"base"`.

Every problem across all combinations is collected into one `DSSATCheckError`
before anything runs, with scenario and treatment labels on input problems.
The first DSSAT run failure stops the sweep, as with `run_treatments()`, and
the error names the kept run directories.

## Read the rows

There is one dict per Summary row, in run order (base first). Its columns are
the original Summary columns, then `scenario`, `treatment`, one key per factor
holding its label, and `run_dir` (a `Path`). A seasonal analysis or sequence can
produce several rows per run. Missing or malformed `Summary.OUT` raises
`DSSATOutputError`.

Pass the rows directly to `to_dataframe()` (requires optional pandas):

```python
df = dl.to_dataframe(rows)
df[["scenario", "planting", "fertilizer", "NICM", "HWAM"]]
```

`NICM` shows nitrogen applied (kg N/ha), and `HWAM` shows grain yield (kg/ha).
Use a row's run directory to read daily plant growth:

```python
growth = dl.read_plant_growth(rows[1]["run_dir"])
```

The same rows go directly into `summarize_seasons()`:

```python
stats = dl.summarize_seasons(rows, variables=["HWAM"])
dl.to_dataframe(stats)
```

For a [seasonal analysis](seasonal.md), set `controls.years` in the base experiment
data and provide weather covering the seasons. Statistics group by scenario,
treatment and rotation component; the statistics table does not add factor columns.

## Scope

Sweeping `cultivar` selects existing cultivar codes. Cultivar coefficient sweeps
(a changed copy of one cultivar's `.CUL` line) are planned for v0.14.1.
Use [scenarios](scenarios.md) to vary weather or soil. Sweeps do not vary single
fields inside sections, sample random combinations, compute sensitivity indices,
or add plotting helpers. Runs are sequential, with no resume or partial skipping.

The design is recorded in [ADR 0016](../adr/0016-sweeps-run-as-generated-scenarios.md).
