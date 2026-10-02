# Run with experiment data

[Management data](management.md) lets you change planting, irrigation and fertilizer without
editing the FileX. **Experiment data** is the same per-treatment YAML (or dict) with three more
sections: which **cultivar** is grown, what the soil holds at the start (**initial conditions**),
and how the simulation is **controlled**. dssatlab applies it to a copy of your FileX; the
original is never changed. You still start from a FileX you already have.

## Generate the experiment template

```python
import dssatlab as dl

dl.write_experiment_template("experiment.yaml", filex="UFGA8201.MZX")
```

The commented file lists each treatment number found in the FileX once (and nothing
else from it), even when a sequence has several rotation component rows. Treatment
numbers follow DSSAT's fixed columns, including sensitivity-tool rows; see
[ADR 0018](../adr/0018-treatment-rows-read-with-dssats-fixed-columns.md).
It refuses to overwrite an existing path. `write_management_template` is unchanged, and a
management-only YAML is still valid: add a section only when you want to change it. Omit a
section and the treatment keeps the FileX's own level.

## Experiment data for sequences

A sequence entry takes `controls` (`years` and `start_date`) and `rotation`, a dictionary
keyed by the rotation component's R number. Each crop component can have its own planting,
cultivar, fertilizer and irrigation. This works for copied sequence FileX files and rotation
FileX templates, including scenarios. The experiment template includes a commented example;
replace its single-treatment sections when using it for a sequence. See
[Experiment data per rotation component](sequence.md#experiment-data-per-rotation-component)
for the YAML, component period checks and the maturity caveat.

## The three new sections

```yaml
treatments:
  1:
    cultivar:
      crop: "MZ"                 # CR code
      code: "IB0035"             # INGENO code, as listed in the .CUL file
      coefficients: {P1: 300}    # optional changed cultivar coefficients
    initial_conditions:
      date: "1982-02-25"
      previous_crop: "MZ"        # optional
      residue_mass: 0.0          # optional, kg/ha
      layers:                    # depth is the bottom of the layer, cm, ascending
        - {depth: 15, water: 0.20, nh4: 0.5, no3: 2.0}
        - {depth: 30, water: 0.22, nh4: 0.5, no3: 2.0}
    controls:
      start_date: "1982-02-20"
      water: "Y"                 # water simulation, "Y" or "N"
      nitrogen: "Y"              # nitrogen simulation, "Y" or "N"
      output_interval: 7         # days between output rows
      years: 1                   # number of seasons (NYERS); see Seasonal analysis
```

Values are in DSSAT's own units and nothing is converted. Dates are quoted ISO strings.

| Section | What `check()` rejects |
|---|---|
| `cultivar` | A code that is not in the one `.CUL` file for that crop beside the FileX; the message lists the codes that do exist. Several `.CUL` files for one crop are rejected, because dssatlab does not choose a model. |
| `initial_conditions` | Layer depths that do not ascend, water outside 0 to 1, negative ammonium, nitrate or residue, detail values outside the ranges below, and, when you pass `soil=`, a layer deeper than the soil profile. Values other than a dict or the quoted string `"off"` are rejected. |
| `controls` | Simulation or management codes outside the tables below, automatic values outside their ranges, an invalid automatic planting window, an `output_interval` that is not a positive integer, `years` that is not a positive integer (or too wide for DSSAT's NYERS column), a bad `start_date`. |

A misspelled field or a misnamed section is reported by name with the allowed list, and every
problem of every treatment is reported at once. Crop-specific rules are still DSSAT's to check
at run time.

A changed `controls` `start_date` replaces the FileX `SDATE` in the weather-coverage and
planting-date checks. The FileX `START` setting is left as it is.

## Simulation options

Set these optional fields under `controls`. Omitted options keep the FileX value.
dssatlab checks the codes and writes them into a copied controls level; DSSAT decides
what each option does. The same fields apply when using a FileX template.

| YAML field | DSSAT column | Allowed codes | Type |
|---|---|---|---|
| `water` | WATER | `"Y"`, `"N"` | Quoted, case-sensitive letter |
| `nitrogen` | NITRO | `"Y"`, `"N"` | Quoted, case-sensitive letter |
| `photosynthesis` | PHOTO | `"C"`, `"R"`, `"L"`, `"V"` | Quoted, case-sensitive letter |
| `co2` | CO2 | `"M"`, `"W"`, `"D"`, `"R"` | Quoted, case-sensitive letter |
| `symbiosis` | SYMBI | `"Y"`, `"N"`, `"U"` | Quoted, case-sensitive letter |
| `phosphorus` | PHOSP | `"Y"`, `"N"` | Quoted, case-sensitive letter |
| `potassium` | POTAS | `"Y"`, `"N"` | Quoted, case-sensitive letter |
| `tillage` | TILL | `"Y"`, `"N"` | Quoted, case-sensitive letter |
| `evapotranspiration` | EVAPO | `"F"`, `"R"`, `"S"`, `"T"` | Quoted, case-sensitive letter |
| `infiltration` | INFIL | `"R"`, `"S"`, `"N"` | Quoted, case-sensitive letter |
| `soil_organic_matter` | MESOM | `"G"`, `"P"` | Quoted, case-sensitive letter |
| `soil_evaporation` | MESEV | `"R"`, `"S"` | Quoted, case-sensitive letter |
| `soil_layers` | MESOL | `1`, `2`, `3` | Integer, not a string or boolean |
| `residue` | RESID | `"N"`, `"R"`, `"D"` | Quoted, case-sensitive letter |

## Automatic management

Set these optional fields under `controls`, for a copied FileX or a FileX template.
Only named columns change in the copied controls level; omitted fields keep its values.
Management codes are quoted, case-sensitive strings. Numeric values must be finite
Python integers or floats, not strings or booleans. Ranges include both endpoints
unless stated otherwise; each value must also fit its FileX column.

| Field | DSSAT column | Allowed codes / range | Unit / format |
|---|---|---|---|
| `irrigation_management` | IRRIG | `"A"`, `"N"`, `"F"`, `"R"`, `"D"`, `"P"`, `"W"` | Quoted, case-sensitive letter |
| `planting_management` | PLANT | `"A"`, `"F"`, `"R"` | Quoted, case-sensitive letter |
| `auto_irrigation_depth` | IMDEP | Above 0 | cm |
| `auto_irrigation_threshold` | ITHRL | 0 to 100 | % |
| `auto_irrigation_refill` | ITHRU | 0 to 100 | % |
| `auto_irrigation_method` | IMETH | `[A-Za-z]{2}[0-9]{3}` | Two ASCII letters followed by three digits, e.g. `"IR001"` |
| `auto_irrigation_amount` | IRAMT | Above 0 | mm |
| `auto_irrigation_efficiency` | IREFF | Above 0 and at most 1 | Unitless |
| `auto_planting_first` | PFRST | Valid calendar date | Quoted `"YYYY-MM-DD"` string |
| `auto_planting_last` | PLAST | Valid calendar date | Quoted `"YYYY-MM-DD"` string |
| `auto_planting_soil_water_low` | PH2OL | 0 to 100 | % |
| `auto_planting_soil_water_high` | PH2OU | 0 to 100 | % |
| `auto_planting_soil_water_depth` | PH2OD | Above 0 | cm |
| `auto_planting_max_temperature` | PSTMX | Any finite number | degrees C |
| `auto_planting_min_temperature` | PSTMN | Any finite number | degrees C |

IRRIG `"A"` lets DSSAT refill soil water when it falls below the threshold;
`"F"` uses the fixed amount (IRAMT). Give `irrigation: []` to remove reported
events under either code. IREFF applies to **automatic irrigation**; the
`irrigation` dict's `efficiency` (EFIR) applies to **that irrigation level's events**.
See [irrigation timing and efficiency](management.md#irrigation-timing-and-efficiency)
for day events (`days_after_planting`, IDATE), the dict form and the IRRIG checks.

```yaml
treatments:
  1:
    irrigation: []
    controls:
      irrigation_management: "A"
      auto_irrigation_depth: 30
      auto_irrigation_threshold: 50
      auto_irrigation_refill: 100
      auto_irrigation_method: "IR001"
      auto_irrigation_efficiency: 1
```

For automatic planting, set `planting_management` to `"A"` or `"F"` and give
window dates and any soil water or temperature limits to change. The effective
window uses your dates, otherwise the copied controls level's PFRST/PLAST.
Its first date must be on or before its last and on or after the effective
simulation start (`controls.start_date`, otherwise SDATE). Given window dates
must lie inside the weather range. These window checks run only under PLANT
A/F when you supply a window date, `planting_management`, or `start_date`;
an unused window under PLANT R is not checked. The checks do not predict
whether DSSAT will find a suitable planting day.

The FileX template still starts with IRRIG R, PLANT R and its automatic defaults;
experiment data applies your changes afterwards. Sequences keep their existing
controls restriction (`years` and `start_date` only). See
[ADR 0020](../adr/0020-automatic-management-as-controls-fields.md) and the
[tutorial notebook](https://github.com/AbdelrahmanAmr3/dssatlab/blob/master/notebook/dssatlab_tutorial.ipynb), Case 15.

## Initial-condition details

Add these optional numeric fields beside `date` and `layers` in `initial_conditions`.
All ranges include their endpoints. Values must be finite numbers, not strings or
booleans. Omitted detail fields write DSSAT's missing-value marker `-99`.

| Field | DSSAT column | Allowed range | Unit |
|---|---|---|---|
| `root_mass` | ICRT | 0 or greater (no upper limit) | kg/ha |
| `nodule_mass` | ICND | 0 or greater (no upper limit) | kg/ha |
| `rhizobia_number` | ICRN | 0 to 1 | Unitless |
| `rhizobia_effectiveness` | ICRE | 0 to 1 | Unitless |
| `residue_n` | ICREN | 0 to 100 | % |
| `residue_p` | ICREP | 0 to 100 | % |
| `residue_incorporation` | ICRIP | 0 to 100 | % |
| `residue_depth` | ICRID | 0 or greater (no upper limit) | cm |

To let DSSAT supply initial soil water and nitrogen, replace the whole section
with `initial_conditions: "off"`. This sets the treatment's IC to 0 in the FileX
copy and adds no IC level. Keep `"off"` quoted: unquoted `off` can become a YAML
boolean, and an empty key (`null`) is rejected. Omitting the section keeps the
FileX's initial conditions. Weather coverage and management date checks still apply.

## Compare photosynthesis options

Use treatment 1 of `UFGA8201.MZX` and weather covering its 1982 season. This sweep
compares PHOTO `"C"` and `"L"`, with initial conditions off for every run:

```python
rows = dl.run_sweep(
    "UFGA8201.MZX", "weather.csv", treatments=[1],
    management={"treatments": {1: {"initial_conditions": "off"}}},
    factors={"controls": {
        "C": {"photosynthesis": "C"},
        "L": {"photosynthesis": "L"},
    }},
)
dl.to_dataframe(rows)[["scenario", "controls", "HWAM"]]
```

The base runs first, followed by C and L. Each factor value replaces the whole
`controls` section; `initial_conditions` stays off. Compare grain yield (`HWAM`,
kg/ha) in the returned rows. `to_dataframe()` requires optional pandas. See
[sweeps](sweeps.md) and the [tutorial notebook](https://github.com/AbdelrahmanAmr3/dssatlab/blob/master/notebook/dssatlab_tutorial.ipynb), Case 14.

## Cultivar coefficients

The optional `cultivar.coefficients` field is a non-empty dict of exact, case-sensitive
`.CUL` header names after `ECO#` (for example `P1` or `G2`) to finite numbers in DSSAT's
own units. Strings, booleans, NaN and infinity are rejected, as are unknown headers.

DSSATLab writes a **changed cultivar**: a copy of the source cultivar's line with the
specified coefficients and the first free `DLnnnn` code (`DL0001`, `DL0002`, ...).
It inserts the changed line immediately after the source line in the simulation folder's
`.CUL` copy and points the copied FileX treatment's `CULTIVARS` level at the new code.
The source `.CUL` is never changed; coefficients you omit keep their source values.

Values are written as given, with no rounding: an integer stays as is, and an integral
float keeps one decimal (`300` versus `300.0`). Each value must fit its fixed-width
column without exponent notation; checks reject values that cannot be written this way.
`coefficients` is not allowed per rotation component. See [cultivar coefficient
sweeps](sweeps.md#cultivar-coefficient-sweep) and
[ADR 0017](../adr/0017-cultivar-coefficients-as-a-changed-cul-line.md).

## Run it

```python
sim = dl.Simulation("UFGA8201.MZX", treatment=1, weather="weather.csv",
                    management="experiment.yaml")
problems = sim.check()
result = sim.run()
```

The copied FileX gets a new `CULTIVARS`, `INITIAL CONDITIONS` or `SIMULATION CONTROLS` level for
each dict section you gave, and only the selected treatment is repointed. With
`initial_conditions: "off"`, it points at IC 0 instead. The `.CUL`, `.ECO` and
`.SPE` files are copied to the simulation folder as before.

## Use it in scenarios

The sections can appear in a scenario's `management` override, so "what if a different cultivar"
is one more scenario:

```python
results = dl.run_treatments(
    "UFGA8201.MZX", "weather.csv", treatments=[1],
    scenarios={"other_cultivar": {"management": {"treatments": {
        1: {"cultivar": {"crop": "MZ", "code": "999991"}}}}}},
)
```

## Checked on real DSSAT

Each section was overridden on a copy of DSSAT's own sample FileX (maize `UFGA8201`, wheat
`KSAS8101`, treatment 1) and the yield (`HWAM`, kg/ha) moved as expected:

| Change | Maize | Wheat |
|---|---|---|
| none (the FileX as it is) | 2293 | 2010 |
| a different cultivar (`999991`) | 658 | 2 |
| seven layers at water 0.30, nitrate 60 mg/kg (`initial_conditions`) | 2499 | 4594 |
| `water: "N"` | 11859 | 4989 |
| `nitrogen: "N"` | 2010 | 4981 |

`output_interval: 7` cut the `PlantGro.OUT` rows from 129 to 20 (maize) and from 251 to 38 (wheat).

The v0.16 real-DSSAT proof covered IRRIG A, F, D (days after planting), R (dated)
and N. P and W can be written and checked for dated events, but have not been
proven on DSSAT. On UFGA8201 treatment 1, automatic irrigation with IREFF 1
versus 0.5 gave IRCM 214 versus 330 mm. The EFIR 0.75 dict form matched a
hand-edited FileX exactly: IRCM 110 mm and HWAM 2335 kg/ha.

## Not included

Editing `.ECO` or `.SPE` files, cultivar coefficients per rotation component,
generated weather and replicates, automatic nitrogen, residue and harvest,
the automatic irrigation stop stage (IROFF), and per-layer roots.
To build a FileX from nothing, use a [FileX template](simulation.md). See the
[roadmap](../reference/roadmap.md) and [ADR 0005](../adr/0005-experiment-data-edits-an-existing-filex.md).
