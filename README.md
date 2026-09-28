# dssatlab

`dssatlab` is intentionally starting small.

Version 0.1 has one job: make a DSSAT-CSM executable easy to locate, install, and reuse from Python on Windows, Linux, Jupyter, and Google Colab.

It is **not** yet a DSSAT experiment editor, FileX parser, plotting package, calibration system, or replacement for DSSATTools.

## Intended API

```python
import dssatlab as dl

dssat = dl.connect()
print(dssat)
```

Advanced/non-interactive use:

```python
dssat = dl.connect(executable="/opt/dssat/bin/dscsm048", interactive=False)
```

Inspection without side effects:

```python
info = dl.detect()
print(info)
```

Linux/Colab managed installation:

```python
dssat = dl.install()                 # latest stable DSSAT release
# or
dssat = dl.install("4.8.6.0")
```

## v0.1 behavior

### Windows

1. Use an explicit `executable=` or `path=` if supplied.
2. Reuse saved configuration if valid.
3. Check `DSSAT_HOME` if set.
4. Check the usual `C:\\DSSAT48` installation.
5. If still missing and interactive, ask the user for the DSSAT folder/executable.
6. Save a successful choice for future calls.

Windows v0.1 should **not** compile DSSAT automatically.

### Linux

1. Use an explicit executable/path if supplied.
2. Reuse saved configuration if valid.
3. Check `DSSAT_HOME` and `PATH`.
4. Reuse a previous dssatlab-managed build if present.
5. If missing and interactive, offer to install the latest stable DSSAT release.
6. Build with Git + CMake + a Fortran compiler and cache the resulting installation.

### Google Colab

Colab is treated as Linux plus a detected notebook environment. On a fresh runtime, `connect()` may offer to install DSSAT automatically. The installation should be cached for the current runtime and must not be rebuilt repeatedly within the same runtime.

## Upstream DSSAT

Official source repository:
https://github.com/DSSAT/dssat-csm-os

The upstream project uses CMake, recommends out-of-source builds, and places the compiled executable under the build `bin/` directory. This package should use the latest stable release by default, not the upstream development branch.

## Scope rule

If a proposed feature is not directly necessary to **detect, install, validate, remember, or connect to DSSAT**, it does not belong in v0.1.
