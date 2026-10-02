# Sweeps

A **Sweep** runs every combination of a few **Factors** as scenarios over the
base inputs. Each Factor is an experiment data section with labelled, complete
section values. `run_sweep()` returns one table of Summary rows with the labels
in their own columns.

## Planting date by nitrogen rate

Use an existing `UFGA8201.MZX` and weather data covering its 1982 season:

```python
import dssatlab as dl

event = {"material": "FE001", "application": "AP001", "depth": 10}
planting = {"method": "S", "distribution": "R", "population": 7.2, "row_spacing": 61, "depth": 5}
rows = dl.run_sweep(
    "UFGA8201.MZX", "weather.csv", treatments=[1],
    factors={
        "planting": {d: dict(planting, date=d) for d in ("1982-02-26", "1982-03-12")},
        "fertilizer": {n: [dict(event, date=d, n=n // 2) for d in ("1982-04-07", "1982-05-17")] if n else [] for n in (0, 60, 120)},
    },
)
```

This runs treatment 1 seven times: the unchanged base, then two planting dates
by three nitrogen rates (0, 60 and 120 kg N/ha). `[]` means no fertilizer events.
The nitrogen rate is split into two equal side-dress applications on April 7
and May 17 (`FE001` = ammonium nitrate). These event dates stay the same for
both planting dates; the sweep does not move event dates automatically.

## Factors and labels

`factors` must be a non-empty Python dict. Its keys are experiment data sections:
`planting`, `irrigation`, `fertilizer`, `cultivar`, `initial_conditions`,
`controls` or `rotation`. Each maps a non-empty dict of labels to complete
section values, using the same fields and checks as
[experiment data](experiment.md). For `rotation`, supply the whole section keyed
by rotation component R number, as in [sequence analysis](sequence.md).

`controls` factors can vary the [automatic irrigation and planting fields](experiment.md#automatic-management).
`irrigation` factors accept [day events and the efficiency dict](management.md#irrigation-timing-and-efficiency).
Every combination must match its effective IRRIG code; for automatic irrigation
threshold sweeps, put `irrigation: []` in the base experiment data.

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
Sequences (treatments with several rotation components) keep their rotation
component names: the scenario name is not written to `TNAME` and the
treatment-name length check does not apply, exactly as for `run_treatments()` scenarios.

Sweep problems (factors, labels, scenario names and treatment selection) are
collected into one `DSSATCheckError`; once those are fixed, every combination's
experiment data problems are collected into one `DSSATCheckError`, with scenario
and treatment labels, still before anything runs.
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

## Cultivar coefficient sweep

Vary `P1` over three values by supplying a `cultivar` factor of complete cultivar
sections, including crop and source code:

```python
rows = dl.run_sweep(
    "UFGA8201.MZX", "weather.csv", treatments=[1],
    factors={"cultivar": {p1: {"crop": "MZ", "code": "IB0035",
                             "coefficients": {"P1": p1}}
                          for p1 in (200, 259, 320)}},
)
dl.to_dataframe(rows)[["scenario", "cultivar", "ADAT", "MDAT", "HWAM"]]
```

The unchanged base runs first, followed by the three coefficient values. Each run
has its own simulation folder with a `.CUL` copy; each coefficient scenario has a changed cultivar
line with a new `DLnnnn` code, and its copied FileX points at that code. The source
`.CUL` stays unchanged. The `cultivar` result column holds the numeric P1 label
(`None` for base). See [coefficient checks](experiment.md#cultivar-coefficients) and
[ADR 0017](../adr/0017-cultivar-coefficients-as-a-changed-cul-line.md).

## Scope

Sweeping `cultivar` can select existing cultivar codes or change their coefficients.
Use [scenarios](scenarios.md) to vary weather or soil. Sweeps do not vary single
fields inside sections, sample random combinations, compute sensitivity indices,
or add plotting helpers. Runs are sequential, with no resume or partial skipping.

The design is recorded in [ADR 0016](../adr/0016-sweeps-run-as-generated-scenarios.md).
