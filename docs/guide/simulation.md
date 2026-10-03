# Run a Simulation from your weather data

A `Simulation` combines one treatment of an existing FileX with your daily weather
data or stock weather files, or creates a FileX from a template and your weather and soil data.
To supply your own soil data, see [Run with soil data](soil.md).
Prepare the FileX and its supporting files, then
[find or install a DSSAT executable](install.md). The examples use
`UFGA8201.MZX`; replace it with your FileX path and choose one of its treatments.

## Start from a FileX template

For any of the ten template crops, supply a FileX template instead of an existing FileX:

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
default to treatment 1. Station and soil IDs come from your data. The simulation starts
on the template's planting date, which must be covered by weather, unless
experiment controls override the start date.

### Template crops

The FileX template supports ten crops, each with one fixed DSSAT model:

| Crop name | Crop code | Model | Genotype files |
| --- | --- | --- | --- |
| `maize` | `MZ` | `MZCER048` | `MZCER048.CUL`, `MZCER048.ECO`, `MZCER048.SPE` |
| `wheat` | `WH` | `CSCER048` | `WHCER048.CUL`, `WHCER048.ECO`, `WHCER048.SPE` |
| `rice` | `RI` | `RICER048` | `RICER048.CUL`, `RICER048.SPE` |
| `soybean` | `SB` | `CRGRO048` | `SBGRO048.CUL`, `SBGRO048.ECO`, `SBGRO048.SPE` |
| `potato` | `PT` | `PTSUB048` | `PTSUB048.CUL`, `PTSUB048.ECO`, `PTSUB048.SPE` |
| `sorghum` | `SG` | `SGCER048` | `SGCER048.CUL`, `SGCER048.ECO`, `SGCER048.SPE` |
| `pearl millet` | `ML` | `MLCER048` | `MLCER048.CUL`, `MLCER048.ECO`, `MLCER048.SPE` |
| `barley` | `BA` | `CSCER048` | `BACER048.CUL`, `BACER048.ECO`, `BACER048.SPE` |
| `peanut` | `PN` | `CRGRO048` | `PNGRO048.CUL`, `PNGRO048.ECO`, `PNGRO048.SPE` |
| `dry bean` | `BN` | `CRGRO048` | `BNGRO048.CUL`, `BNGRO048.ECO`, `BNGRO048.SPE` |

Rice requires only `.CUL` and `.SPE` because DSSAT ships no rice `.ECO`. Legumes (`soybean`, `peanut`, `dry bean`) are automatically written with nitrogen fixation enabled (`SYMBI Y`).

### Planting fields and harvest date

The template `planting` section accepts the standard fields (`date`, `method`, `distribution`, `population`, `row_spacing`, `depth`) and two optional fields:

- `planting_material_weight`: seed piece / planting material weight (`PLWT`) in kg/ha.
- `sprout_length`: sprout length (`SPRL`) in cm.

In addition, an optional top-level `harvest_date` may be specified as a quoted ISO date (`"YYYY-MM-DD"`). When given, dssatlab writes a `*HARVEST DETAILS` section (`HDATE`, stage code `GS000`) and sets harvest management to `R` (harvest on reported date). When omitted, the crop harvests at maturity (`M`). `harvest_date` must be after the planting date and within the weather data.

**Potato requirements**: Potato requires all three fields: `planting_material_weight`, `sprout_length`, and `harvest_date`. Each missing field is reported as a separate problem. For other crops, these fields are optional.

### Crop rotations

To simulate a multi-year crop rotation (such as maize followed by fallow, wheat, and fallow) from scratch, provide `rotation`—a list of 2 to 99 crop or fallow components—instead of the single-crop keys (`crop`, `cultivar`, `planting`, `harvest_date`). A leading fallow takes `start_date` before `end_date`. See [A rotation from the FileX template](sequence.md#a-rotation-from-the-filex-template) for details on template structure, date checks, and multi-cycle simulations.

### Named treatments and multi-treatment experiments

The FileX template accepts either `treatment_name` (one treatment) or `treatments`, a list of 1 to 99 treatment names. Supply exactly one of the two:

```yaml
# Single treatment:
treatment_name: "My treatment"
```

```yaml
# Or multiple treatments:
treatments:
  - "Control"
  - "Nitrogen 120"
  - "Irrigated"
```

Treatments are numbered 1..N in the order listed. In the written FileX, `EXP.DETAILS` and simulation controls (`SNAME`) use the first treatment name. Every treatment starts from the template's cultivar, planting details, and optional harvest date.

To vary treatments, supply **experiment data** keyed by treatment number (`treatments: {2: {...}, 3: {...}}`). Any section you give—such as `fertilizer`, `irrigation`, `cultivar`, `planting`, `residues`, `tillage`, `harvest`, `initial_conditions`, or `controls`—adds a new level and points that treatment to it:

```yaml
# experiment.yaml
treatments:
  2:
    fertilizer:
      - {date: "2021-03-15", material: "FE005", application: "AP001", depth: 5, n: 60}
      - {date: "2021-04-15", material: "FE005", application: "AP001", depth: 5, n: 60}
  3:
    cultivar:
      crop: "MZ"
      code: "IB0060"
    irrigation:
      - {date: "2021-03-20", amount: 30, method: "IR001"}
      - {date: "2021-04-10", amount: 30, method: "IR001"}
```

- A treatment with no entry (like treatment 1, `"Control"`) remains the unchanged base.
- Residue, tillage and harvest events use the [field operation fields](experiment.md#residues-tillage-and-harvest), including RESID/HARVS checks and `controls.harvest_management` (HARVS: `"A"`, `"M"`, `"R"`, `"D"`).
- Automatic irrigation and planting use the [controls fields](experiment.md#automatic-management); the template's IRRIG R and PLANT R defaults stay unchanged until overridden. Irrigation also accepts [day events and an efficiency dict](management.md#irrigation-timing-and-efficiency), checked against IRRIG.
- `initial_conditions: "off"` points the treatment at IC 0 instead of adding a level; DSSAT supplies initial soil water and nitrogen. See [simulation options and initial-condition details](experiment.md).
- Each entry receives its own new level; equal levels are not shared (ADR 0010).
- When you create a single `Simulation(filex_template="filex.yaml", treatment=k, ...)`, `treatment` can be any integer from 1 to N (`treatment=1` by default). Out-of-range treatment numbers are rejected by `check()` with the valid range.
- When `sim.run()` executes, the generated FileX in the simulation folder holds the **whole experiment**: every treatment with its experiment data applied, so you can open or run the entire experiment in DSSAT. If a scenario name is supplied, it is written to the selected treatment row only. Only one weather file is written, for the selected treatment's start year, so give every treatment a start date in that year if you plan to run the whole experiment.
- To run every treatment at once, pass `filex_template=` to `run_treatments()` (see [Run treatments and scenarios](scenarios.md)).

### Several fields in one experiment

In DSSAT, an experiment can define multiple fields, allowing treatments to grow at different locations or on different soils.

The FileX template supports multiple fields through the optional `treatment_fields` list beside `treatments`. Provide one field number per treatment, numbered 1..K without gaps:

```yaml
crop: "maize"
treatments:
  - "Site A"
  - "Site B"
treatment_fields: [1, 2]
cultivar:
  code: "IB0035"
planting:
  date: "2021-03-01"
  method: "S"
  distribution: "R"
  population: 7.2
  row_spacing: 75
  depth: 5
```

When `treatment_fields` is omitted, every treatment grows on field 1, as in single-field experiments.

#### Per-field weather and soil data

When a template defines several fields (1..K), supply `weather` and `soil` as dictionaries keyed by field number (using integers or digit strings):

```python
import dssatlab as dl

sim = dl.Simulation(
    filex_template="two_fields.yaml",
    weather={1: "site_a_weather.csv", 2: "site_b_weather.csv"},
    soil={1: "site_a_soil.csv", 2: "site_b_soil.csv"},
    treatment=2,
)
sim.run()
```

Each value in the dictionary can be any supported weather or soil input: a CSV file path, a list of dicts, or a pandas DataFrame. When only one field exists (K = 1), a single source can still be passed directly without a dictionary.

#### Shared station and soil rules

Fields may share a weather station or a soil profile ID, but only when their underlying data is identical:

- **Comparing two soils at the same site**: Two fields can specify the same weather station code (or use the same weather data) if the parsed weather rows are identical.
- **Comparing two sites on the same soil**: Two fields can share the same soil ID if their soil layers and properties are identical.

If two fields specify the same station code (or soil profile ID) but have different data, `check()` reports a problem so that one field's data never silently overwrites another's.

#### What gets written

Inside the simulation folder, DSSAT receives:

- One generated weather file per distinct station (named `<station><yy>01.WTH` using the selected treatment's start year).
- A single `SOIL.SOL` holding every distinct soil profile in field order.
- A generated FileX defining each field in both `FIELDS` tables with its own station, coordinates, elevation, soil ID, and depth.

Note that per-field dictionaries are supported only for FileX templates. A copied FileX (`filex=...`) represents an existing experiment and expects a single weather source and a single soil source.

### Which crops and cultivars can I use?

To inspect which template crops your installed DSSAT has genotype files for:

```python
import dssatlab as dl

crops = dl.list_crops()
for crop in crops:
    print(crop["crop"], crop["code"], crop["model"], crop["cultivars"])
```

`list_crops()` returns rows of plain dictionaries with keys `"crop"`, `"code"`, `"model"`, and `"cultivars"` (the count of distinct cultivar codes in the `.CUL` file), listing only template crops whose required genotype files are found in the DSSAT `Genotype` folder.

To list the cultivar codes and names available for a template crop:

```python
cultivars = dl.list_cultivars("soybean")
for cv in cultivars[:5]:
    print(cv["code"], cv["name"])
```

`list_cultivars(crop)` returns rows of dictionaries with keys `"code"` and `"name"` in `.CUL` file order, listing the first occurrence of each distinct code.

Both listings accept an optional `executable=` argument, never touch the network or write to saved configuration, and return plain dictionaries compatible with `dl.to_dataframe()`.

Template checks find the data directory beside the explicit or discovered DSSAT
executable and read its `Genotype` folder without saving configuration or writing
files. `management` and `name` work as with an existing FileX: checks inspect the
skeleton in memory, then experiment overrides apply to the generated FileX.
Cultivar overrides must keep the template's crop and use its fixed model's table.

`sim.run()` creates a fresh simulation folder beside the YAML file, or in the
current directory for a dict. It writes the FileX (holding all treatments), weather and `SOIL.SOL`, and
copies the crop's required genotype files from `Genotype`. Your original files are unchanged.
`run_treatments()` also accepts `filex_template=` to run all or selected template treatments (see [Run treatments and scenarios](scenarios.md)).

## Use stock weather files

With a copied FileX (`filex=`), pass a string or `Path` ending in `.WTH`
(case-insensitive), or a non-empty list of such paths:

```python
import dssatlab as dl

sim = dl.Simulation(filex="UFGA7601.PNX", weather="UFGA7601.WTH")
print(sim.check())
result = sim.run()
```

For several yearly files, for example, use
`weather=["MSKB8901.WTH", "MSKB9001.WTH"]` with the corresponding copied FileX.
`run()` copies every supplied file byte for byte into the simulation folder,
under its upper-case filename (`ufga7601.wth` becomes `UFGA7601.WTH`). No weather
file is regenerated. Extra columns and flags, line endings and a trailing DOS EOF
byte (Ctrl-Z) are preserved. A Ctrl-Z inside the daily records is rejected.
Stock files also work through `run_treatments()`, scenarios and `run_sweep()`.
FileX templates, including per-field sources, require weather data rows instead.

`check()` reads the station from the first four filename characters (upper-case),
and latitude, longitude and elevation by the `@ INSI` header. It reads daily
DATE, SRAD, TMAX, TMIN and RAIN by their fixed header spans.
One trailing letter flag on a number is accepted. Other daily columns, including PAR, are ignored
by the checks and reach DSSAT unchanged. Required weather values of `-99` fail
the usual range checks; nothing is filled or repaired.

Dates may be YYDDD (`@DATE`, without `$WEATHER`) or YYYYDDD (`@  DATE`, with a
`$WEATHER` format marker). A `*WEATHER DATA` file uses five-digit dates; seven-digit
dates with that marker are rejected because DSSAT would read only the first five digits.
Five-digit weather dates use
DSSAT's weather century rule, anchored to the simulation start, including a
first-record adjustment back one century when the record falls after that start,
and a 99-to-00 rollover. Files are checked together in the order supplied: daily dates
must be ascending, unique and continuous across file boundaries. Coordinates,
daily ranges use the [weather template checks](#prepare-the-weather-template).
Start coverage, the last seasonal start and scheduled sequence ends use the same
FileX checks as template weather. Stock weather must also cover a fixed harvest
(HARVS R), including the last season's inherited HDATE. Supplied experiment-data event dates are
checked against the weather range; maturity-driven endings still need the
post-run warning scan.

The filenames must be ones DSSAT looks up for the FileX `WSTA` and simulated
years: a four-character WSTA uses `<WSTA4><YY>01.WTH` per year or `<WSTA4>.WTH`.
An eight-character WSTA also permits its explicit `<WSTA8>.WTH`; if its last two
characters are `01`, yearly names are allowed too. Two paths cannot have the
same name after upper-casing. Stock weather must match the FileX station unless
experiment overrides repoint the copied field.

dssatlab does not yet check whether an installed weather file in DSSAT's weather path would be read instead of the supplied file (planned, issue #224); supply weather under a name no installed file uses.

### Stock weather problems

These are the stock-specific messages, with `{...}` standing for the reported
path, value or list. `{error}` is the operating-system read error; quoted values
use Python's representation. Usual weather and FileX problems are reported too.

```text
Weather data mixes file paths and data rows. Supply only stock weather file paths, or only weather data rows or a DataFrame.
A stock weather file needs a copied FileX. Supply weather data rows for a FileX template.
Cannot read stock weather file {path}: {error}. Supply a readable stock weather file path.
Stock weather file {path}: missing required column {label}. Supply a stock weather file with column {label}.
Stock weather file {path}: DATE header spans {width} characters. Supply @DATE for YYDDD, or $WEATHER with @  DATE for YYYYDDD dates.
Stock weather file {path}: DATE header spans {width} characters but the $WEATHER marker is {present_or_absent}. Checked the format marker and DATE width. Supply $WEATHER with @  DATE and YYYYDDD dates, or omit $WEATHER and use @DATE with YYDDD dates.
Stock weather files {first_path} and {path} have the same file name {name} after upper-casing. Supply only one file with each name for the simulation folder.
Stock weather file {path}: DSSAT does not look up this name for WSTA {station!r} in the simulated years. Expected {names}. Rename the file or correct the FileX WSTA.
Stock weather file {path}, line {line}: invalid date {value!r}. Supply a valid YYDDD or YYYYDDD calendar date matching the DATE header width.
```

`{label}` is LAT, LONG, ELEV, DATE, SRAD, TMAX, TMIN or RAIN. A station mismatch
names the stock weather file:

```text
FileX WSTA 'UFGA' expects station 'UFGA', but stock weather file XYZZ8201.WTH has station 'XYZZ'. Make the station codes exactly equal; filenames are case-sensitive on Linux.
```

On real DSSAT, stock UFGA7601.WTH matched DSSAT's reference on 6/6 Summary rows
(HWAM 4348 to 4829), as did the weather template with `par`. UFGA7609 matched
1/1 (HWAM 5115). A list of MSKB8901.WTH and MSKB9001.WTH ran across the year
boundary like a hand run. See [ADR 0024](../adr/0024-stock-weather-and-soil-files-copied-unchanged.md).

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
| `par` | No | Daily photosynthetically active radiation in mol/m² per day, from 0 to 100; finite and filled on every row when present |
| `tav` | No | Station average temperature in °C |
| `amp` | No | Station temperature amplitude in °C |
| `refht` | No | Reference height in m |
| `wndht` | No | Wind measurement height in m |

All ranges include their endpoints. Required numeric values must be non-empty
and finite. Supply one row per calendar day in ascending order, without gaps or
duplicates. `station`, `latitude`, `longitude`, and `elevation` must be identical
on every row.

Optional station columns (`tav`, `amp`, `refht`, `wndht`) may be omitted or left
empty; they are written as `-99` (not given). Supplied values must be finite
numbers. The weather file uses their values from the first row, so put station
values there. The checks do not require these values to be identical across rows.

The template writer's example omits `par`; add it when you have daily PAR.
Unlike station values, `par` must be supplied on every row if present, including
in a list of dicts. A partially or entirely empty PAR column fails the checks.
Daily values may vary and must be finite and from 0 to 100 inclusive. The writer
adds PAR after RAIN, with one decimal place, only when `par` is present. For an
empty column, a non-finite value and an out-of-range value, the messages are:

```text
Weather column 'par' is empty on {n} rows. Supply par on every row or drop the column.
Weather data row {line}, column 'par': found {value}. Supply a non-empty finite number in mol/m2 per day.
Weather data row {line}, column 'par': found {value}; allowed range is 0 to 100 mol/m2 per day. Correct the value using DSSAT's units.
```

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

For every simulation controls level used by the selected treatment (or each rotation
component in a sequence), `check()` also validates the simulation methods and outputs:

- `METHODS` `WTHER` must be `M` (measured weather). If set to `W` (weather generator),
  DSSAT would generate artificial weather and silently ignore your supplied weather data.
- `OUTPUTS` `FNAME=Y` is accepted: DSSAT names outputs after the experiment
  (such as `UFGA7804.OSU`), and the readers find them when standard names are absent.
  See [Standard and experiment-named output files](reading-results.md#standard-and-experiment-named-output-files).

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
weather date must match the two-digit year and day of year in `SDATE`.
Seasonal checks cover the last season's start; sequence checks require weather
through the scheduled end of the component that crosses the stopping boundary
([sequence coverage](sequence.md#sequence-checks)). Maturity-driven endings are
known only during the run. Supply weather for the full period DSSAT will simulate.
The checks do not establish that the DSSAT executable can run.

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
  original FileX; suffix matching ignores case. (When you supply your own soil
  via `soil=...`, `Simulation.run()` writes `SOIL.SOL` from template data or copies
  the stock file under its own name, and does not copy sibling
  `.SOL` files; see [Run with soil data](soil.md).)
- One generated `.WTH` weather file from your weather data, or the supplied stock
  weather files copied byte for byte under upper-case names.
- A `dssat_run_YYYY-MM-DD_HHMMSS` run directory containing the files collected
  after DSSAT exits.

The source weather CSV is not copied; stock weather paths are copied as above.
For generated weather, if `WSTA` has
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
