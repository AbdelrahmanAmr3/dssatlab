# Seasonal analysis

A single-season simulation shows how a crop performs under one weather year. Real
agronomic studies often run a **seasonal analysis**: the same treatments evaluated
over many historical weather years to see how yields vary between seasons, how treatments
behave in adverse years, and which management strategy is better on average.

In `dssatlab`, you set the number of seasons using `years` in experiment data
`controls`. DSSAT runs all seasons in one execution, producing one Summary row per
season. You can then merge per-season rows with `combine_summaries()` and compute
cross-season statistics with `summarize_seasons()`.

## Set the number of seasons with `controls: years`

To run an experiment over multiple seasons, specify `years` under `controls` in
your experiment data YAML or dictionary:

```yaml
treatments:
  1:
    controls:
      years: 9
  2:
    controls:
      years: 9
    fertilizer:
      - date: "1978-03-01"
        material: "FE005"
        application: "AP002"
        depth: 5.0
        n: 120.0
```

`years` must be a positive integer (whole number greater than zero). When the simulation
runs, `dssatlab` writes this value as `NYERS` into the copied `SIMULATION CONTROLS` level
for that treatment. All other controls keep their base values.

`years` works identically for:

- **FileX templates**: multi-treatment or single-treatment templates built from scratch.
- **Copied FileX experiments**: an existing FileX (`filex="MYEXP.MZX"`).
- **Single `Simulation` runs** and **`run_treatments()` batches**.
- **Scenario overrides**: a scenario's `management` override can vary `years` like any other control.

If `years` is omitted, the treatment keeps the FileX's original `NYERS` setting (typically `1`).

## Run a multi-season experiment

Here is a complete example running a two-treatment maize experiment over 9 seasons:

```python
import dssatlab as dl

# 1. Define the FileX template
template = {
    "crop": "maize",
    "treatments": ["Low N", "High N"],
    "cultivar": {"code": "IB0035"},
    "planting": {
        "date": "1978-03-01",
        "method": "S",
        "distribution": "R",
        "population": 7.2,
        "row_spacing": 75.0,
        "depth": 5.0,
    },
}

# 2. Set 9 seasons on both treatments, plus 120 kg N on treatment 2
experiment = {
    "treatments": {
        1: {"controls": {"years": 9}},
        2: {
            "controls": {"years": 9},
            "fertilizer": [
                {
                    "date": "1978-03-01",
                    "material": "FE005",
                    "application": "AP002",
                    "depth": 5.0,
                    "n": 120.0,
                }
            ],
        },
    }
}

# 3. Run all treatments across all seasons
results = dl.run_treatments(
    filex_template=template,
    weather=weather_rows,  # continuous weather covering 1978 to 1987
    soil="soil.csv",
    management=experiment,
)
```

DSSAT runs all seasons inside a single run execution (mode C for a `Simulation`, mode A for `dl.run()`).
No batch file or custom run mode is required ([ADR 0012](../adr/0012-seasons-through-nyers-no-batch-mode.md)).

## The season start rule

DSSAT determines the start date of each season using a fixed calendar day-of-year rule:

Season k (1-based) starts on **day of year D of year Y + k - 1**,
where Y and D come from the simulation start date: `controls.start_date`, else
SDATE under START S; the effective planting date under START P. FileX dates use
DSSAT's rule: years 00-35 are 2000-2035 and 36-99 are 1936-1999. Weather written
by dssatlab never chooses their century.
See [simulation start dates](simulation.md#create-a-simulation-and-inspect-the-checks).

- For example, if season 1 starts on `1978-03-01` (day of year 60 in 1978), season 3 (year 1980) starts
  on day of year 60 of 1980, which is **`1980-02-29`** because 1980 is a leap year.

## Pre-run weather coverage check

Because weather data must be continuous without gaps, `dssatlab` validates that your weather data covers
the start date of the last season before any DSSAT files are written or any process is launched.

If the weather data ends before the last season starts, `check()` and `run()` raise `DSSATCheckError`
with an exact diagnostic message:

```text
Controls years 11: season 11 starts on 1988-02-29 (day 60 of 1988), after the weather data ends (1987-12-31). Supply weather for every season, or fewer years.
```

If you run an existing FileX whose controls already specify `NYERS` above 1 without an override, the check
reports:

```text
FileX NYERS 11: season 11 starts on 1988-02-29 (day 60 of 1988), after the weather data ends (1987-12-31). Supply weather for every season, or fewer years.
```

When using `run_treatments()`, any coverage problem is labelled with the offending scenario and treatment.

**Weather ending during the last crop season.** The pre-run coverage check verifies that every season can *start*. If weather data ends after the
last season starts but before the crop reaches maturity, DSSAT exits with return code 0 and logs a
warning in `WARNING.OUT` (`Weather record not found for YR DOY: ...`).
`Simulation.run()` automatically scans `WARNING.OUT` after the run and raises `DSSATRunError`
naming the first missing weather date, preventing silent `-99` results.

## Inspect per-season results with `combine_summaries`

In a seasonal analysis, `result.summary()` returns one row per season:

```python
# One row per season for treatment 1
summary_rows = results["base", 1].summary()
print(f"Treatment 1 seasons simulated: {len(summary_rows)}")
```

To merge the rows across all treatments and scenarios, call `combine_summaries(results)`:

```python
combined = dl.combine_summaries(results)
```

Each row in `combined` retains the original DSSAT Summary columns (`HWAM`, `CWAM`, `ADAT`, `MDAT`, etc.)
and includes `scenario` and `treatment` labels:

```python
for row in combined:
    print(f"Treatment: {row['treatment']}, Planting year: {row['PDAT'].year}, Yield: {row['HWAM']} kg/ha")
```

Daily outputs (`PlantGro.OUT`, `SoilWat.OUT`, `PlantN.OUT`, `Weather.OUT`) also record all seasons,
separated into DSSAT's standard seasonal `*RUN 1`, `*RUN 2` blocks.

## Compute seasonal statistics with `summarize_seasons`

To compare treatments across seasons without manual calculations, use `summarize_seasons()`:

```python
stats = dl.summarize_seasons(combined, variables=["HWAM"])
```

`summarize_seasons()` accepts Summary rows from `combine_summaries()` or directly from `result.summary()`
(where scenario defaults to `"base"`). It groups rows by `(scenario, treatment, component)` (where `component` is
the rotation component `R#`, defaulting to `1` for single-crop seasonal runs) and calculates summary
statistics for each requested variable.

### Statistics table columns

Each dictionary in the returned list contains the following columns:

| Column | Description |
|---|---|
| `scenario` | Scenario name (`"base"` for single runs without scenario labels) |
| `treatment` | Treatment number (from the row's `treatment` or `TRNO` key) |
| `component` | Rotation component number (`R#`, `1` for single-crop seasonal runs) |
| `crop` | Crop code from the first row of the group (`CR`, or `None` if absent) |
| `variable` | The Summary column name being summarized (e.g., `"HWAM"`) |
| `seasons` | Total number of seasons simulated (total rows in the group) |
| `missing` | Count of missing values (`None` / DSSAT `-99`) |
| `mean` | Arithmetic mean of non-missing values (`None` if all missing) |
| `sd` | Sample standard deviation (`None` if fewer than 2 non-missing values) |
| `min` | Minimum value |
| `p25` | 25th percentile (first quartile, inclusive method) |
| `median` | Median (50th percentile) |
| `p75` | 75th percentile (third quartile, inclusive method) |
| `max` | Maximum value |

### Summarize multiple variables

You can summarize multiple numeric Summary variables in a single call by passing a list or tuple:

```python
stats = dl.summarize_seasons(combined, variables=["HWAM", "CWAM", "PRCP"])
```

Result rows preserve the order in which groups first appear, followed by the requested variables in order.

### Convert to a pandas DataFrame

Pass the output of `summarize_seasons()` directly to `to_dataframe()`:

```python
df = dl.to_dataframe(stats)
print(df[["treatment", "variable", "seasons", "mean", "sd", "min", "median", "max"]])
```

Example output:

```text
   treatment variable  seasons    mean     sd     min  median     max
0          1     HWAM        9   316.8   79.3     232   296.0     453
1          2     HWAM        9  1901.6  897.8     824  1768.0    3471
```

Missing values (`-99`) are excluded from numeric calculations and counted in `missing`, ensuring
incomplete seasons do not skew the statistics.
