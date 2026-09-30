"""Evaluation against small output files, without running DSSAT (ticket #95)."""

import builtins
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
import shutil

import pytest

import dssatlab as dl
from dssatlab.evaluate import Evaluation, load_observed
from dssatlab.runner import RunResult


FIXTURES = Path(__file__).parent / "fixtures" / "output_files"


def table(rows):
    names = list(rows[0])
    header = "".join(f"{name:>10}" for name in names)
    return "@" + header[1:] + "\n" + "".join(
        "".join(f"{row[name]:>10}" for name in names) + "\n" for row in rows)


def run_result(tmp_path, name="run", treatment=7, summary=None, growth=None):
    run_dir = tmp_path / name
    run_dir.mkdir()
    if summary is not None:
        row = dict(RUNNO=1, TRNO=treatment, TNAM="test", **summary)
        (run_dir / "Summary.OUT").write_text(table([row]), encoding="ascii")
    if growth is not None:
        text = f"*RUN 1 : test\n TREATMENT {treatment} : test\n" + table(growth)
        (run_dir / "PlantGro.OUT").write_text(text, encoding="ascii")
    return RunResult(returncode=0, run_dir=run_dir, outputs=[], stdout_tail="")


def test_single_run_uses_own_treatment_and_one_pair_has_no_statistics(tmp_path, monkeypatch):
    result = run_result(tmp_path, summary=dict(HWAM=5))
    observed = [dict(scenario="base", treatment=7, date=None, HWAM=3)]
    before = deepcopy(observed)
    original = builtins.__import__

    def without_pandas(name, *args, **kwargs):
        if name.split(".")[0] == "pandas":
            raise AssertionError("Evaluation must not import pandas")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_pandas)
    evaluation = dl.evaluate(result, observed)
    assert evaluation.pairs == [dict(scenario="base", treatment=7, date=None,
                                     variable="HWAM", observed=3, simulated=5, error=2)]
    assert evaluation.statistics == {}
    assert observed == before
    assert repr(evaluation) == "Evaluation(1 pairs, variables=['HWAM'])"
    assert isinstance(evaluation, Evaluation)
    with pytest.raises(FrozenInstanceError):
        evaluation.pairs = []
    assert "evaluate" in dl.__all__


def test_hand_computed_statistics_across_scenarios_and_daily_dates(tmp_path):
    base = run_result(tmp_path, "base", summary=dict(HWAM=2), growth=[
        dict(YEAR=2025, DOY=1, LAID=2), dict(YEAR=2025, DOY=2, LAID=5)])
    wet = run_result(tmp_path, "wet", treatment=2, summary=dict(HWAM=5))
    unused = run_result(tmp_path, "unused")  # Unobserved files need not even exist.
    results = {("base", 7): base, ("wet", 2): wet, ("unused", 1): unused}
    observed = [dict(scenario="base", treatment=7, HWAM=1),
                dict(scenario="wet", treatment=2, HWAM=3),
                dict(scenario="base", treatment=7, date=2025001, LAID=1),
                dict(scenario="base", treatment=7, date=2025002, LAID=3)]
    evaluation = dl.evaluate(results, observed)
    assert [pair["error"] for pair in evaluation.pairs] == [1, 2, 1, 2]
    # O=[1,3], S=[2,5]: squared errors=5; Willmott denominator=1+16=17.
    expected = dict(n=2, rmse=2.5 ** 0.5, bias=1.5, d_index=12 / 17)
    assert evaluation.statistics["HWAM"] == pytest.approx(expected)
    assert evaluation.statistics["LAID"] == pytest.approx(expected)


@pytest.mark.parametrize("variable", ["ADAT", "MDAT", "SDAT", "PDAT", "EDAT", "HDAT"])
def test_summary_date_errors_and_statistics_use_calendar_days(tmp_path, variable):
    base = run_result(tmp_path, "base", summary={variable: 2025002})
    wet = run_result(tmp_path, "wet", summary={variable: 2025003})
    observed = [dict(scenario="base", treatment=7, **{variable: 2024366}),
                dict(scenario="wet", treatment=7, **{variable: 2025002})]
    evaluation = dl.evaluate({("base", 7): base, ("wet", 7): wet}, observed)
    assert [pair["error"] for pair in evaluation.pairs] == [2, 1]
    assert [pair["observed"] for pair in evaluation.pairs] == [2024366, 2025002]
    assert [pair["simulated"] for pair in evaluation.pairs] == [2025002, 2025003]
    # Relative to Dec 31: O=[0,2], S=[2,3], Obar=1, denominator=4+9.
    assert evaluation.statistics[variable] == pytest.approx(
        dict(n=2, rmse=2.5 ** 0.5, bias=1.5, d_index=8 / 13))


@pytest.mark.parametrize("simulated,expected", [(3, 1.0), (4, 0.0)])
def test_constant_observations_d_index(tmp_path, simulated, expected):
    result = run_result(tmp_path, summary={}, growth=[
        dict(YEAR=2025, DOY=1, LAID=simulated), dict(YEAR=2025, DOY=2, LAID=simulated)])
    observed = [dict(scenario="base", treatment=7, date=day, LAID=3)
                for day in (2025001, 2025002)]
    assert dl.evaluate(result, observed).statistics["LAID"]["d_index"] == expected


def test_summary_and_daily_pairs_pool_by_variable(tmp_path):
    result = run_result(tmp_path, summary={}, growth=[dict(YEAR=2025, DOY=1, LAID=1)])
    observed = [dict(scenario="base", treatment=7, RUNNO=2),
                dict(scenario="base", treatment=7, date=2025001, RUNNO=1)]
    evaluation = dl.evaluate(result, observed)
    assert evaluation.statistics["RUNNO"] == pytest.approx(
        dict(n=2, rmse=0.5 ** 0.5, bias=-0.5, d_index=0.5))


def test_every_matching_problem_is_reported_together(tmp_path):
    result = run_result(tmp_path, summary=dict(HWAM=-99, ADAT=-99),
                        growth=[dict(YEAR=2025, DOY=1, LAID=-99)])
    valid = run_result(tmp_path, "valid", summary=dict(HWAM=5))
    observed = [dict(scenario="valid", treatment=7, HWAM=5),
                dict(scenario="unknown", treatment=7, HWAM=1),
                dict(scenario="base", treatment=2, HWAM=1),
                dict(scenario="base", treatment=2, date=2025001, LAID=1),
                dict(scenario="base", treatment=7, date=2025002, LAID=1),
                dict(scenario="base", treatment=7, HWAM=1, ADAT=2025001, CWAM=2),
                dict(scenario="base", treatment=7, date=2025001, LAID=1, CWAD=2)]
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.evaluate({("base", 7): result, ("base", 2): result, ("valid", 7): valid}, observed)
    assert len(caught.value.problems) == 9
    message = str(caught.value)
    for expected in ("unknown", "no matching result", "treatment 2", "2025002",
                     "no simulated row", "Summary.OUT", "PlantGro.OUT", "HWAM",
                     "ADAT", "LAID", "missing (-99)", "CWAM", "CWAD", "variable absent"):
        assert expected in message


def test_output_read_failures_are_aggregated(tmp_path):
    result = run_result(tmp_path)
    observed = [dict(scenario="base", treatment=7, HWAM=1),
                dict(scenario="base", treatment=7, date=2025001, LAID=1)]
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.evaluate({("base", 7): result}, observed)
    assert len(caught.value.problems) == 2
    assert "Summary.OUT" in str(caught.value) and "PlantGro.OUT" in str(caught.value)
    with pytest.raises(dl.DSSATCheckError, match="Summary.OUT"):
        dl.evaluate(result, observed)


def test_real_fixtures_select_treatment_and_accept_csv_or_loaded_rows(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for folder, filename in (("summary", "Summary.OUT"), ("plant_growth", "PlantGro.OUT")):
        shutil.copyfile(FIXTURES / folder / "two_treatments" / filename, run_dir / filename)
    result = RunResult(returncode=0, run_dir=run_dir, outputs=[], stdout_tail="")
    path = tmp_path / "observed.csv"
    path.write_text("scenario,treatment,date,HWAM,LAID\nbase,2,,2290,\n"
                    "base,2,1982-02-26,,0.5\n", encoding="utf-8")
    evaluation = dl.evaluate(result, path)
    assert evaluation == dl.evaluate(result, load_observed(path))
    assert [pair["treatment"] for pair in evaluation.pairs] == [2, 2]
    assert [pair["error"] for pair in evaluation.pairs] == [5, -0.5]
    assert evaluation.pairs[1]["date"] == 1982057


def test_daily_matching_uses_year_and_treatment(tmp_path):
    result = run_result(tmp_path, summary={}, growth=[
        dict(YEAR=2024, DOY=1, LAID=2), dict(YEAR=2025, DOY=1, LAID=5)])
    path = result.run_dir / "PlantGro.OUT"
    with path.open("a", encoding="ascii") as stream:
        stream.write("*RUN 2 : other\n TREATMENT 2 : other\n"
                     + table([dict(YEAR=2025, DOY=1, LAID=10)]))
    evaluation = dl.evaluate(result, [dict(scenario="base", treatment=7, date=2025001, LAID=4)])
    assert evaluation.pairs[0]["error"] == 1


def test_dataframe_input_and_conversion(tmp_path):
    pd = pytest.importorskip("pandas")
    result = run_result(tmp_path, summary=dict(HWAM=5, ADAT=2025002),
                        growth=[dict(YEAR=2025, DOY=1, LAID=2)])
    frame = pd.DataFrame([dict(scenario="base", treatment=7, HWAM=3, ADAT="2024-12-31"),
                          dict(scenario="base", treatment=7, date="2025-01-01", LAID=1)])
    before = frame.copy(deep=True)
    evaluation = dl.evaluate(result, frame)
    assert [pair["error"] for pair in evaluation.pairs] == [2, 2, 1]
    pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(evaluation.to_dataframe(), pd.DataFrame(evaluation.pairs))


@pytest.mark.parametrize("simulated,observed,expected", [
    (2024366, 2025002, -2), (2024061, 2024059, 2)])
def test_date_errors_can_be_negative_and_count_leap_days(tmp_path, simulated, observed, expected):
    result = run_result(tmp_path, summary=dict(ADAT=simulated))
    evaluation = dl.evaluate(result, [dict(scenario="base", treatment=7, ADAT=observed)])
    assert evaluation.pairs[0]["error"] == expected


def test_ambiguous_simulated_rows_are_not_silently_selected(tmp_path):
    result = run_result(tmp_path, summary={}, growth=[
        dict(YEAR=2025, DOY=1, LAID=2), dict(YEAR=2025, DOY=1, LAID=5)])
    with pytest.raises(dl.DSSATCheckError, match="multiple simulated rows"):
        dl.evaluate(result, [dict(scenario="base", treatment=7, date=2025001, LAID=1)])
