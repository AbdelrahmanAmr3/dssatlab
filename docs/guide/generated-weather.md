# Generated weather from a climate file

With a copied FileX, DSSAT can generate daily weather from a station's climate
file instead of reading measured days. Pass the existing `.CLI` file through
`weather=` and choose WGEN (`W`) or SIMMETEO (`S`) in the treatment's controls.
No daily weather data is needed for that treatment. FileX templates still require
measured weather; use `filex=` for generated weather.

## Supply the climate file DSSAT reads

The filename must be the **first four characters of the FileX field's WSTA**,
followed by `.CLI`: `DTCM` or `DTCM6401` needs `DTCM.CLI`. Obtain the file from
your course inputs or DSSAT's `Weather/Climate` folder and pass its path explicitly.
dssatlab does not find it in the installation or compute it from daily weather.
At most one climate file can be supplied.

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
