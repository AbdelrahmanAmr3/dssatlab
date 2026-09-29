# One-Page Scope Guard

## Done

- v0.1 (`SPEC.md`): `detect()`, `connect()`, `install()`: find, validate, remember, or build a DSSAT executable
- v0.2 (`SPEC_v0.2.md`): `run(filex, treatment=None, executable=None)` runs DSSAT on one existing FileX in a dated run directory; the managed Linux build is runnable

## Build now (v0.3, see `SPEC_v0.3.md`)

- a `Simulation` object: one treatment of one experiment, built from the user's own weather data
- the weather template: one fixed CSV shape in DSSAT's own units, plus `write_weather_template()`
- strict checks (`check()`): every problem an error, all reported at once, nothing auto-fixed
- a narrow read of the FileX (weather station and start date for a treatment) to compare with the weather
- a generated DSSAT weather file, and a fresh simulation folder holding the copied FileX, sibling soil files and that weather file
- `DSSATCheckError`, DataFrame input when pandas is present (never required)

## Do not build now

Everything else.

That specifically includes:
- full FileX or output parsing
- building a FileX from Python objects
- soil or management inputs
- unit converters, gap filling or any automatic repair, warnings
- optional weather columns (PAR, humidity, wind), hourly data, several stations
- batch mode, model selection, timeouts, parallel runs
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

> Does this change directly help a user turn their own weather data into a checked DSSAT simulation and run it?

If the answer is no, defer it.
