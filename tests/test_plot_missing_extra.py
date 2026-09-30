"""Tests for plot_plant_growth when matplotlib is not installed."""

import subprocess
import sys

import pytest

from dssatlab.errors import DSSATError, DSSATOutputError
from dssatlab.plot import plot_plant_growth


def test_missing_matplotlib_raises_dssat_error(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)

    with pytest.raises(DSSATError) as exc_info:
        plot_plant_growth(tmp_path, "LAID")

    assert type(exc_info.value) is DSSATError
    assert not isinstance(exc_info.value, DSSATOutputError)
    message = str(exc_info.value)
    assert "pip install dssatlab[plot]" in message


def test_importing_plot_module_does_not_import_matplotlib():
    cmd = [
        sys.executable,
        "-c",
        "import sys, dssatlab.plot; "
        "assert 'matplotlib' not in sys.modules, 'matplotlib imported at module level'; "
        "assert 'matplotlib.pyplot' not in sys.modules, 'matplotlib.pyplot imported at module level'",
    ]
    subprocess.run(cmd, check=True)
