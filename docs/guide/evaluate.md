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
Summary date variables also require `yyyy-mm-dd`. Leave unmeasured cells blank.

The frozen `Evaluation` dataclass contains:

- `pairs`: a list of dictionaries with `scenario`, `treatment`, `date`, `variable`,
  `observed`, `simulated`, and `error`. Dates use `YYYYDDD` integers; Summary pairs
  have `date=None`. Error is simulated minus observed, in DSSAT units. For `ADAT`,
  `MDAT`, `SDAT`, `PDAT`, `EDAT`, and `HDAT`, error is elapsed calendar days.
- `statistics`: a dictionary keyed by variable, with `n`, `rmse`, `bias`, and
  Willmott's `d_index`. Pairs are pooled across scenarios, treatments and dates.
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

Missing results, simulated rows, variables, or simulated values (`-99`) are
reported together in one `DSSATCheckError` before errors are calculated. No pair
is silently dropped. Results without observations are fine. DSSAT's
`Evaluate.OUT` is not read.
