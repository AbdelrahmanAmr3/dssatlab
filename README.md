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

The project can get a working DSSAT into Python, run an existing experiment file, and run a simulation from your own weather data. This part is done:

- [x] Find an existing DSSAT-CSM installation on Windows and Linux (including Google Colab)
- [x] Build DSSAT-CSM from the official release on Linux and Colab
- [x] Run one existing FileX
- [x] Turn your own daily weather into a strictly checked simulation and run it

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

## Your own weather data

Put your daily weather in the fixed **weather template**, then create a `Simulation` for one treatment of an existing FileX:

```python
import dssatlab as dl

dl.write_weather_template("weather.csv")       # a correct example to start from
sim = dl.Simulation("UFGA8201.MZX", treatment=1, weather="weather.csv")

problems = sim.check()   # every problem at once, nothing is written; [] means fine
result = sim.run()       # checks first, then writes the files and runs DSSAT
```

The template is one comma-separated UTF-8 CSV with these exact lower-case column names, in any order. Values are in DSSAT's own units and nothing is converted:

| Column | Meaning |
|---|---|
| `station` | four letters or digits, the weather station code |
| `latitude`, `longitude` | degrees |
| `elevation` | m |
| `date` | `YYYY-MM-DD`, one row per calendar day, sorted, no gaps or duplicates |
| `srad` | solar radiation, MJ/m2 per day |
| `tmax`, `tmin` | degrees C |
| `rain` | mm |
| `tav`, `amp`, `refht`, `wndht` | optional; left empty they are written as -99 (not given) |

Station, latitude, longitude and elevation must be identical on every row. The weather can also be given as a list of dicts with the same keys, or as a pandas DataFrame (pandas is never required).

What happens:

- `check()` reports every problem it finds: wrong or unknown columns, empty or non-numeric values, bad dates, gaps, impossible values (for example `tmax` below `tmin`, negative rain), and, by reading the chosen treatment in your FileX, a station that does not match the FileX or weather that does not cover its start date. Nothing is fixed or filled in automatically.
- `run()` raises one `DSSATCheckError` listing all problems if there are any, before writing anything.
- Otherwise `run()` makes a new `dssat_sim_<date>` folder beside your FileX holding a copy of the FileX, your `.SOL`, `.CUL`, `.ECO` and `.SPE` files that sit beside it, and the generated weather file, then runs DSSAT there. The run's output files are in the `dssat_run_<date>` folder inside it. Your own files and folder are not changed.
- DSSAT does not fail when weather is missing: it exits normally and gives -99 results. So after the run, `run()` looks for DSSAT's "weather record not found" warning and raises `DSSATRunError` naming the first missing date.

Not built yet: soil and management data, unit converters, reading DSSAT's output files, and more than one treatment per `Simulation`.
