# DSSATLab v0.3 Specification: a Simulation from the user's own weather data

Published as GitHub issue #9. `SPEC.md` and `SPEC_v0.2.md` stay frozen. Vocabulary is in `CONTEXT.md`.

## Problem Statement

A user who wants to run DSSAT on their own weather data has to leave Python and do it by hand. They must learn DSSAT's fixed-width weather file format, name the file so it matches the station code inside their FileX, and place it where DSSAT will find it. A mistake in any of this shows up only as a cryptic DSSAT error ("file not found", a Fortran "Substring out of bounds"), usually after a wasted run. `run()` can run an existing FileX, but nothing helps the user get from their own data to the DSSAT files it needs, and nothing checks that data before DSSAT does.

## Solution

The user puts their daily weather in one fixed CSV shape, the **weather template**, and creates a **Simulation** for one treatment of their FileX. `check()` reports every problem with the weather data and with how it fits the FileX, all at once, before anything is written. `run()` then makes a fresh simulation folder, copies the FileX into it, writes the DSSAT weather file, runs DSSAT, and returns the run result. The user's own folder is left as it was. A small function writes an example template so the user can start from a correct file.

## User Stories

1. As a researcher with my own daily weather, I want a single fixed CSV template, so that I know exactly how to prepare my data.
2. As a researcher, I want a function that writes an example template file, so that I can start from a correct file and avoid typos in column names.
3. As a researcher, I want the example template to pass its own checks, so that I can trust it as a starting point.
4. As a researcher, I want to create a Simulation from my FileX, a treatment number and my weather CSV, so that one object stands for one simulation.
5. As a researcher, I want creating a Simulation to do no work and never fail on missing inputs, so that I can build it step by step.
6. As a researcher, I want `check()` to return a list of problems and write nothing, so that I can inspect my data safely.
7. As a researcher, I want `check()` to report every problem at once, so that I fix everything in one pass instead of one error at a time.
8. As a researcher, I want an empty list from `check()` to mean my data is fine, so that success is unambiguous.
9. As a researcher, I want each problem message to say what is wrong, where (column, row or date), and what to do, so that I can fix it without reading DSSAT's manual.
10. As a researcher, I want a missing required column reported by name, so that I can add it.
11. As a researcher, I want an unknown column reported, so that a misspelled column name is not silently ignored.
12. As a researcher, I want column names to be exact and in any order, so that I can arrange my file freely but not get names wrong.
13. As a researcher, I want values that are not numbers, or are empty, reported with their row, so that I can correct them.
14. As a researcher, I want dates to be ISO `YYYY-MM-DD` only, so that there is no doubt about day and month order.
15. As a researcher, I want an impossible calendar date reported, so that a typo like `2021-02-30` is caught.
16. As a researcher, I want rows to be sorted by date, so that I am told if my file is out of order.
17. As a researcher, I want a gap of missing days reported with the missing date range, so that I know where to fill it myself.
18. As a researcher, I want duplicate dates reported, so that I do not run with ambiguous data.
19. As a researcher, I want nothing filled in or repaired automatically, so that I decide how to treat missing data.
20. As a researcher, I want maximum temperature below minimum temperature reported, so that swapped columns are caught.
21. As a researcher, I want negative rainfall reported, so that bad values are caught.
22. As a researcher, I want physically impossible solar radiation, temperature and rainfall values reported, so that unit mistakes (for example W/m² instead of MJ/m² per day) are caught.
23. As a researcher, I want the units to be DSSAT's own (MJ/m² per day, °C, mm) and to be told so in the template, so that nothing is silently converted.
24. As a researcher, I want the station code to be exactly four characters, so that it can name the weather file correctly.
25. As a researcher, I want station, latitude, longitude and elevation to be identical on every row, so that a copy-paste mistake is caught.
26. As a researcher, I want latitude, longitude and elevation range-checked, so that swapped or mistyped coordinates are caught.
27. As a researcher, I want the optional station values (`tav`, `amp`, `refht`, `wndht`) to default to DSSAT's "not given" value, so that I only supply them if I have them.
28. As a researcher, I want `check()` to read my chosen treatment's weather station and start date from my FileX, so that it can compare them with my data.
29. As a researcher, I want a clear message when my FileX expects a different weather station than my template has, so that I do not get DSSAT's "file not found".
30. As a researcher, I want a clear message when my weather does not cover the simulation's start date, so that I do not get a run that fails immediately.
31. As a researcher, I want the FileX read to handle a station given as four characters or as a full eight-character weather file name, so that both common styles work.
32. As a researcher, I want a message when the FileX cannot be read for the fields needed (for example a treatment number that does not exist), so that I know what is wrong with my FileX.
33. As a researcher, I want weather spanning several years to work, so that long simulations are supported.
34. As a researcher, I want `run()` to run the checks first and raise one `DSSATCheckError` listing all problems, so that a bad simulation never reaches DSSAT.
35. As a researcher, I want `run()` to create a fresh simulation folder, so that a run never overwrites an earlier one.
36. As a researcher, I want two simulations started in the same second to get different folders, so that they do not collide.
37. As a researcher, I want my original FileX and folder to be unchanged, so that my data is never at risk.
38. As a researcher, I want my own soil file that sits beside my FileX to be available to the run, so that a FileX using a local soil file still works.
39. As a researcher, I want the generated weather file to have the exact format and filename DSSAT expects, so that DSSAT reads it without errors.
40. As a researcher, I want `run()` to return the same run result as `run()` does today, so that I already know how to read it.
41. As a researcher, I want the run's output files kept inside the simulation folder, so that everything for one simulation is in one place.
42. As a researcher, I want a clear error when the FileX folder is not writable, so that I know to move it.
43. As a researcher using pandas, I want to pass a DataFrame as my weather data, so that I do not have to save a CSV first.
44. As a researcher without pandas, I want the package to work with a CSV path or plain rows, so that I do not have to install anything extra.
45. As a researcher, I want to pass an explicit DSSAT executable, so that I can choose which DSSAT the simulation uses.
46. As a Python developer reviewing the package, I want the checks, the FileX read and the object in separate small modules, so that each can be read in one sitting.
47. As a Python developer, I want the package to stay free of runtime dependencies, so that installing it stays trivial.
48. As a maintainer, I want the vocabulary in `CONTEXT.md` used in code, tests and messages, so that the project stays consistent.

## Implementation Decisions

- **Public API additions:** a `Simulation` object, a `write_weather_template` function and a `DSSATCheckError` exception. `detect`, `connect`, `install` and `run` keep their signatures and behavior. The `Simulation` calls the existing `run()` underneath.
- **Simulation:** built from a FileX path, a treatment number, the weather data, and an optional explicit executable. Creating it does no work and cannot fail on missing or wrong inputs.
- **`check()`:** returns a list of problem messages (an empty list means no problems). It reads the FileX and the weather data and writes nothing.
- **`run()`:** runs the checks; if there are problems it raises one `DSSATCheckError` (a subclass of the package's base error) whose message lists all of them and which also exposes them as a list. Otherwise it creates the simulation folder, copies the inputs, writes the weather file, runs DSSAT on the copy through the existing `run()`, and returns the run result. The run directory therefore sits inside the simulation folder.
- **Simulation folder:** created beside the user's FileX, named by the date like the run directory (`-2`, `-3` if the name exists, never reused). It holds a copy of the FileX under its original filename (the 12-character limit still applies), the generated weather file, and the run directory. The user's original files are never modified.
- **Sibling files:** DSSAT reads a local soil file that sits beside the FileX. The simulation folder must therefore also contain every sibling `.SOL` file from the FileX folder. Which other sibling files DSSAT reads from the FileX folder (for example cultivar files) is not yet verified and must be checked against a real DSSAT run; the list is extended if DSSAT needs more.
- **Weather template:** one CSV, comma-separated, UTF-8, with these exact lower-case column names in any order. Required: `station` (exactly four characters), `latitude`, `longitude`, `elevation`, `date` (ISO `YYYY-MM-DD`), `srad`, `tmax`, `tmin`, `rain`. Optional: `tav`, `amp`, `refht`, `wndht`, each defaulting to DSSAT's "not given" value (-99). Units are DSSAT's own and are never converted: solar radiation in MJ/m² per day, temperatures in °C, rainfall in mm, elevation in m. Unknown columns are errors.
- **Checks on the weather data (every problem an error, all reported):** required columns present and no unknown ones; every value numeric and not empty; dates valid ISO dates; sorted ascending; one row per calendar day with no gaps or duplicates; `tmax` not below `tmin`; `rain` not negative; solar radiation, temperature and rainfall within physical ranges; latitude within ±90, longitude within ±180, elevation within a plausible range; station code exactly four characters; station, latitude, longitude and elevation identical on every row. The starting ranges are: solar radiation 0 to 45, temperatures −60 to 60, rainfall 0 to 1000 (mm per day), elevation −500 to 9000; they are constants that can be adjusted in review.
- **Nothing is auto-fixed:** no gap filling, no unit conversion, no reordering, no rounding beyond what the weather file format itself requires.
- **Narrow FileX read (not a FileX parser):** for the chosen treatment, follow the treatment row to its field and simulation-controls rows and read the weather station code and the start date. The section and column positions come from each section's header line. The weather station may be four characters (station code) or a full eight-character weather file name; both are handled. Dates in a FileX are two-digit year plus day of year; comparison with the weather data uses the two-digit year and day of year, so no century rule is needed. Anything the read cannot resolve (unknown treatment number, missing section) becomes a problem in `check()`, not an exception.
- **FileX and weather together:** `check()` reports a station mismatch between the FileX and the template, and reports weather that does not cover the start date. The rule for how far past the start the weather must reach is not decided here: it must be settled against real DSSAT behavior when weather ends early, and recorded in the spec before that check is implemented.
- **Weather file writer:** writes DSSAT's daily weather format, matching a real DSSAT sample file: a title line, a station header line (station, latitude, longitude, elevation, average temperature, amplitude, reference heights), then one row per day with the date as two-digit year plus day of year and solar radiation, maximum and minimum temperature and rainfall. Daily values are written with one decimal. The filename is the station code, the two-digit start year and the two-digit number of calendar years covered (for example a single year starting in 1982 with station UFGA gives `UFGA8201.WTH`). A series longer than 99 years is a problem. The exact column widths are copied from the real sample and verified by running real DSSAT on a generated file.
- **Input forms and pandas:** a CSV path or plain rows always work. A DataFrame is accepted when the user passes one, detected without importing pandas. pandas is never required (see the pandas decision record).
- **Template function:** writes a correct example template to a path the user gives. The example must pass `check()` against its own data shape.
- **Errors:** the checks never raise for bad data, they return problems; only `run()` raises, once. A folder that cannot be created reuses the existing run error.
- **Modules:** the feature is split into three small modules (the object, the weather template with its checks and file writer, and the FileX read), each well under 300 lines. The repository guideline of "roughly 4-6 modules" is updated to allow this, in the same change as this spec.
- **Vocabulary:** Simulation, Experiment, Weather data, Weather template, Weather file, Checks and Run are defined in `CONTEXT.md` and used throughout.

## Testing Decisions

- A good test checks external behavior through the public object and does not assert on internal helpers.
- **One main seam: the public `Simulation`.** All weather checks and the FileX read are tested through `check()` with template CSVs, plain rows and small FileX text fixtures built in `tmp_path`, modeled on the real sample experiment. Covered: each check above with a failing and a passing case, several problems reported together, station and coverage mismatch, four- and eight-character station codes, a treatment number that does not exist, and multi-year weather.
- **`run()`** is tested with the same fake `subprocess.run` used for the existing run tests, which writes files into its working directory. It asserts the simulation folder contents (copied FileX, sibling soil file, generated weather file, run directory), that the original folder is untouched, the `-2` collision suffix, and that `DSSATCheckError` lists all problems and stops before any command runs.
- **Template function:** written, then read back through `check()`; it must pass.
- **Weather file:** unit tests compare the writer's output layout with the format of a real DSSAT sample file (header lines, date form, column widths, filename rule). One optional manual test, skipped unless enabled, runs a generated file through a real DSSAT on Windows or WSL and asserts the run succeeds. It also settles the end-of-weather rule and the sibling-files question.
- **DataFrame input:** goes through the same seam; the test is skipped when pandas is not installed.
- Prior art: `tests/test_runner.py` (fake DSSAT that writes files, `tmp_path`, patched executable lookup) and `tests/test_manual_integration.py` (opt-in real-DSSAT test).
- No network, compiler or real DSSAT in normal tests.

## Out of Scope

Soil and management inputs, reading or parsing FileX or output files beyond the narrow read, building a FileX from Python, unit converters, gap filling or any automatic repair, warnings (only errors in this phase), optional daily weather columns such as PAR, humidity or wind, hourly data, several weather stations, several treatments in one object, results parsing, plots, a pandas requirement, batch mode, timeouts.

## Further Notes

- Agreed slicing for the tickets, with blocking edges: (1) the template, the template function and the weather checks; (2) the narrow FileX read and the FileX-versus-weather checks (independent of 1, so it can run in parallel); (3) the weather file writer, proven with real DSSAT, blocked by 1; (4) the `Simulation` object with the simulation folder, blocked by 2 and 3; (5) DataFrame input, blocked by 1; (6) end-to-end check, README, version and wheel, blocked by all.
- Two facts to settle on real DSSAT before the tickets that depend on them are trusted: which sibling files besides `.SOL` DSSAT reads from the FileX folder, and what DSSAT does when weather ends before the crop matures.
- `AGENTS.md` and `PROJECT_SCOPE.md` currently forbid experiment classes and FileX authoring; both are updated with this spec, through a pull request.
- Real DSSAT weather files in the wild use extra columns and other conventions; this phase intentionally supports only the template.
