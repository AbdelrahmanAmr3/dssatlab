# Run a FileX

Use `run()` when you already have a FileX and the files DSSAT needs to run it.
[Find or install a DSSAT executable](install.md) first. Paths below are relative
to the notebook's current directory; replace them with your own FileX path.

## Run all treatments or one treatment

For a non-sequence, non-forecast FileX, omit `treatment` to run all treatments:

```python
import dssatlab as dl

result = dl.run("UFGA8201.MZX")
print(result.run_dir)
```

Pass a treatment number to select one treatment:

```python
import dssatlab as dl

result = dl.run("UFGA8201.MZX", treatment=2)
```

Treatment numbers are read as DSSAT reads the TREATMENTS N column: columns 1-3,
or columns 1-2 in a sequence FileX (R uses column 4, or columns 3-4 respectively).
For example, a sensitivity-tool row `  11 0 0` names treatment 1, matching Summary
`TRNO`, rather than treatment 11. A FileX uses the sequence columns when some
treatment number has two or more rows when read with those columns; the filename
extension does not decide this. See [ADR 0018](../adr/0018-treatment-rows-read-with-dssats-fixed-columns.md).

The FileX must exist. Its filename must contain **at most 12 characters including
the extension**, and **exactly 12 for sequence and forecast runs**, following
DSSAT's 8.3 style, such as `UFGA8201.MZX`. This limit applies to the filename,
not the full path. A missing FileX or an invalid filename length raises
`DSSATRunError` before DSSAT starts.

Without `executable`, `run()` uses `connect(interactive=False)`: it discovers and
remembers a DSSAT executable but never prompts to install one. To choose a DSSAT
executable for this run, pass its path explicitly:

```python
import dssatlab as dl

result = dl.run(
    "UFGA8201.MZX",
    treatment=2,
    executable=r"C:\DSSAT48\DSCSM048.EXE",
)
```

Replace the example path with your DSSAT executable. An explicit `executable`
is checked without changing saved config. A directory directly containing the
DSSAT executable is also accepted.

## Run modes, sequences and forecasts

`run()` picks DSSAT's run mode from the FileX; there is no mode argument:

| FileX and selection | DSSAT run mode |
|---|---|
| `.FCX` extension, in any case | Y: forecast, all treatments or the selected treatment |
| Otherwise, a selected treatment number has two or more TREATMENTS rows | Q: sequence, whatever the extension |
| Otherwise, `treatment=None` (the default) | A: all treatments |
| Otherwise, `treatment=n` | C: one treatment |

A sequence carries soil water and nitrogen from one rotation component to the
next. If its FileX has only one treatment number, you can omit `treatment`:

```python
result = dl.run("MSKB8902.SQX")
print(len(result.summary()))
```

If a FileX contains a sequence and more than one treatment number, pass
`treatment=n` for each treatment separately. DSSAT's Q mode runs one continuous
batch and would carry one treatment into the next. See [sequence analysis](sequence.md).

A forecast FileX runs in Y mode, using observed weather up to its forecast date
(FODAT), then producing results for historical weather years:

```python
result = dl.run("UFAC2301.FCX")
```

A `Simulation` also runs a copied `.FCX` with your weather data and an optional
`controls.forecast_date`; see [forecast with your weather data](simulation.md#forecast-with-your-weather-data).
Forecasts through `run_treatments()` and named scenarios are not promised or tested.

For Q and Y, `run()` writes `DSSBatch.v48` in the FileX folder and invokes
`<executable> Q DSSBatch.v48` or `<executable> Y DSSBatch.v48`. Q has one batch
row per rotation component; Y has one per selected treatment. A/C use no batch
file. See [ADR 0022](../adr/0022-run-picks-dssats-run-mode-from-the-filex.md).

### Guards before DSSAT starts

Each guard raises `DSSATRunError` before running. The messages below use example
filenames and treatment numbers; `<folder>` stands for the resolved FileX folder.
An existing `DSSBatch.v48` is refused for Q/Y and is never overwritten:

```text
Cannot run FileX MSKB8902.SQX in sequence mode (Q): <folder> already holds DSSBatch.v48, which run() writes. Nothing was run. Move or rename it, or use Simulation, which runs in its own folder.
```

For Y, the message says `forecast mode (Y)` in place of `sequence mode (Q)`.
A Simulation stages its forecast in a fresh simulation folder. A/C ignore an existing
batch file. An 11-character name is refused for Q/Y:

```text
Cannot run FileX 'MSKB892.SQX': its filename has 11 characters; DSSAT's sequence mode (Q) accepts exactly 12. Rename the FileX to exactly 12 characters, including the extension, using DSSAT's 8.3 style.
Cannot run FileX 'UFAC231.FCX': its filename has 11 characters; DSSAT's forecast mode (Y) accepts exactly 12. Rename the FileX to exactly 12 characters, including the extension, using DSSAT's 8.3 style.
```

With `treatment=None`, a sequence FileX with treatment numbers 1, 2 and 3 is refused:

```text
Cannot run FileX ROTATE01.SQX in sequence mode (Q) without a treatment: it has treatments 1, 2, 3, and DSSAT runs one continuous batch, carrying each treatment into the next. Nothing was run. Pass run(filex, treatment=n) for each treatment.
```

The existing guards still apply first: the FileX must exist, names longer than
12 characters are refused, and CSV files DSSAT would delete must be moved or
renamed. Their messages are:

```text
Cannot run FileX <path>: it does not exist or is not a file. Pass the path to an existing FileX.
Cannot run FileX 'MSKB89021.SQX': its filename has 13 characters; DSSAT accepts at most 12. Rename the FileX to at most 12 characters, including the extension, using DSSAT's 8.3 style.
Cannot run FileX MSKB8902.SQX: DSSAT deletes files named like its own Output files from the FileX folder, and <folder> holds weather.csv. Nothing was run. Rename or move them (for example my_weather.csv), or use Simulation, which runs in its own folder.
```

### Checked on real DSSAT

On stock MSKB8902.SQX, `run()` in Q mode matched DSSAT's own run on all 55/55
Summary rows; UFAC2301 in Y mode matched on all 46/46 rows. The compared columns
were RUNNO, TRNO, HWAM, HDAT, CWAM and PRCM, identical in each case. An
11-character FileX name was refused before DSSAT ran. An existing `DSSBatch.v48`
was refused and left byte-identical.

## Where the files go

DSSAT runs in the FileX's own folder, where it can find the weather file and other
files beside the FileX. dssatlab creates a new **run directory** beside the FileX,
named `dssat_run_YYYY-MM-DD_HHMMSS`. A numeric suffix is added if that name already
exists.

After DSSAT exits, dssatlab moves newly created files and files whose modification
timestamps changed into the run directory. Unchanged files stay beside the FileX.
This also means that a pre-existing file overwritten by DSSAT is moved; its
previous contents are not restored. Use a copy of the FileX and supporting files
if you need to preserve that folder exactly.

The generated Q/Y `DSSBatch.v48` moves into the run directory with the outputs,
whether DSSAT succeeds or fails. If DSSAT cannot be started, dssatlab deletes
the generated batch file and the empty run directory.

## Inspect the run result

A successful call returns a `RunResult` with these fields:

| Field | Contents |
| --- | --- |
| `returncode` | DSSAT's integer exit status; a returned result has status `0` |
| `run_dir` | `pathlib.Path` to the run directory |
| `outputs` | List of `pathlib.Path` objects for files moved into the run directory, ordered by filename |
| `stdout_tail` | Last 20 lines of DSSAT's standard output, as a string |

After either run above, inspect the result in another notebook cell:

```python
print(result.returncode)
print(result.stdout_tail)
for path in result.outputs:
    print(path.name, path)
```

The result contains file paths, not parsed simulation values. A nonzero exit
status or a collected `ERROR.OUT` raises `DSSATRunError`. The message includes the
command, the last 20 lines of combined standard output and standard error, and
the first 20 lines of `ERROR.OUT` when collected. The run directory is kept for
inspection. If the DSSAT executable cannot start, the empty run directory is
removed instead.

`run()` does not inspect missing-weather warnings. When using your own weather
data, [create a Simulation](simulation.md) to apply the weather checks and detect
DSSAT's missing-weather warning after the run. See
[Troubleshooting](troubleshooting.md) for error messages and next steps.
