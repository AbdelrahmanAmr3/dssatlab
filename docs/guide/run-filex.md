# Run a FileX

Use `run()` when you already have a FileX and the files DSSAT needs to run it.
[Find or install a DSSAT executable](install.md) first. Paths below are relative
to the notebook's current directory; replace them with your own FileX path.

## Run all treatments or one treatment

Omit `treatment` to run all treatments in the FileX:

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
the extension**, following DSSAT's 8.3 style, such as `UFGA8201.MZX`. This limit
applies to the filename, not the full path. A missing FileX or an overlong
filename raises `DSSATRunError` before DSSAT starts.

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
