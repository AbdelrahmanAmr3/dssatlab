# dssatlab

`dssatlab` aims to be a Python interface to the DSSAT-CSM. The goal is to let users work with DSSAT from Python and use the wider Python ecosystem (data, analysis, plotting, notebooks) to make DSSAT easier and more powerful to use.

[![PyPI version](https://img.shields.io/pypi/v/dssatlab)](https://pypi.org/project/dssatlab/)
[![Python versions](https://img.shields.io/pypi/pyversions/dssatlab)](https://pypi.org/project/dssatlab/)
[![Downloads](https://img.shields.io/pypi/dm/dssatlab)](https://pypi.org/project/dssatlab/)
[![Tests](https://github.com/AbdelrahmanAmr3/dssatlab/actions/workflows/tests.yml/badge.svg)](https://github.com/AbdelrahmanAmr3/dssatlab/actions/workflows/tests.yml)
[![License](https://img.shields.io/pypi/l/dssatlab)](LICENSE)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AbdelrahmanAmr3/dssatlab/blob/master/notebook/dssatlab_walkthrough.ipynb)

## Installation

```bash
pip install dssatlab
```

Requires Python 3.10 or newer. To upgrade later: `pip install --upgrade dssatlab`. To include plotting support: `pip install dssatlab[plot]`.

## Current stage

The project can get a working DSSAT into Python, run an existing experiment file, run a simulation from your own weather, soil, and management data, and read and plot the results. This part is done:

- [x] Find an existing DSSAT-CSM installation on Windows and Linux (including Google Colab)
- [x] Build DSSAT-CSM from the official release on Linux and Colab
- [x] Run one existing FileX
- [x] Turn your own daily weather into a strictly checked simulation and run it
- [x] Turn your own soil data into a strictly checked simulation and run it
- [x] Turn your own management data (planting, irrigation, fertilizer) into a strictly checked simulation and run it
- [x] Run all or selected FileX treatments and what-if scenarios in separate folders, and combine their summaries
- [x] Read five DSSAT output files (`Summary.OUT`, `PlantGro.OUT`, `SoilWat.OUT`, `PlantN.OUT`, `Weather.OUT`) and plot plant growth

```python
import dssatlab as dl

dssat = dl.connect()                          # path to the DSSAT executable
result = dl.run("UFGA8201.MZX")               # all treatments
result = dl.run("UFGA8201.MZX", treatment=2)  # one treatment
print(result.run_dir, result.outputs)
```

How a run works:

- DSSAT runs in the FileX's own folder, so weather and soil files beside the FileX are found. Its output files are then moved into a new `dssat_run_<date>` folder beside the FileX, and your FileX folder is left as it was.
- The FileX filename can be at most 12 characters, including the extension (DSSAT's own limit), for example `UFGA8201.MZX`.
- A failed run raises `DSSATRunError` with the command, the end of DSSAT's console output and the start of `ERROR.OUT`. The run folder is kept so you can look inside.
- `run()` returns the files DSSAT wrote. Read outputs with `result.summary()`, `result.plant_growth()`, `result.soil_water()`, `result.plant_nitrogen()`, and `result.weather()`, or plot with `result.plot(variable)`. Building experiments from Python is not built yet.

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

Values are in DSSAT's own units and nothing is converted:

- **Weather template**: comma-separated UTF-8 CSV with `station`, `latitude`, `longitude`, `elevation`, `date` (`YYYY-MM-DD`), `srad`, `tmax`, `tmin`, `rain`, and optional `tav`, `amp`, `refht`, `wndht` (default -99). Station and coordinates repeat on every row; one row per calendar day without gaps or duplicates.
- **Soil template**: one soil profile, one row per layer. Required profile columns: `soil_id` (1 to 10 ASCII characters matching the FileX `ID_SOIL`), `salb`, `slro`, `sldr`, `slpf`. Required layer columns: `slb` (cm, strictly increasing), `slll`, `sdul`, `ssat` (strictly `slll < sdul < ssat`), `srgf`. Optional columns (`slnf`, `ssks`, `sbdm`, `sloc`, etc.) default to -99. Profile values repeat identically on every row.
- **Management template**: YAML file or Python dict organized under `treatments -> {treatment_number: ...}` with optional `planting`, `irrigation`, `fertilizer`, `cultivar`, `initial_conditions`, and `controls` sections (`dl.write_experiment_template()` writes a commented file covering all six; the last three are checked and applied to a copy of your FileX, see the Guide). All dates must be quoted ISO strings (`"YYYY-MM-DD"`). Omitted sections keep the FileX's original levels; empty lists (`[]`) specify no events (level 0). PyYAML is optional (`pip install pyyaml` or `pip install dssatlab[yaml]`) and only imported when loading a YAML path; plain dictionaries require zero runtime dependencies.

Inputs for weather and soil can be given as a CSV path, a list of dicts, or a pandas DataFrame (pandas is never required). Management can be given as a YAML path or a plain dictionary.

What happens:

- `check()` reports every problem it finds: wrong or unknown columns/keys, empty or non-numeric values, bad dates or depths, gaps, impossible values (e.g. `tmax < tmin`, negative rain, non-increasing depths, water limits out of order, non-ascending event dates), and mismatches with the FileX (station code, start date coverage, case-sensitive `soil_id` match, planting date before start date). Nothing is fixed or filled in automatically. When management is supplied, a structured Checks report is printed.
- `run()` raises one `DSSATCheckError` listing all problems if there are any, before writing anything.
- Otherwise `run()` makes a new `dssat_sim_<date>` folder beside your FileX. With `soil`, it writes `SOIL.SOL` and does not copy sibling `.SOL` files (a local `.SOL` beats DSSAT's own Soil folder); `.CUL`, `.ECO`, and `.SPE` files are copied as before. Without `soil`, sibling `.SOL` files are copied. With `management`, it edits the copied FileX to append new management levels and repoints the selected treatment row. The generated weather file is written to the simulation folder, DSSAT runs there, and output files are collected into a `dssat_run_<date>` folder inside it. Your original files are never changed.
- If DSSAT cannot use the soil profile, it exits with return code 99 and `run()` raises `DSSATRunError` with the `ERROR.OUT` message.
- DSSAT does not fail when weather is missing: it exits normally and gives -99 results. After the run, `run()` looks for DSSAT's "weather record not found" warning and raises `DSSATRunError` naming the first missing date.

Not built yet: other management operations (tillage, organic amendments, harvest, chemicals), unit converters, reading other output files (such as `ET.OUT` or `OVERVIEW.OUT`), choosing a soil profile from DSSAT's own soil files, building a FileX from scratch, and parallel or resumed runs.

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
```

How multi-treatment and scenario runs work:

- By default (`treatments=None`), runs all treatments in the FileX; pass a list (e.g. `treatments=[1, 3]`) to select a subset.
- Each `(scenario, treatment)` simulation runs in its own dated folder beside the FileX (`dssat_sim_<date>`).
- Scenarios are defined in a YAML file or plain dictionary. Allowed overrides: `weather`, `soil`, `management`. Overrides replace the whole input without partial merging. The baseline un-overridden run is always included as `"base"`.
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

Dates are parsed into `datetime.date` objects, DSSAT's `-99` missing values become `None`, and column names match DSSAT's own (`HWAM`, `ADAT`, `LAID`, `SWTD`, `NUPC`). Five output files are parsed (`Summary.OUT`, `PlantGro.OUT`, `SoilWat.OUT`, `PlantN.OUT`, and `Weather.OUT`); other output files remain listed in `result.outputs`.
