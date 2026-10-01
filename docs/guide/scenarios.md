# Run treatments and scenarios

A single `Simulation` runs one treatment of an experiment under one set of inputs.
Real studies often evaluate all treatments of an experiment or compare "what if"
questions—such as shifting planting dates, varying nitrogen rates, or testing
different weather years.

`run_treatments()` runs every treatment of a FileX or FileX template (or a selected subset),
optionally across several named **scenarios**, in a single call. Each simulation
executes in its own isolated simulation folder beside the FileX or template YAML, ensuring runs
never overwrite each other.

The un-overridden run is always included under the scenario name `"base"`. Results
are returned in a dictionary keyed by `(scenario, treatment)`, and
`combine_summaries()` merges the summary tables into a single dataset.

Every named scenario writes its name into the copied treatment's `TNAME`/`TNAM`,
so Summary's `TNAM` identifies it, including weather-only and soil-only scenarios.
The `"base"` scenario keeps the source treatment name. Names must fit the FileX
column; checks reject longer names before any simulation runs.

Only when a treatment has experiment overrides in `management` does the copied
field use the supplied weather station and soil profile ID, so they need not
match the source FileX. Without soil data, the source soil ID is retained.
Omitted or empty treatment entries keep the source field IDs and the existing
station/soil matching checks; the scenario name is still written.

## Run all treatments or a subset

To run every treatment defined in a FileX using your weather data:

```python
import dssatlab as dl

# Runs all treatments in UFGA8201.MZX
results = dl.run_treatments("UFGA8201.MZX", weather="weather.csv")
```

By default (`treatments=None`), `run_treatments()` reads the `*TREATMENTS` section
of the FileX and executes every treatment found.

To run a specific subset of treatments, pass a list of treatment integers:

```python
import dssatlab as dl

results = dl.run_treatments(
    "UFGA8201.MZX",
    weather="weather.csv",
    treatments=[1, 3],
)
```

You can also supply custom soil or management data:

```python
results = dl.run_treatments(
    "UFGA8201.MZX",
    weather="weather.csv",
    treatments=[1, 3],
    soil="soil.csv",
    management="management.yaml",
)
```

Treatments must be specified as a list of integers. Supplying an empty list,
non-integers, or treatment numbers not present in the FileX raises `DSSATCheckError`
before any simulation runs.

## Run multi-treatment template experiments

Instead of an existing FileX, you can pass a FileX template via `filex_template`:

```python
import dssatlab as dl

results = dl.run_treatments(
    filex_template="filex.yaml",
    weather="weather.csv",
    soil="soil.csv",
    management="experiment.yaml",
)
```

- **One source**: Supply exactly one of `filex` or `filex_template`. Supplying both or neither raises `DSSATCheckError`.
- **Soil is required**: Just as with a template `Simulation`, `soil` data is required when using a template.
- **All treatments by default**: When `treatments=None`, `run_treatments()` runs all treatments 1..N defined in the template's `treatments` list in order (or treatment 1 for a single-treatment template).
- **Subset selection**: Pass `treatments=[1, 3]` to run only selected treatment numbers.
- **Whole experiment written**: Each simulation folder holds the complete generated FileX with all treatments and their experiment data applied. The scenario name is written to the selected treatment row only.
- **Scenarios**: `scenarios=` works identically with template experiments, allowing you to test weather, soil, or management overrides across all template treatments.

### Two fields in one template experiment

When the FileX template defines multiple fields with `treatment_fields`, supply `weather` and `soil` as dictionaries keyed by field number:

```python
# A two-field template comparing Site A (field 1) and Site B (field 2):
results = dl.run_treatments(
    filex_template="two_fields.yaml",
    weather={1: "site_a_weather.csv", 2: "site_b_weather.csv"},
    soil={1: "site_a_soil.csv", 2: "site_b_soil.csv"},
)
```

Each treatment runs on its assigned field using the corresponding weather and soil data. Calling `combine_summaries(results)` includes `WSTA` and `SOIL_ID` on every row, making it easy to compare results across sites or soils. Scenario overrides of `weather` or `soil` replace the whole per-field dictionary for that scenario.

## Define scenarios

A **scenario** is a named set of input overrides. You can override any of the three
main inputs:

- `weather`: new weather data (CSV path, list of dicts, or DataFrame)
- `soil`: new soil profile (CSV path, list of dicts, DataFrame, or `None`)
- `management`: new management data (YAML path or dictionary)

### Overrides replace the whole input

An override completely replaces the base input for that scenario. There is no
partial or deep merging:

- If a scenario specifies `weather="weather_2022.csv"`, the entire base weather is
  replaced by that file for all treatments in that scenario.
- If a scenario specifies `soil=None`, it runs without custom soil (using the
  FileX's original soil profile and copying sibling `.SOL` files), even if the base
  run provided custom soil.
- If an input is not mentioned in a scenario, the scenario uses the base input.

Unknown keys (anything other than `weather`, `soil`, or `management`) are rejected
with a clear error listing the allowed keys.

### "base" is always included

The un-overridden run is always executed and returned under the scenario name
`"base"`. This guarantees that every scenario can be compared against the baseline.
Because `"base"` is reserved, you cannot define a custom scenario named `"base"`.

### Pass scenarios as a dictionary

You can define scenarios as a plain Python dictionary without any external
dependencies:

```python
import dssatlab as dl

scenarios = {
    "dry_year": {
        "weather": "weather_dry.csv",
    },
    "high_n": {
        "management": {
            "treatments": {
                1: {
                    "fertilizer": [
                        {
                            "date": "1982-03-20",
                            "material": "FE001",
                            "application": "AP001",
                            "depth": 5.0,
                            "n": 150.0,
                        }
                    ]
                }
            }
        },
    },
}

results = dl.run_treatments(
    "UFGA8201.MZX",
    weather="weather.csv",
    treatments=[1, 3],
    scenarios=scenarios,
)
```

In this example, `run_treatments()` executes 6 simulations in total:
- `"base"`, treatment 1
- `"base"`, treatment 3
- `"dry_year"`, treatment 1
- `"dry_year"`, treatment 3
- `"high_n"`, treatment 1
- `"high_n"`, treatment 3

## Prepare the scenario template

You can also write scenarios in a YAML file. Generate a commented YAML template:

```python
import dssatlab as dl

dl.write_scenario_template("scenarios.yaml")
```

If you pass `filex`, the template pre-fills comments listing the treatment numbers
found in your FileX:

```python
dl.write_scenario_template("scenarios.yaml", filex="UFGA8201.MZX")
```

This writes comments such as `# treatments=[1, 3, 5]` into the template so you know
which treatment numbers exist. An existing destination raises `DSSATError`, preserving
existing files.

Example `scenarios.yaml`:

```yaml
# DSSATLab Scenario Template
# Each top-level key is a scenario name.
# Allowed override keys: weather, soil, management.
# An override replaces the whole input (no partial merge).
# The un-overridden baseline is automatically run as "base".

dry_year:
  weather: "weather_dry.csv"

irrigated:
  management:
    treatments:
      1:
        irrigation:
          - date: "1982-03-15"
            amount: 50.0
            method: "IR001"

native_soil:
  soil: null  # null reverts to the FileX's original soil profile
```

Pass the YAML path to `run_treatments()`:

```python
results = dl.run_treatments(
    "UFGA8201.MZX",
    weather="weather.csv",
    scenarios="scenarios.yaml",
)
```

Reading YAML requires PyYAML (ADR 0003), which is imported only when a YAML path is
passed. Install it via `pip install pyyaml` or `pip install dssatlab[yaml]`.
Loading enforces strict parsing: duplicate keys, unquoted dates, or invalid YAML
raise `DSSATCheckError`.

## Inspect the results

`run_treatments()` returns a dictionary mapping `(scenario, treatment)` tuples to
[RunResult](run-filex.md#inspect-the-run-result) objects:

```python
# Access a specific simulation's result
base_tr1 = results["base", 1]
dry_tr1 = results["dry_year", 1]

print("Base treatment 1 run directory:", base_tr1.run_dir)
print("Exit status:", base_tr1.returncode)
```

Each value is a complete `RunResult` created in its own dated simulation folder
(`dssat_sim_YYYY-MM-DD_HHMMSS`) beside the FileX. You can read outputs directly
from any result:

```python
summary_rows = base_tr1.summary()
growth_rows = base_tr1.plant_growth()
water_rows = base_tr1.soil_water()
nitrogen_rows = base_tr1.plant_nitrogen()
weather_rows = base_tr1.weather()
```

## Combine summaries into a single table

To compare end-of-season results across treatments and scenarios, call
`combine_summaries(results)`:

```python
import dssatlab as dl

combined = dl.combine_summaries(results)
for row in combined:
    print(f"Scenario: {row['scenario']}, Treatment: {row['treatment']}, "
          f"Yield: {row['HWAM']} kg/ha, Harvest date: {row['HDAT']}")
```

`combine_summaries()` collects the summary rows (`Summary.OUT`) of every run and adds
`scenario` and `treatment` columns at the beginning of each row.

### Convert to a pandas DataFrame

If pandas is installed, convert the combined summary into a DataFrame:

```python
import dssatlab as dl

df = dl.to_dataframe(dl.combine_summaries(results))
print(df[["scenario", "treatment", "HWAM", "CWAM", "ADAT", "MDAT"]])
```

Because `to_dataframe()` preserves row order, dates (`datetime.date`), and missing
values (`None`), you can group, pivot, and plot results immediately:

```python
# Example: compare yield by scenario and treatment
print(df.pivot(index="treatment", columns="scenario", values="HWAM"))
```

## Validation and error rules

`run_treatments()` applies strict verification before running DSSAT:

### All checks before any run

Every `(scenario, treatment)` combination is checked before any DSSAT process is
launched. If any input has invalid syntax, missing dates, out-of-range values, or
mismatches with the FileX, execution halts immediately.

All discovered problems are collected and raised in a single `DSSATCheckError`.
Each message clearly identifies the offending scenario and treatment:

```text
Simulation checks found 2 problems:
- Scenario 'dry_year', treatment 1: Weather data row 15, column 'rain': found -5.0. Value must be >= 0.
- Scenario 'base', treatment 3: FileX WSTA 'UFGA8201' expects station 'UFGA', but weather data has station 'DEMO'.
```

Fixing every reported problem allows the entire batch to pass on the next attempt.
No simulation folders or files are written if checks fail.

### The station rule (`WSTA`)

For an existing FileX, every weather input (both the base weather and any scenario
weather override) must match the 4-character station code of the field's `WSTA` for
**every** treatment selected in the run. A single `run_treatments()` call on an
existing FileX cannot mix treatments that require different weather stations.

For a FileX template with several fields, each field takes its station from that field's
weather data in the `weather=` dictionary. Fields may share a station code only if their
weather data is identical.

### Stop on first run failure

If a simulation fails during DSSAT execution (a nonzero exit status, an `ERROR.OUT`
file, or a missing-weather warning in `WARNING.OUT`), the batch stops immediately.
It does not continue running remaining simulations.

The error message identifies the failed scenario and treatment, as well as the paths
to all completed run directories kept on disk:

```text
DSSAT run failed for scenario 'base', treatment 5.
Run directories kept on disk:
- /path/to/dssat_sim_2026-09-30_120001/dssat_run_2026-09-30_120001
- /path/to/dssat_sim_2026-09-30_120002/dssat_run_2026-09-30_120002
```

You can inspect the kept run directories and `ERROR.OUT` to diagnose what went wrong.
There are no retries, timeouts, or parallel executions.
