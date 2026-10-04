# Testing and CI

This page describes the organization of the test suite, how to execute tests locally, continuous integration workflows, and manual integration testing.

## Test suite organization

The tests under `tests/` are organized around individual package responsibilities:

- `test_config.py`: Verifies configuration path resolution across platforms, JSON serialization, and saving of the DSSAT executable path.
- `test_core.py`: Tests discovery order precedence, environment variable detection, path validation, interactive prompts, and `DSSATNotFoundError` conditions.
- `test_dataframe_input.py`: Verifies that pandas DataFrames can be passed as weather data, exercising the same validation checks and conversions as CSV inputs without requiring pandas at runtime.
- `test_filex_check.py`: Tests FileX parsing across varied column alignments and section formats, extracting treatment numbers, weather station codes (`WSTA`), and start controls (`START`, `SDATE`).
- `test_installer.py`: Validates Linux build mechanics, version resolution via GitHub API, build tool prerequisites (`git`, `cmake`, `gfortran`), and the 51-character prefix limit.
- `test_public_api.py`: Asserts that the main public names (`connect`, `detect`, `install`, `run`, `DSSATError`, `DSSATRunError`) are importable and listed in `dssatlab.__all__`.
- `test_runner.py`: Tests low-level DSSAT execution via `run()`, verifying run directory creation, output file collection, stdout capture, and error handling.
- `test_simulation.py`: Validates `Simulation` construction, ensuring no premature I/O occurs, and exercises `check()` against valid and invalid weather/FileX combinations.
- `test_simulation_run.py`: Tests `Simulation.run()`, verifying staging into dated simulation folders, sibling file copying (`.SOL`, `.CUL`, `.ECO`, `.SPE`), weather file generation, and scanning of `WARNING.OUT` for missing weather records.
- `test_weather_file.py`: Tests weather template writing (`write_weather_template()`), strict data parsing and range validation (`_parse_weather()`), and fixed-width ASCII weather file generation (`write_weather_file()`).
- `test_manual_integration.py`: End-to-end integration test that builds DSSAT from source on Linux and executes a real FileX experiment and Simulation.

## Running tests locally

To run the automated tests locally, install the package in editable mode with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Execute the test suite with pytest:

```bash
python -m pytest
```

All standard unit tests run offline using synthetic files and mocks without requiring a local DSSAT executable.

## Continuous integration

Continuous integration is handled by GitHub Actions defined in `.github/workflows/`:

### Tests workflow (`tests.yml`)

The tests workflow runs on every `push` and `pull_request`:

- **Matrix**: Tests against `ubuntu-latest` and `windows-latest` across Python `3.10` and `3.12`.
- **Steps**: Checks out the repository, configures Python, installs development dependencies (`pip install -e ".[dev]"`), and executes `python -m pytest`.

### Documentation workflow (`docs.yml`)

The documentation workflow runs on pull requests and pushes to `master`:

- **Environment**: Runs on `ubuntu-latest` with Python `3.12`.
- **Steps**: Installs documentation dependencies (`pip install -e ".[docs]"`) and executes `mkdocs build --strict`.
- **Deployment**: On pushes to `master`, publishes the rendered HTML site to GitHub Pages.

## CI compilation policy

Normal CI never compiles DSSAT.

Building DSSAT from source requires a full Fortran compilation toolchain and several minutes of build time. Standard automated tests in CI isolate Python logic through unit fixtures, synthetic FileX snippets, and mocked subprocess calls. This keeps CI execution fast, deterministic, and free from external compiler dependencies.

## Opt-in manual integration test

A full end-to-end integration test is provided in `tests/test_manual_integration.py`. This test compiles DSSAT from source on Linux and runs simulations against real DSSAT data files.

Because it takes several minutes and requires `git`, `cmake`, and `gfortran`, it is skipped by default during normal test runs and in CI.

To run the manual integration test, supply a real FileX (and optional weather template CSV), and use throwaway cache and configuration directories to avoid altering saved settings:

```bash
XDG_CACHE_HOME=/tmp/dl/cache XDG_CONFIG_HOME=/tmp/dl/config \
DSSATLAB_MANUAL_FILEX=/path/to/UFGA8201.MZX \
DSSATLAB_MANUAL_WEATHER=/path/to/weather.csv \
python -m pytest tests/test_manual_integration.py
```
