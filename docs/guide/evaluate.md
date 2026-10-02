# Evaluate against observed data

Compare measured values with Summary and Plant growth using DSSAT's column names
and units. Start with a CSV template, then replace its example measurements:

```python
import dssatlab as dl

dl.write_observed_template("observed.csv")
# Fill observed.csv before evaluating.
evaluation = dl.evaluate(result, "observed.csv")
print(evaluation)
print(evaluation.pairs)
print(evaluation.statistics)
```

`evaluate(results, observed)` accepts one `RunResult` or the dictionary returned by
`run_treatments()`. For one run, use scenario `base` and the treatment number from
its Summary (`TRNO`). For a dictionary, use its `(scenario, treatment)` keys.
`observed` can also be a pandas DataFrame or a list of dictionaries.

Leave `date` empty for Summary measurements such as `HWAM` or `ADAT`. Supply
`yyyy-mm-dd` for Plant growth measurements such as `LAID` or `CWAD`.
Summary date variables also require `yyyy-mm-dd` strings, including in DataFrames
and dictionaries; DSSAT date codes are not accepted as input. Leave unmeasured
cells blank. Combine measurements for the same scenario, treatment and date in
one row; duplicate keys are rejected. The `date` column can be omitted when all
rows contain Summary measurements.

The frozen `Evaluation` dataclass contains:

- `pairs`: a list of dictionaries with `scenario`, `treatment`, `date`, `variable`,
  `observed`, `simulated`, and `error`. Dates use `yyyyddd` integers, including
  observed and simulated Summary date values; Summary pairs have `date=None`.
  Error is simulated minus observed, in DSSAT units. For `ADAT`,
  `MDAT`, `SDAT`, `PDAT`, `EDAT`, and `HDAT`, error is elapsed calendar days.
- `statistics`: a dictionary keyed by variable, with `n`, `rmse`, `bias`, and
  Willmott's `d_index`. `bias` is mean simulated minus observed. Pairs are pooled
  across scenarios, treatments and dates.
  Variables with fewer than two pairs are omitted. Date statistics use calendar
  days, including across year boundaries.

`evaluation.to_dataframe()` converts the pairs using optional pandas, imported
only when needed. Evaluation itself needs no extra dependencies.

Use `plot_evaluation` for a scatter of simulated versus observed values with a
dashed 1:1 line. Install the optional plotting extra with
`pip install dssatlab[plot]`. Select one variable to keep different units separate;
you can omit `variable` when the Evaluation contains exactly one variable. The
function returns a matplotlib Axes. Date variables use calendar dates on both
axes; their errors and statistics are in days.

```python
ax = dl.plot_evaluation(evaluation, variable="HWAM")
```

`evaluate()` checks observed data and matches it to the outputs. Bad observed
values, duplicate keys, missing results, missing or ambiguous simulated rows,
absent variables, and missing simulated values (`-99`) are collected in one
`DSSATCheckError` before errors are calculated. An unreadable source, an empty
table, or missing key headers stops loading before matching can begin. Unknown
columns are reported once per name, with the closest valid names and the lists
of Summary and Plant growth columns. An observed `-99` is also a problem; leave
unmeasured cells blank instead.

No pair is silently dropped. Results without observations are fine. Loading and
checking observed data are internal to
`evaluate()`; there are no public `load_observed()` or `check_observed()` functions.

## Use DSSAT's own measured data

Read a shipped experiment's FileA (end-of-season measurements) and FileT
(measurements by date) directly. Keep both beside their FileX in the DSSAT Maize
folder, or copy all three into your own folder before running:

```python
from pathlib import Path
import dssatlab as dl

maize = Path("C:/DSSAT48/Maize")  # use your own DSSAT Maize folder
result = dl.run(maize / "UFGA8201.MZX")  # all six treatments
observed_a = dl.read_dssat_observed(maize / "UFGA8201.MZA")
observed_t = dl.read_dssat_observed(maize / "UFGA8201.MZT")
evaluation = dl.evaluate(result, observed_a)  # end-of-season values
print(evaluation.pairs)
print(evaluation.statistics)
ax = dl.plot_observed(result, observed_t, "LAID")
```

`read_dssat_observed()` accepts any header line whose stripped text starts with
`*EXP`. The named `(A)` or `(T)` identifies the kind, with any spacing: for example
`*EXP. DATA (A):`, `*EXP.DATA(A):` and `*EXPT.DATA  (A):` (and the T forms).
If the header names no kind, the extension's last letter supplies it
(case-insensitive): `.SBA` means FileA and `.SBT` means FileT. A generic `.txt`
extension does not identify FileT. At least one `*EXP` header is required;
repeated headers must all name or imply the same kind. Headers of different
kinds, or a header with no kind and no FileA/FileT extension, are check problems.
Rows use scenario `base`, an integer `treatment` from `TRNO`, and `date=None`
for FileA or an ISO `yyyy-mm-dd` date for FileT. Summary date measurements such
as `ADAT` and `MDAT` also become ISO strings. Tables merge by treatment and date.
If you ran only selected treatments, select their observed rows before comparing;
observations for a treatment without a result are a check problem.

Only supported Summary measurement columns are read from FileA (`HWAM`, `CWAM`,
`ADAT`, `MDAT`, etc.), and supported Plant growth measurement columns from FileT
(`LAID`, `CWAD`, etc.). Metadata and unsupported measurements such as `GN%M`,
`VN%D`, and `SW1D` are not read. `-99` cells and rows with no measurement are
omitted. Names and units stay as DSSAT gives them. Problems, including conflicting
measurements, are collected in one `DSSATCheckError` with paths and line numbers.

Short dates are resolved from the treatment's simulation start (`SDATE`), so the
matching FileX must sit beside the FileA/FileT (for example `UFGA8201.MZX`).
A bare day of year uses the start year, or the next year when it precedes the
start day. A five-digit `yyddd` uses the start date's century, advancing a century
if it falls before January 1 of the start year (DSSAT itself anchors on the first
weather date, which dssatlab does not read here). Seven-digit `yyyyddd` dates need no FileX.

`plot_observed()` returns a matplotlib Axes, using the optional `plot` extra.
It draws one Plant growth line per observed scenario and treatment, with measured
points in the same colour. Points outside the simulated season are still drawn;
`evaluate()` requires a simulated row on every observed date, so shipped FileT
files usually hold dates outside the season (before planting or after maturity)
that it reports as problems; plot them, or keep only the dates inside the season
before evaluating. For Summary variables, use `plot_evaluation()` instead.

### Compare with the DSSAT evaluation

DSSATLab computes `evaluation` from Summary and Plant growth. The **DSSAT
evaluation** is DSSAT's own `Evaluate.OUT`; these two calls read the same rows:

```python
dssat_rows = dl.read_dssat_evaluation(result.run_dir)
dssat_rows = result.dssat_evaluation()

# Compare grain yield for each treatment, side by side (optional pandas).
pairs = dl.to_dataframe([p for p in evaluation.pairs if p["variable"] == "HWAM"])
dssat_yield = dl.to_dataframe(dssat_rows)[["TN", "HWAMS", "HWAMM"]]
print(pairs.merge(dssat_yield, left_on="treatment", right_on="TN"))
```

`HWAMS` and `HWAMM` are DSSAT's simulated and measured yield; compare them with
`simulated` and `observed` in the Evaluation pairs. The reader retains DSSAT's
column names, numbers and text, with `-99` as `None`. Date columns in
`Evaluate.OUT` stay as days after planting, not calendar dates. A missing, empty
or malformed `Evaluate.OUT` raises `DSSATOutputError`.

DSSAT fills the measured columns only in some runs. On DSSAT 4.8.5, CERES-Maize
run with `run()` (all treatments) and the FileA beside the FileX fills them. A
`Simulation` runs one treatment (DSSAT run mode C), where DSSAT does not find the
FileA, and CROPSIM wheat (`CSCER048`) does not fill them even with `run()`; their
measured columns come back as `None`. There, `evaluate(results, read_dssat_observed(path))`
is the comparison to use. Column names follow the crop model: CERES-Maize writes
`TN`, CROPSIM writes `TRNO`. DSSATLab
writes no FileA/FileT; [ADR 0008](../adr/0008-read-filea-filet-and-evaluate-out.md)
supersedes the reading restriction in ADR 0007.
