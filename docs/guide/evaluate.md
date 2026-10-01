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

No pair is silently dropped. Results without observations are fine. DSSAT's
`Evaluate.OUT` is not read. Loading and checking observed data are internal to
`evaluate()`; there are no public `load_observed()` or `check_observed()` functions.
