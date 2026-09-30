# Run a Simulation with your management data

A `Simulation` can combine one treatment of an existing FileX with your daily
weather data, your soil profile, and your own management operations (planting,
irrigation schedules, and fertilizer applications). Prepare the FileX and its
supporting files, then [find or install a DSSAT executable](install.md). The examples use
`UFGA8201.MZX`; replace it with your FileX path and choose one of its treatments.

By default, a `Simulation` keeps the management levels defined in the FileX.
When you pass `management` to `Simulation`, dssatlab verifies your management data
against the FileX and weather data, copies the FileX into a fresh simulation folder,
appends your new management levels to the copy, and repoints the selected treatment.
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
| `irrigation` | `date` | Yes | `"YYYY-MM-DD"` | Event date; must be ascending, unique, and within weather range |
| `irrigation` | `amount` | Yes | mm | Water applied; must be strictly positive (`> 0`) |
| `irrigation` | `method` | Yes | `[A-Za-z]{2}[0-9]{3}` | DSSAT irrigation code: 2 ASCII letters + 3 digits (e.g., `IR001`) |
| `fertilizer` | `date` | Yes | `"YYYY-MM-DD"` | Event date; must be ascending, unique, and within weather range |
| `fertilizer` | `material` | Yes | `[A-Za-z]{2}[0-9]{3}` | DSSAT fertilizer material code (e.g., `FE001`) |
| `fertilizer` | `application` | Yes | `[A-Za-z]{2}[0-9]{3}` | DSSAT application method code (e.g., `AP001`) |
| `fertilizer` | `depth` | Yes | cm | Placement depth in cm; must be nonnegative (`>= 0`) |
| `fertilizer` | `n` | Yes | kg/ha | Elemental nitrogen applied; must be nonnegative (`>= 0`) |
| `fertilizer` | `p` | No | kg/ha | Elemental phosphorus applied; must be nonnegative (`>= 0`, defaults to 0) |
| `fertilizer` | `k` | No | kg/ha | Elemental potassium applied; must be nonnegative (`>= 0`, defaults to 0) |

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
2. **Dates within weather range**: Every event date (planting, irrigation, fertilizer) for the selected treatment must fall within the range of dates provided in your weather data.
3. **Planting on or after simulation start date**: Planting date cannot precede the simulation start date (`SDATE` when `START == "S"` in the FileX).
4. **Ascending and unique event dates**: Irrigation and fertilizer event lists must be strictly ordered by ascending date without duplicates on the same day.
5. **Empty list versus omitted section**:
   - **Omitted section**: If `planting`, `irrigation`, or `fertilizer` is omitted for a treatment, the FileX's original Level for that section is kept unchanged.
   - **Empty list (`[]`)**: If `irrigation: []` or `fertilizer: []` is supplied, it explicitly requests **no events** for that treatment (repointed to Level 0).
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
it appends new levels for your planting, irrigation, or fertilizer schedules, and repoints
the selected treatment row (`MP`, `MI`, or `MF`). DSSAT then executes against this isolated
copy.

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
