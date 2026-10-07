# dssatlab

`dssatlab` aims to be a Python interface to the DSSAT-CSM. The goal is to let users work with DSSAT from Python and use the wider Python ecosystem (data, analysis, plotting, notebooks) to make DSSAT easier and more powerful to use.

[![PyPI version](https://img.shields.io/pypi/v/dssatlab)](https://pypi.org/project/dssatlab/)
[![Python versions](https://img.shields.io/pypi/pyversions/dssatlab)](https://pypi.org/project/dssatlab/)
[![Downloads](https://img.shields.io/pypi/dm/dssatlab)](https://pypi.org/project/dssatlab/)
[![Tests](https://github.com/AbdelrahmanAmr3/dssatlab/actions/workflows/tests.yml/badge.svg)](https://github.com/AbdelrahmanAmr3/dssatlab/actions/workflows/tests.yml)
[![License](https://img.shields.io/pypi/l/dssatlab)](LICENSE)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AbdelrahmanAmr3/dssatlab/blob/master/course/00_setup/lesson.ipynb)
[Course](course/README.md)

## Installation

```bash
pip install dssatlab
```

Requires Python 3.10 or newer. To upgrade later: `pip install --upgrade dssatlab`. To include plotting support: `pip install dssatlab[plot]`.

## Current stage

Version 0.22.0 adds a yield forecast from a copied `.FCX` through `Simulation`,
using your measured weather and `controls.forecast_date`. Each Summary row is
one historical weather year; `controls.years` counts those years. See the
[forecast tutorial](docs/guide/simulation.md#forecast-with-your-weather-data).

Version 0.21.1 adds `net_returns()` to compute net return at expected prices
from a DSSAT `.PRI` price file and summarize it across seasons. See
[seasonal economics](docs/guide/seasonal.md#compute-net-return-from-a-price-file).
Generated weather from a supplied climate file, sequence replicates and a fixed
random seed are covered in the [generated weather guide](docs/guide/generated-weather.md).

Version 0.20.0 adds new cultivars under your own code through experiment data
`cultivar.ecotype`, optional `name`, and every required coefficient. It also checks
each rotation component's fixed harvest dates against the stock weather anchor
and fixes edits to multi-digit FileX levels. See [new cultivars](docs/guide/new-cultivars.md).

Version 0.18.1 adds `import_nasa_power()` for a downloaded daily CSV. Simulation
checks use the effective planting date under START P for coverage and harvest
bounds. Stock weather selection follows DSSAT's lookup. See the [NASA POWER tutorial](docs/guide/simulation.md#import-a-nasa-power-file).

Version 0.18.0 adds stock weather and soil files copied unchanged, optional daily PAR in the weather template, deeper initial conditions, and fixes sequence weather coverage, inherited harvest dates and identical treatment rows.

Version 0.16.1 adds residue, tillage and harvest events per treatment or rotation component (including fallow), with RESID/HARVS checks and `harvest_management`.

Version 0.16.0 adds automatic irrigation and planting controls, irrigation in days after planting, and an irrigation efficiency dict with IRRIG/event checks.

Version 0.15.0 adds checked DSSAT simulation options, eight initial-condition detail
fields, and `initial_conditions: "off"` in experiment data. It also checks for a
one-row treatment number colliding with a sequence number before a `Simulation` or
`run_treatments` run (#168).
Zero runtime dependencies are preserved. See the [changelog](docs/changelog.md) and
[experiment data guide](docs/guide/experiment.md).

The project can get a working DSSAT into Python, run an existing experiment file, run a simulation from your own weather, soil, and management data, and read and plot the results. This part is done:

- [x] Find an existing DSSAT-CSM installation on Windows and Linux (including Google Colab)
- [x] Build DSSAT-CSM from the official release on Linux and Colab
- [x] Run one existing FileX
- [x] Turn your own daily weather into a strictly checked simulation and run it
- [x] Run a copied FileX with [generated weather from a climate file](docs/guide/generated-weather.md), sequence replicates and a fixed random seed
- [x] Turn your own soil data into a strictly checked simulation and run it
- [x] Turn your own management data (planting, irrigation, fertilizer) into a strictly checked simulation and run it
- [x] Set DSSAT simulation options (including photosynthesis and CO2), initial-condition details, or initial conditions off through experiment data
- [x] Set automatic irrigation and planting controls, day-based irrigation events, and irrigation efficiency through experiment data
- [x] Supply measured soil analysis and dated environment modifications through experiment data
- [x] Run all or selected FileX treatments and what-if scenarios in separate folders, and combine their summaries
- [x] Read six DSSAT output files (`Summary.OUT`, `PlantGro.OUT`, `SoilWat.OUT`, `PlantN.OUT`, `Weather.OUT`, `Evaluate.OUT`) and plot plant growth
- [x] Write a FileX from a template (single- or multi-treatment, one or several fields) for ten crops (maize, wheat, rice, soybean, potato, sorghum, pearl millet, barley, peanut, dry bean), and list installed crops and cultivars (`list_crops()`, `list_cultivars()`)
- [x] Run multi-year seasonal analyses (`controls: years`), check weather coverage across seasons, and compute season statistics across treatments and scenarios (`summarize_seasons()`)
- [x] Run multi-year crop rotations and sequence analyses in DSSAT's sequence mode (`Q`) from a sequence FileX or a FileX template (`rotation`), with experiment data per rotation component (planting, cultivar, fertilizer, irrigation, residues, tillage and harvest; fallows take the last three), per-component summary statistics and continuous soil water series

```python
import dssatlab as dl

dssat = dl.connect()                          # path to the DSSAT executable
result = dl.run("UFGA8201.MZX")               # all treatments
result = dl.run("UFGA8201.MZX", treatment=2)  # one treatment
print(result.run_dir, result.outputs)
```

How a run works:

- `run()` selects Y for `.FCX` (case-insensitive), otherwise Q when a selected treatment has several TREATMENTS rows, otherwise A for all treatments or C for one treatment. Q/Y write `DSSBatch.v48` in the FileX folder and move it into the run directory on success or failure; a failed launch deletes it. An existing batch file is refused and never overwritten. Q with several treatment numbers requires `treatment=n`. See the [run guide](docs/guide/run-filex.md#guards-before-dssat-starts) for the exact guard messages. A `Simulation` also forecasts from a copied `.FCX` with measured weather; see the [forecast tutorial](docs/guide/simulation.md#forecast-with-your-weather-data).
- DSSAT runs in the FileX's own folder, so weather and soil files beside the FileX are found. Newly created or updated files move into a new `dssat_run_<date>` folder beside the FileX; unchanged files stay beside it.
- The FileX filename can be at most 12 characters, including the extension, and must be exactly 12 for Q/Y, for example `MSKB8902.SQX`.
- A failed run raises `DSSATRunError` with the command, the end of DSSAT's console output and the start of `ERROR.OUT`. The run folder is kept so you can look inside.
- `run()` returns the files DSSAT wrote. Read outputs with `result.summary()`, `result.plant_growth()`, `result.soil_water()`, `result.plant_nitrogen()`, `result.weather()`, and `result.dssat_evaluation()`, or plot with `result.plot(variable)`.

Upgrading from 0.1.x on Linux or Colab: a DSSAT built by 0.1.x cannot run simulations, so the first `dl.install()` (or `dl.connect()` with consent) rebuilds it once.

## Your own weather, soil, and management data

Put your daily weather in the fixed **weather template**, optionally your soil profile in the **soil template**, and optionally your operations in the **management template** (or a plain dictionary), then create a `Simulation` for one treatment of an existing FileX:

```python
import dssatlab as dl

dl.write_weather_template("weather.csv")          # a correct weather example
dl.write_soil_template("soil.csv")                # a valid 3-layer soil profile
dl.write_management_template("management.yaml")   # a commented management template

sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    soil="soil.csv",
    management="management.yaml",
)

problems = sim.check()   # every problem at once, nothing is written; [] means fine
result = sim.run()       # checks first, then writes files and runs DSSAT
```

No FileX yet? For ten template crops (maize, wheat, rice, soybean, potato, sorghum, pearl millet, barley, peanut, dry bean), write one from a **FileX template** instead. Station, coordinates and elevation come from your weather data, and the soil ID from your soil data:

```python
dl.write_filex_template("filex.yaml")   # crop, treatment name(s), cultivar, planting
sim = dl.Simulation(filex_template="filex.yaml", weather="weather.csv", soil="soil.csv")
```

Templates also support multi-treatment experiments and several fields: supply a `treatments` list instead of `treatment_name`, optionally assign fields with `treatment_fields`, supply `weather` and `soil` per field as dictionaries (`{1: ..., 2: ...}`), vary each treatment with experiment data, and run all treatments via `run_treatments(filex_template=...)`. Supply `rotation` (a list of 2 to 99 crop and fallow components) to run a multi-year crop rotation in DSSAT's sequence mode. A leading fallow takes `start_date` before `end_date`; see the [sequence guide](docs/guide/sequence.md#start-with-a-fallow).

Values are in DSSAT's own units and nothing is converted:

- **Weather template**: comma-separated UTF-8 CSV with `station`, `latitude`, `longitude`, `elevation`, `date` (`YYYY-MM-DD`), `srad`, `tmax`, `tmin`, `rain`, and optional `tav`, `amp`, `refht`, `wndht` (default -99). Optional daily `par` is in mol/m2 per day, finite and from 0 to 100 inclusive; fill every row or omit the column. Station and coordinates repeat on every row; one row per calendar day without gaps or duplicates.
- **Soil template**: one soil profile, one row per layer. Required profile columns: `soil_id` (1 to 10 ASCII characters matching the FileX `ID_SOIL`), `salb`, `slro`, `sldr`, `slpf`. Required layer columns: `slb` (cm, strictly increasing), `slll`, `sdul`, `ssat` (strictly `slll < sdul < ssat`), `srgf`. Optional columns (`slnf`, `ssks`, `sbdm`, `sloc`, etc.) default to -99. Profile values repeat identically on every row.
- **Management template**: YAML file or Python dict organized under `treatments -> {treatment_number: ...}` with optional `planting`, `irrigation`, `fertilizer`, `residues`, `tillage`, `harvest`, `cultivar`, `initial_conditions`, `soil_analysis`, `environment`, and `controls` sections (`dl.write_experiment_template()` writes a commented file covering these sections; all are checked and applied to a copy of your FileX, see the Guide). All dates must be quoted ISO strings (`"YYYY-MM-DD"`). Omitted sections keep the FileX's original levels; empty event lists (`[]`) set level 0, including `environment`. Use the quoted `"off"` for `initial_conditions` or `soil_analysis`. The two new sections apply to treatments; rotation components reject them, and sweeps keep them in base data but cannot vary them as factors. PyYAML is optional (`pip install pyyaml` or `pip install dssatlab[yaml]`) and only imported when loading a YAML path; plain dictionaries require zero runtime dependencies.

Inputs for weather and soil can be given as a CSV path, a list of dicts, or a pandas DataFrame (pandas is never required). Management can be given as a YAML path or a plain dictionary.

With a copied FileX (`filex=`), weather also accepts a stock `.WTH` path or a list of paths, and soil a stock `.SOL` path. Weather files are copied byte for byte under upper-case names; soil keeps its own name. Stock files need names DSSAT looks up and pass narrow checks before running. See [stock weather](docs/guide/simulation.md#use-stock-weather-files) and [stock soil](docs/guide/soil.md#use-a-stock-soil-file).

What happens:

- `check()` reports every problem it finds: wrong or unknown columns/keys, empty or non-numeric values, bad dates or depths, gaps, impossible values (e.g. `tmax < tmin`, negative rain, non-increasing depths, water limits out of order, out-of-order event dates), and mismatches with the FileX (station code, start date coverage, case-sensitive `soil_id` match, planting date before start date). Nothing is fixed or filled in automatically. When management is supplied, a structured Checks report is printed.
- `run()` raises one `DSSATCheckError` listing all problems if there are any, before writing anything.
- Otherwise `run()` makes a new `dssat_sim_<date>` folder beside your FileX. With soil data, it writes `SOIL.SOL`; with stock soil, it copies that file unchanged. Both replace sibling `.SOL` files (a local `.SOL` beats DSSAT's own Soil folder); `.CUL`, `.ECO`, and `.SPE` files are copied as before. Without `soil`, sibling `.SOL` files are copied. With `management`, it edits the copied FileX to append new management levels and repoints the selected treatment row. Weather is generated from template data or copied from the stock paths into the simulation folder, DSSAT runs there, and output files are collected into a `dssat_run_<date>` folder inside it. Your original files are never changed.
- If DSSAT cannot use the soil profile, it exits with return code 99 and `run()` raises `DSSATRunError` with the `ERROR.OUT` message.
- DSSAT does not fail when weather is missing: it exits normally and gives -99 results. After the run, `run()` looks for DSSAT's "weather record not found" warning and raises `DSSATRunError` naming the first missing date.

Not built yet: chemical applications and automatic residue or harvest blocks, unit converters, reading other output files (such as `ET.OUT` or `OVERVIEW.OUT`), choosing a soil profile from DSSAT's own soil files, a copied FileX with more than one field, or crops outside the ten template crops, and parallel or resumed runs.

## Multi-treatment and scenario runs

Real studies often compare all treatments of an experiment or test what-if scenarios.
`run_treatments()` runs all treatments (or a selected subset) across named scenarios in a
single call:

```python
import dssatlab as dl

# Generate a scenario template pre-filled with treatment numbers from the FileX:
dl.write_scenario_template("scenarios.yaml", filex="UFGA8201.MZX")

# Run treatments across scenarios:
results = dl.run_treatments(
    "UFGA8201.MZX",
    weather="weather.csv",
    treatments=[1, 3],
    scenarios="scenarios.yaml",
)

# Access a specific run (keyed by (scenario, treatment)):
result = results["base", 1]

# Combine all summaries into a single table:
combined = dl.combine_summaries(results)
df = dl.to_dataframe(combined)

# For seasonal runs (controls years), compute statistics across seasons:
stats = dl.summarize_seasons(combined, variables=["HWAM"])
```

For every combination of planting dates, nitrogen rates or other experiment data sections, [`run_sweep()`](docs/guide/sweeps.md) generates scenarios and returns Summary rows with a column for each factor label, ready for `to_dataframe()` and `summarize_seasons()`.

How multi-treatment and scenario runs work:

- By default (`treatments=None`), runs all treatments in the FileX or FileX template (1..N); pass a list (e.g. `treatments=[1, 3]`) to select a subset.
- Exactly one of `filex` or `filex_template` is required; templates require `soil` data.
- Each `(scenario, treatment)` simulation runs in its own dated folder beside the FileX or template YAML (`dssat_sim_<date>`).
- Scenarios are defined in a YAML file or plain dictionary. Allowed overrides: `weather`, `soil`, `management`. Overrides replace the whole input without partial merging. The baseline un-overridden run is always included as `"base"`.
- For seasonal analyses, set `years` in experiment data `controls` (DSSAT's `NYERS`). `result.summary()` returns one row per season, and `summarize_seasons()` computes the mean, standard deviation, quartiles, and range across seasons.
- Every weather input must match the station code of `WSTA` for all selected treatments.
- All scenario and treatment inputs are verified before any run; a single `DSSATCheckError` lists all problems across all scenarios and treatments.
- A failed run halts execution immediately and reports all completed run directories kept on disk.

## Reading results

Read outputs directly from a run result or any run directory:

```python
import dssatlab as dl

# After a run:
summary_rows = result.summary()          # one dict per simulation (Summary.OUT)
growth_rows = result.plant_growth()       # daily crop development (PlantGro.OUT)
water_rows = result.soil_water()          # daily soil water by layer (SoilWat.OUT)
nitro_rows = result.plant_nitrogen()      # daily nitrogen uptake (PlantN.OUT)
weather_rows = result.weather()           # daily weather as DSSAT saw it (Weather.OUT)

# Convert to a pandas DataFrame (pandas is optional):
df = dl.to_dataframe(growth_rows)

# Plot plant growth against date (requires pip install dssatlab[plot]):
ax = result.plot("LAID")                 # leaf area index over time

# Compare treatments across run directories:
ax = dl.plot_plant_growth([run_dir_rainfed, run_dir_irrigated], "LAID")
```

Dates are parsed into `datetime.date` objects, DSSAT's `-99` missing values become `None`, and column names match DSSAT's own (`HWAM`, `ADAT`, `LAID`, `SWTD`, `NUPC`). Six output files are parsed (`Summary.OUT`, `PlantGro.OUT`, `SoilWat.OUT`, `PlantN.OUT`, `Weather.OUT`, and `Evaluate.OUT`); DSSAT evaluation dates stay as days after planting; other output files remain listed in `result.outputs`.

## Compare with your measurements

Put your observed data in a commented CSV template, using DSSAT's column names and
units. Compare it with one run result or the dictionary from `run_treatments()`:

```python
dl.write_observed_template("observed.csv")
# Replace the example rows with your observed data before continuing.
ev = dl.evaluate(result, "observed.csv")
print(ev.pairs)
print(ev.statistics)
dl.plot_evaluation(ev, variable="HWAM");  # requires dssatlab[plot]
```

Rows use `scenario` (`base` for one run) and `treatment`. Leave `date` blank for
Summary values such as `HWAM`; use `yyyy-mm-dd` for Plant growth measurements on a
day and for Summary date values such as `ADAT`. Evaluation reports simulated minus
observed errors, plus RMSE, mean bias and Willmott's d-index for variables with at
least two pairs. Observed data and matching problems are reported in one
`DSSATCheckError`. See the [evaluation guide](docs/guide/evaluate.md).

Already have DSSAT's own measurements? Read the FileA/FileT beside your FileX:

```python
result = dl.run("UFGA8201.MZX")  # keep UFGA8201.MZA and .MZT beside it
observed_a = dl.read_dssat_observed("UFGA8201.MZA")
observed_t = dl.read_dssat_observed("UFGA8201.MZT")
ev = dl.evaluate(result, observed_a)  # end-of-season values
dl.plot_observed(result, observed_t, "LAID")  # every FileT date, in or out of season
print(result.dssat_evaluation())  # or dl.read_dssat_evaluation(result.run_dir)
```

- `read_dssat_observed(path)` reads supported Summary or Plant growth measurements
  into observed rows under scenario `base`; `-99` measurements are omitted.
- `plot_observed(results, observed, variable)` draws Plant growth curves and
  measured points using optional matplotlib.
- `read_dssat_evaluation(run_dir)` and `RunResult.dssat_evaluation()` read DSSAT's
  `Evaluate.OUT` with its own column names and missing values as `None`.

Short dates need the matching FileX beside the FileA/FileT. DSSAT fills the
measured columns of `Evaluate.OUT` only in some runs (maize through `run()` with the
FileA beside the FileX); a `Simulation` leaves them `None`. No FileA/FileT is written. See [Use DSSAT's own measured data](docs/guide/evaluate.md#use-dssats-own-measured-data).

## Which crops and cultivars can I use?

Experiment data accepts optional `cultivar.coefficients` for coefficient sweeps with `run_sweep()`; each simulation gets its own changed `.CUL` copy and the source stays unchanged. See the [sweep guide](docs/guide/sweeps.md#cultivar-coefficient-sweep).

To define a code absent from the crop's `.CUL`, supply `ecotype`, optional `name`,
and every coefficient of its first table. The simulation copy keeps your code.
See the [new cultivar tutorial](docs/guide/new-cultivars.md).

Inspect which template crops and cultivars are installed before writing a FileX:

```python
crops = dl.list_crops()                 # template crops found in Genotype
cultivars = dl.list_cultivars("soybean") # cultivar codes and names from SBGRO048.CUL
df = dl.to_dataframe(cultivars)
```

- `list_crops(executable=None)` lists the ten template crops (maize, wheat, rice,
  soybean, potato, sorghum, pearl millet, barley, peanut, dry bean) whose genotype
  files exist in your DSSAT data directory.
- `list_cultivars(crop, executable=None)` lists that crop's cultivar codes and names
  in `.CUL` file order.
- Both return rows of plain dicts accepted by `to_dataframe()`, without modifying
  saved config or touching the network.

