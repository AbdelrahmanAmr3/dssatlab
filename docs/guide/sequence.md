# Sequence analysis

A single-crop or seasonal simulation evaluates one crop grown in isolated seasons. In crop rotations, however, crops are grown one after another on the same field over multiple years (for example, dry bean followed by fallow, followed by soybean and fallow), with the soil water and nitrogen state carried over continuously from one crop to the next. In DSSAT, this is a **sequence analysis**.

In `dssatlab`, you run a sequence simply by creating a `Simulation` for a treatment that defines a sequence in an existing FileX. `dssatlab` detects the rotation components automatically, checks all inputs, writes a batch file (`DSSBatch.v48`) into the simulation folder, and runs DSSAT in sequence mode (`Q`) without needing any extra flags ([ADR 0013](../adr/0013-sequences-run-in-mode-q-through-a-batch-file.md)).

## What is a sequence in a FileX?

In a standard FileX (`*.SQX` or other experiment files), a sequence is a treatment number (`N`) that appears on multiple rows in the `*TREATMENTS` section. Each row represents one **rotation component**, distinguished by its rotation component number in the `R` column:

```text
*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 1 0 Bean                       1  1  0  1  1  1  0  0  0  0  0  0  1
 1 2 1 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  1  2
 1 3 1 0 Bean                       1  1  0  0  2  1  0  0  0  0  0  0  3
 1 4 1 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  2  2
 1 5 1 0 Soybean                    3  1  0  0  1  1  0  0  0  0  0  0  4
 1 6 1 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  3  2
```

Here, treatment 1 is a sequence of 6 rotation components: bean (`BN`), fallow (`FA`), bean (`BN`), fallow (`FA`), soybean (`SB`), and fallow (`FA`). Each component has its own cultivar (`CU`), planting (`MP`), irrigation (`MI`), and simulation controls (`SM`) levels, but all components grow on the same field (`FL 1`).

DSSAT runs the components sequentially: component 1 runs until harvest, component 2 (fallow) begins the very next day carrying over the soil water and nitrogen, and the cycle continues until the sequence's duration has elapsed.

## Run a sequence with `Simulation`

To run a sequence, pass the FileX path and sequence treatment number to `dl.Simulation`, along with your daily weather and soil data:

```python
import dssatlab as dl

sim = dl.Simulation(
    "UFGA7804.SQX",
    treatment=1,
    weather=weather_rows,
    soil="soil.csv",  # optional soil template; without it the sibling .SOL files are copied
    management={"treatments": {1: {"controls": {"years": 9}}}},
)

# 1. Run strict pre-run checks
problems = sim.check()
# Report: "FileX: treatment 1 is a sequence of 6 rotation components (R 1-6: BN, FA, BN, FA, SB, FA); it runs in DSSAT's sequence mode."

# 2. Run the simulation
result = sim.run()
```

When `sim.run()` executes, `dssatlab` writes `DSSBatch.v48` into the simulation folder and runs `<executable> Q DSSBatch.v48` with standard input closed, keeping your original FileX folder untouched.

## Sequence checks

Because DSSAT's sequence mode has strict formatting and execution constraints, `dssatlab` validates all sequence requirements before writing files or running DSSAT:

1. **FileX filename length**: DSSAT's sequence mode requires the FileX filename to be exactly 12 characters (8.3 format, e.g. `UFGA7804.SQX`). Shorter or longer names cause DSSAT to crash:
   ```text
   A sequence runs in DSSAT's sequence mode, which needs a FileX filename of exactly 12 characters (8 plus the extension, like UFGA7804.SQX); 'SEQ1.SQX' has 8. Rename the FileX.
   ```
2. **Distinct positive rotation component numbers (`R`)**: Every component row for the treatment must have a distinct, positive integer in column `R`:
   ```text
   Treatment 1 has rotation components R 1, 1: give each row of a sequence its own R number.
   ```
3. **Single field (`FL`)**: Every rotation component must use the same field number, ensuring weather and soil data match:
   ```text
   Treatment 1 is a sequence whose components use fields 1 and 2; dssatlab writes one weather file and one soil profile, so give every component the same field (FL).
   ```
4. **`NREPS` must be 1**: With measured daily weather, running multiple replicates repeats identical rows:
   ```text
   FileX NREPS 5 for sequence treatment 1: with measured weather every replicate repeats the same rows. Set NREPS to 1.
   ```
5. **Weather coverage through the sequence's last day**: Weather data must continuously cover the simulation start date through the sequence's last day. Under DSSAT's sequence end rule (`CSM.for`), the sequence ends at:
   `(start year + years)` at the start date's day of year, minus one day.
   For example, if the sequence starts on `1978-04-20` and runs for `NYERS 10` (or `controls: years: 10`), the end date is `1988-04-18` (since 1988 is a leap year). If weather data ends earlier (e.g. `1987-12-31`), `check()` reports:
   ```text
   FileX NYERS 10: the sequence runs from 1978-04-20 through 1988-04-18, after the weather data ends (1987-12-31). Supply weather through 1988-04-18, or fewer years.
   ```
   If `years` was set via experiment data controls, the prefix is `Controls years 10: ...`.
6. **Experiment data restrictions**: A sequence entry accepts `controls` with `years` and/or `start_date`, and `rotation` for edits to individual crop or fallow components. Controls apply to a copy of the first component's controls level. See [Experiment data per rotation component](#experiment-data-per-rotation-component) for the supported sections and date checks.

## Weather and replicate settings in DSSAT sample sequence files

DSSAT ships sample sequence files (such as `UFGA7804.SQX`) that contain configuration settings that silently break automated runs with your own data:

- **`WTHER W` in `*SIMULATION CONTROLS -> METHODS`**: Sets weather generation mode to `W` (weather generator), causing DSSAT to generate artificial weather from climate files (`UFGA.CLI`) and silently ignore your supplied weather data.
- **`NREPS 5` in `*SIMULATION CONTROLS -> GENERAL`**: Runs 5 replicates of identical simulated rows.

`dssatlab` checks WTHER in every copied FileX and requires NREPS 1 for sequences.
Problems raise a `DSSATCheckError`:

```text
FileX WTHER 'W' in controls level 1 (treatment 1): DSSAT would generate weather and ignore the weather data supplied. Set WTHER to M.
```

`FNAME Y` is accepted for sequences as well: readers find experiment-named files
such as `UFGA7804.OSU`. See [output naming rules](reading-results.md#standard-and-experiment-named-output-files).

### How to fix a copied FileX

Before running a copied DSSAT sequence file, edit the text or modify a copy using simple string replacements:

```python
from pathlib import Path

path = Path("UFGA7804.SQX")
text = path.read_text(encoding="latin-1")

# 1. Set measured weather in all METHODS rows: W -> M
text = text.replace(" ME              W ", " ME              M ")

# 2. Set NREPS to 1 in level 1's GENERAL row: 5 -> 1
text = text.replace(" 1 GE             10     5 ", " 1 GE             10     1 ")

path.write_text(text, encoding="latin-1")
```

Once updated, the FileX passes all checks.

## A rotation from the FileX template

In addition to running sequences from existing FileX files, you can build and run a sequence directly from a **FileX template** without hand-editing any FileX. Instead of single-crop keys (`crop`, `cultivar`, `planting`, `harvest_date`, `treatments`, `treatment_fields`), supply `treatment_name` and `rotation`, a list of 2 to 9 rotation components ([ADR 0014](../adr/0014-rotation-in-the-filex-template.md)).

```yaml
# rotation.yaml
treatment_name: "Maize-wheat rotation"
rotation:
  - crop: "maize"
    cultivar:
      code: "IB0035"
    planting:
      date: "1978-03-15"
      method: "S"
      distribution: "R"
      population: 7.2
      row_spacing: 75
      depth: 5
  - crop: "fallow"
    end_date: "1978-11-14"
  - crop: "wheat"
    cultivar:
      code: "IB1500"
    planting:
      date: "1978-11-15"
      method: "S"
      distribution: "R"
      population: 7.2
      row_spacing: 75
      depth: 5
  - crop: "fallow"
    end_date: "1979-03-14"
```

A crop component takes the standard template crop fields (`crop`, `cultivar.code`, `planting`, and optional `harvest_date`, validated under the same rules as the single-crop template, including potato requirements). A fallow component is defined with `{crop: "fallow", end_date: "YYYY-MM-DD"}`.

### Run with `Simulation`

Pass the template path or dictionary to `dl.Simulation` alongside your daily weather and soil data:

```python
import dssatlab as dl

sim = dl.Simulation(
    filex_template="rotation.yaml",  # or a Python dict
    weather=weather_rows,
    soil="soil.csv",  # or a list of soil layer dicts
)

# 1. Run strict pre-run checks
problems = sim.check()
# Report: "FileX: treatment 1 is a sequence of 4 rotation components (R 1-4: MZ, FA, WH, FA); it runs in DSSAT's sequence mode."

# 2. Run the rotation simulation
result = sim.run()
```

When `sim.run()` executes, `dssatlab` writes `<station><yy>01.SQX`, copies the genotype files (`.CUL`, `.ECO`, `.SPE`) for every crop in the rotation into the simulation folder, writes `SOIL.SOL` and `DSSBatch.v48`, and executes in DSSAT's sequence mode (`Q`).

### One cycle by default, controls `years` for more

By default, the rotation runs for **one complete cycle**. The cycle length in years (`year of last end + 1 day minus first planting year` = 1979 - 1978 = 1 year) is automatically calculated and written as the first component's `NYERS`. Running the single-cycle simulation above returns 4 summary rows (one for each rotation component).

To run more cycles over multiple years, pass experiment data setting controls `years`:

```python
sim = dl.Simulation(
    filex_template="rotation.yaml",
    weather=weather_rows,
    soil="soil.csv",
    management={"treatments": {1: {"controls": {"years": 3}}}},
)
result = sim.run()
```

With `years: 3`, the rotation runs for 3 full cycles, returning 12 summary rows cycling through components 1–4. Experiment data can also edit individual crop components through `rotation`, as described below. You can also run a rotation template with `run_treatments(filex_template=rotation)`.

### Pre-run rotation date checks

DSSAT's sequence mode enforces a silent date-advancement rule: it advances each component's dates forward by whole years, preserving their day of year (DOY), until they fall on or after the component's start date (the day following the previous component's end). Dates entered out of order, or a final component that ends too late in the calendar year, cause DSSAT to silently skip a full year without any warning or error.

To protect against silent year skips, `dssatlab` validates all calendar dates before writing files or running DSSAT:

1. **First component must be a crop**: the simulation begins on its planting date; a fallow cannot be the first component.
   ```text
   FileX template, rotation[1]: the first component must be a crop; the simulation starts on its planting date. Move the fallow later in the rotation.
   ```
2. **Last component needs a known end**: the final component must end on a definite date—either a fallow with `end_date` or a crop with `harvest_date`—so the cycle length is known and subsequent cycles start on time.
   ```text
   FileX template, rotation[4]: the last component needs a known end so the next cycle can start on time. Make it a fallow with end_date, or give it a harvest_date.
   ```
3. **Dates in rotation order**: each component's start date (planting date or fallow `end_date`) must be strictly after the previous component's last known date (its `harvest_date` or `end_date`, else its `planting` date).
   ```text
   FileX template, rotation[3], planting date: 1978-05-30 is not after rotation[2]'s end (1978-11-14). DSSAT would move it a year later. Supply rotation dates in order.
   ```
4. **Cycle closure**: the last component's end date day of year must be strictly before the first component's planting day of year so the next cycle starts on time. The check calculates the DOY and suggests a valid end date:
   ```text
   FileX template, rotation: the last component ends on 1979-03-20 (day 79 of the year), not before the first planting's day of the year (day 74, 1978-03-15); DSSAT would start the next cycle a year late. End the last component before day 74, for example on 1979-03-14.
   ```

### The maturity-overrun caveat

When a crop is harvested at maturity (`harvest_date` omitted), DSSAT determines its actual harvest date dynamically based on weather conditions during simulation. In certain weather years, crop development may be delayed, causing the crop to mature after the next component's calendar date. When this happens, DSSAT moves the next component forward by an entire year. Because weather-driven maturity cannot be predicted prior to the run, this overrun cannot be caught by pre-run checks. To prevent unintended year shifts, specify an explicit `harvest_date` or leave an adequate buffer margin (such as a fallow period) before the following crop.

## Experiment data per rotation component

Give each crop its own planting, cultivar, fertilizer, irrigation, residues, tillage or
harvest in experiment data; fallows take residues, tillage and harvest. Put
`rotation` beside `controls` under the treatment number: it is a dictionary keyed by the
rotation component's **R number**, as shown in the FileX TREATMENTS row and Summary's `R#`.
For a rotation FileX template, R 1 is the first entry of the template's `rotation` list,
R 2 the second, and so on. A copied FileX keeps its own R numbers.

For the maize, fallow, wheat, fallow sequence above, save this as `experiment.yaml`:

```yaml
treatments:
  1:
    controls: {years: 3}
    rotation:
      1:
        fertilizer:
          - {date: "1978-03-15", material: FE005, application: AP001, depth: 5, n: 60}
          - {date: "1978-04-20", material: FE005, application: AP001, depth: 5, n: 60}
        irrigation:
          - {date: "1978-05-01", amount: 25, method: IR001}
      2:
        tillage:
          - {date: "1978-08-01", implement: "TI005", depth: 20}
          - {date: "1978-08-01", implement: "TI003", depth: 10}
        harvest:
          - {date: "1978-11-14"}
      3:
        cultivar: {crop: WH, code: IB1500}
        fertilizer:
          - {date: "1978-11-15", material: FE005, application: AP001, depth: 5, n: 40}
```

Each crop component takes optional `planting`, `cultivar`, `fertilizer`, `irrigation`,
`residues`, `tillage` and `harvest` with the
same fields, units and checks as a [single treatment](experiment.md), except that
irrigation accepts dated events in list form only. `days_after_planting` (IDATE)
and the `{efficiency, events}` dict (EFIR) are rejected per component; irrigation
management is read from each component's SM level. Pass the YAML path or
an equivalent Python dict through `management=`:

```python
sim = dl.Simulation(
    filex_template="rotation.yaml",
    weather=weather_rows,
    soil="soil.csv",
    management="experiment.yaml",
)
sim.check()
result = sim.run()
```

The same experiment data works with a copied sequence FileX, `run_treatments()` and a
scenario's `management` override. Each edit adds a new level and repoints only that
component in the simulation folder's FileX. Other components, shared levels and the
original FileX stay unchanged. Omitted sections keep their levels. Edits apply in every
cycle, with DSSAT advancing the dates along with the component.

`write_experiment_template()` includes a commented `rotation` example. For a sequence,
replace the single-treatment sections with that example and keep only `years` and
`start_date` in `controls`. Initial conditions and controls per component are not
supported. Fallow components take only `residues`, `tillage` and `harvest`; planting,
cultivar, fertilizer and irrigation are rejected. A fallow's `harvest: []` is rejected
because it needs its scheduled end; omit `harvest` to keep the FileX end. A cultivar
must keep the component's crop. `check()` rejects `rotation` on a non-sequence treatment and unknown R numbers, for
example: "the sequence has rotation components R 1-4. Use one of those numbers."

### Field operation fields per component

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

Residue events need the component's RESID `"R"`; `"D"` and `"N"` reject non-empty
`residues`. Harvest events need its HARVS `"R"` or `"M"`; `"A"` and `"D"`
reject non-empty `harvest`. Empty lists do not trigger code problems. Tillage
has no code check; the component's TILL `"Y"` applies tillage. Generated templates
keep TILL `"N"`, so the tillage example above writes events but applying them
requires a copied FileX with that component at TILL `"Y"`. The codes are
never changed for you. For a single treatment, `controls.harvest_management`
sets HARVS (`"A"`, `"M"`, `"R"`, `"D"`); a sequence accepts only `years` and
`start_date` in treatment controls, so change component codes in the copied
FileX itself. See the [code rules and measured harvest behaviour](experiment.md#residues-tillage-and-harvest)
and [ADR 0021](../adr/0021-field-operations-as-event-sections.md).

### Keep dates inside the component's period

DSSAT can silently skip fertilizer and irrigation outside a component's period.
Before writing files, `check()` checks planting overrides and every supplied fertilizer,
irrigation, residue, tillage and harvest event date against the known dates in the
**first cycle**, including planting overrides:

- The lower bound is strictly after the previous component's last known date: its harvest
  or fallow end, otherwise its planting date. For the first component, dates must be on
  or after the simulation start.
- The upper bound is the component's own harvest or fallow end date, inclusive. Without
  that date, events must be strictly before the next component's first known date: its
  planting date or, for a fallow, its end date. Without either, there is no upper bound.

For example, wheat fertilizer on October 1 falls before the preceding fallow ends:

```text
Management data treatment 1, rotation component 3, fertilizer, event 1, field 'date': 1978-10-01 is not after rotation component 2's end (1978-11-14). DSSAT applies a component's events only while it runs and would skip this one without a warning. Move the date into the component's period.
```

Under effective HARVS `"R"`, the latest supplied `harvest` event date replaces the
component's known end, including a fallow's `end_date`. The following component's
checks use that end. For a rotation FileX template, editing the final component's
harvest also updates the default cycle length, cycle-closure and weather coverage
checks. Under HARVS `"M"`, HDATE supplies no end bound even if populated: the report
prints the existing skipped-bound note, and the next known component date may still
give an upper bound. The actual maturity date remains unknown before the run.

An unreadable or `-99` FileX date supplies no bound; the check report notes which bound
could not be checked. Dates are also checked against the supplied weather range.

**Events after a crop's maturity cannot be checked before the run:** maturity depends on
the weather, and a crop can end before the next known component date. Leave a margin
before the expected crop end, even when `check()` passes. Inspect Summary `NICM` (nitrogen
applied, kg N/ha) and `IRCM` (irrigation applied, mm) to see what DSSAT actually applied.

On real DSSAT, the three-cycle probe with two 60 kg N/ha maize events and 50 mm total maize
irrigation returned `NICM 120` and `IRCM 50` on every maize row, and `NICM 40` on every wheat
row. The YAML above illustrates one 25 mm irrigation event; tutorial Case 11 uses two
25 mm events for the probe's 50 mm total. Use `summarize_seasons()` to compare yields per
rotation component across cycles. See [ADR 0015](../adr/0015-experiment-data-per-rotation-component.md).

## Summary rows and rotation components

In a sequence analysis, `result.summary()` returns one row per rotation component run:

- `R#`: The rotation component number (e.g. 1 to 6).
- `CR`: The crop code for that component (`BN` for dry bean, `FA` for fallow, `SB` for soybean).
- `HWAM`: Harvested yield (kg/ha) for that component run (`0` or missing for fallow).
- `PDAT`, `MDAT`: Planting and maturity dates for each individual crop cycle.

```python
import pandas as pd

summary_df = pd.DataFrame(result.summary())
print(summary_df[["R#", "CR", "PDAT", "MDAT", "HWAM"]])
```

### Continuous soil water series

While `Summary.OUT` produces separate rows for each component run, daily outputs like `SoilWat.OUT` (`result.soil_water()`) and `Weather.OUT` (`result.weather()`) produce **one continuous series** spanning the entire multi-year sequence. DSSAT writes them only when the first component's OUTPUTS row asks for them (`WAOUT Y` for soil water, `GROUT Y` for plant growth); `UFGA7804.SQX` ships with both set to `N`. You can inspect or plot the carry-over of soil water between successive crops across years:

```python
soil_water = dl.to_dataframe(result.soil_water())
# Continuous daily series from the start date across all rotation cycles
```

## Summarise sequence statistics with `summarize_seasons`

When you pass sequence summary rows to `summarize_seasons()`, `dssatlab` automatically groups rows by `(scenario, treatment, component)`:

```python
stats = dl.summarize_seasons(result.summary(), variables=["HWAM"])
df = dl.to_dataframe(stats)
print(df[["component", "crop", "variable", "seasons", "mean", "min", "max"]])
```

Output for `UFGA7804.SQX` treatment 1 with Gainesville weather 1978-1987 and controls `years: 9` (28 component runs):

```text
   component crop variable  seasons     mean   min   max
0          1   BN     HWAM        5   903.20   508  1754
1          2   FA     HWAM        5     0.00     0     0
2          3   BN     HWAM        5  1039.80   356  1534
3          4   FA     HWAM        5     0.00     0     0
4          5   SB     HWAM        4  3123.25  1855  3951
5          6   FA     HWAM        4     0.00     0     0
```

Grouping by `component` ensures that fallow zero yields do not dilute crop yields, and different crops in the rotation (such as bean and soybean) are summarized separately.

## Run several sequences with `run_treatments`

If a FileX contains multiple sequences (for example, comparing a 2-year rotation in treatment 1 with a 3-year rotation in treatment 2), calling `run_treatments()` with `treatments=None` automatically identifies each distinct treatment number once and executes each sequence in its own simulation folder:

```python
results = dl.run_treatments(
    filex="ROTATIONS.SQX",
    weather=weather_rows,
)

combined = dl.combine_summaries(results)
all_stats = dl.summarize_seasons(combined, variables=["HWAM"])
```

Each sequence is simulated independently in DSSAT sequence mode, and `combine_summaries()` preserves the scenario, treatment, rotation component (`R#`), and crop (`CR`) for analysis across rotations.
