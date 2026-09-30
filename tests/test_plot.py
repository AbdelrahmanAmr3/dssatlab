"""Tests for plot_plant_growth."""

from datetime import date
from pathlib import Path
import shutil

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dssatlab.errors import DSSATOutputError
from dssatlab.plot import plot_plant_growth


FIXTURES = Path(__file__).parent / "fixtures" / "output_files"


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def make_run_dir(tmp_path, case="maize", name=None):
    dest = tmp_path / (name or case)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "plant_growth" / case / "PlantGro.OUT", dest / "PlantGro.OUT")
    shutil.copy(FIXTURES / "summary" / case / "Summary.OUT", dest / "Summary.OUT")
    return dest


@pytest.mark.parametrize("as_string", [False, True])
def test_plot_one_run_dir_one_treatment(tmp_path, as_string):
    run_dir = make_run_dir(tmp_path, "maize")
    arg = str(run_dir) if as_string else run_dir
    ax = plot_plant_growth(arg, "LAID")

    assert len(ax.lines) == 1
    line = ax.lines[0]
    assert line.get_label() == "RAINFED LOW NITROGEN"

    xdata = line.get_xdata()
    assert len(xdata) == 20
    assert all(isinstance(x, date) for x in xdata)
    assert xdata[0] == date(1982, 2, 26)
    assert line.get_ydata()[-1] == 0.08

    legend = ax.get_legend()
    assert legend is not None
    assert [t.get_text() for t in legend.get_texts()] == ["RAINFED LOW NITROGEN"]


@pytest.mark.parametrize("as_tuple", [False, True])
def test_plot_two_run_directories(tmp_path, as_tuple):
    dir1 = make_run_dir(tmp_path, "maize", "run1")
    dir2 = make_run_dir(tmp_path, "maize", "run2")
    arg = (dir1, dir2) if as_tuple else [dir1, dir2]

    ax = plot_plant_growth(arg, "LAID")
    assert len(ax.lines) == 2
    assert [line.get_label() for line in ax.lines] == [
        "RAINFED LOW NITROGEN",
        "RAINFED LOW NITROGEN",
    ]


def test_plot_two_treatments(tmp_path):
    run_dir = make_run_dir(tmp_path, "two_treatments")
    ax = plot_plant_growth(run_dir, "LAID")

    assert len(ax.lines) == 2
    assert [line.get_label() for line in ax.lines] == [
        "RAINFED LOW NITROGEN",
        "IRRIGATED HIGH NITROGEN",
    ]
    for line in ax.lines:
        assert len(line.get_xdata()) == 10
        assert all(isinstance(x, date) for x in line.get_xdata())


def test_plot_unknown_variable_lists_available(tmp_path):
    run_dir = make_run_dir(tmp_path, "maize")
    with pytest.raises(DSSATOutputError) as exc_info:
        plot_plant_growth(run_dir, "NOT_A_VAR")

    message = str(exc_info.value)
    assert "NOT_A_VAR" in message
    assert "Available variables" in message
    assert "LAID" in message
    assert "CWAD" in message
    for excluded in ("YEAR", "DOY", "DATE", "RUNNO", "TRNO"):
        assert f" {excluded} " not in f" {message} "


@pytest.mark.parametrize("excluded", ["YEAR", "DOY", "DATE", "RUNNO", "TRNO"])
def test_plot_excluded_columns_rejected_as_unknown(tmp_path, excluded):
    run_dir = make_run_dir(tmp_path, "maize")
    with pytest.raises(DSSATOutputError) as exc_info:
        plot_plant_growth(run_dir, excluded)

    message = str(exc_info.value)
    assert excluded in message
    assert "LAID" in message


def test_plot_skips_none_values(tmp_path):
    run_dir = make_run_dir(tmp_path, "missing_value")
    ax = plot_plant_growth(run_dir, "LAID")

    assert len(ax.lines) == 1
    # 20th day has None for LAID in missing_value fixture, so only 19 points plotted
    assert len(ax.lines[0].get_xdata()) == 19


def test_plot_has_title_and_axis_labels(tmp_path):
    make_run_dir(tmp_path)
    ax = plot_plant_growth(tmp_path / "maize", "LAID")
    assert ax.get_title() == "Plant growth: LAID"
    assert ax.get_xlabel() == "Date"
    assert ax.get_ylabel() == "LAID"
