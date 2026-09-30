# Run a Simulation from your weather data

A `Simulation` combines one treatment of an existing FileX with your daily weather
data, or creates a FileX from a template and your weather and soil data.
To supply your own soil data, see [Run with soil data](soil.md).
Prepare the FileX and its supporting files, then
[find or install a DSSAT executable](install.md). The examples use
`UFGA8201.MZX`; replace it with your FileX path and choose one of its treatments.

## Start from a FileX template

For maize or wheat, supply a FileX template instead of an existing FileX:

```python
import dssatlab as dl

dl.write_filex_template("filex.yaml")  # Edit the crop, cultivar and planting values.
sim = dl.Simulation(
    filex_template="filex.yaml", weather="weather.csv", soil="soil.csv",
    executable=r"C:\DSSAT48\DSCSM048.EXE",
)
problems = sim.check()
```

`filex_template` accepts a YAML path (optional PyYAML required) or a dict with the
same fields (no extra dependency). Supply exactly one of `filex` and
`filex_template`; both or neither raise `DSSATCheckError` from `check()` and
`run()`. The existing positional order remains `filex, treatment, weather,
executable`, with defaults `None, 1, None, None`. Templates require `soil` and
use treatment 1. Station and soil IDs come from your data. The simulation starts
on the template's planting date, which must be covered by weather, unless
experiment controls override the start date.

Template checks find the data directory beside the explicit or discovered DSSAT
executable and read its `Genotype` folder without saving configuration or writing
files. `management` and `name` work as with an existing FileX: checks inspect the
skeleton in memory, then experiment overrides apply to the generated FileX.
Cultivar overrides must keep the template's crop and use its fixed model's table.

`sim.run()` creates a fresh simulation folder beside the YAML file, or in the
current directory for a dict. It writes the FileX, weather and `SOIL.SOL`, and
copies the crop's `.CUL`, `.ECO` and `.SPE` files from `Genotype` (`MZCER048` for
maize, `WHCER048` for wheat). Your original files are unchanged.
`run_treatments()` continues to accept an existing FileX path only.

## Prepare the weather template

Create an example CSV in a notebook cell:

```python
import dssatlab as dl

dl.write_weather_template("weather.csv")
```

This writes a UTF-8 weather template with seven example days, March 1–7, 2021,
for station `DEMO`. Replace those example values with your weather data before
running a Simulation. An existing path raises `DSSATError`, so rerunning this
cell does not overwrite your weather data.

Use a comma-separated UTF-8 CSV with the exact lower-case column names below.
Columns may appear in any order. Unknown or repeated columns fail the checks.
Values use DSSAT's own units; nothing is converted.

| Column | Required | Meaning and checks |
| --- | --- | --- |
| `station` | Yes | Exactly four ASCII letters or digits; match the first four characters of the treatment's FileX `WSTA` unless experiment overrides are supplied |
| `latitude` | Yes | Degrees north, from -90 to 90 |
| `longitude` | Yes | Degrees east, from -180 to 180 |
| `elevation` | Yes | Station elevation in m, from -500 to 9000 |
| `date` | Yes | Calendar date as `YYYY-MM-DD` |
| `srad` | Yes | Daily solar radiation in MJ/m² per day, from 0 to 45 |
| `tmax` | Yes | Daily maximum temperature in °C, from -60 to 60; must be at least `tmin` |
| `tmin` | Yes | Daily minimum temperature in °C, from -60 to 60 |
| `rain` | Yes | Daily rainfall in mm, from 0 to 1000 |
| `tav` | No | Station average temperature in °C |
| `amp` | No | Station temperature amplitude in °C |
| `refht` | No | Reference height in m |
| `wndht` | No | Wind measurement height in m |

All ranges include their endpoints. Required numeric values must be non-empty
and finite. Supply one row per calendar day in ascending order, without gaps or
duplicates. `station`, `latitude`, `longitude`, and `elevation` must be identical
on every row.

Optional columns may be omitted or left empty; they are written as `-99` (not
given). Supplied optional values must be finite numbers. The weather file uses
their values from the first row, so put station values there. The checks do not
require optional values to be identical across rows.

## Create a Simulation and inspect the checks

Once you have edited `weather.csv`, create the Simulation:

```python
import dssatlab as dl

sim = dl.Simulation("UFGA8201.MZX", treatment=1, weather="weather.csv")
problems = sim.check()
for problem in problems:
    print(problem)
```

Construction only stores the supplied values. `check()` reads the weather data
and FileX and returns a list of problem strings; `[]` means the checks passed.
It writes nothing and does not run DSSAT. It reports the problems it finds
together, without sorting, filling gaps, or repairing your data.

The FileX checks locate the selected treatment and follow its `FL` and `SM`
references to the field's `WSTA` and the simulation controls' `START` and `SDATE`.
The weather station must match the first four characters of `WSTA`, including
case. `WSTA` must have four or eight characters, and `SDATE` must contain five
digits: two for the year and three for the day of year. The FileX filename must
also fit the 12-character limit.

When `management` supplies experiment overrides for the selected treatment,
the copied FileX uses the weather data's station and, if supplied, the soil
data's profile ID. These IDs need not match the source FileX. An omitted or empty
treatment entry keeps the matching checks above.

Independently of experiment overrides, pass `name="own site"` to write a name
into the copied treatment's `TNAME` (or `TNAM`) column, reported as `TNAM` in
Summary. Both `name=None` (the default) and `name="base"` retain the source
treatment name. Names that exceed the FileX column width are rejected during
checks, including when no experiment data is supplied. Giving a name alone
leaves the copied field IDs unchanged.

**Start-date coverage is checked only when `START` is `S`.** In that case, a
weather date must match the two-digit year and day of year in `SDATE`. These
checks do not establish how long the crop will need weather. Supply weather for
the full period DSSAT will simulate. They also do not check that the DSSAT
executable can run.

## Run after the checks

Continue with the `sim` created above:

```python
try:
    result = sim.run()
except dl.DSSATCheckError as error:
    for problem in error.problems:
        print(problem)
except dl.DSSATRunError as error:
    print(error)
else:
    print(result.run_dir)
    for path in result.outputs:
        print(path)
```

`sim.run()` repeats the checks. If any problems remain, it raises one
`DSSATCheckError` containing the list in `error.problems`, before creating the
simulation folder or writing DSSAT files.

After the checks pass, it creates a new `dssat_sim_YYYY-MM-DD_HHMMSS` folder beside
your FileX, adding a numeric suffix if needed. That simulation folder contains:

- A copy of the FileX.
- Copies of every `.SOL`, `.CUL`, `.ECO`, and `.SPE` file directly beside the
  original FileX; suffix matching ignores case. (When you supply your own soil data
  via `soil=...`, `Simulation.run()` writes `SOIL.SOL` and does not copy sibling
  `.SOL` files; see [Run with soil data](soil.md).)
- One generated `.WTH` weather file from your weather data.
- A `dssat_run_YYYY-MM-DD_HHMMSS` run directory containing the files collected
  after DSSAT exits.

The source weather CSV and existing weather files are not copied. If `WSTA` has
eight characters, the generated weather file is named `<WSTA>.WTH`. If it has
four, the name is `<WSTA><two-digit year from SDATE>01.WTH`. This naming uses
`SDATE` for every `START` option. Your original FileX and supporting files are
left unchanged; DSSAT runs against the copies.

With experiment overrides, `WSTA` is the weather data's four-character station,
so the weather filename uses that station and the year from `SDATE`.

A successful call returns the same [RunResult fields](run-filex.md#inspect-the-run-result)
as `dl.run()`. The simulation folder is kept on failure. For failures after DSSAT
has run, inspect the run directory reported in the error.

After DSSAT returns successfully, `Simulation.run()` scans `WARNING.OUT` in the
run directory for `Weather record not found for YR DOY:`. DSSAT can exit with
status `0` and produce `-99` results when weather is missing. In this case,
`Simulation.run()` raises `DSSATRunError` with the first missing date reported in
that file. Extend the weather data through that date and the remaining days the
crop needs, then run again.

To select a DSSAT executable for a Simulation, pass `executable` at construction:

```python
import dssatlab as dl

sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    executable=r"C:\DSSAT48\DSCSM048.EXE",
)
```

Replace that path with your DSSAT executable. As with `dl.run()`, an explicit
`executable` leaves saved config unchanged. Otherwise discovery is noninteractive
when the Simulation runs.

## Use a DataFrame or plain rows

If pandas is already part of your notebook environment, pass a DataFrame with
the same weather template columns:

```python
import pandas as pd
import dssatlab as dl

weather = pd.read_csv("weather.csv", keep_default_na=False)
sim = dl.Simulation("UFGA8201.MZX", treatment=1, weather=weather)
print(sim.check())
```

`keep_default_na=False` preserves blank optional cells as empty strings. Numeric
`NaN` and infinity fail the checks, including in optional columns. Required
values must still be supplied.

pandas is optional; dssatlab does not import or require it. You can also pass a
list of dictionaries with the weather template names as keys. The same checks
apply to CSV, DataFrame, and list inputs. In-memory dates may be `YYYY-MM-DD`
strings, Python `date` objects, or midnight `datetime` values. Times other than
midnight fail the checks. dssatlab does not modify the supplied weather data.
