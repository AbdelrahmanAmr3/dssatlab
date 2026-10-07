# Friction: Your own weather

No blocking friction was found. The lesson uses only public dssatlab API, unchanged stock DSSAT files, and a course-written weather CSV.

## 1. Check row numbers differ from the displayed table index - non-blocking

- **What the student must do:** Translate weather check row 2 into pandas index 0 to find the deliberately broken first data row.
- **Why it is awkward:** The check counts the CSV header as row 1, even for a DataFrame input, while the displayed table starts its index at 0. The message identifies temperatures but does not include the calendar date.
- **Suggested change:** Include the weather date in daily-row problems and make the CSV-style row numbering explicit for DataFrame inputs.
- **Classification:** **non-blocking**; the notebook explains the numbering and restores the measured maximum temperature using `.loc[0, "tmax"]`.

## 2. The example template does not show daily PAR - non-blocking

- **What the student must do:** Add the optional `par` column when mapping the stock station's daily PAR measurements into the template.
- **Why it is awkward:** `write_weather_template()` shows the required daily columns and optional station metadata but omits PAR. A student copying its headings alone would leave out a column present in this stock weather file.
- **Suggested change:** Offer an `include_par` option or an example template that visibly documents the optional daily PAR column and its units.
- **Classification:** **non-blocking**; the mapping table includes PAR in mol/m2 per day and the course-written CSV preserves every stock PAR value. The lesson does not claim that omitting PAR would change this case's yield.

## 3. Full-year and short-span statistics use two nested layouts - non-blocking

- **What the student must do:** Learn `["years"][0]["srad_mean"]` for the full-year table and `["variables"]["srad"]["mean"]` for a short-span summary.
- **Why it is awkward:** `summarize_weather()` exposes statistics in two different shapes: flat per-year names and nested per-variable statistics. Both layouts are returned for a full year and a short span; the return shape itself does not change with the date range, but students must learn two access patterns used in examples.
- **Suggested change:** Use the same variable layout for overall and per-year statistics, or document one consistent access pattern for single-span summaries.
- **Classification:** **non-blocking**; the lesson retains the annual table and drops the month exercise to make room for a model-based warming exercise.

## Validation

The inputs are stock `Maize/UFGA8201.MZX`, `Soil/SOIL.SOL` and `Weather/UFGA8201.WTH`, matching lesson 01 byte-for-byte, plus `station_weather.csv` written for the course.
The CSV maps all 365 days of 1982 and repeats the stock station metadata; all daily SRAD, TMAX, TMIN, RAIN and PAR values match the original file.
The soil profile is IBMZ910014 and treatment 1 grows McCurdy 84aa (`IB0035`) under the stock water, nitrogen and management settings.

The installed executable reports DSSAT 4.8.5.017 pre-release.
Stock and CSV weather both give HWAM 2,293 kg/ha, a difference of 0 kg/ha, matching lesson 01's stock result.
The annual summary covers 1982-01-01 through 1982-12-31: 365 days, mean solar radiation 14.65 MJ/m2/day, mean maximum/minimum temperatures 28.27/15.69 degrees C, rainfall 1,544.50 mm and mean PAR 29.66 mol/m2/day.

The intentionally broken first data row has tmax 14.6 below tmin 15.6 degrees C; `Simulation.run()` raises `DSSATCheckError` before DSSAT runs.
Restoring tmax to its measured 24.4 degrees C makes `sim.check(verbose=False)` return `[]`.
The self-contained exercise adds 2 degrees C to every daily tmax and tmin, runs treatment 1 with unchanged station weather and warmed weather, and compares HWAM and maturity dates.
Unchanged station weather gives HWAM 2,293 kg/ha and maturity 1982-07-04; warmed weather gives 1,718 kg/ha and maturity 1982-06-24, a yield change of -575 kg/ha and maturity 10 days earlier.
The stock management remains unchanged, including its one 13 mm irrigation.

The exercise also passed in a fresh kernel with only LESSON, SETUP_CELL and the tools cell before it.
Changing warming to 0 in that kernel gave HWAM 2,293 kg/ha and the same maturity date for both runs.
The two final consecutive `python course/execute.py 04_own_weather` executions both printed `04_own_weather: ok`.
`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all 15 tests; no pytest temp directories were created in the worktree.

Validation used process-local PYTHONPATH pointing to this worktree's `src`, because the existing editable install resolves to the main checkout.
Process-local LOCALAPPDATA, IPYTHONDIR and JUPYTER_RUNTIME_DIR point under system temp, with DSSAT_HOME selecting the stock installation; the required setup cell remains byte-identical to SETUP_CELL.
The inline plot was visually checked, and the notebook's source and textual outputs contain none of the encoding corruption patterns `??`, `m?` or ` ? `.

Both successful runs retain the stock warnings about zero soil saturated hydraulic conductivity, SLPF 0.92 and SRAD 0.80 MJ/m2/day on day 98 of 1982, also recorded by lesson 01; none is a missing-weather warning.
The optional NASA POWER cell requests Gainesville (29.63 N, 82.37 W) daily AG-community CSV data for 1982, then passes the downloaded file to `dl.import_nasa_power()`.
Network errors are caught without exposing exception paths; both executions printed exactly `NASA POWER skipped: no network`.
The online import branch was not exercised against the remote service because network access is blocked; all required cells run offline against the local installation.
