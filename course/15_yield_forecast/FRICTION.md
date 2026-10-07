# Friction

No blocking dssatlab friction was found. The lesson uses only public API, unchanged stock inputs and `controls.forecast_date` to change the simulation copy.

## 1. Historical weather years must be attached by the student — non-blocking

- **Student action:** Read the forecast Summary, then label its rows with `range(2020 - 36, 2020)` using the start year, NYERS and documented row order.
- **Why awkward:** The result table shows dates for the forecast crop in 2020 but has no explicit historical weather year column. A student could mistake these 36 members for consecutive future seasons or use the wrong historical-year labels.
- **Suggested change:** Provide a public forecast-result helper that includes the forecast date and historical weather year with each Summary row, and demonstrate it in the forecast guide.

## 2. Stock forecast weather coverage is checked only during the run — non-blocking

- **Student action:** Ensure that a stock `.WTH` contains the required history and current-season observations, then rely on `Simulation.run()` to catch missing-weather warnings.
- **Why awkward:** The forecast guide states that stock `.WTH` coverage is not checked before the run, unlike weather-template rows. An empty `check()` result alone does not establish historical coverage; the first/last dates displayed in this lesson do not prove there are no gaps.
- **Suggested change:** Apply the same conservative forecast-coverage check to stock weather rows without rewriting the file, while retaining the missing-weather warning scan after execution.

## Case and validation

The case is stock `YieldForecast/CAPE2002.FCX`, wheat cultivar North KAZAK1 (`KZ0001`) near Petropavl, Kazakhstan. It uses stock `Weather/CAPE8437.WTH` (84001–20229) and unchanged `Soil/KZ.SOL`, selecting profile `KZ01826030`. No additional input files or genotype files are bundled.

The parent course spec describes a South African case, but this ticket's FileX and weather header explicitly identify Kazakhstan. The notebook follows these visible stock inputs and uses no unseen agronomic references.

Treatment 1 is used throughout, retaining automatic planting and irrigation, water and nitrogen simulation, initial conditions and all other stock management. Only the forecast date is changed through public controls; `years=36` retains the stock historical ensemble, 1984–2019. DSSAT gives the same planting date, 14 May 2020, for all members at all three dates.

The June 1 forecast has 36 valid HWAM values: mean 1076.9 kg/ha, minimum 669, P10 821.5, median 1044, P90 1332, maximum 1576, and P90–P10 width 510.5 kg/ha. The August 1 forecast has 36 valid values: mean 1315.7, minimum 1281, P10 1294, median 1322, P90 1322, maximum 1322, and width 28.0 kg/ha. The July 1 exercise has mean 1227.7 kg/ha, P10 1131.5, P90 1339.5 and width 208.0 kg/ha.

The August forecast's repeated 1322 kg/ha values are shown plainly. Longer shared current-season weather and the displayed mid-August maturity dates are consistent with little remaining weather influence; the lesson does not assert a physiological cause from yield alone. Percentiles are computed in pandas from the equally weighted historical-weather members and describe that ensemble, not all model or input uncertainty.

Validation uses process-local `PYTHONPATH` pointing to this worktree's `src` because the editable install otherwise resolves to another tree. `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` use system temporary directories outside the worktree so the unchanged setup cell and Jupyter can write in this restricted environment. No repository files outside this lesson are changed.

Both consecutive final executions of `python course/execute.py 15_yield_forecast` print `15_yield_forecast: ok` against real DSSAT, with no missing-weather warnings. The exercise also passes in a fresh kernel using only LESSON, the exact setup cell, the tools cell and the exercise cell; all 36 yields are valid and reproduce the July 1 mean and spread. All 15 tests in `tests/test_course.py` pass using a system temporary `--basetemp` outside the worktree and `-p no:cacheprovider`.

The three bundled inputs are byte-identical to the stock DSSAT files and readable as UTF-8. The notebook passed checks for exact setup-cell text, execution counts, error-free outputs, relative paths and corrupted punctuation, and the inline plot was visually inspected. A read-only review found no critical or important issues; the friction-file punctuation it flagged has been repaired.
