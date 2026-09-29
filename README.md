# dssatlab

`dssatlab` aims to be a Python interface to the DSSAT-CSM. The goal is to let users work with DSSAT from Python and use the wider Python ecosystem (data, analysis, plotting, notebooks) to make DSSAT easier and more powerful to use.

[![PyPI version](https://img.shields.io/pypi/v/dssatlab)](https://pypi.org/project/dssatlab/)
[![Python versions](https://img.shields.io/pypi/pyversions/dssatlab)](https://pypi.org/project/dssatlab/)
[![Downloads](https://img.shields.io/pypi/dm/dssatlab)](https://pypi.org/project/dssatlab/)
[![Tests](https://github.com/AbdelrahmanAmr3/dssatlab/actions/workflows/tests.yml/badge.svg)](https://github.com/AbdelrahmanAmr3/dssatlab/actions/workflows/tests.yml)
[![License](https://img.shields.io/pypi/l/dssatlab)](LICENSE)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AbdelrahmanAmr3/dssatlab/blob/master/notebook/dssatlab_walkthrough.ipynb)

## Installation

```bash
pip install dssatlab
```

Requires Python 3.10 or newer. To upgrade later: `pip install --upgrade dssatlab`.

## Current stage

The project can get a working DSSAT into Python and run one existing experiment file. This part is done:

- [x] Find an existing DSSAT-CSM installation on Windows and Linux (including Google Colab)
- [x] Build DSSAT-CSM from the official release on Linux and Colab
- [x] Run one existing FileX

```python
import dssatlab as dl

dssat = dl.connect()                          # path to the DSSAT executable
result = dl.run("UFGA8201.MZX")               # all treatments
result = dl.run("UFGA8201.MZX", treatment=2)  # one treatment
print(result.run_dir, result.outputs)
```

How a run works:

- DSSAT runs in the FileX's own folder, so weather and soil files beside the FileX are found. Its output files are then moved into a new `dssat_run_<date>` folder beside the FileX, and your FileX folder is left as it was.
- The FileX filename can be at most 12 characters, including the extension (DSSAT's own limit), for example `UFGA8201.MZX`.
- A failed run raises `DSSATRunError` with the command, the end of DSSAT's console output and the start of `ERROR.OUT`. The run folder is kept so you can look inside.
- `run()` returns the files DSSAT wrote and does not read them. Reading input or output files, building experiments and plotting are not built yet.

Upgrading from 0.1.x on Linux or Colab: a DSSAT built by 0.1.x cannot run simulations, so the first `dl.install()` (or `dl.connect()` with consent) rebuilds it once.
