# Changelog

All notable changes to dssatlab. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The entries for 0.1.0 to 0.3.0 were backfilled from the GitHub release notes; from now on new entries are written here first and the release notes copy from them.

## [0.13.1] - UNDATED

### Added
- Crop rotations from the FileX template: the FileX template accepts `treatment_name` and `rotation`, a list of 2 to 9 rotation components, instead of single-crop keys (`crop`, `cultivar`, `planting`, `harvest_date`, `treatments`, `treatment_fields`) (ADR 0014).
- Rotation components: crop components support the standard template crops with `crop`, `cultivar.code`, `planting`, and optional `harvest_date` (including potato rules and column-width validation); fallow components are defined with `{crop: "fallow", end_date: "YYYY-MM-DD"}`. Component errors identify their position (`FileX template, rotation[3]...`).
- Pre-run rotation date checks: catches dates that DSSAT would silently move forward by whole years: the first component must be a crop (simulation starts on its planting date); the last component must have a known end date (fallow `end_date` or crop `harvest_date`); each component's start date must be strictly after the previous component's end date; and cycle closure requires the last component's day of year to end before the first planting's day of year, with an example valid end date suggested in the message.
- Cycle length and multi-cycle runs: the rotation cycle in years (`year of last end + 1 day minus first planting year`) is written as the first component's `NYERS`, so a bare rotation template runs one full cycle by default; experiment data controls `years` overrides it to simulate multiple cycles (with experiment data restricted to controls `years` and `start_date`).
- Rotation sequence execution: `Simulation(filex_template=rotation, weather=..., soil=...)` writes `<station><yy>01.SQX`, copies genotype files (`.CUL`, `.ECO`, `.SPE`) for every crop in the rotation, and executes in DSSAT's sequence mode (`Q`) via `DSSBatch.v48`. `check()` reports the rotation components (e.g. `FileX: treatment 1 is a sequence of 4 rotation components (R 1-4: MZ, FA, WH, FA); it runs in DSSAT's sequence mode.`).
- `run_treatments(filex_template=rotation)` runs the rotation sequence once.
- `write_filex()` writes a rotation template to `.SQX`.
- `write_filex_template()` includes a commented rotation example.
- Guide section "A rotation from the FileX template" in `docs/guide/sequence.md` and tutorial Case 10 demonstrating a maize-fallow-wheat-fallow rotation across 1 and 3 cycles with Gainesville weather and `IBSB910015` soil.
- Architecture Decision Record 0014 recording rotation FileX templates and day-of-year date checks.

### Changed
- `list_crops` and `list_cultivars` moved from `filex_template.py` to `cultivar.py`; public imports from `dssatlab` remain unchanged.

### Notes
- Crops harvested at maturity can still overrun into a subsequent year depending on simulated weather; users should specify a fixed `harvest_date` or leave a margin before the next component.
- Experiment data per rotation component is deferred to v0.13.2.
- Upgrading from 0.13.0 needs no changes. Zero runtime dependencies are preserved.

## [0.13.0] - 2026-10-01

### Added
- Sequence analysis: a `Simulation` whose treatment number has multiple `*TREATMENTS` rows in the FileX runs as a multi-year crop sequence in DSSAT's sequence mode (`Q`) through a batch file (`DSSBatch.v48`) written to the simulation folder, with the user's weather and soil data (ADR 0013).
- Pre-run sequence checks: validates a 12-character FileX filename, distinct positive `R` numbers, single field across all components, `NREPS` equal to 1, and continuous weather data covering through the sequence's last day calculated via DSSAT's calendar day-of-year end rule (`(start year + years)` at start day of year, minus one day).
- Sequence experiment data: supports controls `years` and `start_date` applied to a copy of the first component's controls level; unsupported edits are reported as check problems.
- Continuous daily series: `SoilWat.OUT` and `Weather.OUT` provide a continuous series across rotation components over the whole sequence.
- Guide page "Sequence analysis" (`docs/guide/sequence.md`) and tutorial Case 9 demonstrating a 9-year crop rotation (bean, fallow, soybean) with `UFGA7804.SQX`.
- Architecture Decision Record 0013 recording sequence execution in mode Q via a batch file.

### Changed
- Copied FileX controls checks: verifies for every copied FileX (sequence or single-crop) that used controls levels have `METHODS` `WTHER` set to `M` (not `W`) and `OUTPUTS` `FNAME` set to `N` (not `Y`), preventing silent weather generation or missing `Summary.OUT`.
- `summarize_seasons()` groups by scenario, treatment, and rotation component (`R#`, defaulting to 1), adding `component` and `crop` keys to each returned dictionary.
- The weather station written into a copied FileX field (experiment data) is left-justified, as in DSSAT's own files; DSSAT's sequence mode rejects a right-justified station.
- `run_treatments(treatments=None)` selects each FileX treatment number once in file order, allowing multi-sequence FileX experiments to run each sequence once.

### Notes
- Run modes now include C (`Simulation`), Q (`Simulation` of a sequence), and A (`dl.run()`). `dl.run()` remains unchanged.
- Experiment data per rotation component and FileX template generation from scratch for sequences are deferred to v0.13.1.
- `evaluate()` continues to reject multiple Summary rows per treatment; sequence evaluation remains out of scope.
- Upgrading from 0.12.0: a copied FileX with `WTHER` other than `M` or `FNAME` other than `N` in a controls level the run uses is now a check problem; set them to `M` and `N`. Nothing else changes. Zero runtime dependencies are preserved.

## [0.12.0] - 2026-10-01

### Added
- Experiment data controls key `years`: an optional positive integer specifying the number of seasons to simulate, written as DSSAT's `NYERS` into the copied controls level for the selected treatment. Works for both copied FileX and FileX template experiments, in a `Simulation` and in `run_treatments()`.
- Season start rule: season k (1-based) starts on day-of-year D of year Y + k - 1 from the simulation start date (from controls `start_date`, FileX `SDATE` when `START` is `S`, or the template planting date), correctly accounting for leap years (e.g. March 1 gives Feb 29 on day 60 in leap years).
- Pre-run weather coverage check: verifies that weather data covers the start date of the last season for `years` or an existing FileX whose `NYERS` is above 1 before any simulation files are written or DSSAT is run.
- `summarize_seasons(rows, variables=("HWAM",))` computes cross-season statistics (seasons, missing, mean, sample standard deviation, min, p25, median, p75, max) per scenario, treatment, and variable from Summary rows (`result.summary()` or `combine_summaries()`). Output rows pass directly to `to_dataframe()`.
- Guide page "Seasonal analysis" (`docs/guide/seasonal.md`) and tutorial Case 8 demonstrating a multi-year seasonal analysis with 9 years of Gainesville weather.
- Proven on real DSSAT 4.8.5 (yields equal to a hand-edited NYERS run) with a two-treatment maize template experiment across 9 seasons and single-treatment copied FileX runs.

### Changed
- `write_experiment_template()` comments include `years` in the `controls` section.
- Checks report weather shortages for the last season's start labelled as `Controls years <N>` or `FileX NYERS <N>`.

### Notes
- Seasonal analysis sets NYERS in the controls level; no batch file, no new run mode (ADR 0012).
- Weather ending inside the last crop season continues to be caught after the run by scanning `WARNING.OUT` for missing weather records.
- `evaluate()` continues to reject multiple Summary rows for a treatment; observed data across seasons remains out of scope.
- Upgrading from 0.11.1 needs no changes. Zero runtime dependencies are preserved.

## [0.11.1] - 2026-10-01

### Added
- FileX template key `treatment_fields`: an optional list of field numbers 1..K (whole numbers without gaps) matching `treatments` in length, placing each treatment on a specific field. When omitted, all treatments grow on field 1.
- Per-field weather and soil dictionaries: template `Simulation` and `run_treatments(filex_template=...)` accept `weather=` and `soil=` as dicts keyed by field number (`{1: "gainesville.csv", 2: "ames.csv"}`; integer or digit-string keys), accepting CSV paths, lists of dicts, or pandas DataFrames. A plain source still means one field.
- The written FileX defines each field in both `FIELDS` tables with its own station, coordinates, elevation, soil ID, and depth; the simulation folder holds one weather file per station and one `SOIL.SOL` containing every distinct profile in field order.
- Guide sections and tutorial Case 7 show writing a two-field maize FileX template, supplying per-field weather and soil data, and comparing sites with `run_treatments()` and `combine_summaries()`.
- Proven on real DSSAT 4.8.5 (yields equal to a hand-edited NYERS run) with a multi-field maize experiment (`UFGA` and `AMES` weather stations, two soil profiles) run through `run_treatments()` and as a whole experiment via `run()`.

### Changed
- Fields sharing a station code or soil ID must have identical parsed data; sharing an ID with differing data is rejected with both field numbers before writing anything.
- Checks report weather and soil problems labelled by field number (`Weather data, field k` / `Soil data, field k`).
- Selected treatment dates and initial condition depths are validated against that treatment's assigned field weather and soil.
- `write_filex_template()` comments show `treatment_fields` alongside `treatments`.
- Passing a per-field dictionary with a copied FileX (`filex=...`) is rejected with a clear message explaining that per-field data requires a FileX template.

### Notes
- Template fields are numbered per treatment, and weather and soil are keyed by field (ADR 0011).
- Per-field data for copied FileX experiments remains out of scope.
- Upgrading from 0.11.0 needs no changes. Zero runtime dependencies are preserved.

## [0.11.0] - 2026-10-01

### Added
- FileX template key `treatments`: a list of 1 to 99 treatment names, the alternative to `treatment_name` (exactly one of the two is required). Treatments are numbered 1..N in list order, each pointing at the base levels. `EXP.DETAILS` and `SNAME` take the first treatment name.
- Multi-treatment template `Simulation`: `treatment` accepts 1..N; experiment data keyed by treatment number (`treatments: {2: {...}, 3: {...}}`) varies each treatment with its own new levels.
- The simulation folder's generated FileX holds the entire experiment with every treatment's experiment data applied, allowing the whole experiment to be opened or run in DSSAT; a scenario name applies to the selected treatment row only.
- `run_treatments(filex_template=...)` runs all treatments 1..N (when `treatments=None`) or a selected subset of a FileX template across named scenarios, writing each simulation in its own folder beside the template YAML.
- Guide sections and tutorial Case 6 show writing a three-treatment maize FileX template (rainfed, irrigated, irrigated with 120 kg N), varying treatments with experiment data, and comparing yields with `run_treatments()` and `combine_summaries()`.
- Proven on real DSSAT 4.8.5 (yields equal to a hand-edited NYERS run) with a three-treatment maize experiment (control, two N applications, irrigation plus cultivar IB0060) run through `run_treatments()` and as a whole experiment via `run()`.

### Changed
- `run_treatments(filex=None, weather=None, treatments=None, soil=None, management=None, executable=None, scenarios=None, filex_template=None)` accepts exactly one of `filex` and `filex_template`; passing both or neither raises `DSSATCheckError`.
- `write_filex_template()` comments show the `treatments` list alternative alongside `treatment_name`.
- `Simulation` treatment out-of-range checks report the valid 1..N range for multi-treatment templates.

### Notes
- Template treatments are named in the FileX template and varied by experiment data (ADR 0010). Each treatment entry gets its own new level; equal levels are not shared.
- Several fields from scratch (multiple stations or soil profiles) is planned next (v0.11.1).
- Experiment-data dates are checked against weather for the selected treatment.
- Upgrading from 0.10.0 needs no changes. Zero runtime dependencies are preserved.

## [0.10.0] - 2026-09-30

### Added
- Ten template crops for the FileX template: maize, wheat, rice, soybean, potato, sorghum, pearl millet, barley, peanut and dry bean, each with one fixed DSSAT model and genotype support files. Legumes (soybean, peanut, dry bean) write N fixation on (`SYMBI Y`); rice requires only `.CUL` and `.SPE`.
- `list_crops(executable=None)` returns rows (`crop`, `code`, `model`, `cultivars`) for each template crop whose genotype files exist in the installed DSSAT data directory.
- `list_cultivars(crop, executable=None)` returns rows (`code`, `name`) for a template crop in `.CUL` file order, listing the first occurrence of each distinct code. Both listings return plain dicts accepted by `to_dataframe()`.
- Optional top-level `harvest_date` in the FileX template writes a `*HARVEST DETAILS` section (`HDATE`, `GS000`) and sets harvest mode to `R` (harvest on reported date).
- Optional planting fields `planting_material_weight` (`PLWT`, kg/ha) and `sprout_length` (`SPRL`, cm) with numeric range and fixed-width column checks.
- Potato requires `planting_material_weight`, `sprout_length`, and `harvest_date`; each missing field is reported as a distinct problem.
- Guide section and tutorial Case 5 demonstrate inspecting installed crops and cultivars, writing a soybean FileX template, and running the simulation.
- Proven on real DSSAT 4.8.5 (yields equal to a hand-edited NYERS run) with all ten template crops, clean runs, non-zero yields, and matching cultivars.

### Changed
- `write_filex_template()` comments list all ten template crops, potato requirements, and `harvest_date`.
- A crop that is not a template crop is reported with the list of all ten template crops (FileX template and `list_cultivars`).
- Genotype file checks and staging copy only the required files for each crop (e.g. rice requires only `.CUL` and `.SPE`).

### Notes
- A crop becomes a template crop only after a real DSSAT run proved it; other crops still run from an existing FileX (ADR 0009).
- Yields from the template default management are not calibrated.
- Upgrading from 0.9.0 needs no changes. Zero runtime dependencies are preserved.

## [0.9.0] - 2026-09-30

### Added
- `read_dssat_observed(path)` reads DSSAT's FileA/FileT into observed data under scenario `base`, ready for `evaluate()`. Reads supported Summary and Plant growth measurements, omits `-99` cells, and resolves short dates from the sibling FileX treatment's `SDATE`. Problems are reported together with paths and line numbers.
- `read_dssat_evaluation(run_dir)` and `result.dssat_evaluation()` read DSSAT's own `Evaluate.OUT` as rows, retaining its column names, days-after-planting dates and missing values as `None`.
- `plot_observed(results, observed, variable)` overlays observed points on Plant growth curves, with one colour per scenario and treatment and optional matplotlib. Points outside the simulated season remain visible.
- `read_dssat_evaluation()` also reads the `$` title line and `TRNO` column CROPSIM (wheat) writes.
- Guide section and tutorial Case 4 use the shipped `UFGA8201.MZA` and `UFGA8201.MZT`, compare the end-of-season measurements, plot LAID and show HWAM beside the DSSAT evaluation.
- Proven on real DSSAT 4.8.5 (yields equal to a hand-edited NYERS run) with maize `UFGA8201` and wheat `KSAS8101`: all six treatments of each, FileA end-of-season values and FileT time series read straight from the shipped files.

### Notes
- DSSAT fills `Evaluate.OUT`'s measured columns only in some runs. Verified on DSSAT 4.8.5: CERES-Maize through `run()` with the FileA beside the FileX fills them; a `Simulation` (one treatment, DSSAT run mode C) and CROPSIM wheat leave them `-99`. Where they are `-99`, compare with `evaluate(results, read_dssat_observed(path))`. The simulation folder therefore does not copy FileA/FileT (ADR 0008).
- Only FileA/FileT reading and `Evaluate.OUT` reading were added to file support; no FileA/FileT is written. ADR 0008 amends ADR 0007: dssatlab now reads FileA/FileT and `Evaluate.OUT`.
- Upgrading from 0.8.0 needs no changes. Runtime dependencies remain zero; plotting still uses optional matplotlib.

## [0.8.0] - 2026-09-30

### Added
- `write_observed_template(path)` writes one commented CSV for your measurements: one row per scenario and treatment for end-of-season Summary values (`HWAM`, `ADAT`, `MDAT`, ...), and one row per date (yyyy-mm-dd) for Plant growth values (`LAID`, `CWAD`, ...). Use DSSAT's own column names and units; nothing is converted.
- `evaluate(results, observed)` compares one `RunResult` (scenario `base`) or the `run_treatments()` results with your observed data (CSV path, list of dicts or DataFrame). It returns an `Evaluation` with the error of each pair and, for variables with at least two pairs, RMSE, mean bias (simulated minus observed) and Willmott's d-index. Date errors are in days. `to_dataframe()` gives the pairs as a table.
- Every problem is reported at once in one `DSSATCheckError` before anything is compared: unknown column names (with the closest valid names), bad dates, `-99` measurements, keys with no matching run, dates with no simulated row and `-99` simulated values. Nothing is dropped silently.
- `plot_evaluation(evaluation, variable=None)` draws a 1:1 simulated-versus-observed scatter (optional matplotlib); dates are plotted on calendar axes.
- Proven on real DSSAT 4.8 with all six treatments of maize `UFGA8201` and wheat `KSAS8101`, compared with the measured data DSSAT ships for them.
- Tutorial Case 3 compares a run with invented observed numbers.

### Changed
- `check()` says when the planting-versus-start-date check was skipped and why (unreadable or impossible `SDATE`, no or ambiguous weather year), instead of skipping silently (#57).
- `Simulation.run()` loads the experiment data once and uses the same checked dict to write the FileX (#58).

### Notes
- No FileA/FileT is written and `Evaluate.OUT` is not read (ADR 0007).
- Irrigation header placement re-measured on real DSSAT (#56): the writer's layout was already correct; no change.

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
