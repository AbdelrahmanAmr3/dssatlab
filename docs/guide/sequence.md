# Sequence analysis

A single-crop or seasonal simulation evaluates one crop grown in isolated seasons. In crop rotations, however, crops are grown one after another on the same field over multiple years (for example, dry bean followed by fallow, followed by soybean and fallow), with the soil water and nitrogen state carried over continuously from one crop to the next. In DSSAT, this is a **sequence analysis**.

In `dssatlab`, you run a sequence simply by creating a `Simulation` for a treatment that defines a sequence in an existing FileX. `dssatlab` detects the rotation components automatically, checks all inputs, writes a batch file (`DSSBatch.v48`) into the simulation folder, and runs DSSAT in sequence mode (`Q`) without needing any extra flags ([ADR 0013](../adr/0013-sequences-run-in-mode-q-through-a-batch-file.md)).

With a FileX and its supporting DSSAT files already prepared, you can also call
`dl.run("MSKB8902.SQX")`. `run()` selects Q from the treatment rows, whatever the
extension (except `.FCX`, which selects forecast mode Y). It writes the batch file
in the FileX folder and collects it into the run directory. If that FileX has
more than one treatment number, select each with `treatment=n`. See
[run modes and guards](run-filex.md#run-modes-sequences-and-forecasts).

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

Identical TREATMENTS rows remain separate ([#207](https://github.com/AbdelrahmanAmr3/dssatlab/issues/207)).
`run()` selects Q when the selected treatment has two rows, even if their text
is identical. `Simulation.check()` reports their duplicate R numbers with the
distinct-number message below. On real DSSAT, two identical rows ran in Q and
produced 2 rows matching a hand run.

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
The batch file moves into the run directory with the outputs on success or
failure; a failed launch removes it.

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
4. **`NREPS` must be 1 with measured weather**: With measured daily weather, running multiple replicates repeats identical rows:
   ```text
   FileX NREPS 5 for sequence treatment 1: with measured weather every replicate repeats the same rows. Set NREPS to 1.
   ```
   With generated weather (W or S), larger NREPS values are accepted; see
   [generated weather and replicates](generated-weather.md#replicate-a-sequence-and-read-every-row).
5. **Measured weather coverage through the last component's known end**: Weather must continuously cover the simulation start through the end of the component that crosses DSSAT's stopping boundary. Under DSSAT's calendar rule (`CSM.for`), that boundary is:
   `(start year + years)` at the start date's day of year, minus one day.
   DSSAT tests the boundary after finishing a component, so that component can
   end later. Checks follow scheduled planting, fallow and harvest dates across
   the cycles, using the effective `NYERS` and experiment overrides. For example,
   if the sequence starts on `1978-04-20` and runs for `NYERS 10`, the boundary is
   `1988-04-18` (1988 is a leap year). When the scheduled final end equals that
   boundary and weather ends on `1987-12-31`, `check()` reports:
   ```text
   FileX NYERS 10: the sequence runs from 1978-04-20 through 1988-04-18, after the weather data ends (1987-12-31). Supply weather through 1988-04-18, or fewer years.
   ```
   If `years` was set via experiment data controls, the prefix is `Controls years 10: ...`.
6. **Experiment data restrictions**: A sequence entry accepts `controls` with `years`, `start_date`, `weather_source`, `replicates` and `random_seed`, and `rotation` for edits to individual crop or fallow components. Years and start date apply to a copy of the first component's controls level; the three weather controls apply to every controls level the sequence uses. See [Experiment data per rotation component](#experiment-data-per-rotation-component) for the supported sections and date checks.

This fixes [#205](https://github.com/AbdelrahmanAmr3/dssatlab/issues/205): on real
DSSAT, MSKB8921 with weather ending 1998-02-28 was refused because it needs
1998-05-06, and complete weather ran 18 rows. When an end depends on maturity
or automatic management and cannot be known before the run, the checks retain
the boundary requirement. Missing weather beyond it is caught by the post-run
`WARNING.OUT` scan; passing the checks does not predict maturity.

FileX dates use DSSAT's two-digit-year rule: years 00-35 are 2000-2035 and
36-99 are 1936-1999, including the sequence start and inherited component dates.
Weather written by dssatlab never chooses their century.

## Weather and replicate settings in DSSAT sample sequence files

DSSAT sample sequences such as `UFGA7874.SQX` use WTHER W and NREPS above 1.
Pass the matching climate file through `weather=` to keep their generated weather
and replicates; see the [generated weather guide](generated-weather.md).

To use your measured daily weather instead, set `weather_source: "M"` and
`replicates: 1` in the treatment's experiment data controls through `management=`.
These overrides reach every controls level the sequence uses. No source FileX
edit is needed. Supplying both daily weather and a climate file for this single
sequence is a problem because one input would be unused.

`FNAME Y` is accepted for sequences as well: readers find experiment-named files
such as `UFGA7804.OSU`. See [output naming rules](reading-results.md#standard-and-experiment-named-output-files).

## A rotation from the FileX template

In addition to running sequences from existing FileX files, you can build and run a sequence directly from a **FileX template** without hand-editing any FileX. Instead of single-crop keys (`crop`, `cultivar`, `planting`, `harvest_date`, `treatments`, `treatment_fields`), supply `treatment_name` and `rotation`, a list of **2 to 99 rotation components** ([ADR 0014](../adr/0014-rotation-in-the-filex-template.md)). The R numbers are 1 through the list length, including 10 through 99. Fewer than 2 or more than 99 are rejected with `Supply a list of 2 to 99 rotation components.`

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

### Start with a fallow

Only the first component may take `start_date`, and it must be a fallow with
`start_date` strictly before `end_date`. For example:

```yaml
# leading-fallow.yaml
treatment_name: "Fallow then maize"
rotation:
  - {crop: "fallow", start_date: "1977-12-15", end_date: "1978-03-14"}
  - crop: "maize"
    cultivar: {code: "IB0035"}
    planting:
      date: "1978-03-15"
      method: "S"
      distribution: "R"
      population: 7.2
      row_spacing: 75
      depth: 5
    harvest_date: "1978-08-01"
  - {crop: "fallow", end_date: "1978-12-14"}
```

Use this template through `filex_template="leading-fallow.yaml"` in the
Simulation example below, with weather covering the leading fallow too.
The simulation starts on 1977-12-15: SDATE and the generated FileX stem's year
come from that date, as do cycle length, weather coverage and component period
checks. A crop-first rotation still starts on its first planting date.
Experiment data `controls.start_date` can override SDATE for either form.

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

By default, the rotation runs for **one complete cycle**. dssatlab writes the
fewest years whose calculated stopping day reaches the last component's known
end as the first component's `NYERS`. For `rotation.yaml`, that is 1 year;
for `leading-fallow.yaml`, it is also 1 year. A leading fallow uses its
`start_date` instead of the first planting date when calculating this length.

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

1. **Leading fallow needs ordered dates**: a crop-first rotation starts on its
   planting date; a leading fallow needs `start_date` before `end_date`. Missing,
   unordered, or misplaced `start_date` gives messages such as:
   ```text
   FileX template, rotation[1]: a leading fallow needs start_date. Supply start_date before end_date.
   FileX template, rotation[1], start_date: 1978-03-14 is not before end_date (1978-03-14). Supply start_date before end_date.
   FileX template, rotation[2], start_date: only a leading fallow takes start_date. Remove start_date from this component.
   ```
2. **Last component needs a known end**: the final component must end on a definite date—either a fallow with `end_date` or a crop with `harvest_date`—so the cycle length is known and subsequent cycles start on time.
   ```text
   FileX template, rotation[4]: the last component needs a known end so the next cycle can start on time. Make it a fallow with end_date, or give it a harvest_date.
   ```
3. **Dates in rotation order**: each component's start date (planting date or fallow `end_date`) must be strictly after the previous component's last known date (its `harvest_date` or `end_date`, else its `planting` date).
   ```text
   FileX template, rotation[3], planting date: 1978-05-30 is not after rotation[2]'s end (1978-11-14). DSSAT would move it a year later. Supply rotation dates in order.
   ```
4. **Cycle closure**: the last component's end date day of year must be strictly before the first planting's day of year, or the leading fallow's `start_date` day of year, so the next cycle starts on time. The start cannot be January 1. The check calculates the DOY and suggests a valid end date:
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
scenario's `management` override. Each edit writes a level and repoints only that
component in the simulation folder's FileX. Other components, shared levels and the
original FileX stay unchanged. Omitted sections keep their levels. Edits apply in every
cycle, with DSSAT advancing the dates along with the component.

`write_experiment_template()` includes a commented `rotation` example. For a sequence,
replace the single-treatment sections with that example. Controls accept `years`,
`start_date`, `weather_source`, `replicates` and `random_seed`; FileX templates
still require measured weather and one replicate. Initial conditions and controls per component are not
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
reject non-empty `harvest`. A crop under HARVS R must have a dated harvest
event, including when no experiment data is supplied (see below). Tillage
has no code check; the component's TILL `"Y"` applies tillage. Generated templates
keep TILL `"N"`, so the tillage example above writes events but applying them
requires a copied FileX with that component at TILL `"Y"`. The codes are
never changed for you. For a single treatment, `controls.harvest_management`
sets HARVS (`"A"`, `"M"`, `"R"`, `"D"`); a sequence accepts only `years`,
`start_date`, `weather_source`, `replicates` and `random_seed` in treatment
controls, so change component management codes in the copied
FileX itself. See the [code rules and measured harvest behaviour](experiment.md#residues-tillage-and-harvest)
and [ADR 0021](../adr/0021-field-operations-as-event-sections.md).

### HARVS R needs a dated harvest

For every crop component, `check()` reads HARVS from its SM level. Under `"R"`
(reported dates), there must be at least one usable dated harvest event. A
supplied `harvest` list replaces the inherited events; `harvest: []` therefore
fails under R. If `harvest` is omitted, the FileX MH level must be nonzero and
contain a usable HDATE. The check runs even without experiment data and reports:

```text
Treatment 1, rotation[3]: harvest management is "R" (reported dates), but there are no harvest events with a date. Add a harvest event to this component, or change HARVS in the FileX simulation controls.
```

Add a dated event under that component's `harvest`, or change HARVS in the copied
FileX. Sequence experiment data cannot set `harvest_management`. This fixes
[#192](https://github.com/AbdelrahmanAmr3/dssatlab/issues/192); the requirement
does not apply to fallows or crops under M/A. Other event/code checks still apply.

### Reuse free levels past 99

An edit normally appends a level numbered highest + 1. When that would pass 99,
it reuses the lowest number from 1 through 99 that no TREATMENTS row references
after the edited row is repointed. The old rows for that level are replaced in
every header block of the section, in the FileX copy only. A level still used by
another component or treatment is kept. If no number is free, `check()` reports
the existing level-limit problem.

This applies to planting, irrigation, fertilizer, harvest, residue, tillage and
chemical event sections, cultivar, initial conditions and controls wherever
dssatlab writes those levels. It adds no new experiment-data sections or
per-component controls. Below the limit, output remains byte-identical to the
previous writer. This fixes [#193](https://github.com/AbdelrahmanAmr3/dssatlab/issues/193);
see [ADR 0023](../adr/0023-reuse-free-levels-past-99.md).

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

## Checked on real DSSAT for 0.17

- `run()` on stock MSKB8902.SQX in Q mode matched DSSAT's own run on all 55/55
  Summary rows, with identical RUNNO, TRNO, HWAM, HDAT, CWAM and PRCM.
- A 12-component rotation with NYERS 2 matched the same FileX run by hand.
  A 99-component rotation template ran with 99 Summary rows and no ERROR.OUT.
- HARVS R with `harvest: []` was rejected; adding a dated harvest passed the checks.
- MSKB8902 rebuilt with 56 harvest events used levels 57 through 99, then reused
  1 through 13, and matched the stock run on all 55/55 rows exactly.

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
    filex="ROTATE01.SQX",
    weather=weather_rows,
)

combined = dl.combine_summaries(results)
all_stats = dl.summarize_seasons(combined, variables=["HWAM"])
```

Each sequence is simulated independently in DSSAT sequence mode, and `combine_summaries()` preserves the scenario, treatment, rotation component (`R#`), and crop (`CR`) for analysis across rotations.
