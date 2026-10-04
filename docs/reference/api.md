# API reference

This page documents the public API exported by `dssatlab`. Only names explicitly exported in `dssatlab.__all__` are part of the public interface.

## Discovery and execution

::: dssatlab.connect

::: dssatlab.detect

::: dssatlab.install

::: dssatlab.run

## Simulation, weather, soil, and management

::: dssatlab.Simulation

::: dssatlab.write_weather_template

Weather template columns are `station`, `latitude`, `longitude`, `elevation`,
`date`, `srad`, `tmax`, `tmin`, `rain`, and optional `tav`, `amp`, `refht`,
`wndht`, `par`. Daily `par` is in mol/m2 per day, finite and from 0 to 100
inclusive; fill every row or omit the column. The written example omits `par`.
See [weather columns and checks](../guide/simulation.md#prepare-the-weather-template).

::: dssatlab.import_nasa_power
    options:
      show_root_heading: true
      show_signature: true
      show_signature_annotations: true
      separate_signature: true

Returns the `Path` of a new weather template CSV. Coordinates come from the
NASA POWER header unless the corresponding keyword replaces them. No gap
filling, unit conversion or range checking is done. Pass the returned path as
`weather=` to `Simulation`. See [Import a NASA POWER file](../guide/simulation.md#import-a-nasa-power-file).

::: dssatlab.write_soil_template

### summarize_weather(source)

::: dssatlab.summarize_weather

Accepts a weather template CSV path (`str` or `Path`), a list of row dicts,
or a pandas DataFrame with the weather template columns. No DSSAT executable
is needed. Returns a plain dict with these keys:

| Key | Value |
| --- | --- |
| `station` | Four-character station code |
| `latitude`, `longitude` | Station coordinates in degrees, as supplied |
| `elevation` | Station elevation in m, as supplied; an explicit `-99` is kept |
| `first_date`, `last_date` | First and last `datetime.date` values |
| `days` | Number of daily rows |
| `variables` | Dict keyed by `srad`, `tmax`, `tmin`, `rain`, and `par` when supplied; each value has `min`, `mean`, `max` |
| `rain_total` | Total rainfall in mm over all rows |
| `years` | List of dicts in calendar-year order; each has `year`, `days`, `srad_mean`, `tmax_mean`, `tmin_mean`, `rain_total`, and `par_mean` when PAR is supplied |

SRAD uses MJ/m2 per day, temperatures use degrees C, rain uses mm, and PAR
uses mol/m2 per day. Each year's `days` is its actual row count, including
partial years. `par` and `par_mean` appear only when PAR is supplied on every row.
Statistics and rain totals use unrounded data, then Python's `round(value, 2)`
once on each result. Station coordinates and elevation are not rounded.
Use `to_dataframe(summary["years"])` for a yearly table if pandas is installed.

Raises one `DSSATCheckError` with all weather template problems in
`error.problems`, using the same source checks as `Simulation.check()`.
It does not repair data or check FileX coverage. Stock `.WTH` or `.SOL` paths
(any suffix case) and lists of paths are rejected. Supply weather template
data instead; a Simulation copies stock weather files unchanged.

### summarize_soil(source)

::: dssatlab.summarize_soil

Accepts a soil template CSV path (`str` or `Path`), a list of row dicts,
or a pandas DataFrame with the soil template columns. No DSSAT executable
is needed. Returns a plain dict for one soil profile:

| Key | Value |
| --- | --- |
| `soil_id` | Soil profile ID |
| `layers` | Number of soil layers |
| `depth` | Deepest layer bottom in cm |
| `extractable_water` | Sum of `(sdul - slll) * layer_thickness_cm * 10`, in mm; the first layer starts at 0 cm |
| `salb` | Soil albedo, fraction |
| `slro` | Runoff curve number, dimensionless |
| `sldr` | Drainage rate, fraction per day |
| `slpf` | Soil fertility factor, dimensionless |

`depth`, `extractable_water`, `salb`, `slro`, `sldr`, and `slpf` use Python's
`round(value, 2)`. Extractable water is summed from unrounded layer values
before rounding the result.

Raises one `DSSATCheckError` with all soil template problems in
`error.problems`, using the same source checks as `Simulation.check()`.
Stock `.SOL` or `.WTH` paths (any suffix case) and lists of paths are rejected.
Supply soil template data instead; a Simulation copies stock soil files unchanged.
See [Summarise your weather and soil before a run](../guide/simulation.md#summarise-your-weather-and-soil-before-a-run).

### Management and FileX templates

::: dssatlab.write_management_template

::: dssatlab.write_experiment_template

::: dssatlab.write_filex_template

::: dssatlab.list_crops

::: dssatlab.list_cultivars

## Treatments, scenarios and sweeps

::: dssatlab.run_treatments

::: dssatlab.run_sweep

::: dssatlab.combine_summaries

::: dssatlab.summarize_seasons

::: dssatlab.write_scenario_template

## Economics

### net_returns(rows, price_file)

```python
net_returns(rows: list[dict], price_file: str | Path) -> list[dict]
```

::: dssatlab.net_returns

Arguments:

- `rows: list[dict]`: Summary rows from `read_summary()`, `result.summary()` or
  `combine_summaries()`. Each row needs `CR` and `TRNO`, plus the quantity columns
  used by its price section. Matching uses `(CR, TRNO)`, not the scenario's
  `treatment` label; fallow rows also need a matching section.
- `price_file: str | pathlib.Path`: an existing, readable UTF-8 DSSAT `.PRI`
  price file. No default price file is selected. Crop headings cover subsequent
  treatment sections until the next crop heading; both `TREATMENT10` and
  `TREATMENT 10` are accepted.

Returns `list[dict]`: copies of the input rows, in input order, retaining every
column and adding `net_return` as a float in $/ha or `None` when a used quantity
is `None`. Input rows are unchanged. `IDIS=-1` ignores a component, `0` uses
fixed `PAR1`, `1` uses the uniform mean, `2` the triangular mean, and `3` the
normal mean (`PAR1`). Price risk is not modelled. An empty row list returns `[]`
after validating the price file.

Raises one `DSSATCheckError` collecting file and row problems in
`error.problems`: unreadable files; missing, duplicate or malformed sections;
missing, extra or duplicate price columns; missing, duplicate or unknown
parameter rows; non-finite or non-numeric price values; unknown IDIS or
inconsistent distribution parameters; rows that are not a list of dicts;
missing or invalid `CR`/`TRNO`, or no matching section; absent used quantity
columns; and used quantities that are bools, strings or non-finite numbers.
Required price columns are `GRAN BYPR BASE NFER NCOS IRRI IRCO SCOS RESM PCOS
PFER KCOS KFER`, with `IDIS`, `PAR1`, `PAR2` and `PAR3` rows in each section.
Uniform parameters require `PAR1 <= PAR2`, triangular parameters require
`PAR1 <= PAR2 <= PAR3`, and normal parameters require `PAR2 >= 0`.

Pass the result to `summarize_seasons(rows, variables=["net_return"])` or
`to_dataframe(rows)` (optional pandas). See
[seasonal economics](../guide/seasonal.md#compute-net-return-from-a-price-file)
for the required quantities and missing-value limits.

## Reading outputs and plotting

::: dssatlab.read_summary

::: dssatlab.read_plant_growth

::: dssatlab.read_soil_water

::: dssatlab.read_plant_nitrogen

::: dssatlab.read_weather

::: dssatlab.read_dssat_evaluation

::: dssatlab.runner.RunResult.dssat_evaluation

::: dssatlab.to_dataframe

::: dssatlab.plot_plant_growth
    options:
      docstring_options:
        warn_missing_types: false

## Observed data and evaluation

::: dssatlab.read_dssat_observed

::: dssatlab.plot_observed
    options:
      docstring_options:
        warn_missing_types: false

::: dssatlab.write_observed_template

::: dssatlab.evaluate

::: dssatlab.evaluate.Evaluation

::: dssatlab.plot_evaluation
    options:
      docstring_options:
        warn_missing_types: false

## Exceptions

::: dssatlab.DSSATError

::: dssatlab.DSSATNotFoundError

::: dssatlab.DSSATInstallError

::: dssatlab.DSSATRunError

::: dssatlab.DSSATOutputError

::: dssatlab.DSSATCheckError
