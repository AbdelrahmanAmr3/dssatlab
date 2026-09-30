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

**Treatment**:
One numbered row of a FileX. A run covers all treatments or a single one.

**Experiment**:
The set of treatments one FileX describes. A FileX holds one experiment.

**Simulation**:
One treatment of one experiment, described by its inputs, checked, and run to produce
one set of results. The unit a future `Simulation` object stands for. A run carries out
one or more simulations (one per treatment it covers).
_Avoid_: job, experiment (an experiment holds several simulations)

**Scenario**:
A named set of input overrides applied to a base Simulation's inputs (weather, soil, or
experiment data), run as its own simulation. Results are labelled with the scenario's name.
_Avoid_: treatment (a treatment is a row of the FileX, a scenario is not), variant

**Weather data**:
A user's own daily weather, as they hold it (a table), before it is converted into a
DSSAT weather file.

**Weather template**:
The one fixed CSV shape (named columns, DSSAT's own units) a user must put their weather
data in. Weather data that does not follow it is rejected by the checks, never guessed at.
_Avoid_: input format, schema

**Weather file**:
The DSSAT `*.WTH` file generated from weather data. DSSAT finds it beside the FileX.

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

**Soil profile**:
One named set of soil layers in a soil file, identified by the FileX's `ID_SOIL`. The
soil template describes exactly one.

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
data is one part of it, not a synonym.
_Avoid_: management (for the whole dict), FileX input

**FileX template**:
The one fixed shape a user fills in so dssatlab can write a FileX from scratch: one field, one
treatment, one crop. Built from the experiment data plus the crop, station and soil profile.
Not the same as the experiment template, which only edits a copy of an existing FileX.
_Avoid_: FileX generator

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
soil water, plant nitrogen, and weather); every other one is only listed.
_Avoid_: result file

**Summary**:
The parsed `Summary.OUT` of a run directory: one row per simulation, with DSSAT's own
column names (`HWAM`, `ADAT`, ...).

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
