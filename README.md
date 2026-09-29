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

Requires Python 3.10 or newer. To upgrade later: `pip install --upgrade dssatlab`.

## Current stage

The project can get a working DSSAT into Python, run an existing experiment file, and run a simulation from your own weather and soil data. This part is done:

- [x] Find an existing DSSAT-CSM installation on Windows and Linux (including Google Colab)
- [x] Build DSSAT-CSM from the official release on Linux and Colab
- [x] Run one existing FileX
- [x] Turn your own daily weather into a strictly checked simulation and run it
- [x] Turn your own soil data into a strictly checked simulation and run it

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

## Your own weather and soil data

Put your daily weather in the fixed **weather template**, and optionally your soil profile in the **soil template**, then create a `Simulation` for one treatment of an existing FileX:

```python
import dssatlab as dl

dl.write_weather_template("weather.csv")       # a correct weather example
dl.write_soil_template("soil.csv")             # a valid 3-layer soil profile

sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    soil="soil.csv",
)

problems = sim.check()   # every problem at once, nothing is written; [] means fine
result = sim.run()       # checks first, then writes files and runs DSSAT
```

The templates are comma-separated UTF-8 CSVs with exact lower-case column names, in any order. Values are in DSSAT's own units and nothing is converted:

- **Weather template**: `station`, `latitude`, `longitude`, `elevation`, `date` (`YYYY-MM-DD`), `srad`, `tmax`, `tmin`, `rain`, and optional `tav`, `amp`, `refht`, `wndht` (default -99). Station and coordinates repeat on every row; one row per calendar day without gaps or duplicates.
- **Soil template**: one soil profile, one row per layer. Required profile columns: `soil_id` (1 to 10 ASCII characters matching the FileX `ID_SOIL`), `salb`, `slro`, `sldr`, `slpf`. Required layer columns: `slb` (cm, strictly increasing), `slll`, `sdul`, `ssat` (strictly `slll < sdul < ssat`), `srgf`. Optional columns (`slnf`, `ssks`, `sbdm`, `sloc`, etc.) default to -99. Profile values repeat identically on every row.

Inputs can be given as a CSV path, a list of dicts with the same keys, or a pandas DataFrame (pandas is never required).

What happens:

- `check()` reports every problem it finds: wrong or unknown columns, empty or non-numeric values, bad dates or depths, gaps, impossible values (e.g. `tmax < tmin`, negative rain, non-increasing depths, water limits out of order), and mismatches with the FileX (station code, start date coverage, case-sensitive `soil_id` match). Nothing is fixed or filled in automatically.
- `run()` raises one `DSSATCheckError` listing all problems if there are any, before writing anything.
- Otherwise `run()` makes a new `dssat_sim_<date>` folder beside your FileX. With `soil`, it writes `SOIL.SOL` and does not copy sibling `.SOL` files (a local `.SOL` beats DSSAT's own Soil folder); `.CUL`, `.ECO`, and `.SPE` files are copied as before. Without `soil`, sibling `.SOL` files are copied. The generated weather file is written to the simulation folder, DSSAT runs there, and output files are collected into a `dssat_run_<date>` folder inside it. Your original files are not changed.
- If DSSAT cannot use the soil profile, it exits with return code 99 and `run()` raises `DSSATRunError` with the `ERROR.OUT` message.
- DSSAT does not fail when weather is missing: it exits normally and gives -99 results. After the run, `run()` looks for DSSAT's "weather record not found" warning and raises `DSSATRunError` naming the first missing date.

Not built yet: management data, unit converters, reading DSSAT's output files, choosing a soil profile from DSSAT's own soil files, and more than one treatment per `Simulation`.
