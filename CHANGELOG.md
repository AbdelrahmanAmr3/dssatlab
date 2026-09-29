# Changelog

All notable changes to dssatlab. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The entries for 0.1.0 to 0.3.0 were backfilled from the GitHub release notes; from now on new entries are written here first and the release notes copy from them.

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

[0.3.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.3.0
[0.2.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.2.0
[0.1.1]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.1.1
[0.1.0]: https://github.com/AbdelrahmanAmr3/dssatlab/releases/tag/v0.1.0
