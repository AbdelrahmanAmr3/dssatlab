"""Evaluation against small output files, without running DSSAT (ticket #95)."""

import builtins
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
import shutil

import pytest

import dssatlab as dl
from dssatlab.evaluate import Evaluation
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
                dict(scenario="base", treatment=7, date="2025-01-01", LAID=1),
                dict(scenario="base", treatment=7, date="2025-01-02", LAID=3)]
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
    observed = [dict(scenario="base", treatment=7, **{variable: "2024-12-31"}),
                dict(scenario="wet", treatment=7, **{variable: "2025-01-02"})]
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
                for day in ("2025-01-01", "2025-01-02")]
    assert dl.evaluate(result, observed).statistics["LAID"]["d_index"] == expected


def test_summary_and_daily_pairs_pool_by_variable(tmp_path):
    result = run_result(tmp_path, summary={}, growth=[dict(YEAR=2025, DOY=1, LAID=1)])
    observed = [dict(scenario="base", treatment=7, RUNNO=2),
                dict(scenario="base", treatment=7, date="2025-01-01", RUNNO=1)]
    evaluation = dl.evaluate(result, observed)
    assert evaluation.statistics["RUNNO"] == pytest.approx(
        dict(n=2, rmse=0.5 ** 0.5, bias=-0.5, d_index=0.5))


def test_every_matching_problem_is_reported_together(tmp_path):
    result = run_result(tmp_path, summary=dict(HWAM=-99, ADAT=-99),
                        growth=[dict(YEAR=2025, DOY=1, LAID=-99),
                                dict(YEAR=2025, DOY=3, LAID=1)])
    valid = run_result(tmp_path, "valid", summary=dict(HWAM=5))
    observed = [dict(scenario="valid", treatment=7, HWAM=5),
                dict(scenario="unknown", treatment=7, HWAM=1),
                dict(scenario="base", treatment=2, HWAM=1),
                dict(scenario="base", treatment=2, date="2025-01-01", LAID=1),
                dict(scenario="base", treatment=7, date="2025-01-02", LAID=1),
                dict(scenario="base", treatment=7, HWAM=1, ADAT="2025-01-01", CWAM=2),
                dict(scenario="base", treatment=7, date="2025-01-01", LAID=1, CWAD=2)]
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
                dict(scenario="base", treatment=7, date="2025-01-01", LAID=1)]
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.evaluate({("base", 7): result}, observed)
    assert len(caught.value.problems) == 2
    assert "Summary.OUT" in str(caught.value) and "PlantGro.OUT" in str(caught.value)
    with pytest.raises(dl.DSSATCheckError, match="Summary.OUT"):
        dl.evaluate(result, observed)


def test_real_fixtures_select_treatment_and_accept_csv_or_plain_rows(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for folder, filename in (("summary", "Summary.OUT"), ("plant_growth", "PlantGro.OUT")):
        shutil.copyfile(FIXTURES / folder / "two_treatments" / filename, run_dir / filename)
    result = RunResult(returncode=0, run_dir=run_dir, outputs=[], stdout_tail="")
    path = tmp_path / "observed.csv"
    path.write_text("scenario,treatment,date,HWAM,LAID\nbase,2,,2290,\n"
                    "base,2,1982-02-26,,0.5\n", encoding="utf-8")
    evaluation = dl.evaluate(result, path)
    assert evaluation == dl.evaluate(result, [dict(scenario="base", treatment=2, HWAM=2290),
                                             dict(scenario="base", treatment=2, date="1982-02-26", LAID=0.5)])
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
    evaluation = dl.evaluate(result, [dict(scenario="base", treatment=7, date="2025-01-01", LAID=4)])
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
    (2024366, "2025-01-02", -2), (2024061, "2024-02-28", 2)])
def test_date_errors_can_be_negative_and_count_leap_days(tmp_path, simulated, observed, expected):
    result = run_result(tmp_path, summary=dict(ADAT=simulated))
    evaluation = dl.evaluate(result, [dict(scenario="base", treatment=7, ADAT=observed)])
    assert evaluation.pairs[0]["error"] == expected


def test_ambiguous_simulated_rows_are_not_silently_selected(tmp_path):
    result = run_result(tmp_path, summary={}, growth=[
        dict(YEAR=2025, DOY=1, LAID=2), dict(YEAR=2025, DOY=1, LAID=5)])
    with pytest.raises(dl.DSSATCheckError, match="multiple simulated rows"):
        dl.evaluate(result, [dict(scenario="base", treatment=7, date="2025-01-01", LAID=1)])


@pytest.mark.parametrize("source_kind", ["rows", "csv", "dataframe"])
def test_observed_and_matching_problems_share_one_error(tmp_path, source_kind):
    result = run_result(tmp_path, summary=dict(HWAM=-99),
                        growth=[dict(YEAR=2025, DOY=1, LAID=2),
                                dict(YEAR=2025, DOY=3, LAID=2)])
    rows = [dict(scenario="base", treatment=7, HWAM=1, CWAM=2),
            dict(scenario="missing", treatment=7, HWAM=1),
            dict(scenario="base", treatment=7, date="2025-01-02", LAID=1),
            dict(scenario="bad", treatment="oops", HWAM="bad")]
    if source_kind == "csv":
        import csv
        path = tmp_path / "observed.csv"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["scenario", "treatment", "date", "HWAM", "CWAM", "LAID"])
            writer.writeheader()
            writer.writerows(rows)
        rows = path
    elif source_kind == "dataframe":
        rows = pytest.importorskip("pandas").DataFrame(rows)
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.evaluate(result, rows)
    for expected in ("invalid treatment", "non-numeric", "missing (-99)",
                     "no matching result", "no simulated row", "variable absent", "PlantGro.OUT"):
        assert expected in str(caught.value)


def test_unknown_column_is_one_problem_with_suggestions(tmp_path):
    result = run_result(tmp_path, summary=dict(HWAM=5))
    path = tmp_path / "observed.csv"
    path.write_text("scenario,treatment,HWMA\nbase,7,1\nwet,7,2\n")
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.evaluate({("base", 7): result, ("wet", 7): result}, path)
    assert len(caught.value.problems) == 1
    message = caught.value.problems[0]
    for expected in ("HWMA", "Closest", "HWAM", "Summary columns", "Plant growth columns"):
        assert expected in message


@pytest.mark.parametrize("column", ["date", "ADAT"])
def test_numeric_date_codes_are_rejected(tmp_path, column):
    result = run_result(tmp_path, summary=dict(ADAT=2025001))
    row = dict(scenario="base", treatment=7, **{column: 2025001})
    if column == "date":
        row["LAID"] = 1
    with pytest.raises(dl.DSSATCheckError, match="Use yyyy-mm-dd"):
        dl.evaluate(result, [row])


def test_evaluation_excluded_defaults_are_independent():
    first, second = Evaluation([], {}), Evaluation([], {})
    first.excluded.append(dict(reason="test"))
    assert second.excluded == []
    assert repr(second) == "Evaluation(0 pairs, variables=[])"


@pytest.mark.parametrize("source_kind", ["rows", "csv", "dataframe"])
def test_outside_rows_skip_measurements_and_statistics_use_only_pairs(tmp_path, source_kind):
    result = run_result(tmp_path, summary=dict(HWAM=5), growth=[
        dict(YEAR=2024, DOY=366, LAID=2, CWAD=10),
        dict(YEAR=2025, DOY=1, LAID=5, CWAD=20)])
    rows = [dict(scenario="base", treatment=7, date="2024-12-30", LAID="bad", HWAM=-99),
            dict(scenario="base", treatment=7, date="2024-12-31", LAID=1, CWAD=9),
            dict(scenario="base", treatment=7, date="2025-01-01", LAID=3, CWAD=18),
            dict(scenario="base", treatment=7, date="2025-01-02", LAID=-99, HWAM="bad")]
    before = deepcopy(rows)
    source = rows
    if source_kind == "csv":
        import csv

        source = tmp_path / "observed.csv"
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["scenario", "treatment", "date", "LAID", "CWAD", "HWAM"])
            writer.writeheader()
            writer.writerows(rows)
    elif source_kind == "dataframe":
        source = pytest.importorskip("pandas").DataFrame(rows)
    evaluation = dl.evaluate(result, source)
    assert rows == before
    assert len(evaluation.pairs) == 4
    assert [pair["date"] for pair in evaluation.pairs] == [2024366, 2024366, 2025001, 2025001]
    assert evaluation.excluded == [
        dict(scenario="base", treatment=7, date=2024365,
             reason="before the first simulated day 2024-12-31 (2024366)"),
        dict(scenario="base", treatment=7, date=2025002,
             reason="after the last simulated day 2025-01-01 (2025001)")]
    assert repr(evaluation) == "Evaluation(4 pairs, 2 excluded, variables=['LAID', 'CWAD'])"
    assert evaluation.statistics["LAID"] == pytest.approx(
        dict(n=2, rmse=2.5 ** 0.5, bias=1.5, d_index=12 / 17))


def test_ranges_are_per_scenario_and_treatment_and_can_be_unsorted(tmp_path):
    base = run_result(tmp_path, summary=dict(HWAM=5), growth=[
        dict(YEAR=2025, DOY=3, LAID=3), dict(YEAR=2025, DOY=1, LAID=1)])
    with (base.run_dir / "PlantGro.OUT").open("a", encoding="utf-8") as stream:
        stream.write("*RUN 2 : other\n TREATMENT 2 : other\n" + table([
            dict(YEAR=2025, DOY=10, LAID=10), dict(YEAR=2025, DOY=12, LAID=12)]))
    wet = run_result(tmp_path, "wet", growth=[dict(YEAR=2025, DOY=5, LAID=5)])
    observed = [dict(scenario="base", treatment=7, date="2025-01-03", LAID=2),
                dict(scenario="base", treatment=2, date="2025-01-03", LAID="bad"),
                dict(scenario="wet", treatment=7, date="2025-01-03", LAID=-99),
                dict(scenario="base", treatment=7, HWAM=4)]
    evaluation = dl.evaluate({("base", 7): base, ("base", 2): base, ("wet", 7): wet}, observed)
    assert [pair["variable"] for pair in evaluation.pairs] == ["LAID", "HWAM"]
    assert [(row["scenario"], row["treatment"]) for row in evaluation.excluded] == [("base", 2), ("wet", 7)]
    assert "2025-01-10 (2025010)" in evaluation.excluded[0]["reason"]
    assert "2025-01-05 (2025005)" in evaluation.excluded[1]["reason"]


def test_excluded_unknown_columns_and_empty_measurements_are_not_checked(tmp_path):
    result = run_result(tmp_path, summary=dict(HWAM=5), growth=[dict(YEAR=2025, DOY=2, LAID=2)])
    evaluation = dl.evaluate(result, [
        dict(scenario="base", treatment=7, date="2025-01-01", typo="bad"),
        dict(scenario="base", treatment=7, date="2025-01-03"),
        dict(scenario="base", treatment=7, HWAM=4)])
    assert len(evaluation.excluded) == 2
    assert len(evaluation.pairs) == 1


def test_every_row_excluded_raises_with_next_step(tmp_path):
    result = run_result(tmp_path, summary={}, growth=[dict(YEAR=2025, DOY=2, LAID=2)])
    with pytest.raises(dl.DSSATCheckError, match="every row is outside") as caught:
        dl.evaluate(result, [dict(scenario="base", treatment=7, date="2025-01-01", LAID="bad"),
                             dict(scenario="base", treatment=7, date="2025-01-03", LAID=-99)])
    assert len(caught.value.problems) == 1
    assert "Supply observations within" in str(caught.value)


@pytest.mark.parametrize("growth", [[], [dict(TRNO=2, YEAR=2025, DOY=2, LAID=2)],
                                    [dict(TRNO=7, YEAR=None, DOY=None, DATE=None, LAID=2)]])
def test_empty_growth_or_missing_treatment_has_no_range_to_exclude(tmp_path, monkeypatch, growth):
    result = run_result(tmp_path, summary={})
    monkeypatch.setattr(RunResult, "plant_growth", lambda self: growth)
    with pytest.raises(dl.DSSATCheckError, match="no simulated row in PlantGro.OUT"):
        dl.evaluate({("base", 7): result}, [
            dict(scenario="base", treatment=7, date="2025-01-01", LAID=1)])


@pytest.mark.parametrize("problem", ["duplicate", "bad date", "invalid treatment", "no matching result"])
def test_outside_rows_still_require_valid_unique_keys_and_matching_results(tmp_path, problem):
    result = run_result(tmp_path, summary=dict(HWAM=5), growth=[dict(YEAR=2025, DOY=2, LAID=2)])
    outside = dict(scenario="base", treatment=7, date="2025-01-01", LAID=1)
    rows = [dict(scenario="base", treatment=7, HWAM=4), outside]
    if problem == "duplicate":
        rows.append(dict(outside))
    elif problem == "bad date":
        outside["date"] = "2025-02-30"
    elif problem == "invalid treatment":
        outside["treatment"] = "bad"
    else:
        outside["scenario"] = "missing"
    with pytest.raises(dl.DSSATCheckError, match=problem):
        dl.evaluate(result, rows)
