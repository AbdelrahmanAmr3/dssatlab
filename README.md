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

The project is at its first step: getting a working DSSAT into Python. This part is done:

- [x] Find an existing DSSAT-CSM installation on Windows and Linux (including Google Colab)
- [x] Build DSSAT-CSM from the official release on Linux and Colab

```python
import dssatlab as dl

dssat = dl.connect()   # path to the DSSAT executable
```

Running simulations and everything after that is not built yet. Progress will be added here step by step.
