# Troubleshooting

Read the exception message first. `DSSATNotFoundError` concerns discovery,
`DSSATInstallError` concerns installation, `DSSATCheckError` lists problems found
before a Simulation runs, and `DSSATRunError` concerns a run. All inherit from
`DSSATError`.

Messages below are copied from the source. Braced fields stand for the values
inserted at runtime. Where only part of a message is shown, it is marked as an
excerpt.

## DSSAT was not found

`DSSATNotFoundError`:

```text
DSSAT was not found. Checked saved configuration, DSSAT_HOME, and PATH/platform defaults (including the managed cache on Linux). Pass connect(path="/path/to/dscsm048") or call install() on Linux.
```

Discovery found no valid DSSAT executable. Use `dl.detect()` to inspect the
environment, then `dl.connect(path=...)` with an existing DSSAT executable or its
containing directory. On Linux, `dl.install()` can build a managed install.
See the exact [discovery order](install.md#inspect-discovery).

For an explicit path, the message is:

```text
No valid DSSAT executable found at {str(path)!r}. Checked for a dscsm048 or DSCSM048.EXE file with execute permission on POSIX. Pass connect(path=...) with the executable file or the directory that contains it.
```

Check the spelling, filename, and execute permission. A directory search does
not descend into subdirectories; give the directory directly containing the
DSSAT executable.

## Installation is unavailable on this platform

`DSSATInstallError`:

```text
DSSAT installation is only supported on Linux/Colab in v0.1. Pass connect(path=...) to use an existing installation.
```

The message still says `v0.1` in the current source. `install()` requires Linux.
On Windows or another platform, point `connect(path=...)` at an existing DSSAT
executable.

## Build tools are missing

`DSSATInstallError`:

```text
Missing required tools on PATH: {', '.join(missing)}. Install the missing tools and retry. On Debian/Ubuntu, ask your administrator to use: apt install git cmake gfortran.
```

A build needs `git`, `cmake`, and `gfortran` on `PATH`. Install the listed tools
using your system's package manager, make them available to the notebook's
Python process, and retry `dl.install()`. dssatlab does not install these tools.

If a build command runs but fails, its message begins with this excerpt:

```text
{step} failed with exit code {result.returncode}. Command: {shlex.join(command)}
```

The rest includes the last 20 lines of standard output and standard error. Read
those lines to identify whether Git clone, CMake configure, build, or install
failed. Correct the reported network, release tag, tool, or permission problem.
If a fresh install location is needed, set `XDG_CACHE_HOME` to a different short,
writable directory before retrying.

## The install prefix is too long

`DSSATInstallError`:

```text
Cannot install DSSAT: prefix {prefix} is {len(str(prefix))} characters long; the limit is {MAX_PREFIX_LENGTH}. Set the XDG_CACHE_HOME environment variable to a shorter folder (for example ~/dl) and try again.
```

`MAX_PREFIX_LENGTH` is `51`. The limit includes the full resolved path, the
`dssatlab` directory, and the release version. Use the shorter cache example in
[Install and connect](install.md#install-on-linux-or-colab), then retry. Expanding
`Path.home()` in Python avoids leaving a literal `~` in the environment variable.

## The FileX is missing or its name is too long

`DSSATRunError` from `dl.run()`:

```text
Cannot run FileX {filex}: it does not exist or is not a file. Pass the path to an existing FileX.
```

Check the path relative to the notebook's current directory, or pass an absolute
path to the FileX.

```text
Cannot run FileX {filex.name!r}: its filename has {len(filex.name)} characters; DSSAT accepts at most 12. Rename the FileX to at most 12 characters, including the extension, using DSSAT's 8.3 style.
```

Rename the FileX to a short name such as `UFGA8201.MZX` and update the path in
your code. A Simulation reports the filename limit through its checks instead.

## The FileX folder is not writable

`DSSATRunError`:

```text
Cannot create {label} {folder}: the FileX folder {parent} is not writable ({error}). Move the FileX somewhere writable and try again.
```

The label identifies either the run directory or the simulation folder.
Move or copy the FileX and its supporting files to a folder where your Python
process can create files and directories, then use the new FileX path.

## The weather template already exists

`DSSATError` from `write_weather_template()`:

```text
Weather template path {path} already exists. Choose another path.
```

The function preserves existing data. Edit that weather template, or call
`write_weather_template()` with a new filename.

## Simulation checks found problems

`DSSATCheckError` starts with this excerpt:

```text
Simulation checks found {len(self.problems)} problems:
```

Every reported problem follows on its own line. Inspect `sim.check()` or the
exception's `problems` list, correct the data or FileX, and repeat the checks.
No simulation folder or DSSAT files have been written by this failed call.

Examples of check messages include:

```text
Weather data has no daily rows. Supply at least one row following the weather template.
```

A header alone is insufficient. Supply your daily rows using the
[weather template columns](simulation.md#prepare-the-weather-template).

```text
FileX treatment number is invalid. Supply an int or digit string.
```

Pass a treatment number such as `treatment=1`, referring to a treatment that
exists in the FileX. A Simulation requires one treatment.

```text
FileX WSTA {values['WSTA']!r} expects station {expected!r}, but the weather template has station {station!r}. Make the station codes exactly equal; filenames are case-sensitive on Linux.
```

Check that your weather data belongs to the selected field. Its `station` must
equal the first four characters of that treatment's `WSTA`, including case.
Replace the weather template's example `DEMO` station with the correct code.

```text
FileX start year {start[:2]} day {start[2:]} is not covered by weather data ({min(days)} to {max(days)}). Supply weather for the simulation's start date.
```

For `START S`, include the date identified by `SDATE`, as well as the days needed
after it. Fill gaps with your weather data; dssatlab does not fill them for you.

## DSSAT could not start or reported a failed run

`DSSATRunError` may begin with this excerpt:

```text
Could not start the DSSAT executable: {shlex.join(command)}
```

Read the operating system error that follows. Check the DSSAT executable path
and execute permission. The empty run directory is removed in this case.

If DSSAT started, the failure message begins with this excerpt:

```text
DSSAT run failed (return code {completed.returncode}).
```

This means DSSAT exited with a nonzero status or wrote an `ERROR.OUT` that was
collected, even if the status was `0`. Read the command, console tail, and any
`ERROR.OUT` excerpt in the exception. Open `ERROR.OUT` and `WARNING.OUT` in the
reported run directory when present, correct the reported problem, and retry.
The run directory is kept.

## Weather ran out during a Simulation

`DSSATRunError`:

```text
DSSAT reported no weather for year {year}, day of year {day} ({calendar_date}). DSSAT exits 0 in this case and gives -99 for anything it could not reach.
Run directory (kept): {result.run_dir}
Extend the weather data through that date and the days the crop needs, then run again.
```

The weather checks can pass without covering the full crop period.
`Simulation.run()` detects DSSAT's missing-weather warning in `WARNING.OUT` after
the run, even when DSSAT reports status `0`. Extend the weather data through the
reported date and the remaining simulation period, then rerun the Simulation.
The message names the first missing date encountered in the warning file.
