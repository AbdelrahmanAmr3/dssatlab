# Run a Simulation with your management data

A `Simulation` can combine one treatment of an existing FileX with your daily
weather data, your soil profile, and your own management operations (planting,
irrigation schedules, fertilizer applications, residues, tillage and harvest). Prepare the FileX and its
supporting files, then [find or install a DSSAT executable](install.md). The examples use
`UFGA8201.MZX`; replace it with your FileX path and choose one of its treatments.

By default, a `Simulation` keeps the management levels defined in the FileX.
When you pass `management` to `Simulation`, dssatlab verifies your management data
against the FileX and weather data, copies the FileX into a fresh simulation folder,
writes your management levels into the copy, and repoints the selected treatment.
Your original FileX is never modified.

## Prepare the management template

Generate a commented YAML template in a notebook cell or Python script:

```python
import dssatlab as dl

dl.write_management_template("management.yaml")
```

This writes a UTF-8 YAML template documenting every field, its units, code
formats, and quoting rules. An existing destination raises `DSSATError`, preserving
any existing file.

When `filex=` is supplied, the template names each treatment once, using DSSAT's
fixed-column treatment numbers ([ADR 0018](../adr/0018-treatment-rows-read-with-dssats-fixed-columns.md)).

The template organizes operations under `treatments`, keyed by treatment number:

```yaml
# DSSATLab Management Template
treatments:
  1:
    # Planting details (optional section; omit to keep the FileX planting level)
    planting:
      date: "1982-02-26"          # Planting date (quoted "YYYY-MM-DD"); on or after simulation start date
      method: "S"                 # Planting method: single ASCII letter DSSAT code (e.g., S=seed, T=transplant)
      distribution: "R"           # Plant distribution: single ASCII letter DSSAT code (e.g., R=rows, H=hills, B=broadcast)
      population: 7.2             # Plant population at seeding, plants/m2 (must be > 0)
      row_spacing: 75.0           # Row spacing, cm (must be > 0)
      depth: 5.0                  # Planting depth, cm (must be >= 0)
      # Optional planting fields:
      emergence_date: "1982-03-05" # Emergence date (quoted "YYYY-MM-DD")
      emergence_population: 7.0   # Emergence population, plants/m2
      row_direction: 0.0          # Row direction, degrees from north
      planting_material_weight: 0.0 # Weight of planting material, kg/ha
      transplant_age: 0.0         # Transplant age, days
      transplant_environment: 0.0 # Transplant environment temperature, degrees C
      plants_per_hill: 1.0        # Plants per hill
      sprout_length: 0.0          # Sprout length, cm

    # Irrigation schedule (optional section; omit to keep the FileX level, or [] for none)
    irrigation:
      - date: "1982-03-15"        # Event date (quoted "YYYY-MM-DD"); must be ascending and unique
        amount: 30.0              # Water applied, mm (must be > 0)
        method: "IR001"           # Irrigation method: 2 ASCII letters + 3 digits (e.g., IR001)

    # Fertilizer schedule (optional section; omit to keep the FileX level, or [] for none)
    fertilizer:
      - date: "1982-03-20"        # Event date (quoted "YYYY-MM-DD"); must be ascending and unique
        material: "FE001"         # Fertilizer material: 2 ASCII letters + 3 digits (e.g., FE001)
        application: "AP001"      # Application method: 2 ASCII letters + 3 digits (e.g., AP001)
        depth: 5.0                # Application depth, cm (must be >= 0)
        n: 50.0                   # Elemental nitrogen applied, kg/ha (must be >= 0)
        # Optional fertilizer fields:
        p: 20.0                   # Elemental phosphorus applied, kg/ha (must be >= 0)
        k: 10.0                   # Elemental potassium applied, kg/ha (must be >= 0)
```

For residue, tillage and harvest comments too, use
`dl.write_experiment_template("experiment.yaml")`; `write_management_template()`
continues to cover planting, irrigation and fertilizer.

### Quoted ISO dates

Every calendar date in YAML or dictionary management data must be a **quoted string** in
`"YYYY-MM-DD"` format (for example, `"1982-02-26"`).

In YAML, bare unquoted dates like `1982-02-26` are automatically parsed into Python `date`
objects by some YAML loaders and rejected by others. Unquoted words like `no` can parse as
the boolean `False`. Quoting every date ensures unambiguous, strict parsing.

### Fields and units

Values use DSSAT's native units without automatic conversion:

| Section | Field | Required | Units / Format | Description and constraints |
| --- | --- | --- | --- | --- |
| `planting` | `date` | Yes | `"YYYY-MM-DD"` | Quoted ISO date; must be on or after simulation start date and within weather range |
| `planting` | `method` | Yes | single letter | DSSAT planting method code (e.g., `S` for seed, `T` for transplant) |
| `planting` | `distribution` | Yes | single letter | DSSAT plant distribution code (e.g., `R` for rows, `H` for hills, `B` for broadcast) |
| `planting` | `population` | Yes | plants/m² | Plant population at seeding; must be strictly positive (`> 0`) |
| `planting` | `row_spacing` | Yes | cm | Row spacing; must be strictly positive (`> 0`) |
| `planting` | `depth` | Yes | cm | Planting depth; must be nonnegative (`>= 0`) |
| `planting` | `emergence_date` | No | `"YYYY-MM-DD"` | Quoted emergence date |
| `planting` | `emergence_population`| No | plants/m² | Emergence population; defaults to `population` if omitted |
| `planting` | `row_direction` | No | degrees | Degrees from north |
| `planting` | `planting_material_weight`| No | kg/ha | Weight of planting material |
| `planting` | `transplant_age` | No | days | Age of transplants |
| `planting` | `transplant_environment`| No | °C | Transplant environment temperature |
| `planting` | `plants_per_hill` | No | count | Number of plants per hill |
| `planting` | `sprout_length` | No | cm | Sprout length |
| `irrigation` event | `date` | One timing field | `"YYYY-MM-DD"` | DSSAT IDATE: event date; ascending, unique, and within weather range |
| `irrigation` event | `days_after_planting` | One timing field | integer >= 0 | DSSAT IDATE: days counted from planting; not a boolean; ascending and unique |
| `irrigation` event | `amount` | Yes | mm | DSSAT IRVAL: finite number strictly above 0, not a string or boolean |
| `irrigation` event | `method` | Yes | `[A-Za-z]{2}[0-9]{3}` | DSSAT IROP: 2 ASCII letters + 3 digits (e.g., `"IR001"`) |
| `irrigation` dict | `efficiency` | Yes in dict form | above 0 and at most 1 | DSSAT EFIR: finite number, not a string or boolean; applies to this level's events |
| `irrigation` dict | `events` | Yes in dict form | list of event dicts | Same event fields as above; may be empty; no DSSAT column of its own |
| `fertilizer` | `date` | Yes | `"YYYY-MM-DD"` | Event date; must be ascending, unique, and within weather range |
| `fertilizer` | `material` | Yes | `[A-Za-z]{2}[0-9]{3}` | DSSAT fertilizer material code (e.g., `FE001`) |
| `fertilizer` | `application` | Yes | `[A-Za-z]{2}[0-9]{3}` | DSSAT application method code (e.g., `AP001`) |
| `fertilizer` | `depth` | Yes | cm | Placement depth in cm; must be nonnegative (`>= 0`) |
| `fertilizer` | `n` | Yes | kg/ha | Elemental nitrogen applied; must be nonnegative (`>= 0`) |
| `fertilizer` | `p` | No | kg/ha | Elemental phosphorus applied; must be nonnegative (`>= 0`, defaults to 0) |
| `fertilizer` | `k` | No | kg/ha | Elemental potassium applied; must be nonnegative (`>= 0`, defaults to 0) |

## Irrigation timing and efficiency

An event gives exactly one of `date` or `days_after_planting` (DSSAT IDATE).
Every event in a list must use the same timing kind, in ascending order without
duplicates. Under IRRIG D, the writer puts the day count itself in IDATE.
The dict form has exactly `efficiency` and `events`:

```yaml
treatments:
  1:
    controls: {irrigation_management: "D"}
    irrigation:
      efficiency: 0.75
      events:
        - {days_after_planting: 20, amount: 30, method: "IR001"}
        - {days_after_planting: 40, amount: 30, method: "IR001"}
```

The list form remains valid and writes EFIR 1. A dict with `events: []` writes
an irrigation level header with EFIR and no events; `irrigation: []` points MI
at level 0. EFIR applies to the irrigation level's **reported events**.
`controls.auto_irrigation_efficiency` (IREFF) applies to **automatic irrigation**.
All automatic irrigation and planting fields, their DSSAT columns and exact
ranges are listed in [automatic management](experiment.md#automatic-management).

`check()` uses `controls.irrigation_management` if supplied, otherwise IRRIG
from the treatment's SIMULATION CONTROLS level. It rejects events DSSAT would
ignore or misread and asks you to change the events or the code; it never changes
the code itself. Empty event lists are accepted with every code.

| Effective IRRIG | Allowed events when supplied | Real-DSSAT proof |
|---|---|---|
| `"A"` | No events; automatic refill | Proven |
| `"F"` | No events; automatic fixed amount | Proven |
| `"D"` | `days_after_planting` events only | Proven |
| `"R"` | Dated events only | Proven |
| `"N"` | No events; irrigation off | Proven |
| `"P"`, `"W"` | Dated events only | Written and checked, not proven on DSSAT |

If you supply `irrigation_management` and omit `irrigation` while the treatment
inherits a nonzero MI level, the checks ask for the section: give events matching
the code, or `[]`. An inherited MI 0 needs no section. This prevents old FileX
events being silently ignored under a new code.

For day events, planting date from your experiment-data `planting` section plus
the day count must fall inside the weather range. If that planting date is
unknown or invalid, effective PLANT is A/F, or weather coverage is unavailable,
the report prints a skipped-check note. It does not infer a planting date from
the FileX. Rotation components accept dated events in list form only; day events
and the efficiency dict are rejected. Values must also fit their FileX columns.
See [ADR 0020](../adr/0020-automatic-management-as-controls-fields.md).

## Residue, tillage and harvest events

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
It does not require events under M/A or for fallows; other event/code rules still
apply. The checks ask you to change the events or code; dssatlab never changes
a code for you. For a crop treatment with no dated harvest under R, the message is:

```text
Treatment 1: harvest management is "R" (reported dates), but there are no harvest events with a date. Add a harvest event, or set controls harvest_management to another code.
```

For sequences, the codes come from each component's own SM level; component
`controls` edits are not supported. See the
[component period rules](sequence.md#keep-dates-inside-the-components-period).

For the measured harvest behaviour, see
[Checked on real DSSAT](experiment.md#checked-on-real-dssat) and
[ADR 0021](../adr/0021-field-operations-as-event-sections.md).

## The check() report and rules

Instantiate `Simulation` with your management YAML file or dictionary:

```python
import dssatlab as dl

sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    management="management.yaml",
)
problems = sim.check()
```

When `management` is passed, `check()` automatically prints a structured **Checks** report:

```text
Checks
Weather data: OK
FileX: OK
Management data: OK
  Treatment 1: OK
    planting: OK
    irrigation: OK
    fertilizer: OK
Crop-specific fields are checked by DSSAT at run time.
```

If any check fails, the report marks the offending section as `REJECTED` and prints the
specific problems under it. `check()` returns the complete list of problem strings without
raising an exception.

### Validation rules

1. **Unknown keys are rejected**: Only documented template fields are accepted. Misspelled or extra keys fail immediately without guessing.
2. **Dates within weather range**: Every event date (planting, irrigation, fertilizer, residues, tillage, harvest) for the selected treatment must fall within the range of dates provided in your weather data.
3. **Planting on or after simulation start date**: Planting date cannot precede the simulation start date (`SDATE` when `START == "S"` in the FileX).
4. **Ascending and unique event timing**: Irrigation and fertilizer event lists must be strictly ordered without duplicates. Irrigation uses either dates or days after planting throughout the list, matching the effective IRRIG code above. Residue, tillage and harvest lists allow several events on the same date, in non-descending order.
5. **Empty list versus omitted section**:
   - **Omitted section**: If `planting`, `irrigation`, `fertilizer`, `residues`, `tillage`, or `harvest` is omitted for a treatment, the FileX's original Level for that section is kept unchanged.
   - **Empty list (`[]`)**: If `irrigation: []`, `fertilizer: []`, `residues: []`, `tillage: []`, or `harvest: []` is supplied, it explicitly requests **no events** for that treatment (repointed to Level 0).
6. **One rejected item stops the run**: `sim.run()` repeats all checks. If any problem is found anywhere in weather, soil, FileX, or management, execution halts and raises `DSSATCheckError`. No files or folders are written.
7. **User's FileX is never edited**: dssatlab copies the FileX into the dated simulation folder and applies changes only to the copy. The original FileX on disk is never modified.

## Run after the checks

Run the simulation:

```python
try:
    result = sim.run()
except dl.DSSATCheckError as error:
    for problem in error.problems:
        print(problem)
except dl.DSSATRunError as error:
    print(error)
else:
    print("Run directory:", result.run_dir)
    for path in result.outputs:
        print(path.name)
```

`sim.run()` creates a dated simulation folder (`dssat_sim_YYYY-MM-DD_HHMMSS`) beside the FileX.
Inside the simulation folder, it copies supporting files (`.CUL`, `.ECO`, `.SPE`, and `.SOL`
if no custom soil was provided), generates the weather file, and edits the copied FileX:
it appends new levels for your planting, irrigation, fertilizer, residue, tillage or harvest
schedules, and repoints the selected treatment row (`MP`, `MI`, `MF`, `MR`, `MT` or `MH`). DSSAT then executes against this isolated
copy. When highest + 1 would pass 99, an edit reuses the lowest free level
number after repointing the selected row, replacing its old rows in the copy.
If no level is free, the checks report the existing problem. See
[level reuse](sequence.md#reuse-free-levels-past-99).

A successful call returns a [RunResult](run-filex.md#inspect-the-run-result).

## Input forms: YAML or plain dictionary

You can provide management data as a YAML file path or as a plain Python dictionary.

### YAML file input and optional PyYAML

Reading a YAML file uses PyYAML:

```python
sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    management="management.yaml",
)
```

PyYAML is an **optional dependency** (ADR 0003). It is only imported when you pass a YAML
file path. If PyYAML is not installed, `check()` and `run()` report a clear message:

```text
Management file management.yaml: PyYAML is not installed. Install PyYAML with 'pip install pyyaml' to load management YAML files.
```

Install it via `pip install pyyaml` or `pip install dssatlab[yaml]`.

### Plain Python dictionary (zero dependencies)

If you prefer zero runtime dependencies, or are generating management schedules programmatically,
pass a plain Python dictionary directly:

```python
import dssatlab as dl

management_data = {
    "treatments": {
        1: {
            "planting": {
                "date": "1982-02-26",
                "method": "S",
                "distribution": "R",
                "population": 7.2,
                "row_spacing": 75.0,
                "depth": 5.0,
            },
            "irrigation": [
                {"date": "1982-03-15", "amount": 30.0, "method": "IR001"},
            ],
            "fertilizer": [
                {
                    "date": "1982-03-20",
                    "material": "FE001",
                    "application": "AP001",
                    "depth": 5.0,
                    "n": 50.0,
                },
            ],
        },
    },
}

sim = dl.Simulation(
    "UFGA8201.MZX",
    treatment=1,
    weather="weather.csv",
    management=management_data,
)
sim.run()
```

Passing a dictionary requires **no external packages**. Dates must still be quoted ISO strings
(`"YYYY-MM-DD"`).

## Scenario sweep loop

Because management data can be passed as a plain dictionary, running parameter sweeps or
management scenarios in a Python loop is straightforward.

For example, to evaluate crop response across different nitrogen fertilizer rates:

```python
import dssatlab as dl

n_rates = [0.0, 50.0, 100.0, 150.0, 200.0]
results = {}

for rate in n_rates:
    mgmt = {
        "treatments": {
            1: {
                "fertilizer": [
                    {
                        "date": "1982-03-20",
                        "material": "FE001",
                        "application": "AP001",
                        "depth": 5.0,
                        "n": rate,
                    }
                ],
            }
        }
    }

    sim = dl.Simulation(
        "UFGA8201.MZX",
        treatment=1,
        weather="weather.csv",
        management=mgmt,
    )
    result = sim.run()
    results[rate] = result.run_dir
    print(f"Completed run for N={rate} kg/ha: {result.run_dir.name}")
```

Each run creates its own dated simulation folder and run directory beside the FileX without
clobbering previous runs or altering the original FileX.
