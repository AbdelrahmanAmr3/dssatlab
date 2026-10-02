# DSSATLab v0.2 Specification: run one FileX

`SPEC.md` (v0.1) stays frozen as the record of the discovery/connection release.
Vocabulary is in `CONTEXT.md`.

## Goal

Give a user a Python call that runs DSSAT on one existing FileX and tells them where
the outputs are. Nothing else.

## Public API

One new function, in addition to `detect()`, `connect()`, `install()`:

```python
result = dssatlab.run("KSAS8101.MZX", treatment=None, executable=None)
```

- `filex`: path to an existing FileX. Missing file -> `DSSATRunError`.
- `treatment=None`: run every treatment (DSSAT mode `A`).
  An int runs that one treatment (mode `C`).
- `executable=None`: use `connect(interactive=False)`. A given path goes through the same
  validation as `connect(path=...)`.
- No `model` argument. DSSAT picks the model from the crop in the FileX.

Returns a frozen dataclass:

```python
RunResult(returncode: int, run_dir: Path, outputs: list[Path], stdout_tail: str)
```

## Commands

Explicit `subprocess.run` with an argument list, `cwd=<FileX directory>`, the FileX given
as its **bare filename**, and `stdin` closed:

```text
<executable> A <filename>            # all treatments
<executable> C <filename> <n>        # one treatment
```

Verified by a prototype on Windows with DSSAT 4.8.5.017 (`C:\DSSAT48`), and against
`CSM.for` at `v4.8.6.0` for the argument order:

- DSSAT cuts the FileX argument to **12 characters** and resolves it against its working
  directory. A full path fails (even from the FileX folder), and a bare filename fails from
  any other folder. So the working directory must be the FileX directory.
- The FileX filename must therefore be at most 12 characters (normal DSSAT 8.3 names
  such as `UFGA8201.MZX`). A longer name raises `DSSATRunError` before running.
- With that layout DSSAT finds weather and soil files that sit beside the FileX (tested
  with a station and soil id that exist nowhere in the DSSAT install). Mode `C` runs one
  treatment the same way.
- On a fatal input error DSSAT prints "Please press < ENTER > key to continue" and waits.
  `stdin` must be closed (`subprocess.DEVNULL`) or a failed run hangs.
- On the error tested (FileX not found) DSSAT exited **99** and wrote `ERROR.OUT`.

Batch mode (`B`) was tried and not resolved; it is out of scope.

## Run directory

DSSAT writes its files into its working directory, which must be the FileX directory. So a
run works like this:

1. Create `<FileX directory>/dssat_run_<YYYY-MM-DD_HHMMSS>/` (append `-2`, `-3`, ... if the
   name exists; never reuse or overwrite).
2. Record the start time and run DSSAT with `cwd=<FileX directory>`.
3. Afterwards, move every file in the FileX directory that was created or modified since
   the run started into the run directory. This includes `ERROR.OUT`, `WARNING.OUT` and
   `LUN.LST`. Do this on failure too, so the run directory holds the evidence.

The FileX and its weather and soil files are never copied, moved or modified. If the run
directory cannot be created (read-only location), raise `DSSATRunError` saying so.

Known limits, documented not solved: two runs at the same time in one FileX directory
would mix their files, and a file the user edits in that directory during a run would be
moved.

## Failure handling

- FileX missing, or its filename longer than 12 characters -> `DSSATRunError`.
- Executable cannot start -> `DSSATRunError` with the command.
- Non-zero exit -> `DSSATRunError` with the command and the last 20 lines of stdout/stderr.
- If `ERROR.OUT` exists in the run directory, raise `DSSATRunError` with its first lines,
  even when the return code is 0. The run directory is kept so the user can inspect it.
- No timeout in v0.2.

## Outputs

`RunResult.outputs` is the files moved into the run directory, as `Path`s sorted by name.

## Data directory (changes to `install()`)

A managed install must be runnable, not just built. From upstream `CMakeLists.txt`,
`DSSATPRO.L48` is generated with paths rooted at `CMAKE_INSTALL_PREFIX`, and `Data/`
is installed there. So the build becomes:

```text
git clone --depth 1 --branch <tag> <repo> <source>
cmake -S <source> -B <build> -DCMAKE_BUILD_TYPE=RELEASE -DCMAKE_INSTALL_PREFIX=<prefix>
cmake --build <build> --parallel
cmake --install <build>
```

with `<prefix>` = `<cache>/dssatlab/<version>`, where `<cache>` is `$XDG_CACHE_HOME` or
`~/.cache`, and `<source>` and `<build>` under `<cache>/dssatlab/work/<version>/`. The
executable is then `<prefix>/dscsm048`. `manifest.json` sits in the prefix and records the
prefix. `dssat-csm-data` is not fetched: it holds sample experiments, weather and soil,
which the user's FileX supplies itself.

**Prefix length limit (verified on a real build).** DSSAT cannot read its own
`DSSATPRO.L48` when the install prefix is longer than **51 characters**: `run()` fails with a
Fortran "Substring out of bounds" error (exit 2) or exit 99. Tested on `v4.8.6.0`
(aarch64): 40, 50 and 51 characters work; 52 and longer fail. That is why the prefix is
short and `source/` and `build/` live elsewhere: `~/.cache/dssatlab/installs/<v>/dssat`
would fail for any home directory longer than 12 characters, such as `/home/abdosaleh`.
Before building, if the prefix is longer than 51 characters, raise `DSSATInstallError`
saying the length, the limit, and to set `XDG_CACHE_HOME` to a shorter folder. Cache
entries from v0.1 (`<cache>/dssatlab/installs/...`) are ignored; they could not run
anyway.

## Windows

A normal `C:\DSSAT48` install already has its data directory. `run()` uses the same
command and needs no extra setup.

## Out of scope

Parsing FileX or any `.OUT` file, building FileX from Python, batch (`B`) mode,
model selection, timeouts, parallel runs, cleaning old run directories, DataFrames,
plots.

## Tests

Mock `subprocess.run`; no real DSSAT. Use `tmp_path` and `monkeypatch`.
- mode `A` and mode `C` command construction: bare filename, `cwd` is the FileX directory,
  stdin closed
- run directory is created beside the FileX and named by the date
- files the fake run creates or modifies in the FileX directory are moved into the run
  directory; untouched files (the FileX, weather, soil) stay put
- files are moved into the run directory on failure too
- missing FileX, a filename over 12 characters, unwritable directory, non-zero exit each
  raise `DSSATRunError`
- `outputs` lists the moved files, sorted
- exit 0 with an `ERROR.OUT` present raises `DSSATRunError`
- a second run in the same second gets a `-2` directory
- `run()` uses `connect(interactive=False)` when no executable is given
- managed build issues the four commands including the install prefix
- a prefix longer than 51 characters raises `DSSATInstallError` before any build command
- v0.1 cache entries under the old `installs/` folder are ignored

One optional manual test runs a sample FileX on a real build.

## Definition of done

```python
import dssatlab as dl
dl.install()                       # Linux/Colab, once
result = dl.run("MyExperiment.MZX")
print(result.run_dir, result.outputs)
```

produces a dated folder beside the FileX containing DSSAT's output files, and leaves the
FileX folder as it was.

## Verified on Linux

Built `v4.8.6.0` on WSL (Ubuntu 26.04, aarch64) with `-DCMAKE_INSTALL_PREFIX=<prefix>` and
`cmake --install`:

- The executable to use is **`<prefix>/dscsm048`** (top level of the prefix, not `bin/`).
  `<prefix>` also holds `DSSATPRO.L48` (every path rooted at the prefix), `Genotype/`,
  `Pest/`, `StandardData/` and the `*.CDE` files.
- The build-tree executable `build/bin/dscsm048` **does not work**: it exits 99 because it
  looks for `MODEL.ERR` next to itself. So a v0.1 managed install (which records the
  build-tree executable) cannot run, and the manifest must record `<prefix>/dscsm048`.
- Bare filename with `cwd` = FileX directory works with the installed executable: modes `A`
  and `C` exit 0 and write the usual output files, using weather and soil files beside the
  FileX.
- The filename is case-sensitive on Linux (`zzga8201.mzx` is "file not found").
- Search for the executable to record: `<prefix>/dscsm048`, not a recursive search of the
  build tree.
