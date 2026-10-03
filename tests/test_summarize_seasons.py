"""Unit tests for summarize_seasons (seasonal analysis summary statistics)."""

from datetime import date
import statistics

import pytest

import dssatlab as lab


def test_empty_list_returns_empty():
    assert lab.summarize_seasons([]) == []
    assert lab.summarize_seasons([], variables=["HWAM", "CWAM"]) == []
    assert lab.summarize_seasons([], variables=("HWAM",)) == []


@pytest.mark.parametrize("components", [(1, 2, 3), (3, 1, 2)])
@pytest.mark.parametrize("labels", [
    [{"TRNO": 1}],
    [{"scenario": "late", "treatment": 2}, {"scenario": "early", "treatment": 2},
     {"scenario": "late", "treatment": 1}],
])
def test_sequence_statistics_per_rotation_component(components, labels):
    crops = {1: "BN", 2: "FA", 3: "SB"}
    yields = {1: [1000, 2000, 3000], 2: [0, 0, 0], 3: [2000, 4000, 6000]}
    rows = [dict(label, **{"R#": component, "CR": crops[component],
                          "HWAM": yields[component][season]})
            for season in range(3) for label in labels for component in components]
    results = lab.summarize_seasons(rows)
    expected = []
    for label in labels:
        for component in components:
            values = yields[component]
            expected.append({
                "scenario": label.get("scenario", "base"),
                "treatment": label.get("treatment", label.get("TRNO")),
                "component": component, "crop": crops[component], "variable": "HWAM",
                "seasons": 3, "missing": 0, "mean": values[1],
                "sd": values[1] - values[0], "min": values[0],
                "p25": (values[0] + values[1]) / 2, "median": values[1],
                "p75": (values[1] + values[2]) / 2, "max": values[2],
            })
    assert results == expected
    assert list(results[0]) == list(expected[0])


@pytest.mark.parametrize("component_fields", [{}, {"R#": None}, {"R#": 1}])
@pytest.mark.parametrize("crop_fields,crop", [({}, None), ({"CR": "BN"}, "BN")])
def test_default_component_and_first_row_crop(component_fields, crop_fields, crop):
    rows = [dict(TRNO=1, HWAM=1000, **component_fields, **crop_fields),
            {"TRNO": 1, "R#": 1, "CR": "SB", "HWAM": 3000}]
    assert lab.summarize_seasons(rows) == [{
        "scenario": "base", "treatment": 1, "component": 1, "crop": crop,
        "variable": "HWAM", "seasons": 2, "missing": 0, "mean": 2000,
        "sd": pytest.approx(statistics.stdev([1000, 3000])), "min": 1000,
        "p25": 1500, "median": 2000, "p75": 2500, "max": 3000,
    }]


def test_single_run_rows_defaults_scenario_to_base_and_treatment_to_trno():
    rows = [{"TRNO": 1, "HWAM": 1000}, {"TRNO": 1, "HWAM": 2000}]
    results = lab.summarize_seasons(rows)
    assert len(results) == 1
    expected_keys = ["scenario", "treatment", "component", "crop", "variable", "seasons", "missing",
                     "mean", "sd", "min", "p25", "median", "p75", "max"]
    assert list(results[0].keys()) == expected_keys
    row = results[0]
    assert row["scenario"] == "base"
    assert row["treatment"] == 1
    assert row["component"] == 1
    assert row["crop"] is None
    assert row["variable"] == "HWAM"
    assert row["seasons"] == 2
    assert row["missing"] == 0
    assert row["mean"] == 1500
    assert row["sd"] == pytest.approx(statistics.stdev([1000, 2000]))
    assert row["min"] == 1000
    assert row["p25"] == 1250.0
    assert row["median"] == 1500.0
    assert row["p75"] == 1750.0
    assert row["max"] == 2000


def test_single_run_rows_with_multiple_treatments():
    rows = [{"TRNO": 1, "HWAM": 1000}, {"TRNO": 2, "HWAM": 3000}]
    results = lab.summarize_seasons(rows)
    assert [(r["scenario"], r["treatment"]) for r in results] == [("base", 1), ("base", 2)]
    assert results[0]["mean"] == 1000
    assert results[1]["mean"] == 3000


def test_combined_rows_grouped_by_scenario_and_treatment_in_first_appearance_order():
    rows = [
        {"scenario": "late", "treatment": 2, "HWAM": 200},
        {"scenario": "early", "treatment": 1, "HWAM": 500},
        {"scenario": "late", "treatment": 2, "HWAM": 400},
        {"scenario": "early", "treatment": 1, "HWAM": 700},
    ]
    results = lab.summarize_seasons(rows)
    assert [(r["scenario"], r["treatment"]) for r in results] == [("late", 2), ("early", 1)]
    assert results[0]["seasons"] == 2
    assert results[0]["mean"] == 300
    assert results[0]["min"] == 200
    assert results[0]["max"] == 400
    assert results[1]["seasons"] == 2
    assert results[1]["mean"] == 600
    assert results[1]["min"] == 500
    assert results[1]["max"] == 700


def test_several_variables_and_order():
    rows = [
        {"TRNO": 1, "HWAM": 1000, "CWAM": 2000},
        {"TRNO": 1, "HWAM": 3000, "CWAM": 4000},
        {"TRNO": 2, "HWAM": 5000, "CWAM": 6000},
    ]
    results = lab.summarize_seasons(rows, variables=["CWAM", "HWAM"])
    assert [(r["treatment"], r["variable"]) for r in results] == [
        (1, "CWAM"), (1, "HWAM"), (2, "CWAM"), (2, "HWAM"),
    ]
    assert results[0]["mean"] == 3000
    assert results[1]["mean"] == 2000
    assert results[2]["mean"] == 6000
    assert results[3]["mean"] == 5000


def test_missing_values_counted_and_excluded_from_statistics():
    rows = [
        {"TRNO": 1, "HWAM": 1000},
        {"TRNO": 1, "HWAM": None},
        {"TRNO": 1, "HWAM": 3000},
    ]
    results = lab.summarize_seasons(rows)
    assert len(results) == 1
    row = results[0]
    assert row["seasons"] == 3
    assert row["missing"] == 1
    assert row["mean"] == 2000
    assert row["sd"] == pytest.approx(statistics.stdev([1000, 3000]))
    assert row["min"] == 1000
    assert row["p25"] == 1500.0
    assert row["median"] == 2000.0
    assert row["p75"] == 2500.0
    assert row["max"] == 3000


def test_omitted_column_counts_as_missing():
    rows = [{"TRNO": 1, "HWAM": 1000}, {"TRNO": 1}]
    results = lab.summarize_seasons(rows)
    assert len(results) == 1
    row = results[0]
    assert row["seasons"] == 2
    assert row["missing"] == 1
    assert row["mean"] == 1000
    assert row["sd"] is None
    assert row["p25"] == 1000
    assert row["median"] == 1000
    assert row["p75"] == 1000


@pytest.mark.parametrize("rows,seasons,missing", [
    ([{"TRNO": 1, "HWAM": 2500}], 1, 0),
    ([{"TRNO": 1, "HWAM": 2500}, {"TRNO": 1, "HWAM": None}], 2, 1),
])
def test_one_value_statistics(rows, seasons, missing):
    results = lab.summarize_seasons(rows)
    assert len(results) == 1
    row = results[0]
    assert row["seasons"] == seasons
    assert row["missing"] == missing
    assert row["mean"] == 2500
    assert row["sd"] is None
    assert row["min"] == 2500
    assert row["p25"] == 2500
    assert row["median"] == 2500
    assert row["p75"] == 2500
    assert row["max"] == 2500


def test_all_missing_statistics():
    rows = [
        {"TRNO": 1, "HWAM": None},
        {"TRNO": 1, "HWAM": None},
    ]
    results = lab.summarize_seasons(rows)
    assert len(results) == 1
    row = results[0]
    assert row["seasons"] == 2
    assert row["missing"] == 2
    for stat in ("mean", "sd", "min", "p25", "median", "p75", "max"):
        assert row[stat] is None


@pytest.mark.parametrize("row,variable,expected_msg", [
    ({"TRNO": 1, "TNAM": "Low N"}, "TNAM",
     "Variable 'TNAM' has a non-numeric value 'Low N' (scenario 'base', treatment 1). Choose a numeric Summary column."),
    ({"TRNO": 1, "HWAM": True}, "HWAM",
     "Variable 'HWAM' has a non-numeric value True (scenario 'base', treatment 1). Choose a numeric Summary column."),
    ({"TRNO": 2, "scenario": "drought", "SDAT": date(1982, 3, 1)}, "SDAT",
     f"Variable 'SDAT' has a non-numeric value {date(1982, 3, 1)!r} (scenario 'drought', treatment 2). Choose a numeric Summary column."),
])
def test_non_numeric_values_rejected(row, variable, expected_msg):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons([row], variables=[variable])
    assert expected_msg in exc.value.problems


def test_unknown_variable_rejected():
    rows = [{"TRNO": 1, "HWAM": 1000}]
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons(rows, variables=["HWAMX"])
    assert "Variable 'HWAMX' is not a Summary column. Use a column name from the Summary rows, such as HWAM." in exc.value.problems


@pytest.mark.parametrize("rows", [
    None, "not a list", 123, {"TRNO": 1}, [1, 2], [{"TRNO": 1}, "bad"],
])
def test_bad_rows_not_a_list_of_dicts(rows):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons(rows)
    assert "Summary rows: expected a list of dicts. Supply the rows from result.summary() or combine_summaries()." in exc.value.problems


@pytest.mark.parametrize("rows", [
    [{"HWAM": 1000}],
    [{"scenario": "base", "HWAM": 1000}],
    [{"treatment": None, "HWAM": 1000}],
    [{"TRNO": None, "HWAM": 1000}],
])
def test_bad_rows_missing_treatment_and_trno(rows):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons(rows)
    assert exc.value.problems == ["Summary row 1: found neither 'treatment' nor 'TRNO'. Supply rows from result.summary() or combine_summaries()."]


@pytest.mark.parametrize("variables", [
    "HWAM", [], (), [123], ["HWAM", 123], None, {"HWAM"},
])
def test_bad_variables(variables):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons([{"TRNO": 1, "HWAM": 1000}], variables=variables)
    assert any(p.startswith("Variables: found ") and p.endswith(
        "Supply variables as a list of Summary column names, such as ['HWAM'].") for p in exc.value.problems)


def test_several_problems_collected_in_one_check_error():
    rows = [
        {"HWAM": 1000},                         # Missing treatment
        {"TRNO": 1, "HWAM": "non-numeric"},     # Non-numeric value
    ]
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons(rows, variables=["HWAM", "HWAMX"])
    problems = exc.value.problems
    assert len(problems) == 3
    assert any("neither 'treatment' nor 'TRNO'" in p for p in problems)
    assert any("Variable 'HWAMX' is not a Summary column" in p for p in problems)
    assert any("Variable 'HWAM' has a non-numeric value 'non-numeric'" in p for p in problems)


def test_bad_rows_and_bad_variables_collected_together():
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons("not a list", variables=123)
    assert len(exc.value.problems) == 2
    assert "Summary rows: expected a list of dicts. Supply the rows from result.summary() or combine_summaries()." in exc.value.problems
    assert any(p.startswith("Variables: found ") and p.endswith(
        "Supply variables as a list of Summary column names, such as ['HWAM'].") for p in exc.value.problems)


def test_to_dataframe_round_trip():
    pd = pytest.importorskip("pandas")
    rows = [
        {"TRNO": 1, "HWAM": 1000},
        {"TRNO": 1, "HWAM": 2000},
    ]
    summary = lab.summarize_seasons(rows)
    df = lab.to_dataframe(summary)
    assert isinstance(df, pd.DataFrame)
    expected_columns = ["scenario", "treatment", "component", "crop", "variable", "seasons", "missing",
                        "mean", "sd", "min", "p25", "median", "p75", "max"]
    assert list(df.columns) == expected_columns
    assert df["scenario"].tolist() == ["base"]
    assert df["treatment"].tolist() == [1]
    assert df["variable"].tolist() == ["HWAM"]
    assert df["seasons"].tolist() == [2]
    assert df["missing"].tolist() == [0]
    assert df["mean"].tolist() == [1500]
    assert df["min"].tolist() == [1000]
    assert df["max"].tolist() == [2000]


def test_non_numeric_reported_once_per_group():
    rows = [{"TRNO": 1, "TNAM": "Low N"}, {"TRNO": 1, "TNAM": "Low N"}, {"TRNO": 2, "TNAM": "High N"}]
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.summarize_seasons(rows, variables=["TNAM"])
    assert exc.value.problems == [
        "Variable 'TNAM' has a non-numeric value 'Low N' (scenario 'base', treatment 1). "
        "Choose a numeric Summary column.",
        "Variable 'TNAM' has a non-numeric value 'High N' (scenario 'base', treatment 2). "
        "Choose a numeric Summary column."]
