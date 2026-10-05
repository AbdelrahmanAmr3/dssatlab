# DSSATLab

A Python package that lets a user drive the DSSAT crop model without touching a
shell: find a working DSSAT, turn their own data into proper DSSAT files with strict
checks, then run simulations with it.

## Language

**DSSAT executable**:
The validated `dscsm048` / `DSCSM048.EXE` file that runs the crop model.
What `connect()` and `install()` return. Not called a "connection".
_Avoid_: connection, binary

**Connecting**:
Finding a DSSAT executable, validating it, and remembering it for next time.
_Avoid_: linking, setup

**Discovery**:
The fixed search for a DSSAT executable when the user names none: saved config,
`DSSAT_HOME`, platform defaults, managed install.

**Saved config**:
The one remembered DSSAT executable, reused by later discovery.

**Managed install**:
A DSSAT release that dssatlab itself built and keeps in its own cache, on Linux.
Contains the DSSAT executable and its data directory.
_Avoid_: local build, cached install

**Data directory**:
The folder holding the files DSSAT reads at run time (genotype, code definitions,
`DSSATPRO`). In a managed install it is the install prefix; on Windows it is the
official `C:\DSSAT48` folder.

**FileX**:
DSSAT's experiment file (`*.MZX`, `*.SBX`, ...). It describes fields, treatments
and management for one experiment.
_Avoid_: experiment file, input file

**FileX date**:
A five-digit YYDDD date in a FileX (SDATE, PDATE, EDATE, HDATE, irrigation and automatic planting
dates). Always read with DSSAT's rule: years 00-35 are 2000-2035, 36-99 are 1936-1999. Weather written by
dssatlab never chooses its century. Experiment data dates must be in 1936-2035 to be written as one.
A stock weather file with `$WEATHER` anchors DSSAT's reading to its first date: a start or harvest date
before that date, or strictly more than 99 years after it (yyyyddd > F + 99000), is a check problem (ADR 0029).

**Treatment**:
One numbered row of a FileX. A run covers all treatments or a single one. Its number is the
N column as DSSAT reads it, so it always equals the Summary's TRNO.

**Experiment**:
The set of treatments one FileX describes. A FileX holds one experiment.

**Field**:
One numbered row of a FileX's FIELDS section: where a treatment grows, with one weather station
and one soil profile. Several treatments can share a field. In a FileX template each field gets its
own weather data and soil data, keyed by field number.
_Avoid_: site, location

**Simulation**:
One treatment of one experiment, described by its inputs, checked, and run to produce
one set of results (one per season in a seasonal analysis, one per rotation component run in a
sequence). The unit a future `Simulation` object stands for. A run carries out
one or more simulations (one per treatment it covers).
_Avoid_: job, experiment (an experiment holds several simulations)

**Season**:
One year of a seasonal analysis: the same treatment run again from the same day of year in the
next weather year, with its management dates moved by the same years. DSSAT runs the seasons
of a treatment in one run, one Summary row each.
_Avoid_: year (alone), replicate

**Seasonal analysis**:
Running one experiment's treatments over several seasons (DSSAT's NYERS, set by the controls
`years`) and comparing the results across seasons: mean, spread and range of a Summary variable.
_Avoid_: multi-year run, long-term run

**Sequence**:
A treatment whose number has several TREATMENTS rows in the FileX, one per rotation component.
DSSAT runs the components one after another, each starting the day after the previous one ended,
with soil water and nitrogen carried over, until the sequence's years (the first component's
NYERS or the controls `years`) have passed. dssatlab runs it in DSSAT's sequence mode (Q) through
a batch file it writes, in a Simulation and in `run()`.
_Avoid_: rotation (alone), crop sequence file, multi-crop treatment

**Rotation component**:
One row of a sequence, numbered by the FileX's R column: one crop (or fallow) with its own
cultivar, planting and other levels. A Summary row's `R#` names the component it came from.
_Avoid_: phase, step, sub-treatment

**Fallow**:
A rotation component with no crop: the field stays bare, soil water and nitrogen still change,
until the fallow's end date. DSSAT's crop code FA; it has no cultivar, planting or model of its own.
_Avoid_: empty crop, bare crop

**Sequence analysis**:
Running a sequence over several years and comparing results per rotation component and over
time, the way DSSAT's sequence analysis does.
_Avoid_: rotation analysis, long-term run

**Scenario**:
A named set of input overrides applied to a base Simulation's inputs (weather, soil, or
experiment data), run as its own simulation. Results are labelled with the scenario's name.
_Avoid_: treatment (a treatment is a row of the FileX, a scenario is not), variant

**Sweep**:
Running every combination of a few factors' values (a grid) as scenarios over the base inputs,
and getting one table of Summary rows labelled with each factor's value.
_Avoid_: batch (DSSAT's batch file is something else), grid search

**Factor**:
One experiment data section (planting, fertilizer, irrigation, ...) varied in a sweep over a few
labelled values, each a complete section. The same idea as a treatment factor in XBuild.
_Avoid_: level (a level is one entry of a FileX section), parameter

**Cultivar coefficient**:
One number on a cultivar's line in a .CUL file, named by its column header after `ECO#` (P1, G2,
PHINT ...). Experiment data may change some of them: dssatlab writes a **changed cultivar**, a
copy of the cultivar's line with those values and a new VAR# (DL0001, DL0002 ...), into the
simulation folder's .CUL copy and points the treatment at it. The source .CUL never changes.
_Avoid_: parameter, genetic coefficient file edit, calibration (GLUE is not planned)

**New cultivar**:
A cultivar the user defines in experiment data under their own code, absent from the crop's .CUL:
an existing ecotype and every cultivar coefficient of that .CUL. dssatlab adds it as one line to
the simulation folder's .CUL copy, keeping the user's code (unlike a changed cultivar's DLnnnn).
_Avoid_: custom cultivar, cultivar file

**Weather data**:
A user's own daily weather, as they hold it (a table), before it is converted into a
DSSAT weather file.

**Weather template**:
The one fixed CSV shape (named columns, DSSAT's own units) a user must put their weather
data in. Weather data that does not follow it is rejected by the checks, never guessed at.
_Avoid_: input format, schema

**NASA POWER file**:
A daily point CSV downloaded by the user from NASA POWER. `import_nasa_power()` turns it into a
weather template CSV once: its columns are already in DSSAT's units, so only the names and the
missing marker (-999 becomes -99) change. It is never passed as `weather=` directly.
_Avoid_: POWER weather, downloaded weather

**Weather summary**:
What `summarize_weather()` returns for weather data that passes the weather checks: station values,
first and last date, day count, min/mean/max per variable, rain total and one row per calendar year.
Only the user's weather data (the weather template), never a stock weather file.
_Avoid_: weather report, weather statistics

**Simulation start date**:
The day used by the start-day, season and sequence coverage checks: SDATE under START S, read as
a FileX date, or the effective planting date under START P.
controls.start_date replaces SDATE under START S only.

**Weather file**:
The DSSAT `*.WTH` file generated from weather data. DSSAT finds it beside the FileX.

**Stock weather file**:
A DSSAT `*.WTH` file the user already has (for example from DSSAT's own Weather folder), handed
to a Simulation as its weather. It is copied unchanged, under its upper-case name, into the simulation
folder; the checks read only its station, coordinates, dates and srad, tmax, tmin and rain.
_Avoid_: raw weather, native weather

**Generated weather**:
Daily weather DSSAT makes itself from a climate file instead of reading measured days: WTHER W
(WGEN) or S (SIMMETEO) in the simulation controls. A run treatment with generated weather needs a
climate file and no weather data.
_Avoid_: synthetic weather, simulated weather, gap filling

**Climate file**:
A DSSAT `*.CLI` file of station monthly averages (for example from DSSAT's `Weather/Climate`
folder), handed to a Simulation through `weather=`. DSSAT reads `<first four characters of WSTA>.CLI`
beside the FileX; it is copied unchanged, under its upper-case name, into the simulation folder.
The checks read only its header, station row and the table its WTHER method needs (monthly averages for S, WGEN parameters for W).
A FileX template field can take a climate file as its only weather (ADR 0034).

**Replicate**:
One repetition of a treatment's seasons with a different random weather series (DSSAT NREPS,
seeded by RSEED). Replicates only differ under generated weather.

**Daily PAR**:
Photosynthetically active radiation for one day (DSSAT PAR, mol/m2 per day). An optional weather
template column; a weather file carries it when the weather data has it.

**Soil data**:
A user's own soil profile, as they hold it (a table of layers), before it is converted
into a DSSAT soil file.

**Soil template**:
The one fixed CSV shape (named columns, DSSAT's own units) a user must put their soil
data in. Soil data that does not follow it is rejected by the checks, never guessed at.
_Avoid_: soil input, soil schema

**Soil file**:
The DSSAT `*.SOL` file generated from soil data. Not the same as a `.SOL` file the user
already keeps beside their FileX.

**Stock soil file**:
A DSSAT `*.SOL` file the user already has, handed to a Simulation as its soil. It is copied
unchanged, under its own name, instead of the FileX's sibling soil files; the checks read only its
soil profile IDs.

**Soil profile**:
One named set of soil layers in a soil file, identified by the FileX's `ID_SOIL`. The
soil template describes exactly one.

**Soil summary**:
What `summarize_soil()` returns for soil data that passes the soil checks: the soil profile ID,
layer count, depth, extractable water (sum of DUL minus LL over the layers, mm) and the profile
values. Only the user's soil data (the soil template), never a stock soil file.
_Avoid_: soil report

**Level**:
One numbered entry of a FileX section (a planting, an irrigation schedule, a fertilizer
schedule). A treatment points at its levels by number; level 0 means none.

**Management data**:
A user's own planting, irrigation and fertilizer for each treatment, as they hold it,
before it is written into the FileX.

**Management template**:
The one fixed shape (named fields, DSSAT's own units and codes) a user must put their
management data in. Management data that does not follow it is rejected by the checks,
never guessed at.
_Avoid_: management input, management schema

**Scenario template**:
The one fixed YAML shape a user writes their scenarios in: each scenario's name and the
inputs it overrides. Scenarios that do not follow it are rejected by the checks, never
guessed at.

**Experiment template**:
The one fixed YAML shape (named fields, DSSAT's own units and codes) a user must put their
experiment data in. A superset of the management template; a management-only file stays
valid.
_Avoid_: experiment input, FileX template

**Experiment data**:
The one user-supplied dict of everything written into a copy of the FileX for a treatment:
management data, and later cultivar, initial conditions and simulation controls. Management
data is one part of it, not a synonym. For a sequence it holds the controls years and start
date, and `rotation`: planting, cultivar, fertilizer, irrigation, residues, tillage and harvest
per rotation component, keyed by the component's R number (a fallow takes only the last three).
_Avoid_: management (for the whole dict), FileX input

**Simulation option**:
One DSSAT OPTIONS, METHODS or MANAGEMENT code a user sets in experiment data `controls` under a
plain name (`photosynthesis` for PHOTO, `symbiosis` for SYMBI, `residue` for RESID). Allowed codes
are DSSAT's active SIMULATION.CDE codes plus those stock DSSAT FileX use (ADR 0019). An omitted
option keeps the copied level's code.
_Avoid_: method flag, switch

**Automatic management**:
DSSAT deciding an operation itself during the run instead of on reported dates: automatic
irrigation (when soil water in the management depth falls below a threshold, refill it) and
automatic planting (the first day in a planting window when soil water and temperature allow).
Set in experiment data `controls` with `irrigation_management` / `planting_management` codes and
`auto_irrigation_*` / `auto_planting_*` fields (ADR 0020).
_Avoid_: auto mode, smart irrigation

**Irrigation management**:
The treatment's DSSAT IRRIG code: how its irrigation events are read. "R" (and "P", "W") read
event dates, "D" reads days after planting, "A", "F" and "N" take no events. The checks reject
events that DSSAT would ignore or misread under the code.
_Avoid_: irrigation mode (a run mode is something else)

**Days after planting**:
An irrigation event's timing given as whole days counted from the treatment's planting date, used
under irrigation management "D". An event has a date or days after planting, never both.
_Avoid_: DAP (in messages), relative date

**Irrigation efficiency**:
The share of applied irrigation water that reaches the soil (DSSAT EFIR, 0 to 1) for the
treatment's reported irrigation events. Automatic irrigation has its own efficiency (IREFF).
_Avoid_: application efficiency

**Field operation**:
A residue application, tillage pass or harvest on a reported date, given in experiment data
`residues`, `tillage` or `harvest` (DSSAT RESIDUES AND ORGANIC FERTILIZER, TILLAGE AND
ROTATIONS, HARVEST DETAILS). Events are in non-descending date order; several on one date are
allowed. Residue events are checked against the RESID code and harvest events against the HARVS
code (`harvest_management`), as irrigation events are against IRRIG (ADR 0021).
_Avoid_: operation (alone, too broad), cultural practice

**Harvest details**:
A harvest event's date plus optional growth stage (HSTG), component (HCOM), size group (HSIZE)
and the percent of product and by-product removed (HPC, HBPC). Under HARVS "M" the date is not
used but the percents are, so the events are allowed.
_Avoid_: harvest settings

**Initial conditions off**:
Experiment data `initial_conditions: "off"`: the treatment's IC factor level is set to 0 in the
FileX copy, so DSSAT uses its own initial soil water and nitrogen. Not the same as omitting the
section, which keeps the FileX's own level.
_Avoid_: no IC, disabled IC (in code and messages)

**Soil analysis**:
Measured soil properties for a treatment's field, given in experiment data `soil_analysis` (DSSAT
SOIL ANALYSIS, level SA): a date, optional method codes and layers with values such as extractable
phosphorus (SAPX) or organic carbon. DSSAT replaces the soil profile's values with them, and uses a
column only when the first layer has a value. Soil phosphorus only matters with `phosphorus: "Y"`.
`"off"` sets SA to 0 (ADR 0028).
_Avoid_: soil test, soil sample

**Environment modification**:
A change to the daily weather from a date onwards, given in experiment data `environment` (DSSAT
ENVIRONMENT MODIFICATIONS, level ME): add, subtract, multiply or replace one or more of day length,
srad, tmax, tmin, rain, CO2, dew point and wind. Each event lasts until the next one. The weather
file and the weather checks are unchanged (ADR 0028).
_Avoid_: climate change scenario, weather modification (in code and messages)

**FileX template**:
The one fixed shape a user fills in so dssatlab can write a FileX from scratch: one crop, one or
more fields, and one treatment or a list of named treatments, each on one field. Every treatment starts from the template's
cultivar, planting and harvest; experiment data keyed by treatment number varies each one. Built
from the experiment data plus the crop, station and soil profile. Each field's weather is weather
data or one climate file, whose station row gives the field's station and coordinates. Instead of one crop it can hold a
rotation: one sequence of 2 to 99 rotation components (crops or fallows), each crop with its own
cultivar, planting and harvest, written as a sequence FileX. It starts on the first crop's planting
date, or on the start date of a leading fallow. Instead of one crop it can also hold numbered crop
entries in `crops`, each with its own cultivar, planting and optional harvest date; `treatment_crops`
points each named treatment at an entry. Several treatments can share an entry, and entries can
name the same crop with different cultivars: different crops in different treatments.
Not the same as the experiment template, which only edits a copy of an existing FileX.
_Avoid_: FileX generator

**Template crop**:
A crop the FileX template can write, with one fixed DSSAT model and its genotype files. A crop is
a template crop only after a real DSSAT run proved it. Other crops still run from an existing FileX.
_Avoid_: supported crop (ambiguous with every crop DSSAT has)

**Crop entry**:
One crop of a mixed-crop FileX template: a template crop with its own cultivar, planting and
optional harvest date. Treatments pick an entry by number, as they pick a field. Each entry gets its
own cultivar, planting and simulation controls levels, so each treatment runs its crop's model.
Not the same as a rotation component, which follows the others in time within one sequence.
_Avoid_: crop treatment, crop factor

**Observed data**:
The user's own measured values (for example yield, anthesis day, or LAI on a date), given per
scenario and treatment, as a CSV, DataFrame or list of rows. dssatlab compares them with the
Summary and Plant growth itself and writes nothing for DSSAT. Observed data can also be read from a
FileA/FileT.
_Avoid_: measured file

**FileA/FileT**:
DSSAT's own observed files beside the FileX, with the same name and the last extension letter A
(end-of-season averages per treatment) or T (values per treatment and date). dssatlab reads them into
observed data; it never writes them. `-99` in them means "not measured".
_Avoid_: observed file (ambiguous with the observed data CSV)

**DSSAT evaluation**:
DSSAT's own simulated-versus-measured table, `Evaluate.OUT`. DSSAT fills its measured columns only
in some runs (verified: CERES-Maize through run() with the FileA beside the FileX); a Simulation runs
one treatment and DSSAT leaves them -99. Read as rows; not the same as dssatlab's Evaluation.
_Avoid_: evaluation (alone)

**Evaluation**:
The comparison of observed data with a run's Summary and Plant growth: the error for each
variable, and RMSE, bias and d-index across scenarios, computed by dssatlab. Not the DSSAT evaluation.
_Avoid_: Evaluate.OUT, validation

**Example**:
A complete, ready-to-run folder of filled-in files (a FileX with its genotype files,
plus weather data, soil data and experiment data) that runs with no edits. Shows what a
user's own files should look like. Not the same as a template, which shows only the
fixed shape and is meant to be edited.
_Avoid_: sample, demo

**Checks**:
The strict validation of a simulation's inputs, done before any DSSAT files are written or
DSSAT is run, reporting every problem at once.
_Avoid_: validation errors, lint

**Run**:
One invocation of the DSSAT executable on one FileX.
_Avoid_: job

**Run mode**:
The letter DSSAT is started with, which decides how it reads the FileX: A (all treatments), C (one
treatment), Q (sequences, through a batch file) or Y (forecast, through a batch file). dssatlab
picks it from the FileX: Y for a forecast FileX, Q when a treatment run is a sequence, else A or C.
_Avoid_: batch mode (a batch file is how Q and Y receive their treatments), irrigation mode

**Forecast run**:
A run in DSSAT's forecast mode (Y) of a forecast FileX (`.FCX`): observed weather from the start
date to the day before the forecast date, then one result per historical weather year, from
(start year - NYERS) to (start year - 1). `run()` does it, and so does a Simulation whose FileX
template is a `.FCX` (measured weather only, one treatment).
_Avoid_: prediction, seasonal analysis (that is NYERS seasons of one weather record)

**Forecast date**:
The first day a forecast run takes from the historical weather years instead of observed weather
(FileX SIMDATES FODAT, experiment data `controls.forecast_date`). A Simulation needs one, and it
must not be before the start date.

**Run directory**:
A new, dated folder created beside the FileX for one run. DSSAT runs in the FileX's own
folder, and its output files are moved into the run directory when the run ends.
_Avoid_: output folder, working directory

**Run result**:
What `run()` hands back: exit status, run directory, the output files found, and a
tail of DSSAT's console output. It holds no parsed values itself, but gives access to
the parsed output files (summary, plant growth, soil water, plant nitrogen, and weather).

**Output file**:
A file DSSAT writes into a run directory (`Summary.OUT`, `PlantGro.OUT`, `SoilWat.OUT`,
`PlantN.OUT`, `Weather.OUT`, ...). Five output files are read (summary, plant growth,
soil water, plant nitrogen, and weather); every other one is only listed. When a FileX asks
for experiment-named output files (FNAME=Y), DSSAT names the same files after the experiment
(`DTCM6401.OSU` for `Summary.OUT`); they are still the same output files.
_Avoid_: result file

**Summary**:
The parsed `Summary.OUT` of a run directory: one row per simulation and season (per rotation
component run in a sequence), with DSSAT's own column names (`HWAM`, `ADAT`, `R#`, ...).

**Price file**:
A DSSAT `*.PRI` file of crop prices and production costs (for example from DSSAT's `Economic`
folder), sectioned by crop and treatment number. Each price or cost is fixed or a distribution
(IDIS); dssatlab uses its expected value. DSSAT-CSM itself never reads it.
_Avoid_: cost file, economics file

**Net return**:
The money one Summary row earns per hectare at the price file's expected prices: harvested yield
and by-product times their prices, minus base, fertilizer, irrigation, seed and amendment costs.
Computed in Python by `net_returns()`; `None` when a quantity it needs is missing.
_Avoid_: profit, gross margin, income

**Plant growth**:
The parsed `PlantGro.OUT` of a run directory: one row per simulation day, with DSSAT's own
column names (`LAID`, `CWAD`, ...).

**Soil water**:
The parsed `SoilWat.OUT` of a run directory: one row per simulation day, with DSSAT's own
column names (`SWTD`, `SW1D`, ...).

**Plant nitrogen**:
The parsed `PlantN.OUT` of a run directory: one row per simulation day, with DSSAT's own
column names (`NUPC`, `NICD`, ...).

**Weather output**:
The parsed `Weather.OUT` of a run directory: one row per simulation day, with DSSAT's own
column names (`SRAD`, `TMAX`, ...).

**Missing value**:
DSSAT's `-99` marker in an output file. Read as an empty value (`None`), never as a number.

**Docs site**:
The published website built from the repository's `docs/` folder. It has two sections:
the Guide (for users) and Reference and Architecture (for engineers). It shows the latest
release only.

**Changelog**:
The one hand-written `CHANGELOG.md` listing what each release added, changed and fixed.
The docs site includes it and GitHub release notes copy from it. It is the project's
"log"; it is not Python `logging` output and not simulation output.
_Avoid_: release notes (those copy from it), log
