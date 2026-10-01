"""Evaluation scatter plots without running DSSAT (ticket #96)."""

from copy import deepcopy
import sys

import pytest

import dssatlab as dl
from dssatlab.evaluate import Evaluation


@pytest.fixture
def pyplot():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    yield plt
    plt.close("all")


@pytest.fixture
def evaluation():
    return Evaluation([
        dict(scenario="base", treatment=1, date=None, variable="HWAM",
             observed=4, simulated=2, error=-2),
        dict(scenario="wet", treatment=2, date=None, variable="HWAM",
             observed=6, simulated=8, error=2),
    ], {"HWAM": dict(n=2, rmse=2, bias=0, d_index=0.6)})


def test_plot_evaluation_scatter_labels_and_identity_line(pyplot, evaluation):
    before = deepcopy(evaluation)
    ax = dl.plot_evaluation(evaluation)

    assert "plot_evaluation" in dl.__all__
    assert isinstance(ax, pyplot.Axes)
    assert ax.figure.axes == [ax]
    assert len(ax.collections) == 1
    assert ax.collections[0].get_offsets().tolist() == [[4, 2], [6, 8]]
    assert ax.get_xlabel() == "Observed"
    assert ax.get_ylabel() == "Simulated"
    assert [text.get_text() for text in ax.get_legend().get_texts()] == ["HWAM"]
    assert len(ax.lines) == 1
    line = ax.lines[0]
    assert line.get_linestyle() == "--"
    assert list(line.get_xdata()) == [2, 8]
    assert list(line.get_ydata()) == [2, 8]
    assert evaluation == before


def test_plot_evaluation_selects_one_variable(pyplot, evaluation):
    evaluation.pairs.append(dict(scenario="base", treatment=1, date=2025001,
                                 variable="LAID", observed=0.5, simulated=1, error=0.5))
    ax = dl.plot_evaluation(evaluation, variable="LAID")

    assert len(ax.collections) == 1
    assert ax.collections[0].get_offsets().tolist() == [[0.5, 1]]
    assert [text.get_text() for text in ax.get_legend().get_texts()] == ["LAID"]
    assert list(ax.lines[0].get_xdata()) == [0.5, 1]


def test_plot_evaluation_multiple_variables_requires_selection(pyplot, evaluation):
    evaluation.pairs.append(dict(scenario="base", treatment=1, date=2025001,
                                 variable="LAID", observed=0.5, simulated=1, error=0.5))
    with pytest.raises(dl.DSSATError) as exc_info:
        dl.plot_evaluation(evaluation)

    message = str(exc_info.value)
    assert "HWAM" in message and "LAID" in message
    assert "variable=" in message
    assert pyplot.get_fignums() == []


def test_plot_evaluation_unknown_variable_lists_available(pyplot, evaluation):
    with pytest.raises(dl.DSSATError) as exc_info:
        dl.plot_evaluation(evaluation, variable="UNKNOWN")

    message = str(exc_info.value)
    assert "UNKNOWN" in message
    assert "Available variables" in message and "HWAM" in message
    assert "Choose" in message
    assert pyplot.get_fignums() == []


def test_plot_evaluation_empty_pairs_raises_helpful_error(pyplot):
    with pytest.raises(dl.DSSATError) as exc_info:
        dl.plot_evaluation(Evaluation([], {}))

    message = str(exc_info.value)
    assert "pairs" in message
    assert "evaluate()" in message
    assert pyplot.get_fignums() == []


@pytest.mark.parametrize("value", [0, 5, -5])
def test_plot_evaluation_single_pair_without_statistics(pyplot, value):
    evaluation = Evaluation([
        dict(scenario="base", treatment=1, date=None, variable="HWAM",
             observed=value, simulated=value, error=0),
    ], {})
    ax = dl.plot_evaluation(evaluation)

    assert ax.collections[0].get_offsets().tolist() == [[value, value]]
    line = ax.lines[0]
    low, high = line.get_xdata()
    assert low < value < high
    assert list(line.get_ydata()) == [low, high]


def test_plot_evaluation_date_codes_are_plotted_unchanged(pyplot):
    evaluation = Evaluation([
        dict(scenario="base", treatment=1, date=None, variable="ADAT",
             observed=2024366, simulated=2025002, error=2),
    ], {})
    ax = dl.plot_evaluation(evaluation)

    assert ax.collections[0].get_offsets().tolist() == [[2024366, 2025002]]


def test_plot_evaluation_missing_matplotlib(monkeypatch, evaluation):
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)

    with pytest.raises(dl.DSSATError) as exc_info:
        dl.plot_evaluation(evaluation)

    assert type(exc_info.value) is dl.DSSATError
    assert str(exc_info.value) == (
        "Plotting needs matplotlib. Install it with: pip install dssatlab[plot]"
    )
