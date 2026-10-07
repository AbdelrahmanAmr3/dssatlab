# Friction: Your first simulation

No blocking lesson friction was found on the stock Gainesville case.
The notebook uses only the public dssatlab API and leaves the DSSAT inputs unchanged.

## 1. Showing a run result exposes an absolute path - non-blocking

- **What the student must do:** assign `dl.run()` to `result`, then print `result.run_dir.relative_to(HERE)` and make each output path relative to `HERE`.
- **Why it is awkward:** displaying the run result directly includes an absolute machine path, and the guide's output-list example prints absolute paths too.
- **Suggested change:** offer a public run-result display helper accepting a base directory and update teaching examples to show relative paths.
- **Classification:** **non-blocking**; ordinary `pathlib` operations provide the required relative display.

## 2. Growth plots need labels with units and readable dates - non-blocking

- **What the student must do:** add the LAID or CWAD unit to the returned matplotlib Axes and call `ax.figure.autofmt_xdate()` before showing each plot.
- **Why it is awkward:** the default y-axis is only a DSSAT variable code, and the default date labels overlapped at the notebook's default figure size.
- **Suggested change:** label known variables with their meanings and native units, and format date labels by default.
- **Classification:** **non-blocking**; the returned public matplotlib Axes supports both adjustments.

## 3. A successful run leaves stock-data warnings in a file - non-blocking

- **What the student must do:** find `WARNING.OUT` in the listed output files to learn about warnings despite a zero DSSAT exit status.
- **Why it is awkward:** this case reports zero saturated hydraulic conductivity treated as missing, a soil photosynthesis factor of 0.92, and solar radiation of 0.80 MJ/m2/day on day 98 of 1982; `run()` returns successfully without surfacing these messages.
- **Suggested change:** expose a public warning summary on the run result and make successful runs with warnings visible in teaching examples.
- **Classification:** **non-blocking**; the stock case produces complete yield, dates and growth output, and no source data was changed.

## 4. Saving discovery config in a restricted environment - non-blocking

- **What the student must do:** use a writable application-data location if running Python in an environment that forbids writes to the user profile.
- **Why it is awkward:** the first validation attempt failed in the exact setup cell because `connect()` tried to rewrite the existing saved config; discovery had already found a working DSSAT executable.
- **Suggested change:** avoid rewriting an unchanged saved executable, or report an actionable DSSAT error when saving config is forbidden.
- **Classification:** **non-blocking** for the lesson; this was a validation-environment restriction, resolved by setting process-local `LOCALAPPDATA` to a temporary writable directory without changing the notebook, DSSAT files or package code.

## Validation

The stock executable identifies itself as DSSAT 4.8.5.017 pre-release.
Treatment 1 (RAINFED LOW NITROGEN) and treatment 2 (RAINFED HIGH NITROGEN) both gave HWAM 2,293 kg/ha; their difference was 0 kg/ha.
Treatment 1's ADAT was 1982-05-13 and MDAT was 1982-07-04.

Execution uses this worktree's `src` through process-local `PYTHONPATH`, because the existing editable install points at the main checkout.
The two final consecutive `python course/execute.py 01_first_simulation` runs printed `01_first_simulation: ok`.
The required static course check passed all 13 tests.
Automatic approval review rejected temporary cleanup as "blocked by policy", including a narrower attempt to remove individual entries without recursive deletion; `.pytest_tmp` and the lesson's `.validation` directory remain.
Git staging and committing were attempted, but the shared worktree metadata is read-only: Git could not create `index.lock`, so the lesson files remain uncommitted.
