# Architecture

`dssatlab` is designed as a small, dependency-free Python interface to the DSSAT-CSM crop model. It emphasizes plain functions, small dataclasses, and strict pre-execution checks without shell dependencies or hidden background processes.

## Module map

The codebase under `src/dssatlab/` includes these modules:

- `__init__.py`: Defines `__version__` and exports the public API via `__all__`.
- `config.py`: Reads and writes persistent JSON configuration storing the remembered DSSAT executable path.
- `core.py`: Discovers, validates, and installs the DSSAT executable (`connect`, `detect`, `install`).
- `controls.py`: Checks the experiment `controls` section (start date, water and nitrogen switches, output interval) and writes a new `SIMULATION CONTROLS` level in the copied FileX.
- `cultivar.py`: Checks an experiment `cultivar` code against the `.CUL` file beside the FileX and writes a new `CULTIVARS` level in the copied FileX.
- `dssat_observed.py`: Reads FileA/FileT into observed data rows, keeps supported measurements, and resolves short dates from the sibling FileX treatment's `SDATE` (ADR 0008).
- `errors.py`: Defines the exception hierarchy for discovery, installation, input checks, and run failures.
- `evaluate.py`: Matches observed data with Summary and Plant growth, collects check problems, and returns an `Evaluation` with pairs, RMSE, mean bias and Willmott's d-index.
- `experiment.py`: Shared field, date and number checks for the experiment sections, and the `controls` shape check.
- `filex.py`: Reads a FileX to extract field station codes (`WSTA`), field soil profile IDs (`ID_SOIL`), and simulation controls (`START`, `SDATE`) for a treatment.
- `filex_skeleton.py`: Formats and writes a minimal FileX from scratch for template simulations.
- `filex_template.py`: Writes the FileX template YAML (`write_filex_template`), validates template structure and cultivar codes, resolves the DSSAT data directory, and lists installed template crops and cultivars (`list_crops`, `list_cultivars`).
- `filex_write.py`: Modifies FileX text to append new management levels (planting details, irrigation schedules, fertilizer applications, residues, tillage and harvest) and repoints treatment entries without altering other sections.
- `initial_conditions.py`: Checks the experiment `initial_conditions` section (positive ascending depths and value ranges, allowing layers deeper than the soil profile) and writes a new `INITIAL CONDITIONS` level in the copied FileX.
- `installer.py`: Builds and installs DSSAT from source on Linux within a short cache prefix using Git, CMake, and gfortran.
- `management.py`: Validates management dictionary shape, field keys, numeric bounds, date order, and start date / weather bounds; formats structured check report lines.
- `operations.py`: Holds residue, tillage and harvest field tables, event checks (including RESID/HARVS), component harvest end rules and FileX row values ([fields and columns](../guide/experiment.md#residues-tillage-and-harvest)).
- `management_file.py`: Writes the YAML management template (`write_management_template`) and provides strict YAML loading (`_load_management`) using PyYAML SafeLoader with duplicate key rejection.
- `observed.py`: Writes the commented observed data template (`write_observed_template`) and privately loads and checks CSV/DataFrame/list-of-dict measurements in DSSAT's own units.
- `outputs.py`: Reads Summary, Plant growth, soil water, plant nitrogen and weather using fixed-width headers, and the DSSAT evaluation (`Evaluate.OUT`) using whitespace-separated columns. Converts missing values to `None`; DSSAT evaluation dates stay as days after planting. Also builds DataFrames (`to_dataframe`).
- `plot.py`: Plots Plant growth variables against date across simulations (`plot_plant_growth`) and simulated versus observed values with a 1:1 line (`plot_evaluation`) using optional matplotlib. `plot_observed` overlays measured points on Plant growth curves and shares the private result-key mapping with `evaluate`.
- `runner.py`: Executes the DSSAT executable on a FileX and moves generated output files into a dated run directory.
- `simulation.py`: Coordinates pre-run checks, staging, weather, soil, and management file generation, execution, and output scanning for a single simulation.
- `soil.py`: Writes the soil template, parses CSV/DataFrame/dict soil data, validates ranges and layer depths, and formats DSSAT soil files (`*.SOL`).
- `stock.py`: Reads stock weather metadata and daily values into the shared checks, checks stock soil IDs and filenames, and copies stock weather/soil bytes unchanged ([ADR 0024](../adr/0024-stock-weather-and-soil-files-copied-unchanged.md)).
- `weather.py`: Writes the weather template, parses CSV/DataFrame/dict weather data, validates ranges and dates, and writes DSSAT weather files (`*.WTH`).

## State management

Only `Simulation` holds state.

All other parts of `dssatlab` are structured as stateless, procedural functions or immutable data structures:

- Discovery and configuration functions (`detect()`, `connect()`, `config_file()`) operate directly on arguments, environment variables, or on-disk configuration.
- The low-level runner (`run()`) is a standalone function that accepts explicit paths and returns an immutable `RunResult` dataclass.
- File parsing and formatting helpers (`_read_table()`, `_read_filex()`, `write_weather_file()`) do not mutate input data structures or retain internal cache.

`Simulation` is the sole stateful class in the package. An instance of `Simulation` stores references to the inputs for a single treatment of an experiment: the FileX path, the treatment number, the weather data source, optional soil data, optional management data, and an optional DSSAT executable override. Instantiating `Simulation` does not perform file I/O, does not read disk state, and does not run DSSAT; validation and execution occur only when explicitly invoking `check()` or `run()`.

## Data flow

The execution pipeline for a `Simulation` proceeds through five distinct stages:

```text
Weather source + optional soil source + optional management source + FileX
                       │
                       ▼
           [ 1. Input Ingestion ]
           ├── Weather data (CSV / dicts / DataFrame)
           ├── Soil data (CSV / dicts / DataFrame)
           └── Management data (YAML file / dicts)
                       │
                       ▼
             [ 2. Pre-run Checks ]
             ├── weather._parse_weather      (column names, types, ranges, date order, gaps)
             ├── soil._parse_soil            (columns, ranges, profile consistency, depths, water limits)
             ├── management._check_management (keys, types, code format, bounds, date ordering, weather/start bounds)
             ├── filex._read_filex           (treatment row, WSTA, ID_SOIL, START, SDATE)
             └── simulation.check            (station equality, soil_id equality, simulation start coverage, 12-char limit)
                       │
                       ▼
             [ 3. File Generation & Staging ]
             ├── Create dated simulation folder (dssat_sim_YYYY-MM-DD_HHMMSS)
             ├── Copy FileX and model support files (*.CUL, *.ECO, *.SPE; and *.SOL if no soil data)
             ├── filex_write._write_management -> append levels and repoint treatment in copied FileX
             ├── weather.write_weather_file -> *.WTH
             └── soil.write_soil_file -> SOIL.SOL (when soil data is provided)
                       │
                       ▼
             [ 4. DSSAT Executable Run ]
             ├── runner.run() invokes DSSAT executable (batch mode C)
             ├── Create dated run directory (dssat_run_YYYY-MM-DD_HHMMSS)
             └── Move generated and updated outputs into run directory
                       │
                       ▼
             [ 5. Output Verification & Scan ]
             ├── Catch exit code 99 / ERROR.OUT (e.g. soil profile missing or corrupt) -> raise DSSATRunError
             └── WARNING.OUT scan: check for silent missing-weather terminations -> raise DSSATRunError
                       │
                       ▼
                   RunResult
```

### 1. Weather, soil, and management data ingestion

Weather and soil data are accepted as CSV file paths, lists of dictionary rows, or pandas DataFrames. When CSV files are provided, table reading helpers open them as UTF-8 (handling optional BOM) using the standard library `csv` module. If a pandas DataFrame is passed, it is converted to row dictionaries via `to_dict("records")` without importing pandas unless the object is detected (ADR 0002).

With a copied FileX, weather also accepts a stock `.WTH` path or list of paths,
and soil a stock `.SOL` path. `stock.py` reads these narrowly using Latin-1:
weather metadata, dates and daily values for the usual checks; soil profile IDs
and the filename DSSAT looks up. It does not parse stock soil layers. Optional
daily `par` in weather-template rows is checked as finite, 0 to 100 mol/m2 per
day, with a value on every row when present.

Management data is accepted as a YAML file path or a plain Python dictionary. When a YAML file is provided, `_load_management` parses it using PyYAML's `SafeLoader` with strict duplicate-key rejection (ADR 0003). PyYAML is never imported if a dictionary is passed or if `management` is omitted.

### 2. Pre-run checks

Before writing any files or invoking DSSAT, `Simulation.check()` executes strict validation:

- **Weather data checks**: `weather._parse_weather` ensures all required weather template columns are present, rejects unknown columns, validates numerical ranges (solar radiation, temperatures, precipitation, coordinates, elevation), verifies that daily rows are sorted chronologically without duplicates or missing calendar days, and confirms that station coordinates remain identical across all rows.
- **Soil data checks**: When `soil` is provided, `soil._parse_soil` validates required and optional soil template column names, confirms single soil profile ID length (at most 10 ASCII characters), checks that profile values repeat identically across all rows, validates numerical ranges, ensures layer bottom depths are positive and strictly increasing, and verifies that water fractions strictly satisfy `0 < slll < sdul < ssat < 1`.
- **Management data checks**: When `management` is provided, `management._check_management` validates that `treatments` is keyed by valid treatment numbers, verifies that only allowed fields are present, rejects unquoted dates, checks code patterns and numerical ranges, requires event dates within lists to be strictly ascending and unique, and validates that planting is on or after the simulation start date and all event dates fall within the weather date range.
- **FileX inspection**: `filex._read_filex` parses the FileX to confirm that the requested treatment number exists, extracts the linked field row to obtain the weather station code (`WSTA`) and soil profile ID (`ID_SOIL`), and reads simulation controls for the start mode (`START`) and start date (`SDATE`).
- **Cross-validation**: Verifies that the FileX filename does not exceed 12 characters (DSSAT 8.3 convention), confirms that the weather template station code matches the FileX `WSTA` code, and checks coverage from the simulation start date. `sequence._simulation_start` resolves SDATE or `controls.start_date` under START S, or the effective planting date under START P. `weather_files.py` follows DSSAT's stock weather lookup and rollover. When soil data is supplied, checks verify that `soil_id` matches the treatment field's `ID_SOIL` exactly (case-sensitive).

All identified issues are collected and returned as a list of strings. When `management` is provided (or `verbose=True`), a structured report is printed to standard output. If any problems are found during `Simulation.run()`, a `DSSATCheckError` is raised with the complete problem list, stopping execution before any files are created.

### 3. File generation and staging

When checks pass, `Simulation.run()` creates a dated simulation folder (`dssat_sim_YYYY-MM-DD_HHMMSS`) beside the FileX to isolate the execution environment. The FileX and sibling model files with extensions `.CUL`, `.ECO`, or `.SPE` are copied into this folder. FileA/FileT are not copied: in run mode C DSSAT would not read them (ADR 0008).

When management data is provided, `filex_write._write_management()` edits the copied FileX inside the simulation folder: it appends new levels to the planting details, irrigation, or fertilizer sections and updates the treatment pointer (`MP`, `MI`, `MF`). The original FileX remains untouched.

When soil data is provided, `Simulation.run()` writes `SOIL.SOL` directly into the simulation folder and skips copying sibling `.SOL` files. A stock soil path is copied byte for byte under its own name, also replacing sibling soil files. Because a `.SOL` file in the FileX folder always takes precedence over DSSAT's own `Soil` directory, DSSAT uses the user-provided soil profile. If no soil was provided, sibling `.SOL` files are copied as before.

Stock weather paths are copied byte for byte under upper-case names instead of
generating weather; other columns, flags and a trailing DOS EOF byte survive.

`weather.write_weather_file()` formats the parsed weather rows into DSSAT's fixed-width ASCII weather file format (`*.WTH`), writing station metadata headers and daily weather records directly into the simulation folder. The filename is derived from the station code and start date using DSSAT naming rules (`_weather_filename`).

### 4. DSSAT executable run

Execution is dispatched to `runner.run()`, which executes in the simulation folder. It resolves the DSSAT executable (via `connect(interactive=False)` or an explicit path), creates a dated run directory (`dssat_run_YYYY-MM-DD_HHMMSS`) inside the simulation folder, and records timestamps of all existing files.

The DSSAT executable is invoked as a subprocess with arguments `["C", filex_name, treatment_number]`. After process completion, all newly created or modified files in the simulation folder are moved into the run directory. If DSSAT returns a non-zero exit code (such as exit code 99 when a soil profile cannot be found or read) or produces an `ERROR.OUT` file, a `DSSATRunError` is raised while preserving the run directory for inspection.

### 5. Output verification and scan

DSSAT can exit with return code `0` even when daily weather data terminates prematurely during a simulation run, filling subsequent simulation days with `-99` error sentinels and logging a message to `WARNING.OUT` (`Weather record not found for YR DOY: ...`).

`Simulation.run()` scans `WARNING.OUT` in the run directory for this pattern. If detected, it parses the missing year and day of year, converts them to a calendar date, and raises `DSSATRunError` detailing the missing date. This prevents silent simulation failures from being treated as successful runs.
