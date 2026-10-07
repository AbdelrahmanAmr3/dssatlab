# Generated weather from a climate file

With a copied FileX, DSSAT can generate daily weather from a station's climate
file instead of reading measured days. Pass the existing `.CLI` file through
`weather=` and choose WGEN (`W`) or SIMMETEO (`S`) in the treatment's controls.
No daily weather data is needed for that treatment. FileX templates can also
use a climate file as a field's weather, as shown below.

## Supply the climate file DSSAT reads

The filename must be the **first four characters of the FileX field's WSTA**,
followed by `.CLI`: `DTCM` or `DTCM6401` needs `DTCM.CLI`. Obtain the file from
your course inputs or DSSAT's `Weather/Climate` folder and pass its path explicitly.
dssatlab does not find it in the installation or compute it from daily weather.
For a copied FileX, at most one climate file can be supplied.

```python
import dssatlab as dl

sim = dl.Simulation(
    filex="DTCM6401.SNX", treatment=1,
    weather=r"C:\DSSAT48\Weather\Climate\DTCM.CLI",
    executable=r"C:\DSSAT48\DSCSM048.EXE",
)
problems = sim.check()  # The stock FileX already selects WTHER S.
if not problems:
    result = sim.run()
    rows = dl.read_summary(result.run_dir)
    print(len(rows))  # Ten seasons for this stock treatment.
```

Keep the FileX's supporting soil and genotype files beside it, as for other
copied FileX simulations. `run()` copies the climate file byte for byte under
its upper-case filename into the simulation folder beside the copied FileX.
The Windows probes confirmed that DSSAT reads this local copy before its
installation's climate folder.

The narrow checks require a `*CLIMATE` header, an `@ INSI` station matching the
filename's first four characters (case-insensitive), and numeric LAT, LONG,
ELEV, TAV and AMP values. The required table depends on the weather method:

| `weather_source` | DSSAT method | Required climate table |
|---|---|---|
| `"M"` | Measured weather | Weather data or stock `.WTH` files; no climate file |
| `"W"` | WGEN | `*WGEN PARAMETERS`, months 1 to 12 and fourteen numeric values per month, none `-99` |
| `"S"` | SIMMETEO | `*MONTHLY AVERAGES`, months 1 to 12 with numeric SAMN, XAMN, NAMN, RTOT and RNUM, none `-99` |

Real-DSSAT probes verified that W needs WGEN parameters but not monthly
averages, and S needs monthly averages but not WGEN parameters. These checks
do not prove every climate value is usable by DSSAT; errors during a run still
surface through `DSSATRunError`. Weather methods other than M, W and S are problems.

## Select weather, seasons and seed through management

Use experiment data through the existing `management=` argument to switch a
copied FileX without editing the source:

```python
import dssatlab as dl

experiment = {"treatments": {1: {"controls": {
    "weather_source": "W", "years": 3, "random_seed": 1234,
}}}}
sim = dl.Simulation(
    filex="DTCM6401.SNX", treatment=1,
    weather=r"C:\DSSAT48\Weather\Climate\DTCM.CLI",
    management=experiment, executable=r"C:\DSSAT48\DSCSM048.EXE",
)
problems = sim.check()
if not problems:
    result = sim.run()
    print(dl.read_summary(result.run_dir))  # Three seasons.
```

Set `weather_source` to `"S"` to use SIMMETEO with the same climate file.
`years` sets DSSAT's NYERS, as in [seasonal analysis](seasonal.md).
`write_management_template()` includes comments showing the three weather controls:

| Controls key | DSSAT column | Allowed values and meaning |
|---|---|---|
| `weather_source` | WTHER | `"M"`, `"W"` or `"S"` |
| `replicates` | NREPS | Whole number from 1 to 99999; above 1 requires a sequence with W or S |
| `random_seed` | RSEED | Whole number from 0 to 99999, passed unchanged to DSSAT |

Omitted keys keep the copied FileX's values. **Seed 0 is passed as is; it does
not select seed 2510.** With the same inputs and DSSAT executable, a fixed seed
repeats the generated weather results, including seed 0. In the verified W and S
examples, seed 1234 repeated on rerun and seed 4321 changed the results.

A common seed reproduces each management option, but does not guarantee the
same generated daily weather across different options. In the seasonal soybean
comparison, options with seed 1234 had different rainfall in later seasons.
Treat them as separate weather samples and avoid attributing their differences
solely to irrigation. For a comparison using shared weather, supply the same
measured weather to each option with `weather_source: "M"`, covering every season.

## Replicate a sequence and read every row

For a copied [sequence FileX](sequence.md), set the controls at treatment level:

```python
import dssatlab as dl

experiment = {"treatments": {1: {"controls": {
    "weather_source": "W", "replicates": 10, "random_seed": 1234,
}}}}
sim = dl.Simulation(
    filex="UFGA7874.SQX", treatment=1,
    weather=r"C:\DSSAT48\Weather\Climate\UFGA.CLI",
    management=experiment, executable=r"C:\DSSAT48\DSCSM048.EXE",
)
problems = sim.check()
if not problems:
    result = sim.run()
    rows = dl.read_summary(result.run_dir)
    first_replicate = [row for row in rows if row["P#"] == 1]
    print(len(rows), len(first_replicate))
```

The three weather controls apply to every controls level the sequence uses.
All components must use the same WTHER; mixing methods is a problem.
`replicates` above 1 with measured weather is a problem because every replicate
would repeat the same rows. Above 1 outside a sequence is also a problem:
**DSSAT ignores seasonal NREPS**. A copied seasonal FileX retains its NREPS and
RSEED as supplied, but NREPS does not multiply its seasons.

`read_summary()` returns every season and rotation component run in every
replicate. **Summary `P#` identifies the replicate**. `RUNNO` and `WYEAR` restart
in each replicate block, while `R#` identifies the rotation component.
In the UFGA7874 probe, one replicate had 91 rows and two had 182, in consecutive
blocks with `P#` 1 and 2. Averaging replicates is left to your analysis code.

## Mix measured and generated treatments

`weather=` accepts a climate path alone or a list containing `.CLI` and `.WTH`
paths. For a FileX with both measured and generated treatments, use
`dl.run_treatments("UFGA8201.MZX", weather=["UFGA8201.WTH", "UFGA.CLI"])`,
with each treatment's WTHER already set appropriately or overridden through
`management`. The unused-input check covers all selected treatments, and each
simulation folder receives only the input its treatment needs.

Supplying daily weather when no selected treatment uses M is a problem because
DSSAT would ignore it. Supplying a climate file when no selected treatment uses
W or S is also a problem. Remove the unused input or select the matching method.

## Override weather per scenario

The unused-input check runs separately for each scenario. A shared
`weather=["UFGA8201.WTH", "UFGA.CLI"]` is rejected when the base scenario uses
only M and another scenario uses only W or S: each has an unused input.
Supply measured weather as the base input and replace it with the climate file
through the scenario's `weather` key:

```python
import dssatlab as dl

results = dl.run_treatments(
    "UFGA8201.MZX", treatments=[1], weather="UFGA8201.WTH",
    management={"treatments": {1: {"controls": {"weather_source": "M"}}}},
    scenarios={"wgen": {
        "weather": "UFGA.CLI",
        "management": {"treatments": {1: {"controls": {"weather_source": "W"}}}},
    }},
)
```

This runs treatment 1 under both `"base"` (measured weather) and `"wgen"`
(generated weather). Each scenario override replaces the whole input; omitted
keys inherit the base input. If the base `management` contains other settings
you need, include them in the scenario's replacement too. The climate filename
must still match the FileX's WSTA as described above. See
[scenarios](scenarios.md#overrides-replace-the-whole-input) for the override rules.

## Use a climate file in a FileX template

A template field's `weather` can be one `.CLI` path as a string, `Path` or
one-item list. Set the treatment's `controls.weather_source` to `"W"` or `"S"`
through `management=`. This works for single-crop, crop-entry and rotation
templates; a rotation template can also use `replicates` above 1.

The file keeps its four-letter station name: `UFGA.CLI` for `@ INSI` UFGA,
with lowercase names accepted. FIELDS station, latitude, longitude and elevation
come from the climate file header. No daily weather-coverage checks apply to
that field; calendar dates and their order are still checked. `run()` copies
the file unchanged under its upper-case name and writes no `.WTH` for it.

```python
import dssatlab as dl

template = {
    "crop": "maize", "treatment_name": "Generated weather",
    "cultivar": {"code": "IB0035"},
    "planting": {"date": "2021-03-01", "method": "S", "distribution": "R",
                 "population": 7.2, "row_spacing": 75, "depth": 5},
}
soil = [{"soil_id": "SOIL123456", "salb": 0.13, "slro": 60,
         "sldr": 0.5, "slpf": 1, "slb": 30, "slll": 0.1,
         "sdul": 0.24, "ssat": 0.45, "srgf": 1}]
experiment = {"treatments": {1: {"controls": {
    "weather_source": "W", "years": 3, "random_seed": 1234,
}}}}
sim = dl.Simulation(
    filex_template=template, weather=r"C:\DSSAT48\Weather\Climate\UFGA.CLI",
    soil=soil, management=experiment, executable=r"C:\DSSAT48\DSCSM048.EXE",
)
if not sim.check():
    result = sim.run()
    print(dl.read_summary(result.run_dir))  # Three seasons.
```

Templates default to measured weather (`M`); supplying a `.CLI` does not change
the method automatically. For field 1 and treatment 1, `check()` reports:

> Field 1 weather is a climate file, but treatment 1 uses WTHER M. Checked the treatment's weather source. Set controls weather_source W or S, or supply weather data rows.

With `W` and data rows instead of a climate file, it reports (the same message
uses `WTHER S` for `S`):

> Treatment 1 uses generated weather (WTHER W), but field 1 weather is data rows. Checked the field's weather source. Supply the station's .CLI file for this field.

A per-field dict may use rows for one field and a `.CLI` for another. Mixing
a `.CLI` with rows or another weather path within one field gives:

> Field 1 weather mixes a climate file with other weather. Supply one .CLI path or only data rows.

The [real-DSSAT proof in ADR 0034](../adr/0034-climate-file-as-a-template-fields-weather.md#proof-on-real-dssat)
verified W and S, fixed seeds, a supplied altered climate file, rotation
replicates and crop-entry templates on Windows DSSAT 4.8.5.017. Linux was not run.

## Verified course results

The public-API proofs recorded in [ADR 0032](../adr/0032-generated-weather-from-a-copied-climate-file.md#real-dssat-proofs)
ran on Windows DSSAT 4.8.5.017 with stock climate files and copied course FileXs:

| Course case | Setup | Reference equality |
|---|---|---|
| DTCM6401 | `DTCM6401.SNX`, S, ten seasons, sixteen treatments run individually, `DTCM.CLI` | 160 rows equal `DTCM6401.OSU` on TRNO, CR, MODEL, SDAT, HWAM, ADAT, MDAT and HDAT (sorted-row digests) |
| UFGA7874 | `UFGA7874.SQX`, W, ten replicates, thirty years, six components, `UFGA.CLI` | 910 rows equal the sequence-mode Q reference `UFGA7874.OSU` on RUNNO, TRNO, R#, P#, CR, MODEL, SDAT, HWAM, ADAT, MDAT and HDAT |

These equalities use the stock controls and seed. The seed override above
demonstrates reproducibility and is not the course-reference setup. A locally
altered `DTCM.CLI` changed yields, confirming DSSAT used the supplied copy.
A stock Linux managed install was unavailable, so no Linux real-DSSAT proof
was run. To compute net returns from `.PRI` price files after a run, see
[seasonal economics](seasonal.md#compute-net-return-from-a-price-file).
