# Reading results

DSSAT writes its simulation results as fixed-width text files in the run directory.
dssatlab provides functions to read five primary **output files**:
the **summary** (`Summary.OUT`), **plant growth** (`PlantGro.OUT`), **soil water** (`SoilWat.OUT`),
**plant nitrogen** (`PlantN.OUT`), and **weather** (`Weather.OUT`), as well as plot plant growth.

You can access these directly from a [Run result](run-filex.md#inspect-the-run-result)
after a simulation, or call the reader functions on any **run directory**, including
runs performed outside dssatlab.

## What you get back

After running a FileX or a `Simulation`:

```python
import dssatlab as dl

# Run a simulation or existing FileX
result = dl.run("UFGA8201.MZX", treatment=1)

# Read the summary (one dict per simulation)
summary_rows = result.summary()

# Read plant growth (one dict per simulation day)
growth_rows = result.plant_growth()

# Read soil water (one dict per simulation day)
water_rows = result.soil_water()

# Read plant nitrogen (one dict per simulation day)
nitrogen_rows = result.plant_nitrogen()

# Read weather as DSSAT saw it (one dict per simulation day)
weather_rows = result.weather()
```

You can also pass a path to any run directory:

```python
summary_rows = dl.read_summary("path/to/dssat_run_2026-09-30_120000")
growth_rows = dl.read_plant_growth("path/to/dssat_run_2026-09-30_120000")
water_rows = dl.read_soil_water("path/to/dssat_run_2026-09-30_120000")
nitrogen_rows = dl.read_plant_nitrogen("path/to/dssat_run_2026-09-30_120000")
weather_rows = dl.read_weather("path/to/dssat_run_2026-09-30_120000")
```

All five reader functions return a `list[dict]` containing ordinary Python data structures.

## Summary: one row per simulation

`Summary.OUT` records end-of-season totals, harvest yields, and key crop phenology
dates for each simulation in a run.

`read_summary(run_dir)` (or `result.summary()`) parses this file into a list of
dictionaries:

- **One row per simulation**: A run covering three treatments produces three dictionaries.
- **Identity on every row**: Each row carries `RUNNO` (run number), `TRNO` (treatment
  number), and `TNAM` (treatment name).
- **DSSAT column names**: Keys match DSSAT's own column headers without header padding
  dots, such as `HWAM` (harvest yield, kg/ha), `CWAM` (tops weight at maturity, kg/ha),
  and `HIAM` (harvest index).
- **Data types**: Numeric columns are converted to `int` or `float`. Text columns (such
  as `CR`, `MODEL`, `EXNAME`, `TNAM`, `FNAM`, `WSTA`, `SOIL_ID`) remain strings.

```python
for row in result.summary():
    print(f"Treatment {row['TRNO']} ({row['TNAM']}): Yield = {row['HWAM']} kg/ha")
```

## Plant growth: one row per day

`PlantGro.OUT` records daily crop development throughout the growing season.

`read_plant_growth(run_dir)` (or `result.plant_growth()`) parses this file into a list
of dictionaries:

- **One row per simulation day**: Each day DSSAT simulated is returned as a separate
  dictionary.
- **Identity on every row**: Each row carries its `RUNNO` and `TRNO`.
- **DSSAT column names**: Keys match DSSAT's own column headers, such as `LAID` (leaf area
  index), `CWAD` (tops weight, kg/ha), and `GWAD` (grain weight, kg/ha).
- **Data types**: Daily measurements are converted to `int` or `float`.

```python
for row in result.plant_growth()[:5]:
    print(row["DATE"], "LAI:", row["LAID"], "Biomass:", row["CWAD"])
```

## Soil water: one row per day

`SoilWat.OUT` records daily soil water content and water balance components across
the soil profile.

`read_soil_water(run_dir)` (or `result.soil_water()`) parses this file into a list
of dictionaries:

- **One row per simulation day**: Each day simulated is returned as a separate dictionary.
- **Identity on every row**: Each row carries its `RUNNO` and `TRNO`.
- **DSSAT per-layer column names**: Keys match DSSAT's own column headers without reshaping,
  such as `SWTD` (total soil water, mm), layer-specific volumetric water contents (`SW1D`,
  `SW2D`, `SW3D`, ...), `DRAI` (drainage, mm/day), and `ROFC` (runoff, mm/day).
- **Data types**: Daily measurements are converted to `int` or `float`.

```python
for row in result.soil_water()[:5]:
    print(row["DATE"], "Total soil water:", row["SWTD"], "Layer 1:", row.get("SW1D"))
```

## Plant nitrogen: one row per day

`PlantN.OUT` records daily plant nitrogen uptake, mobilization, and concentrations.

`read_plant_nitrogen(run_dir)` (or `result.plant_nitrogen()`) parses this file into a
list of dictionaries:

- **One row per simulation day**: Each day simulated is returned as a separate dictionary.
- **Identity on every row**: Each row carries its `RUNNO` and `TRNO`.
- **DSSAT column names**: Keys match DSSAT's own column headers, such as `NUPC` (cumulative
  nitrogen uptake, kg/ha), `NICD` (leaf N concentration), `NSTD` (nitrogen stress factor),
  and other crop nitrogen metrics.
- **Data types**: Daily measurements are converted to `int` or `float`.

```python
for row in result.plant_nitrogen()[:5]:
    print(row["DATE"], "Cumulative N uptake:", row["NUPC"])
```

## Weather output: one row per day

`Weather.OUT` records daily weather variables as DSSAT processed and used them during
the simulation.

`read_weather(run_dir)` (or `result.weather()`) parses this file into a list of
dictionaries:

- **One row per simulation day**: Each day simulated is returned as a separate dictionary.
- **Identity on every row**: Each row carries its `RUNNO` and `TRNO`.
- **DSSAT column names**: Keys match DSSAT's own headers, such as `SRAD` (solar radiation,
  MJ/m² per day), `TMAX` (maximum temperature, °C), `TMIN` (minimum temperature, °C),
  and `RAIN` (rainfall, mm).
- **Dates**: Contains `YEAR`, `DOY`, and `DATE` (`datetime.date`). When DSSAT includes the
  seven-digit `WDATE` (`YYYYDDD`) column, it is also converted to a `datetime.date` object
  (or `None`).
- **Data types**: Daily measurements are converted to `int` or `float`.

```python
for row in result.weather()[:5]:
    print(row["DATE"], "Max temp:", row["TMAX"], "Rain:", row["RAIN"])
```

## Dates and missing values

DSSAT uses compact conventions in text files that can easily distort analysis if read
naively. dssatlab converts them during parsing:

### Dates converted to `datetime.date`

- **Summary dates**: DSSAT writes dates as seven-digit `YYYYDDD` integers (year and day
  of year, e.g. `1982133`). In summary rows, `SDAT` (start date), `PDAT` (planting date),
  `EDAT` (emergence date), `ADAT` (anthesis date), `MDAT` (maturity date), and `HDAT`
  (harvest date) are converted into Python `datetime.date` objects. Unset or invalid dates
  become `None`.
- **Daily output dates**: Daily output files (`PlantGro.OUT`, `SoilWat.OUT`, `PlantN.OUT`,
  and `Weather.OUT`) retain the original `YEAR` and `DOY` columns and gain a new `DATE`
  column containing a `datetime.date` object. If `YEAR` or `DOY` is missing, `DATE` is
  `None`. In `Weather.OUT`, the `WDATE` column is also parsed into a `datetime.date` object
  (or `None`).

### Missing values (`-99`) become `None`

DSSAT uses `-99` (or `-99.0`) as a **missing value** sentinel when a variable was not
measured or not simulated.

dssatlab converts every `-99` sentinel to Python `None`. This guarantees that missing
values are never treated as valid numbers, preventing corrupted averages, sums, or
erroneous plot lines.

| DSSAT Output Field | Raw Text in File | Parsed Python Value | Type |
| --- | --- | --- | --- |
| `ADAT` (anthesis date) | `1982133` | `datetime.date(1982, 5, 13)` | `datetime.date` |
| `HDAT` (harvest date) | `-99` | `None` | `NoneType` |
| `HWAM` (harvest yield) | `3450` | `3450` | `int` |
| `LAID` (leaf area index) | `2.45` | `2.45` | `float` |
| `SWTD` (soil water) | `125.4` | `125.4` | `float` |
| `NUPC` (N uptake) | `45.2` | `45.2` | `float` |
| `LAID` (missing) | `-99.0` | `None` | `NoneType` |

## Multi-treatment runs and scenarios

When a FileX is run across multiple treatments with `dl.run("UFGA8201.MZX")`, DSSAT writes
all treatments into single output files (`Summary.OUT`, `PlantGro.OUT`, etc.).

Because `RUNNO` and `TRNO` are preserved on every parsed row, you can filter or group
simulations cleanly:

```python
result = dl.run("UFGA8201.MZX")  # all treatments

# Filter daily plant growth for treatment 2
tr2_growth = [row for row in result.plant_growth() if row["TRNO"] == 2]
```

When running treatments and scenarios via `run_treatments()`, each `(scenario, treatment)`
simulation runs in its own directory. Use `combine_summaries(results)` to merge their
end-of-season summaries into a single table with `scenario` and `treatment` columns:

```python
results = dl.run_treatments("UFGA8201.MZX", weather="weather.csv")
all_summaries = dl.combine_summaries(results)
```

See [Run treatments and scenarios](scenarios.md) for full details.

## Convert to a pandas DataFrame

If you use pandas for data analysis, convert any parsed output list into a
`pandas.DataFrame`:

```python
import dssatlab as dl

growth_rows = result.plant_growth()
df_growth = dl.to_dataframe(growth_rows)

water_rows = result.soil_water()
df_water = dl.to_dataframe(water_rows)

combined_summaries = dl.combine_summaries(results)
df_summaries = dl.to_dataframe(combined_summaries)
```

`to_dataframe(rows)` preserves dictionary key order, `datetime.date` objects, and `None`
missing values (represented in pandas as `None` or `NaN`).

pandas is an **optional dependency** (ADR 0002). It is imported only when you invoke
`to_dataframe()`. If pandas is not installed, the function raises `DSSATError` with
instructions to install it:

```text
Cannot create a DataFrame: could not import pandas. Install it with pip install pandas, then call to_dataframe(rows) again.
```

## Plotting and comparing treatments

Visualizing plant growth over time is supported through `plot_plant_growth()` or the
convenience method `result.plot()`:

```python
import dssatlab as dl
import matplotlib.pyplot as plt

# Plot leaf area index for a single run
ax = result.plot("LAID")
plt.show()
```

### Compare treatments across run directories

To compare treatments across different runs (e.g., a rainfed scenario versus an
irrigated scenario), pass a sequence of run directories to `dl.plot_plant_growth()`:

```python
import dssatlab as dl
import matplotlib.pyplot as plt

# Compare two separate runs
ax = dl.plot_plant_growth(
    [rainfed_result.run_dir, irrigated_result.run_dir],
    variable="LAID",
)
plt.title("Leaf Area Index: Rainfed vs Irrigated")
plt.show()
```

### Plotting behavior

- **Date on x-axis**: The horizontal axis is plotted against `DATE`.
- **One line per simulation**: Each distinct simulation is drawn as a separate curve,
  labelled by its treatment name (`TNAM` from `Summary.OUT`, or fallback `Run X Treatment Y`).
- **Returns matplotlib Axes**: The function returns the matplotlib `Axes` object, allowing
  you to adjust titles, labels, or save the figure (`ax.figure.savefig("lai.png")`).
- **Optional matplotlib**: Plotting requires matplotlib (ADR 0004). Install it using the
  `plot` extra: `pip install dssatlab[plot]`. If matplotlib is not installed, calling the
  function raises `DSSATError`:

```text
Plotting needs matplotlib. Install it with: pip install dssatlab[plot]
```

- **Unknown variable check**: If you specify a variable name not present in `PlantGro.OUT`,
  `plot_plant_growth()` raises a `DSSATOutputError` listing the available growth variables
  found in the output file:

```text
Unknown plant growth variable 'BADVAR'. Checked PlantGro.OUT in the run directory for plant growth variables. Available variables are: CANHT, CLAID, CWAD, CWID, DWAD, EWAD, GSTD, GWAD, HIAD, LAID, LWAD, RWAD, SWAD. Choose an available growth variable to plot.
```

## Error handling

If an output file is missing, empty, or corrupted, the readers raise a `DSSATOutputError`.
They will never guess at column alignments or return partial data from a truncated file.

Errors follow the 3-part message standard:
1. **What failed**: The specific file issue, missing header, or malformed row line number.
2. **What was checked**: The file path and header expected in the run directory.
3. **What to do next**: How to correct the problem or re-run DSSAT.

Example error message:

```text
Summary.OUT is missing or unreadable ([Errno 2] No such file or directory: '.../Summary.OUT'). Checked .../Summary.OUT in the run directory for a Summary @ header and complete data rows. Check the run directory and output file, or rerun DSSAT to produce a complete Summary.OUT.
```

Catch `DSSATOutputError` to handle missing or unreadable outputs separately from run or
check errors:

```python
try:
    rows = result.summary()
except dl.DSSATOutputError as error:
    print("Could not read summary:", error)
```

## What is not read

dssatlab deliberately restricts output parsing to five files: `Summary.OUT`, `PlantGro.OUT`,
`SoilWat.OUT`, `PlantN.OUT`, and `Weather.OUT`:

- **Other output files**: DSSAT produces over 20 other output files during a run
  (`ET.OUT`, `SoilNi.OUT`, `OVERVIEW.OUT`, `Evaluate.OUT`, etc.). These files
  are collected into the run directory and listed in `result.outputs`, but their contents
  are not parsed.
- **No unit conversions**: Values remain in DSSAT's native output units.
- **Readers preserve simulated values**: readers do not compute statistics or fill gaps.
  Use [evaluate()](evaluate.md) to compare these values with observed data and compute
  RMSE, bias, and d-index.
- **No new plots**: Plotting functions focus specifically on plant growth curves over time.
