# Architecture

`dssatlab` is designed as a small, dependency-free Python interface to the DSSAT-CSM crop model. It emphasizes plain functions, small dataclasses, and strict pre-execution checks without shell dependencies or hidden background processes.

## Module map

The codebase under `src/dssatlab/` consists of nine modules:

- `__init__.py`: Defines `__version__` and exports the public API via `__all__`.
- `config.py`: Reads and writes persistent JSON configuration storing the remembered DSSAT executable path.
- `core.py`: Discovers, validates, and installs the DSSAT executable (`connect`, `detect`, `install`).
- `errors.py`: Defines the exception hierarchy for discovery, installation, input checks, and run failures.
- `filex.py`: Reads a FileX to extract field station codes (`WSTA`) and simulation controls (`START`, `SDATE`) for a treatment.
- `installer.py`: Builds and installs DSSAT from source on Linux within a short cache prefix using Git, CMake, and gfortran.
- `runner.py`: Executes the DSSAT executable on a FileX and moves generated output files into a dated run directory.
- `simulation.py`: Coordinates pre-run checks, staging, weather file generation, execution, and output scanning for a single simulation.
- `weather.py`: Writes the weather template, parses CSV/DataFrame/dict weather data, validates ranges and dates, and writes DSSAT weather files (`*.WTH`).

## State management

Only `Simulation` holds state.

All other parts of `dssatlab` are structured as stateless, procedural functions or immutable data structures:

- Discovery and configuration functions (`detect()`, `connect()`, `config_file()`) operate directly on arguments, environment variables, or on-disk configuration.
- The low-level runner (`run()`) is a standalone function that accepts explicit paths and returns an immutable `RunResult` dataclass.
- File parsing and formatting helpers (`_read_weather()`, `_read_filex()`, `write_weather_file()`) do not mutate input data structures or retain internal cache.

`Simulation` is the sole stateful class in the package. An instance of `Simulation` stores references to the inputs for a single treatment of an experiment: the FileX path, the treatment number, the weather data source, and an optional DSSAT executable override. Instantiating `Simulation` does not perform file I/O, does not read disk state, and does not run DSSAT; validation and execution occur only when explicitly invoking `check()` or `run()`.

## Data flow

The execution pipeline for a `Simulation` proceeds through five distinct stages:

```text
Weather source (CSV / dicts / DataFrame) + FileX
                       │
                       ▼
           [ 1. Weather CSV / Input ]
                       │
                       ▼
             [ 2. Pre-run Checks ]
             ├── weather._parse_weather  (column names, types, ranges, date order, gaps)
             ├── filex._read_filex       (treatment row, WSTA, START, SDATE)
             └── simulation.check        (station equality, SDATE coverage, 12-char limit)
                       │
             [ 3. Weather File Generation ]
             ├── Create dated simulation folder (dssat_sim_YYYY-MM-DD_HHMMSS)
             ├── Copy FileX and model support files (*.SOL, *.CUL, *.ECO, *.SPE)
             └── weather.write_weather_file -> *.WTH
                       │
                       ▼
             [ 4. DSSAT Executable Run ]
             ├── runner.run() invokes DSSAT executable (batch mode C)
             ├── Create dated run directory (dssat_run_YYYY-MM-DD_HHMMSS)
             └── Move generated and updated outputs into run directory
                       │
                       ▼
             [ 5. WARNING.OUT Scan ]
             └── Check for silent missing-weather terminations -> raise DSSATRunError
                       │
                       ▼
                   RunResult
```

### 1. Weather data ingestion

Weather data is accepted as a CSV file path, a list of dictionary rows, or a pandas DataFrame. When a CSV is provided, `weather._read_weather` opens the file as UTF-8 (handling optional BOM) using the standard library `csv` module. If a pandas DataFrame is passed, it is converted to row dictionaries via `to_dict("records")` without importing pandas unless the object is detected.

### 2. Pre-run checks

Before writing any files or invoking DSSAT, `Simulation.check()` executes strict validation:

- **Weather data checks**: `weather._parse_weather` ensures all required weather template columns are present, rejects unknown columns, validates numerical ranges (solar radiation, temperatures, precipitation, coordinates, elevation), verifies that daily rows are sorted chronologically without duplicates or missing calendar days, and confirms that station coordinates remain identical across all rows.
- **FileX inspection**: `filex._read_filex` parses the FileX to confirm that the requested treatment number exists, extracts the linked field row to obtain the weather station code (`WSTA`), and reads simulation controls for the start mode (`START`) and start date (`SDATE`).
- **Cross-validation**: Verifies that the FileX filename does not exceed 12 characters (DSSAT 8.3 convention), confirms that the weather template station code matches the FileX `WSTA` code, and verifies that the weather data covers `SDATE` when `START == "S"`.

All identified issues are collected and returned as a list of strings. If any problems are found during `Simulation.run()`, a `DSSATCheckError` is raised with the complete problem list, stopping execution before any files are created.

### 3. Weather file generation

When checks pass, `Simulation.run()` creates a dated simulation folder (`dssat_sim_YYYY-MM-DD_HHMMSS`) beside the FileX to isolate the execution environment. The FileX and any sibling model files with extensions `.SOL`, `.CUL`, `.ECO`, or `.SPE` are copied into this folder.

`weather.write_weather_file()` formats the parsed weather rows into DSSAT's fixed-width ASCII weather file format (`*.WTH`), writing station metadata headers and daily weather records directly into the simulation folder. The filename is derived from the station code and start date using DSSAT naming rules (`_weather_filename`).

### 4. DSSAT executable run

Execution is dispatched to `runner.run()`, which executes in the simulation folder. It resolves the DSSAT executable (via `connect(interactive=False)` or an explicit path), creates a dated run directory (`dssat_run_YYYY-MM-DD_HHMMSS`) inside the simulation folder, and records timestamps of all existing files.

The DSSAT executable is invoked as a subprocess with arguments `["C", filex_name, treatment_number]`. After process completion, all newly created or modified files in the simulation folder are moved into the run directory. If DSSAT returns a non-zero exit code or produces an `ERROR.OUT` file, a `DSSATRunError` is raised while preserving the run directory for inspection.

### 5. WARNING.OUT scan

DSSAT can exit with return code `0` even when daily weather data terminates prematurely during a simulation run, filling subsequent simulation days with `-99` error sentinels and logging a message to `WARNING.OUT` (`Weather record not found for YR DOY: ...`).

`Simulation.run()` scans `WARNING.OUT` in the run directory for this pattern. If detected, it parses the missing year and day of year, converts them to a calendar date, and raises `DSSATRunError` detailing the missing date. This prevents silent simulation failures from being treated as successful runs.
