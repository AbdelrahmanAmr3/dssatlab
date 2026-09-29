# DSSATLab v0.1 Implementation Specification

## Goal

Implement the smallest understandable Python package that gives users a valid DSSAT-CSM executable connection on Windows and Linux, including fresh Google Colab runtimes.

## Public API

Only these three user-facing functions are required:

```python
info = dssatlab.detect()
connection = dssatlab.connect(...)
connection = dssatlab.install(...)
```

Do not add additional public abstractions unless they are essential.

## 1. `detect()`

`detect()` must have no side effects.

It should determine:
- OS (`windows`, `linux`, or other)
- machine architecture
- whether a usable DSSAT executable can already be found

It must not clone repositories, compile software, edit config, or prompt the user.

## 2. Executable validation

A candidate connection is valid only when:
- the executable exists and is a file
- it is executable on POSIX
- its filename is compatible with DSSAT 4.8 (`dscsm048`, `DSCSM048.EXE`, case-insensitive)
- a small version/probe command is used only if DSSAT supports one reliably

If a reliable version-only command cannot be confirmed, do not invent one. It is acceptable for v0.1 to infer version from a managed-install manifest or leave `version=None` for a manual installation.

Never run a crop simulation merely to validate a path.

## 3. Search order for `connect()`

Explicit choices always win:
1. `executable=`
2. `path=`
3. saved config
4. `DSSAT_HOME`
5. platform defaults
6. interactive fallback

### Windows defaults

At minimum inspect:
- `C:\\DSSAT48`
- `C:\\DSSAT48\\DSCSM048.EXE`

When `path=` is a directory, look for `DSCSM048.EXE` inside it.

If no installation is found and `interactive=True`, ask for a path using normal text input. Keep the prompt simple and notebook-safe.

If `interactive=False`, raise `DSSATNotFoundError` with a useful message.

### Linux defaults

At minimum inspect:
- executable `dscsm048` on `PATH`
- `DSSAT_HOME`
- dssatlab's managed-install cache

If missing and `interactive=True`, ask whether to install the latest stable release.

If `interactive=False`, raise `DSSATNotFoundError`.

## 4. Linux/Colab installation

Installation is supported only on Linux for v0.1.

### Stable release policy

`install()` defaults to `version="latest"`, where latest means the latest stable GitHub release/tag from:
https://github.com/DSSAT/dssat-csm-os

Do **not** use `develop` by default.

When a concrete version such as `4.8.6.0` is requested, build the corresponding stable tag (`v4.8.6.0`). After resolution, record the exact tag/version used.

### External tools

Target zero runtime Python dependencies. Use the standard library and these external tools:
- git
- cmake
- a Fortran compiler, normally `gfortran`

Check them with `shutil.which()` and give an actionable error if missing.

On a normal Linux machine, never execute `sudo` or a system package manager.

On Colab, v0.1 should still avoid silently changing the environment. If a build dependency is missing, report it clearly. Automatic `apt` installation is deferred.

### Build process

Use an out-of-source CMake build. Keep subprocess calls explicit and easy to inspect.

Conceptually:

```text
git clone --depth 1 --branch <tag> <repo> <source>
cmake -S <source> -B <build> -DCMAKE_BUILD_TYPE=RELEASE
cmake --build <build> --parallel
```

Upstream documents that the executable is produced under the build `bin/` directory. Verify the actual executable filename/path against the targeted stable release during implementation.

### Managed cache

Use one simple directory tree, e.g.:

```text
~/.cache/dssatlab/
  installs/
    4.8.6.0/
      source/
      build/
      manifest.json
```

On Windows, prefer `%LOCALAPPDATA%\\dssatlab` for project-owned state.

Do not invent a backend registry or plugin architecture.

`manifest.json` should contain only useful reproducibility/debug fields:
- DSSAT version/tag
- executable path
- optional Git commit
- platform

A valid cached install must be reused instead of rebuilt.

## 5. Configuration

Store one selected/default connection in `config.json` with a simple schema, e.g.:

```json
{
  "executable": "/path/to/dscsm048",
  "root": "/path/to/dssat",
  "version": "4.8.6.0",
  "source": "managed"
}
```

If config is corrupt or points to a missing executable, ignore it and continue discovery. Do not create migrations or schema-version infrastructure in v0.1.

## 6. Interaction rules

- Importing `dssatlab` must never prompt, download, compile, or mutate files.
- `detect()` must never prompt or mutate files.
- `connect()` prompts only when discovery fails and `interactive=True`.
- `install()` may perform network/build work because the user explicitly requested it.
- Prefer clear exceptions over custom UI frameworks.

## 7. Explicitly out of scope

Do not implement in v0.1:
- FileX/WTH/SOL parsing
- DSSAT experiment objects
- high-level simulation APIs
- output parsing
- pandas/numpy/matplotlib
- ipywidgets
- Docker
- WSL-specific layers
- SLURM/HPC orchestration
- databases
- remote services
- async code
- plugin systems
- dependency injection frameworks
- logging frameworks
- telemetry
- automatic updates
- GUI applications

## 8. Tests

Tests must not require network access, a real DSSAT installation, or a Fortran compiler, except for one optional/manual integration test.

Required unit tests:
- OS/Colab detection with monkeypatching
- explicit executable precedence
- directory path resolves executable
- saved config is reused
- invalid config is ignored
- `DSSAT_HOME` is respected
- Windows default path discovery
- Linux PATH discovery
- non-interactive missing DSSAT raises `DSSATNotFoundError`
- install dependency checks
- latest-release lookup mocked
- clone/build subprocess command construction mocked
- cached managed install is reused
- successful connection is saved

Use `pytest`, `tmp_path`, and `monkeypatch`. Avoid extra mocking libraries unless truly necessary.

## 9. Definition of done

### Windows

```python
import dssatlab as dl
x = dl.connect()
```

finds a normal `C:\\DSSAT48` installation or clearly asks for a path and remembers it.

### Linux with existing DSSAT

```python
x = dl.connect(executable="/path/to/dscsm048")
```

returns a validated `DSSATConnection` with no network access.

### Fresh Linux/Colab

```python
x = dl.install()
```

resolves a stable release, clones it, performs the CMake build, locates the resulting executable, writes a small manifest/config, and returns a connection. A second call reuses it.

### Packaging

These commands succeed:

```bash
python -m pytest
python -m build
python -m twine check dist/*
```

The built wheel installs in a clean environment and:

```python
import dssatlab
print(dssatlab.detect())
```

works with no runtime Python dependencies.
