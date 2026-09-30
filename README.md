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

The project can get a working DSSAT into Python, run an existing experiment file, and run a simulation from your own weather, soil, and management data. This part is done:

- [x] Find an existing DSSAT-CSM installation on Windows and Linux (including Google Colab)
- [x] Build DSSAT-CSM from the official release on Linux and Colab
- [x] Run one existing FileX
- [x] Turn your own daily weather into a strictly checked simulation and run it
- [x] Turn your own soil data into a strictly checked simulation and run it
- [x] Turn your own management data (planting, irrigation, fertilizer) into a strictly checked simulation and run it

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
- `run()` returns the files DSSAT wrote and does not read them. Reading input or output files, building experiments and plotting are not built yet.

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
- **Management template**: YAML file or Python dict organized under `treatments -> {treatment_number: ...}` with optional `planting`, `irrigation`, and `fertilizer` sections. All dates must be quoted ISO strings (`"YYYY-MM-DD"`). Omitted sections keep the FileX's original levels; empty lists (`[]`) specify no events (level 0). PyYAML is optional (`pip install pyyaml` or `pip install dssatlab[yaml]`) and only imported when loading a YAML path; plain dictionaries require zero runtime dependencies.

Inputs for weather and soil can be given as a CSV path, a list of dicts, or a pandas DataFrame (pandas is never required). Management can be given as a YAML path or a plain dictionary.

What happens:

- `check()` reports every problem it finds: wrong or unknown columns/keys, empty or non-numeric values, bad dates or depths, gaps, impossible values (e.g. `tmax < tmin`, negative rain, non-increasing depths, water limits out of order, non-ascending event dates), and mismatches with the FileX (station code, start date coverage, case-sensitive `soil_id` match, planting date before start date). Nothing is fixed or filled in automatically. When management is supplied, a structured Checks report is printed.
- `run()` raises one `DSSATCheckError` listing all problems if there are any, before writing anything.
- Otherwise `run()` makes a new `dssat_sim_<date>` folder beside your FileX. With `soil`, it writes `SOIL.SOL` and does not copy sibling `.SOL` files (a local `.SOL` beats DSSAT's own Soil folder); `.CUL`, `.ECO`, and `.SPE` files are copied as before. Without `soil`, sibling `.SOL` files are copied. With `management`, it edits the copied FileX to append new management levels and repoints the selected treatment row. The generated weather file is written to the simulation folder, DSSAT runs there, and output files are collected into a `dssat_run_<date>` folder inside it. Your original files are never changed.
- If DSSAT cannot use the soil profile, it exits with return code 99 and `run()` raises `DSSATRunError` with the `ERROR.OUT` message.
- DSSAT does not fail when weather is missing: it exits normally and gives -99 results. After the run, `run()` looks for DSSAT's "weather record not found" warning and raises `DSSATRunError` naming the first missing date.

Not built yet: other management operations (tillage, organic amendments, harvest, chemicals), unit converters, reading output files other than the summary and plant growth, choosing a soil profile from DSSAT's own soil files, FileX authoring, and more than one treatment per `Simulation`.

## Reading results

Read summary and plant growth outputs directly from a run result or any run directory:

```python
import dssatlab as dl

# After a run:
summary_rows = result.summary()          # one dict per simulation (yield, dates, ...)
growth_rows = result.plant_growth()       # one dict per simulation day (leaf area, ...)

# Convert to a pandas DataFrame (pandas is optional):
df = dl.to_dataframe(growth_rows)

# Plot a variable against date (requires pip install dssatlab[plot]):
ax = result.plot("LAID")                 # leaf area index over time

# Compare treatments across run directories:
ax = dl.plot_plant_growth([run_dir_rainfed, run_dir_irrigated], "LAID")
```

Dates are parsed into `datetime.date` objects, DSSAT's `-99` missing values become `None`, and column names match DSSAT's own (`HWAM`, `ADAT`, `LAID`). Only `Summary.OUT` and `PlantGro.OUT` are read; other output files remain listed in `result.outputs`.

