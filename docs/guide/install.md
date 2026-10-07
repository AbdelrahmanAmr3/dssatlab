# Install and connect

Install dssatlab into the Python environment used by your notebook. It requires
Python 3.10 or newer and has no runtime Python dependencies.

```bash
python -m pip install dssatlab
```

The DSSAT executable is separate from the Python package. You can use an existing
DSSAT installation or build a managed install on Linux, including Google Colab.

## Inspect discovery

`detect()` reports what is available without prompting, installing anything, or
changing saved config. It does not run the DSSAT executable.

```python
import dssatlab as dl

environment = dl.detect()
print(environment["os_name"])
print(environment["architecture"])
print(environment["dssat_path"])
```

`os_name` is `"windows"`, `"linux"`, or `"other"`; `architecture` comes from the
platform. `dssat_path` is a `pathlib.Path`, or `None` when discovery finds nothing.

Discovery tries these locations in order, stopping at the first valid candidate:

1. The DSSAT executable in saved config.
2. `DSSAT_HOME`, which may name the DSSAT executable or its containing directory.
3. Platform defaults: `C:\DSSAT48` on Windows, or `dscsm048` on `PATH` on Linux.
4. On Linux only, managed installs under the cache root, newest version first
   (dotted numeric version segments are compared numerically).

On other platforms, discovery stops after saved config and `DSSAT_HOME`.
Directory searches inspect immediate files only. Accepted filenames are
`dscsm048` and `DSCSM048.EXE`, matched without regard to case. The file must exist
and, on POSIX systems, have execute permission. These checks do not prove that
DSSAT can run successfully.

## Choose and remember a DSSAT executable

`connect()` returns the path to the DSSAT executable and saves it for later use:

```python
import dssatlab as dl

dssat = dl.connect()
print(dssat)
```

If discovery finds nothing, the default `interactive=True` prompts for a path on
Windows or asks whether to install the latest stable DSSAT release on Linux.
Only `y` or `yes` accepts the Linux installation prompt. On other platforms there
is no interactive fallback. If no DSSAT executable is found or installed,
`DSSATNotFoundError` is raised.

For a notebook that must not prompt, use `dl.connect(interactive=False)`. It uses
the same discovery order and raises `DSSATNotFoundError` if nothing is found.

An explicit `path` takes precedence over all discovery locations. It may name the
DSSAT executable or the directory directly containing it. Replace this example
with your installation's path:

```python
import dssatlab as dl

dssat = dl.connect(path=r"C:\DSSAT48\DSCSM048.EXE")
```

An invalid explicit path raises `DSSATNotFoundError`; it does not fall back to
discovery. A successful `connect()` or `install()` replaces the remembered path
in saved config, a JSON file with an `executable` entry:

| Platform | Saved config location |
| --- | --- |
| Windows | `%LOCALAPPDATA%\dssatlab\config.json`; if unset, use `%APPDATA%` |
| Other systems | `$XDG_CONFIG_HOME/dssatlab/config.json`, when set |
| Fallback when the relevant environment variables are unset | `~/.config/dssatlab/config.json` |

Later discovery reuses that path if it still passes the file and permission
checks. An unreadable or invalid saved config is ignored during discovery.

## Install on Linux or Colab

`install()` never prompts. It requires `git`, `cmake`, and `gfortran` on `PATH`
when a build is needed; missing tools are reported rather than installed.

```python
import dssatlab as dl

dssat = dl.install()
```

The default `version="latest"` resolves the latest stable release through GitHub.
To select a concrete release, use `dl.install(version="4.8.6.0")`, without a
leading `v`. The installer clones the official DSSAT source at the release tag,
then configures, builds, and installs it with CMake. A managed install with a
usable manifest and an existing DSSAT executable is reused for that version.

An older managed install whose manifest lacks an install prefix is rebuilt by
`install()`. `connect()` can still accept its saved DSSAT executable path because
discovery checks that file without inspecting its manifest. Use `install()`
explicitly when rebuilding an older managed install.

The cache root is `$XDG_CACHE_HOME/dssatlab` when `XDG_CACHE_HOME` is set, otherwise
`~/.cache/dssatlab`. Each release is installed under `<cache root>/<version>`;
this install prefix holds the DSSAT executable and data directory. Build files
are kept under `<cache root>/work/<version>`.

The resolved, absolute install prefix must be **at most 51 characters**, including
the `dssatlab` and version components. DSSAT cannot read its `DSSATPRO.L48` file
with a longer prefix. If needed, choose a shorter cache location before installing
in the notebook:

```python
import os
from pathlib import Path
import dssatlab as dl

os.environ["XDG_CACHE_HOME"] = str(Path.home() / "dl")
dssat = dl.install()
```

Check that the full prefix still fits the limit and is writable. This assignment
changes the environment of the current Python process. On Windows and other
non-Linux platforms, `install()` raises `DSSATInstallError` after checking the
platform. Windows users install DSSAT 4.8 from [dssat.net](https://dssat.net),
then call `connect(path=...)` with its executable or directory. On other
non-Linux platforms, use `connect(path=...)` with an existing installation.

Continue with [Run a FileX](run-filex.md), or consult
[Troubleshooting](troubleshooting.md) if discovery or installation fails.
