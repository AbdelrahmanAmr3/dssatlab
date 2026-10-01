"""Observed points over Plant growth curves, without running DSSAT (#106)."""

from copy import deepcopy
from datetime import date
import sys

import pytest

import dssatlab as dl
from dssatlab.runner import RunResult
from test_evaluate import run_result, table


@pytest.fixture
def pyplot():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    yield plt
    plt.close("all")


@pytest.fixture
def result(tmp_path):
    return run_result(tmp_path, summary=dict(HWAM=5), growth=[
        dict(YEAR=2025, DOY=1, LAID=2), dict(YEAR=2025, DOY=2, LAID=3)])


def measurement(scenario="base", treatment=7, day="2025-01-01", **values):
    return dict(scenario=scenario, treatment=treatment, date=day, **(values or {"LAID": 1}))


@pytest.mark.parametrize("source_kind", ["rows", "csv", "dataframe"])
def test_single_run_inputs_and_out_of_season_points(pyplot, result, tmp_path, source_kind):
    from matplotlib.colors import to_rgba
    from matplotlib.dates import date2num

    rows = [measurement(day="2024-12-30"), measurement(day="2025-01-04", LAID=4),
            measurement(day=None, HWAM=5)]
    before = deepcopy(rows)
    source = rows
    if source_kind == "csv":
        source = tmp_path / "observed.csv"
        source.write_text("scenario,treatment,date,LAID,HWAM\n"
                          "base,7,2024-12-30,1,\nbase,7,2025-01-04,4,\nbase,7,,,5\n")
    elif source_kind == "dataframe":
        source = pytest.importorskip("pandas").DataFrame(rows)
    ax = dl.plot_observed(result, source, "LAID")
    assert isinstance(ax, pyplot.Axes)
    assert "plot_observed" in dl.__all__
    assert len(ax.lines) == len(ax.collections) == 1
    assert list(ax.lines[0].get_xdata()) == [date(2025, 1, 1), date(2025, 1, 2)]
    assert list(ax.lines[0].get_ydata()) == [2, 3]
    assert ax.collections[0].get_offsets().tolist() == [
        [date2num(date(2024, 12, 30)), 1], [date2num(date(2025, 1, 4)), 4]]
    assert ax.collections[0].get_facecolors()[0] == pytest.approx(to_rgba(ax.lines[0].get_color()))
    assert ax.get_title() == "LAID: simulated and observed"
    assert ax.get_xlabel() == "Date"
    assert ax.get_ylabel() == "LAID"
    assert [text.get_text() for text in ax.get_legend().get_texts()] == ["base, treatment 7"]
    assert rows == before


def test_scenarios_and_treatments_select_only_observed_curves(pyplot, result):
    from matplotlib.colors import to_rgba

    with (result.run_dir / "PlantGro.OUT").open("a") as stream:
        stream.write("*RUN 2 : other\n TREATMENT 2 : other\n" + table([
            dict(YEAR=2025, DOY=1, LAID=9)]))
    results = {("base", 7): result, ("wet", 7): result,
               ("wet", 2): result, ("unobserved", 7): result}
    rows = [measurement(), measurement("wet"), measurement("wet", 2),
            measurement("unobserved", CWAD=10)]
    ax = dl.plot_observed(results, rows, "LAID")
    assert len(ax.lines) == len(ax.collections) == 3
    assert [line.get_label() for line in ax.lines] == [
        "base, treatment 7", "wet, treatment 7", "wet, treatment 2"]
    assert [list(line.get_ydata()) for line in ax.lines] == [[2, 3], [2, 3], [9]]
    for line, markers in zip(ax.lines, ax.collections):
        assert markers.get_facecolors()[0] == pytest.approx(to_rgba(line.get_color()))


def test_single_run_maps_multiple_summary_treatments(pyplot, result):
    (result.run_dir / "Summary.OUT").write_text(table([
        dict(RUNNO=1, TRNO=7, TNAM="first"), dict(RUNNO=2, TRNO=2, TNAM="second")]))
    with (result.run_dir / "PlantGro.OUT").open("a") as stream:
        stream.write("*RUN 2 : other\n TREATMENT 2 : other\n" + table([
            dict(YEAR=2025, DOY=1, LAID=9)]))
    ax = dl.plot_observed(result, [measurement(treatment=2)], "LAID")
    assert list(ax.lines[0].get_ydata()) == [9]
    assert ax.lines[0].get_label() == "base, treatment 2"


def test_all_observed_and_output_problems_are_collected_before_drawing(pyplot, result, tmp_path):
    absent = run_result(tmp_path, "absent", growth=[dict(YEAR=2025, DOY=1, CWAD=2)])
    unreadable = run_result(tmp_path, "unreadable")
    results = {("base", 7): result, ("absent", 7): absent,
               ("unreadable", 7): unreadable, ("base", 2): result}
    observed = [measurement("missing"), measurement("absent"), measurement("unreadable"),
                measurement(treatment=2), measurement(LAID=1, CWAD="bad")]
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.plot_observed(results, observed, "LAID")
    assert len(caught.value.problems) == 5
    for text in ("non-numeric", "no matching result", "variable absent from PlantGro.OUT",
                 "no Plant growth rows", "PlantGro.OUT is missing or unreadable"):
        assert text in str(caught.value)
    assert pyplot.get_fignums() == []


def test_single_run_summary_read_problem_is_retained(pyplot, result):
    (result.run_dir / "Summary.OUT").unlink()
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.plot_observed(result, [measurement()], "LAID")
    assert "Summary.OUT" in str(caught.value)
    assert "no matching result" in str(caught.value)
    assert pyplot.get_fignums() == []


@pytest.mark.parametrize("variable,observed", [
    ("HWAM", [measurement(day=None, HWAM=5)]),
    ("HWAM", [measurement()]),
    ("RUNNO", [measurement(day=None, RUNNO=1)]),
])
def test_summary_variables_redirect_to_evaluation(pyplot, result, variable, observed):
    with pytest.raises(dl.DSSATError) as caught:
        dl.plot_observed(result, observed, variable)
    assert type(caught.value) is dl.DSSATError
    assert "end-of-season" in str(caught.value)
    assert "plot_evaluation(evaluate(...), variable)" in str(caught.value)
    assert pyplot.get_fignums() == []


def test_no_dated_measurement_lists_dated_variables(pyplot, result):
    with pytest.raises(dl.DSSATError) as caught:
        dl.plot_observed(result, [measurement(), measurement(day=None, HWAM=5)], "CWAD")
    assert type(caught.value) is dl.DSSATError
    assert "Available dated variables are: LAID" in str(caught.value)
    assert "HWAM" not in str(caught.value)
    assert pyplot.get_fignums() == []


def test_missing_matplotlib(monkeypatch, result):
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)
    with pytest.raises(dl.DSSATError) as caught:
        dl.plot_observed(result, [measurement()], "LAID")
    assert type(caught.value) is dl.DSSATError
    assert str(caught.value) == (
        "Plotting needs matplotlib. Install it with: pip install dssatlab[plot]"
    )


def test_evaluate_preserves_single_summary_read(result, monkeypatch):
    original = RunResult.summary
    calls = []

    def summary(run):
        calls.append(run.run_dir)
        return original(run)

    monkeypatch.setattr(RunResult, "summary", summary)
    evaluation = dl.evaluate(result, [measurement(day=None, HWAM=3)])
    assert evaluation.pairs[0]["error"] == 2
    assert calls == [result.run_dir]
