# dssatlab

DSSATLab 0.1.0 provides basic environment diagnostics for Python users preparing
to work with DSSAT-CSM. It reports the operating system, machine architecture,
and Python version with zero runtime dependencies. Requires Python 3.10 or newer.

## Install and use

```bash
python -m pip install dssatlab
```

```python
import dssatlab

info = dssatlab.detect()
print(info)
print(info.os_name)
```

Example output on Linux:

```text
EnvironmentInfo(os_name='linux', architecture='x86_64', python_version='3.12.10')
linux
```

`detect()` returns an immutable `EnvironmentInfo` dataclass:

| Field | Meaning |
| --- | --- |
| `os_name` | Lowercase OS name, such as `windows`, `linux`, or `darwin` (macOS). |
| `architecture` | Machine architecture as reported by Python, such as `AMD64`, `x86_64`, or `arm64`. |
| `python_version` | Version of the running Python interpreter. |

Unavailable OS or architecture values are reported as `unknown`. Importing the
package and calling `detect()` do not prompt, download, or change files.

This first release only reports the Python environment. DSSAT executable
discovery, installation, connection, Colab detection, and simulation support
are not implemented. No DSSAT software or data is bundled.

## Source and development

```text
src/dssatlab/
  __init__.py       # Public exports
  core.py           # EnvironmentInfo and detect()
tests/
  test_detect.py    # OS normalization and unknown-platform cases
pyproject.toml      # Package metadata and development dependencies
.github/workflows/workflow.yml
README.md
LICENSE
.gitignore
```

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m build
python -m twine check dist/*
```

## Release

For a packaging check on GitHub, open **Actions > Publish to PyPI > Run workflow**
and choose `master`, leaving **Publish the package to PyPI** unchecked. This runs
tests, builds and validates the wheel and source archive, and saves them as an
artifact. To retry a failed upload using updated workflow configuration, run
the workflow with **Publish the package to PyPI** checked. This publishes the
version in the selected source after all checks pass; it does not create a tag.

To publish, update `version` in `pyproject.toml`, pass the tests and build checks,
and commit the source. Publish a GitHub release using a new matching tag on that
commit: version `0.1.0` uses tag `v0.1.0`. Publishing the release starts the PyPI
workflow; saving a draft or pushing a tag alone does not. Development versions
(`.dev`) are currently blocked by the workflow.

The PyPI Trusted Publisher uses owner `AbdelrahmanAmr3`, repository `dssatlab`,
workflow `workflow.yml`, and environment `pypi`. No API token is required.
