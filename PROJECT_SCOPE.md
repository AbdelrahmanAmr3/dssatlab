# One-Page Scope Guard

## Done (v0.1, see `SPEC.md`)

- `detect()`, `connect()`, `install()`: find, validate, remember, or build a DSSAT executable
- Windows discovery around `C:\\DSSAT48`, Linux/Colab managed build

## Build now (v0.2, see `SPEC_v0.2.md`)

- `run(filex, treatment=None, executable=None)` runs DSSAT on one existing FileX
- dated run directory beside the FileX, holding DSSAT's output files
- `RunResult` with return code, run directory, output file list, console tail
- managed Linux build installs into its own prefix so the data directory exists
- `DSSATRunError`, unit tests with mocked subprocess

## Do not build now

Everything else.

That specifically includes:
- FileX or output parsing
- building FileX from Python objects
- batch mode, model selection, timeouts, parallel runs
- DataFrames
- plots
- widgets
- dashboards
- calibration
- sensitivity analysis
- Docker
- cloud execution
- HPC
- plugin systems

## Design question to ask before every change

> Does this change directly help a user run one existing FileX and find its outputs?

If the answer is no, defer it.
