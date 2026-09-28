# One-Page Scope Guard

## Build now

- `detect()` current OS/Colab/DSSAT availability
- `connect()` to an existing DSSAT executable
- Windows default discovery around `C:\\DSSAT48`
- user-supplied Windows/Linux path
- simple remembered config
- `install()` latest stable or requested stable DSSAT on Linux/Colab
- Git/CMake/gfortran prerequisite checks
- build cache + manifest
- clear exceptions and text prompts
- unit tests
- PyPI-ready packaging

## Do not build now

Everything else.

That specifically includes:
- running experiments as a high-level API
- input file editors/parsers
- output parsers
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

> Does this change directly help a user get a valid DSSAT executable connection?

If the answer is no, defer it.
