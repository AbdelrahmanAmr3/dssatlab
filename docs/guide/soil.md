# Run a Simulation with your soil data

A `Simulation` can combine one treatment of an existing FileX with your daily
weather data and your own soil profile. Prepare the FileX and its supporting files,
then [find or install a DSSAT executable](install.md). The examples use
`UFGA8201.MZX`; replace it with your FileX path and choose one of its treatments.

By default, a `Simulation` copies sibling `.SOL` files sitting beside the FileX.
When you pass soil-template data to `Simulation`, dssatlab generates a single
`SOIL.SOL` instead. A stock soil path is copied unchanged under its own name.
Both replace sibling soil files. A `.SOL` file in the FileX folder always beats
DSSAT's own `Soil` directory (`C:\DSSAT48\Soil` on Windows or the managed install
cache on Linux), so the soil profile you provide is the one DSSAT uses.

## Use a stock soil file

With a copied FileX (`filex=`), `soil=` also accepts a string or `Path` ending in
`.SOL` (suffix recognition ignores case). Supply one path, not a list of paths:

```python
import dssatlab as dl

sim = dl.Simulation(
    filex="UFGA7601.PNX", weather="UFGA7601.WTH", soil="SOIL.SOL",
)
print(sim.check())
result = sim.run()
```

`UFGA7601.PNX` selects profile `IBPN910015`, held in DSSAT's `Soil/SOIL.SOL`.
Copy that file beside the FileX for this example.

`run()` copies the file byte for byte into the simulation folder under its own
filename. It copies no sibling `.SOL` files; `.CUL`, `.ECO` and `.SPE` siblings
are still copied. The stock profile's ID is kept in the copied FileX, including
when experiment data edits other sections. Stock soil also works through
`run_treatments()`, scenarios and `run_sweep()`. FileX templates, including
per-field sources, require soil data rows instead.

`check()` reads only profile IDs: the first token after `*` on profile lines,
skipping `*SOILS`. The FileX's `ID_SOIL` must be among them, with exactly the
same case. The filename must be exactly `<first two ID_SOIL characters>.SOL`
or `SOIL.SOL`; suffix recognition alone does not make a lower-case filename
acceptable. Soil names are not upper-cased when copied, and DSSAT's filename
lookup is case-sensitive on Linux. Layer values are not parsed or checked;
DSSAT checks whether it can use the profile at run time. A trailing DOS EOF byte
(Ctrl-Z) is accepted and preserved in the copy.

These are the stock-soil messages, with `{...}` standing for the reported path,
ID or list; `{error}` is the operating-system read error, and IDs use Python's
quoted representation. `{ids}` is the IDs found, comma-separated, or `none`:

```text
A stock soil file needs a copied FileX. Supply soil data rows for a FileX template.
Cannot read stock soil file {path}: {error}. Supply a readable stock soil file path.
FileX has no readable ID_SOIL in the selected treatment's FIELDS row. Supply ID_SOIL matching a profile in stock soil file {path}. IDs found: {ids}.
Stock soil file {path}: FileX ID_SOIL {soil_id!r} is not in the file. IDs found: {ids}. Supply a file containing that ID or correct the FileX ID_SOIL.
Stock soil file {path}: DSSAT does not look up this name for ID_SOIL {soil_id!r}. Expected {names}. Rename the file or correct the FileX ID_SOIL; filenames are case-sensitive on Linux.
```

On real DSSAT, a stock `.SOL` gave the same outputs as the sibling-copy soil.
See [ADR 0024](../adr/0024-stock-weather-and-soil-files-copied-unchanged.md).

## Initial conditions deeper than the profile

Experiment data `initial_conditions.layers` may extend below the deepest soil
layer, with template soil or stock soil. Depths remain positive and strictly
ascending; water must be from 0 to 1 and ammonium/nitrate nonnegative.
There is no soil-depth rejection or warning. On real DSSAT, UFGA8222 with
180 cm initial conditions on profiles from 60 to 210 cm matched 12/12.
See [initial conditions](experiment.md#cultivar-initial-conditions-and-controls).

## Prepare the soil template

Create an example CSV in a notebook cell:

```python
import dssatlab as dl

dl.write_soil_template("soil.csv")
```

This writes a UTF-8 soil template with one valid three-layer soil profile,
`IBMZ910214`, with layer bottom depths of 5, 15, and 30 cm. Replace those example
values with your soil data before running a Simulation. An existing path raises
`DSSATError`, so rerunning this cell does not overwrite your soil data.

The soil template is ONE flat CSV describing exactly one soil profile, with one
row per soil layer. Use a comma-separated UTF-8 CSV with the exact lower-case
column names below. Columns may appear in any order. Unknown or repeated columns
fail the checks. Values use DSSAT's own units; nothing is converted.

Profile-level values repeat on every row and must be identical across all rows.
Layer bottom depths (`slb`) must be positive and strictly increasing from top to bottom.

| Column | Level | Required | Units | Meaning and checks |
| --- | --- | --- | --- | --- |
| `soil_id` | Profile | Yes | ASCII | 1 to 10 ASCII letters or digits; must match the treatment's FileX `ID_SOIL` unless experiment overrides are supplied |
| `salb` | Profile | Yes | fraction | Soil albedo, from 0 to 1 |
| `slro` | Profile | Yes | dimensionless | Runoff curve number, from 0 to 100 |
| `sldr` | Profile | Yes | fraction/day | Drainage rate, from 0 to 1 |
| `slpf` | Profile | Yes | factor | Soil fertility factor, from 0 to 1 |
| `slnf` | Profile | No | factor | Mineralization factor, from 0 to 1; defaults to -99 |
| `slu1` | Profile | No | mm | Stage 1 soil evaporation limit; defaults to -99 |
| `smhb` | Profile | No | code | DSSAT method code (for example `IB001`); defaults to -99 |
| `smpx` | Profile | No | code | DSSAT method code (for example `IB001`); defaults to -99 |
| `scom` | Profile | No | code | Soil colour code (for example `BN`); defaults to -99 |
| `smke` | Profile | No | code | DSSAT method code (for example `IB001`); defaults to -99 |
| `slb` | Layer | Yes | cm | Layer bottom depth, positive and strictly increasing without duplicates |
| `slll` | Layer | Yes | cm³/cm³ | Lower limit / wilting point, strictly between 0 and 1; must satisfy `slll < sdul < ssat` |
| `sdul` | Layer | Yes | cm³/cm³ | Drained upper limit / field capacity, strictly between 0 and 1; must satisfy `slll < sdul < ssat` |
| `ssat` | Layer | Yes | cm³/cm³ | Saturated water content, strictly between 0 and 1; must satisfy `slll < sdul < ssat` |
| `srgf` | Layer | Yes | fraction | Root growth factor, from 0 to 1 |
| `ssks` | Layer | No | cm/h | Saturated hydraulic conductivity, from 0 to 500; defaults to -99 |
| `sbdm` | Layer | No | g/cm³ | Bulk density, from 0.5 to 2.5; defaults to -99 |
| `sloc` | Layer | No | % | Organic carbon, from 0 to 100; defaults to -99 |
| `slmh` | Layer | No | code | Master horizon code (for example `AP` or `BT`); defaults to -99 |
| `slcl` | Layer | No | % | Clay content; defaults to -99 |
| `slsi` | Layer | No | % | Silt content; defaults to -99 |
| `slcf` | Layer | No | % | Coarse fraction; defaults to -99 |
| `slni` | Layer | No | % | Total nitrogen; defaults to -99 |
| `slhw` | Layer | No | pH | pH in water; defaults to -99 |
| `slhb` | Layer | No | pH | pH in buffer; defaults to -99 |
| `scec` | Layer | No | cmol/kg | Cation exchange capacity; defaults to -99 |
| `sadc` | Layer | No | - | Anion exchange capacity or property; defaults to -99 |

Required numeric columns (`salb`, `slro`, `sldr`, `slpf`, `slb`, `slll`,
`sdul`, `ssat`, `srgf`) must be supplied with non-empty, finite numbers. Real
DSSAT stops with an error if any of these are missing or `-99`.

Profile-level columns (`soil_id`, `salb`, `slro`, `sldr`, `slpf`, and optional
`slnf`, `slu1`, `smhb`, `smpx`, `smke`, `scom`) describe the overall profile and must have
identical values on every row. `soil_id` must consist of 1 to 10 ASCII letters or
digits; DSSAT silently truncates longer IDs.

Layer bottom depths (`slb`) must be strictly positive and strictly increasing
from the surface downwards, without duplicate depths.

Water limits (`slll`, `sdul`, `ssat`) must each be fractions strictly between 0
and 1, and must be in strict ascending order: `slll < sdul < ssat`. While DSSAT
itself accepts equal values and only fails when `slll > sdul` or `sdul > ssat`,
dssatlab enforces strict inequalities because equal values leave no plant-available
water or no pore space.

Optional columns default to `-99` (DSSAT's "not given" sentinel) when omitted or
left blank. The soil template includes the optional profile column `scom`.

`slmh` (layer) and `smhb`, `smpx`, `smke`, `scom` (profile) are DSSAT text codes:
use 1-5 ASCII letters, digits or `_ . + -`, without spaces. Blank or `-99` means
missing; optional DataFrame `NaN` cells also count as missing. Numbers still work
and are written as code text (for example `1.0` becomes `1`); text such as `1E2` stays as written. `scom` must be the
same on every row of a profile, including missing values. Codes such as `IB0001`,
`A B` or `2*BN` fail the checks with the row, column, value and code rule.

Other optional columns must be finite numbers and satisfy their valid ranges
when supplied; range checks are skipped for `-99`.

## Create a Simulation and inspect the checks

Once you have edited `soil.csv` and your [weather data](simulation.md#prepare-the-weather-template),
create the Simulation:

```python
import dssatlab as dl

sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    soil="soil.csv",
)
problems = sim.check()
for problem in problems:
    print(problem)
```

`soil` is an optional, keyword-only argument. Construction only stores the supplied
inputs. `check()` reads the soil data, weather data, and FileX and returns a list
of problem strings; `[]` means all checks passed. It writes nothing, does not
repair data, and does not run DSSAT. It reports all problems together.

The checks verify that:

- All required columns are present and no unknown columns appear.
- `soil_id` has 1 to 10 ASCII letters or digits (DSSAT truncates longer IDs).
- Profile values are identical on every row.
- Layer bottom depths (`slb`) are positive and strictly increasing.
- Water limits satisfy `0 < slll < sdul < ssat < 1`.
- Numeric values fall within valid physical bounds.
- `soil_id` matches the field's `ID_SOIL` in the FileX for the chosen treatment
  exactly, including case. With experiment overrides for that treatment in
  `management`, the copied field's `ID_SOIL` is replaced by the supplied soil ID
  instead. DSSAT matches soil IDs case-sensitively on every system.

A named soil-only scenario still writes its scenario name into the copied
treatment's `TNAME`/`TNAM` column (`"base"` retains the source treatment name).
This label change does not override the field's `ID_SOIL`; experiment overrides
are still required for that change.

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
your FileX. That simulation folder contains:

- A copy of the FileX.
- Copies of every `.CUL`, `.ECO`, and `.SPE` file directly beside the original
  FileX; suffix matching ignores case.
- One generated `.WTH` weather file from your weather data, or supplied stock
  weather files copied under upper-case names.
- One generated `SOIL.SOL` from soil data, or the stock soil file copied under
  its own name.
- A `dssat_run_YYYY-MM-DD_HHMMSS` run directory containing the files collected
  after DSSAT exits.

When `soil` is provided, `Simulation.run()` writes `SOIL.SOL` from template data
or copies the stock soil file into the simulation folder, and copies no sibling
`.SOL` files. Because a `.SOL` file in the
FileX folder always beats DSSAT's own `Soil` directory, DSSAT uses your soil profile.
When `soil` is not provided (`soil=None`), behavior is unchanged: sibling `.SOL`
files are copied as before.

If DSSAT cannot use the soil profile (for example, if the profile ID is missing
or the soil file is corrupted), DSSAT exits with return code 99 and writes
`ERROR.OUT`. In this case, `Simulation.run()` raises `DSSATRunError` containing the
`ERROR.OUT` message and keeps the run directory for inspection.

A successful call returns a [RunResult](run-filex.md#inspect-the-run-result).

## Use a DataFrame or plain rows

If pandas is already part of your environment, pass a DataFrame with the same
soil template columns:

```python
import pandas as pd
import dssatlab as dl

soil = pd.read_csv("soil.csv")
sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    soil=soil,
)
print(sim.check())
```

A blank or `NaN` cell in an optional column counts as "not given" and is written
as `-99`, exactly as in a CSV. In a required column it is reported by the checks.
A numeric-looking `soil_id` is kept as text.

pandas is optional; dssatlab does not import or require it. You can also pass a
list of dictionaries with the soil template names as keys. The same checks apply
to CSV, DataFrame, and list inputs. dssatlab does not modify the supplied soil data.
