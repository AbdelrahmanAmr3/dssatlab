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

The commented file lists the treatment numbers found in the FileX (and nothing else from it).
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
| `initial_conditions` | Layer depths that do not ascend, water outside 0 to 1, negative ammonium, nitrate or residue, and, when you pass `soil=`, a layer deeper than the soil profile. |
| `controls` | `water` or `nitrogen` other than `"Y"`/`"N"`, an `output_interval` that is not a positive integer, `years` that is not a positive integer (or too wide for DSSAT's NYERS column), a bad `start_date`. |

A misspelled field or a misnamed section is reported by name with the allowed list, and every
problem of every treatment is reported at once. Crop-specific rules are still DSSAT's to check
at run time.

A changed `controls` `start_date` replaces the FileX `SDATE` in the weather-coverage and
planting-date checks. The FileX `START` setting is left as it is.

## Run it

```python
sim = dl.Simulation("UFGA8201.MZX", treatment=1, weather="weather.csv",
                    management="experiment.yaml")
problems = sim.check()
result = sim.run()
```

The copied FileX gets a new `CULTIVARS`, `INITIAL CONDITIONS` or `SIMULATION CONTROLS` level for
each section you gave, and only the selected treatment is repointed. The `.CUL`, `.ECO` and
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

## Not included

Building a FileX from nothing, writing `.CUL`, `.ECO` or `.SPE` parameters, simulation controls
beyond the five above, and other initial-condition detail such as per-layer roots. See the
[roadmap](../reference/roadmap.md) and [ADR 0005](../adr/0005-experiment-data-edits-an-existing-filex.md).
