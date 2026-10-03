# Run with experiment data

[Management data](management.md) lets you change planting, irrigation and fertilizer without
editing the FileX. **Experiment data** extends the same per-treatment YAML (or dict) with
`residues`, `tillage`, `harvest`, which **cultivar** is grown, what the soil holds at the
start (**initial conditions**), and how the simulation is **controlled**. dssatlab applies it to a copy of your FileX; the
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

Edits normally append a new level. Past 99 they reuse the lowest number no
TREATMENTS row references after the edit is repointed, replacing rows in the
copy; if none is free, the checks report the level-limit problem. See
[level reuse](sequence.md#reuse-free-levels-past-99) and
[ADR 0023](../adr/0023-reuse-free-levels-past-99.md).

## Experiment data for sequences

A sequence entry takes `controls` (`years` and `start_date`) and `rotation`, a dictionary
keyed by the rotation component's R number. Each crop component can have its own planting,
cultivar, fertilizer, irrigation, residues, tillage and harvest. Fallows take only the
last three sections. This works for copied sequence FileX files and rotation
FileX templates, including scenarios. The experiment template includes a commented example;
replace its single-treatment sections when using it for a sequence. See
[Experiment data per rotation component](sequence.md#experiment-data-per-rotation-component)
for the YAML, component period checks and the maturity caveat.

## Cultivar, initial conditions and controls

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
| `initial_conditions` | Nonpositive or non-ascending layer depths, water outside 0 to 1, negative ammonium, nitrate or residue, and detail values outside the ranges below. Layers may go deeper than the soil profile. Values other than a dict or the quoted string `"off"` are rejected. |
| `controls` | Simulation or management codes outside the tables below, automatic values outside their ranges, an invalid automatic planting window, an `output_interval` that is not a positive integer, `years` that is not a positive integer (or too wide for DSSAT's NYERS column), a bad `start_date`. |

A misspelled field or a misnamed section is reported by name with the allowed list, and every
problem of every treatment is reported at once. Crop-specific rules are still DSSAT's to check
at run time.

A changed `controls` `start_date` replaces the FileX `SDATE` in the weather-coverage and
planting-date checks under START S. Under START P the effective planting date is
the simulation start date. `controls.start_date` replaces SDATE under START S only.
The FileX `START` setting
is left as it is. See [simulation start dates](simulation.md#create-a-simulation-and-inspect-the-checks).

## Residues, tillage and harvest

```yaml
treatments:
  1:
    controls: {residue: "R", tillage: "Y", harvest_management: "R"}
    residues:
      - {date: "1982-02-25", material: "RE001", amount: 1500, n: 0.8, depth: 15}
    tillage:
      - {date: "1982-02-25", implement: "TI005", depth: 20}
      - {date: "1982-02-25", implement: "TI003", depth: 10}
    harvest:
      - {date: "1982-06-30", stage: "GS003", component: "IBHCS", size: "IBHCS", product_percent: 100, byproduct_percent: 100}
```

| Section | Field | DSSAT column | Required | Units / allowed values |
|---|---|---|---|---|
| `residues` | `date` | RDATE | Yes | Valid quoted `"YYYY-MM-DD"` string, within weather range |
| `residues` | `material` | RCOD | Yes | `[A-Za-z]{2}[0-9]{3}`: two ASCII letters + three digits |
| `residues` | `amount` | RAMT | Yes | kg/ha, strictly above 0 |
| `residues` | `n` | RESN | No | %, 0 to 100 inclusive |
| `residues` | `p` | RESP | No | %, 0 to 100 inclusive |
| `residues` | `k` | RESK | No | %, 0 to 100 inclusive |
| `residues` | `incorporation` | RINP | No | %, 0 to 100 inclusive |
| `residues` | `depth` | RDEP | No | cm, at least 0 |
| `residues` | `method` | RMET | No | `[A-Za-z]{2}[0-9]{3}` |
| `tillage` | `date` | TDATE | Yes | Valid quoted `"YYYY-MM-DD"` string, within weather range |
| `tillage` | `implement` | TIMPL | Yes | `[A-Za-z]{2}[0-9]{3}` |
| `tillage` | `depth` | TDEP | Yes | cm, at least 0 |
| `harvest` | `date` | HDATE | Yes | Valid quoted `"YYYY-MM-DD"` string, within weather range |
| `harvest` | `stage` | HSTG | No | `[A-Za-z]{2}[0-9]{3}` |
| `harvest` | `component` | HCOM | No | 1 to 5 printable ASCII characters without spaces (`[!-~]{1,5}`) |
| `harvest` | `size` | HSIZE | No | 1 to 5 printable ASCII characters without spaces (`[!-~]{1,5}`) |
| `harvest` | `product_percent` | HPC | No | %, 0 to 100 inclusive |
| `harvest` | `byproduct_percent` | HBPC | No | %, 0 to 100 inclusive |

Each section is a list of event dicts. Dates must be in non-descending order;
several events on the same date are allowed and keep their supplied order.
Irrigation and fertilizer still require unique, ascending dates. These field
operations accept calendar dates only, with no `days_after_planting` field.
Numbers must be finite Python integers or floats, never strings or booleans.
Unknown keys are rejected, and every value must fit its FileX column.
Omitted optional fields and the names RENAME, TNAME and HNAME write DSSAT's -99.

Omit a section to keep the FileX level, or give `[]` to set MR (residues), MT
(tillage) or MH (harvest) to 0. A fallow's `harvest: []` is rejected because it
needs its scheduled end; omit `harvest` to keep that end.

For a treatment, `check()` uses `controls.residue` (RESID) and
`controls.harvest_management` (HARVS) when supplied, otherwise the treatment's
SIMULATION CONTROLS level. Codes are quoted, case-sensitive strings:

| Controls field | DSSAT column | Allowed codes | Allowed supplied events |
|---|---|---|---|
| `residue` | RESID | `"R"`, `"D"`, `"N"` | R accepts dated residue events; D and N reject non-empty `residues` |
| `harvest_management` | HARVS | `"A"`, `"M"`, `"R"`, `"D"` | R and M accept dated harvest events; A and D reject non-empty `harvest` |
| `tillage` | TILL | `"Y"`, `"N"` | Y applies tillage; there is no tillage/event code check |

RESID D and HARVS D read days after planting, which these sections do not
support. RESID N ignores residue events; HARVS A uses the automatic harvest
block, which cannot yet be edited through experiment data. HARVS G is not
accepted. Empty residues do not trigger a RESID code problem. A crop under
effective HARVS R must have at least one usable dated harvest event: supplying
`harvest: []` fails. If `harvest` is omitted, the inherited MH level must be
nonzero and contain a usable HDATE. This check runs even without management
edits, fixing [#192](https://github.com/AbdelrahmanAmr3/dssatlab/issues/192).
An inherited HDATE under HARVS R must also be on or after both the known
simulation start and planting dates, including experiment-data overrides. Under
effective planting management A or F, DSSAT chooses the planting date, so the
reported PDATE is ignored and only the simulation-start bound applies
([#206](https://github.com/AbdelrahmanAmr3/dssatlab/issues/206)). FileX YYDDD dates
use DSSAT's cutoff: years 00 through 40 mean 2000 through 2040, and 41 through
99 mean 1941 through 1999. The message names the harvest level and each failed
bound, for example:

```text
Treatment 1: FileX HDATE '82054' (1982-02-23) in harvest level 1 is before simulation start date (1982-02-25) and planting date (1982-02-25). Move HDATE on or after these bounds, or change the start or planting date.
```

For a sequence the prefix also names `rotation[R]`.
It does not require events under M/A or for fallows; other event/code rules still
apply. The checks ask you to change the events or code; dssatlab never changes
a code for you. For a crop treatment with no dated harvest under R, the message is:

```text
Treatment 1: harvest management is "R" (reported dates), but there are no harvest events with a date. Add a harvest event, or set controls harvest_management to another code.
```

For sequences, the codes come from each component's own SM level; component
`controls` edits are not supported. See the
[component period rules](sequence.md#keep-dates-inside-the-components-period).

See [ADR 0021](../adr/0021-field-operations-as-event-sections.md).

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
| `harvest_management` | HARVS | `"A"`, `"M"`, `"R"`, `"D"` | Quoted, case-sensitive letter |
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
simulation start date. Given window dates
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

Residues on UFGA7901 and tillage on MSKB8921/MSKB8902 rebuilt from stock through
experiment data matched the stock FileX runs exactly on the same weather file.

On UFGA7601 peanut under HARVS M set through `controls.harvest_management`,
harvest event dates `"1976-09-15"` and
`"1976-10-01"` gave identical Summary results: HDAT stayed `1976-09-18`.
Changing HPC from 100 to 50 halved HWAH (4760 to 2380 kg/ha), while HWAM
stayed 4760 kg/ha. Changing HSTG from GS003 to GS002 left HDAT unchanged.
HBPC was held at 0 and HCOM/HSIZE at IBHCS, so this proof makes no claim
about by-product removal, harvest component or size sensitivity.

## Not included

Editing `.ECO` or `.SPE` files, cultivar coefficients per rotation component,
generated weather and replicates, automatic nitrogen, residue and harvest,
the automatic irrigation stop stage (IROFF), and per-layer roots.
To build a FileX from nothing, use a [FileX template](simulation.md). See the
[roadmap](../reference/roadmap.md) and [ADR 0005](../adr/0005-experiment-data-edits-an-existing-filex.md).
