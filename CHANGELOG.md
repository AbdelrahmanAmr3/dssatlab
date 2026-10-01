# Changelog

All notable changes to dssatlab. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The entries for 0.1.0 to 0.3.0 were backfilled from the GitHub release notes; from now on new entries are written here first and the release notes copy from them.

## [0.7.0] - 2026-09-30

### Added
- `write_filex_template(path)` writes one commented YAML for a new experiment: one field, one treatment, one crop (maize or wheat), a cultivar and planting details. `Simulation(filex_template=..., weather=..., soil=...)` writes the FileX for you, so no existing FileX is needed. Station, coordinates and elevation come from your weather data and the soil ID from your soil data. Give exactly one of `filex` and `filex_template`; soil is required with a template.
- `check()` validates the template at once with the rest of the inputs: unsupported crop (with the supported list) and a cultivar missing from the crop's `.CUL` file (with the closest codes). Nothing is written.
- `run()` writes the FileX beside the weather and soil files and copies the crop's `.CUL`, `.ECO` and `.SPE` from the DSSAT `Genotype` folder. Experiment data (planting, irrigation, fertilizer, cultivar, initial conditions, controls) works on top of it.
- Proven on real DSSAT 4.8 with maize (`MZCER048`) and wheat (`CSCER048`, genotype files `WHCER048`).

### Changed
- With experiment data, the copied FileX takes the weather data's station (`WSTA`) and the soil data's profile ID (`ID_SOIL`), so your own site data no longer has to be named after the source FileX's station.
- A named scenario writes its name into `TNAM` of the copied FileX, so `Summary.OUT` identifies it. The `base` scenario and a `Simulation` without `name=` keep the FileX treatment name.

### Notes
- Upgrading from 0.6.x needs no changes. `Simulation` gains one optional keyword, `name`, and `filex` and `treatment` now have defaults.
- Still one field and one treatment per template; other crops are added only after a real-DSSAT run.

## [0.6.1] - 2026-09-30

### Fixed
- `run(filex)` now stops before starting when the FileX folder holds a `.csv` file DSSAT would delete (`weather.csv`, `summary.csv`, `plantgro.csv`, and the other Output file names). Checked on real DSSAT 4.8. `Simulation` was never affected because it runs in its own folder.
- `check()` now reports a weather column missing from rows given as a list of dicts once, not once per row.
- An unknown cultivar code is reported with the five closest codes and the `.CUL` file to open, not the whole list.
- `check()` now catches a `controls` `start_date` after the FileX's first irrigation date. DSSAT stopped with error `IPIRR` after the check had passed.
- `check(verbose=False)` prints nothing. Left unset, it still prints the report when management data is given.
- "Found DSSAT via saved config" is now a debug message, so it no longer appears on every `Simulation`.
- `RunResult` prints on one line instead of the whole console tail and file list.
- `plot_plant_growth()` and `result.plot()` add a title and axis labels.
- The walkthrough notebook now reads results with `result.summary()`.

### Notes
- Upgrading from 0.6.0 needs no changes.
- Weather that ends before the crop matures is still caught by `run()`, not `check()`.

## [0.6.0] - 2026-09-30

### Added
- Experiment data: the per-treatment management YAML (or dict) gains three sections, `cultivar`, `initial_conditions` and `controls`, applied to a copy of your FileX. The original is never changed, and an omitted section keeps the FileX's own level.
- `cultivar` (`crop` and `code`) is checked against the one crop-matching `.CUL` file beside the FileX; an unknown code is reported with the codes that do exist. A new `CULTIVARS` level is written and only the selected treatment is repointed.
- `initial_conditions` (`date`, optional `previous_crop` and `residue_mass`, and `layers` of `depth`, `water`, `nh4`, `no3`) rejects non-ascending depths and out-of-range values with the allowed range, and, when `soil=` is given, layers deeper than the soil profile. A new `INITIAL CONDITIONS` level is written.
- `controls` (`start_date`, `water` and `nitrogen` as `"Y"`/`"N"`, `output_interval` in days) writes a new `SIMULATION CONTROLS` level. A changed `start_date` replaces `SDATE` in the weather-coverage and planting-date checks.
- `write_experiment_template(path, filex=None)` writes one commented YAML covering every section. `filex=` pre-fills treatment numbers only, here and in `write_management_template`.
- The new sections work in scenario `management` overrides.
- Guide page "Run with experiment data" and ADR 0005.
- Proven on real DSSAT (4.8.5) with maize `UFGA8201` and wheat `KSAS8101`: each section moved the summary as expected (for example a different cultivar changed `HWAM` from 2293 to 658 on maize).

### Changed
- `check()` now lists `cultivar`, `initial_conditions` and `controls` as "omitted" in its Management report when they are not given. A management-only YAML is still valid.

### Notes
- Upgrading from 0.5.0 needs no changes.
- Not included yet: building a FileX from scratch, writing `.CUL`, `.ECO` or `.SPE` parameters, simulation controls beyond the four named, per-crop parameter checks.

## [0.5.0] - 2026-09-30

### Added
- `run_treatments(filex, weather, treatments=None, soil=None, management=None, executable=None, scenarios=None)` runs all treatments (or a selected subset) of a FileX across named scenarios in separate, isolated folders and returns a `dict[(scenario, treatment)] -> RunResult`.
- Scenario overrides: named overrides of `weather`, `soil`, or `management` that replace the whole input without partial merging, with the un-overridden run always included as `"base"`.
- `write_scenario_template(path, filex=None)` creates a commented YAML template, optionally pre-filling treatment numbers found in a FileX. Refuses existing files with `DSSATError`.
- Scenario input as a YAML file path (using optional PyYAML and strict validation) or a plain Python dictionary.
- Pre-run validation: checks all scenario-treatment pairs before any DSSAT execution and collects all issues into a single `DSSATCheckError`.
- Station check rule: weather data (base and scenario overrides) must match the `WSTA` station code of every selected treatment.
- Stop on first run failure: halts execution immediately if any run fails, reporting what failed and listing all kept run directories.
- `combine_summaries(results)` combines summary rows across all scenario-treatment runs into a single list of dicts with added `scenario` and `treatment` columns, ready for `to_dataframe()`.
- `read_soil_water(run_dir)` reads daily soil water by layer from `SoilWat.OUT` into a list of dicts with DSSAT's per-layer column names, parsed `DATE`, `-99` missing values as `None`, and `RUNNO` and `TRNO` on each row.
- `read_plant_nitrogen(run_dir)` reads daily plant nitrogen from `PlantN.OUT` into a list of dicts with DSSAT column names, parsed `DATE`, `-99` missing values as `None`, and `RUNNO` and `TRNO` on each row.
- `read_weather(run_dir)` reads daily weather data from `Weather.OUT` into a list of dicts with DSSAT column names, parsed `DATE` and `WDATE` (`datetime.date`), `-99` missing values as `None`, and `RUNNO` and `TRNO` on each row.
- `RunResult` convenience methods: `result.soil_water()`, `result.plant_nitrogen()`, and `result.weather()`.
- Guide page: "Run treatments and scenarios" (`docs/guide/scenarios.md`).

### Changed
- Output file parsing expanded from two files to five (`Summary.OUT`, `PlantGro.OUT`, `SoilWat.OUT`, `PlantN.OUT`, and `Weather.OUT`). All other output files remain listed in `RunResult.outputs`.

### Notes
- Upgrading from 0.4.0 needs no changes.
- Existing single-treatment `Simulation` and `run()` behavior remains unchanged.
- Not included yet: per-station weather, deep merging of scenario overrides, other management operations, FileX authoring, reading other output files (`ET.OUT`, `OVERVIEW.OUT`, etc.), parallel runs, retries, and timeouts.

## [0.4.0] - 2026-09-30

### Added
- `read_summary(run_dir)` reads `Summary.OUT` from any run directory into a list of dicts (one row per simulation) with DSSAT column names, summary dates (`SDAT`, `PDAT`, `EDAT`, `ADAT`, `MDAT`, `HDAT`) as `datetime.date` objects, `-99` missing values as `None`, and `RUNNO`, `TRNO`, and `TNAM` on every row.
- `read_plant_growth(run_dir)` reads `PlantGro.OUT` from any run directory into a list of dicts (one row per simulation day) with DSSAT column names, a parsed `DATE` column (`datetime.date`) alongside `YEAR` and `DOY`, `-99` missing values as `None`, and `RUNNO` and `TRNO` on every row.
- `to_dataframe(rows)` converts parsed summary or plant growth rows into a pandas DataFrame in row key order. pandas is imported only when called (ADR 0002).
- `plot_plant_growth(run_dirs, variable)` plots a plant growth variable against `DATE` across simulations, drawing one line per simulation labelled by treatment name, and returns the matplotlib `Axes`. Accepts a single run directory or a sequence of run directories to compare treatments.
- `RunResult` convenience methods: `result.summary()`, `result.plant_growth()`, and `result.plot(variable)`.
- `DSSATOutputError` exception for missing, empty, or malformed output files or unknown plot variables, with messages reporting what failed, what was checked, and what to do next.
- Optional `plot` installation extra (`pip install dssatlab[plot]`) providing matplotlib for plotting.
- ADR 0004: matplotlib is an optional extra, used only for plots.
- Guide page: "Reading results" (`docs/guide/reading-results.md`).

### Changed
- None for existing behavior. `Summary.OUT` and `PlantGro.OUT` are the only output files parsed; all other output files remain listed in `RunResult.outputs`.

### Notes
- Upgrading from 0.3.2 needs no changes.
- Reading and plotting functions work on any run directory, including runs made outside dssatlab.
- Not included yet: reading other output files (`SoilWat.OUT`, `ET.OUT`, `Weather.OUT`, etc.), plot styling options, unit converters, and automated result statistics.

## [0.3.2] - 2026-09-29

### Added
- `Simulation(filex, treatment, weather, executable=None, *, soil=None, management=None)`: `management` is optional and keyword-only, accepting the user's own management data as a YAML file path or a plain dict.
- A fixed YAML management template with commented examples, and `write_management_template(path)` to write it. The template documents planting, irrigation, and fertilizer fields, units, DSSAT codes, and quoting rules.
- Management data input as a YAML file path or a plain Python dictionary. PyYAML is optional and imported only when a YAML path is passed (ADR 0003); passing a YAML path without PyYAML provides a clear install hint. A dictionary needs zero extra packages.
- Management checks in `check()`: reports every problem at once, with what is wrong, where, and what to do: unknown keys, invalid types, unquoted dates, non-ascending or duplicate event dates, out-of-range numeric values, planting date before simulation start date, management dates outside the weather date range, and treatment numbers not found in the FileX.
- Clear distinction between omitting a section (keeps the FileX's original level) and providing an empty list `[]` (specifies no events / level 0).
- Printed checks report: when `management` is provided (or `verbose=True`), `check()` prints a structured report showing the status of each section for every treatment.
- Non-destructive FileX updates during `run()`: appends new management levels to the copied FileX inside the simulation folder and repoints the selected treatment without altering untouched sections. The user's original FileX is never modified.

### Changed
- `Simulation` accepts `management` as an optional keyword-only argument placed after `soil`. Positional and keyword calls from 0.3.1 keep their meaning.

### Notes
- Upgrading from 0.3.1 needs no changes.
- Not included yet: other management operations (tillage, organic amendments, harvest, chemical applications, environmental modifications), FileX authoring, unit converters, reading DSSAT output files, and more than one treatment per `Simulation`.

## [0.3.1] - 2026-09-29

### Added
- `Simulation(filex, treatment, weather, executable=None, *, soil=None)`: `soil` is optional and keyword-only, accepting the user's own soil data for one soil profile.
- A fixed soil template in DSSAT's own units (required profile columns `soil_id`, `salb`, `slro`, `sldr`, `slpf`, required layer columns `slb`, `slll`, `sdul`, `ssat`, `srgf`, and optional columns defaulting to -99), and `write_soil_template(path)` to write a valid three-layer example profile (`IBMZ910214`).
- Soil data input as a CSV path, a list of dicts, or a pandas DataFrame. pandas is never required.
- Soil checks in `check()`: reports every problem at once, with what is wrong, where and what to do: wrong or unknown columns, empty or non-numeric values, profile values that differ across layer rows, profile IDs longer than 10 ASCII characters (DSSAT truncates longer IDs), non-positive or non-increasing layer depths, water fractions not in strict order `slll < sdul < ssat`, out-of-range physical bounds, and a `soil_id` that does not match the FileX treatment's `ID_SOIL` (case-sensitive). Nothing is fixed or converted automatically.
- When soil is given, `run()` writes a single `SOIL.SOL` into the simulation folder. Sibling `.SOL` files are not copied, ensuring the user's soil profile is the one DSSAT uses (a `.SOL` in the FileX folder always beats DSSAT's own Soil folder).

### Changed
- `Simulation` accepts `soil` as a keyword-only argument placed after `executable`. Positional calls from 0.3.0 keep their meaning.
- When `soil` is provided, `run()` skips copying sibling `.SOL` files into the simulation folder, while `.CUL`, `.ECO`, and `.SPE` files are copied as before. Without soil, sibling `.SOL` files are copied as before.

### Notes
- Upgrading from 0.3.0 needs no changes.
- If DSSAT cannot use the soil profile, it exits with return code 99 and writes `ERROR.OUT`, and `run()` raises `DSSATRunError` with the `ERROR.OUT` text.
- Not included yet: management data, unit converters, output parsing, several treatments per `Simulation`, and choosing a soil profile from DSSAT's own soil files.

## [0.3.0] - 2026-09-29

### Added
- `Simulation(filex, treatment, weather, executable=None)`: one treatment of a FileX and the user's own weather data, as a checked DSSAT run.
- A fixed weather template in DSSAT's own units (station, latitude, longitude, elevation, date, srad, tmax, tmin, rain, and optional tav, amp, refht, wndht), and `write_weather_template(path)` to write a correct example.
- Weather input as a CSV path, a list of dicts, or a pandas DataFrame. pandas is never required.
- `check()` reports every problem at once, with what is wrong, where and what to do: wrong or unknown columns, empty or non-numeric values, bad dates, gaps, duplicates, impossible values, and, by reading the FileX, a station that does not match or weather that misses the start date. Nothing is fixed or converted automatically.
- `run()` raises `DSSATCheckError` listing all problems before writing anything. Otherwise it creates a `dssat_sim_<date>` folder beside the FileX with a copy of the FileX, the `.SOL`, `.CUL`, `.ECO` and `.SPE` files beside it, and the generated weather file, then runs DSSAT there. The user's own files and folder are not changed.
- Silent weather shortages are caught. DSSAT exits normally and gives -99 results when weather is missing, so after the run `run()` looks for DSSAT's "weather record not found" warning and raises `DSSATRunError` naming the first missing date.


### Notes
- Upgrading from 0.2.0 needs no changes.
- Tested on real DSSAT on Windows, Linux (WSL) and Google Colab. Automated tests run on Ubuntu and Windows with Python 3.10 and 3.12.
- Not included yet: soil and management data, unit converters, reading DSSAT's output files, and more than one treatment per `Simulation`.

## [0.2.0] - 2026-09-29

### Added
- `run(filex, treatment=None, executable=None)` runs DSSAT on one existing FileX and returns a `RunResult` (return code, run directory, output files, end of the console output).
- DSSAT's output files are moved into a new `dssat_run_<date>` folder beside the FileX, and a second run never overwrites the first.
- `DSSATRunError` shows the command, the end of DSSAT's console output and the start of `ERROR.OUT`. It is also raised when DSSAT wrote an error file but exited with code 0.

### Changed
- On Linux and Colab, `install()` now installs DSSAT with its data directory (`cmake --install`), so a fresh install can run a simulation. A too-long install path fails early with a clear message.
- A DSSAT built by 0.1.x cannot run simulations, so the first `install()` (or `connect()` with consent) rebuilds it once. The old cache folder is ignored and left in place.
- The FileX filename must be at most 12 characters including the extension (a DSSAT limit), and the install path at most 51 characters.

### Notes
- Tested on real DSSAT: Windows (DSSAT 4.8.5), Linux via WSL (built from `v4.8.6.0`) and Google Colab.
- Not included yet: reading FileX or output files, building experiments from Python, plots and unit conversion.

## [0.1.1] - 2026-09-28

### Added
- `detect()` reports the OS, Python version, and the Git, CMake and gfortran tools it finds.
- `connect()` finds an existing DSSAT installation and checks that the DSSAT executable works, looking in this order: the path passed in, the saved configuration, the `DSSAT_HOME` environment variable, `PATH`, the managed cache.
- `install()` builds the latest stable DSSAT-CSM release from the official repository on Linux with explicit Git and CMake commands, and reuses the build if it is already cached. It never uses `sudo` and never edits shell startup files.
- The DSSAT executable path is saved in the saved config so later calls to `connect()` are quick.

### Notes
- Replaces the 0.1.0 placeholder. No runtime dependencies; Python 3.10 or newer.
- Not included yet: running simulations, reading or writing DSSAT input and output files, and cleaning up managed installations.

## [0.1.0] - 2026-09-28

### Added
- `detect()` reports the OS, machine architecture and Python version, returned as a small immutable `EnvironmentInfo` dataclass.
- Python 3.10 or newer, with zero runtime dependencies.

### Notes
- Environment diagnostics only. DSSAT discovery, connecting, installation and simulation support were deferred.

[0.6.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.6.0
[0.5.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.5.0
[0.4.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.4.0
[0.3.2]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.3.2
[0.3.1]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.3.1
[0.3.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.3.0
[0.2.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.2.0
[0.1.1]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.1.1
[0.1.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.1.0
