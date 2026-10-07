"""Observed data behaviour for ticket #94, without running DSSAT."""

import builtins
from copy import deepcopy
import csv
from datetime import date
from pathlib import Path

import pytest

import dssatlab
from dssatlab import DSSATCheckError, DSSATError, write_observed_template
from dssatlab.observed import _load_observed


def checked_rows(source):
    rows, problems = _load_observed(source)
    if problems:
        raise DSSATCheckError(problems)
    return rows


def write_csv(tmp_path, text):
    path = tmp_path / "observed.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_filled_template_loads_and_passes_checks(tmp_path):
    path = tmp_path / "observed.csv"
    write_observed_template(path)
    text = path.read_text(encoding="utf-8")
    assert "write_observed_template" in dssatlab.__all__
    assert text.startswith("#")
    assert '"base"' in text and "yyyy-mm-dd" in text
    assert "no conversion" in text and "ADAT/MDAT" in text
    for units in ("HWAM/CWAM/CWAD: kg[dm]/ha", "LAID: m2/m2", "ADAT/MDAT: yyyy-mm-dd"):
        assert units in text
    # Keep the template's comments and header; fill in the user's measurements.
    lines = text.splitlines(keepends=True)
    header = next(line for line in lines if not line.startswith("#"))
    path.write_text("".join(line for line in lines if line.startswith("#")) + header
                    + "base,1,,7200,2024-02-29,2024-09-01,14000,,\n"
                    + "base,1,2024-06-01,,,,,3.2,4500\n", encoding="utf-8")
    rows = checked_rows(path)
    assert rows == [dict(scenario="base", treatment=1, date=None, HWAM=7200,
                         ADAT=date(2024, 2, 29), MDAT=date(2024, 9, 1), CWAM=14000),
                    dict(scenario="base", treatment=1, date=date(2024, 6, 1), LAID=3.2, CWAD=4500)]


def test_template_examples_are_valid_and_existing_file_is_preserved(tmp_path):
    path = tmp_path / "observed.csv"
    write_observed_template(str(path))
    before = path.read_bytes()
    assert checked_rows(str(path))
    with pytest.raises(DSSATError, match="already exists"):
        write_observed_template(path)
    assert path.read_bytes() == before


def test_date_column_is_optional_and_scenario_names_are_preserved(tmp_path):
    path = write_csv(tmp_path, '\ufeff# measurements\nscenario,treatment,HWAM\n'
                     '"dry, hot",01,7.2e3\nbase,2,0\n')
    assert checked_rows(path) == [dict(scenario="dry, hot", treatment=1, date=None, HWAM=7200),
                                   dict(scenario="base", treatment=2, date=None, HWAM=0)]


@pytest.mark.parametrize("name", ["SDAT", "PDAT", "EDAT", "ADAT", "MDAT", "HDAT"])
def test_all_summary_dates_are_normalized(tmp_path, name):
    value = "2024-02-29"
    rows = checked_rows(write_csv(tmp_path, f"scenario,treatment,{name}\nbase,1,{value}\n"))
    assert rows[0][name] == date(2024, 2, 29)


def test_all_check_problems_are_reported_together_without_mutation():
    rows = [dict(scenario="", treatment="", HWAM="oops", ADAT="2023-02-29", typo=10),
            dict(scenario="base", treatment=1, date="2024-02-30", LAID="bad"),
            dict(scenario="base", treatment=1, HWAM=1),
            dict(scenario="base", treatment="01", date="", HWAM=2)]
    before = deepcopy(rows)
    with pytest.raises(DSSATCheckError) as caught:
        checked_rows(rows)
    message = str(caught.value)
    for expected in ("scenario", "treatment", "non-numeric", "HWAM", "ADAT",
                     "typo", "Summary columns:", "LAID", "bad date", "duplicate"):
        assert expected in message
    assert len(caught.value.problems) >= 8
    assert rows == before


def test_missing_key_header_stops_loading(tmp_path):
    path = write_csv(tmp_path, "treatment,HWAM\n1,2\n")
    with pytest.raises(DSSATCheckError, match="missing 'scenario'"):
        checked_rows(path)


def test_loading_aggregates_header_shape_and_cell_problems(tmp_path):
    path = write_csv(tmp_path, "scenario,treatment,HWAM,HWAM,typo\n"
                     "base,x,1,oops,5,extra\nbase,1,2,3,4\nbase,1,2,3,4\n")
    with pytest.raises(DSSATCheckError) as caught:
        checked_rows(path)
    for expected in ("repeated column", "values for", "typo", "non-numeric", "invalid treatment"):
        assert expected in str(caught.value)


@pytest.mark.parametrize("day,wrong,valid", [(None, "LAID", "HWAM"),
                                             ("2024-06-01", "HWAM", "LAID")])
def test_variable_names_depend_on_output(day, wrong, valid):
    with pytest.raises(DSSATCheckError) as caught:
        checked_rows([dict(scenario="base", treatment=1, date=day, **{wrong: 5})])
    problem = caught.value.problems[0]
    assert f"variable '{wrong}' is not a" in problem
    allowed = problem.split("Valid names: ")[1].split(". Use")[0].split(", ")
    assert valid in allowed and wrong not in allowed


@pytest.mark.parametrize("column", ["date", "ADAT"])
@pytest.mark.parametrize("value", ["2023-02-29", "2024-2-01", "01/02/2024", "24060",
                                  "2024060", 2024060, "2024000", "2023366", "2024367", "2024-02-29T00:00:00"])
def test_bad_dates_are_check_problems(column, value):
    row = dict(scenario="base", treatment=1, **{column: value})
    row["LAID" if column == "date" else "HWAM"] = 1
    with pytest.raises(DSSATCheckError, match="bad date"):
        checked_rows([row])


def test_duplicate_daily_keys_are_normalized_but_other_keys_are_distinct(tmp_path):
    path = write_csv(tmp_path, "scenario,treatment,date,LAID\n"
                     "base,1,2024-02-29,1\nbase,01,2024-02-29,2\n")
    with pytest.raises(DSSATCheckError, match="duplicate scenario\\+treatment\\+date"):
        checked_rows(path)
    rows = [dict(scenario="base", treatment=1, date="2024-02-29", LAID=1),
            dict(scenario="base", treatment=1, date="2024-03-01", LAID=2),
            dict(scenario="dry", treatment=1, date="2024-02-29", LAID=3),
            dict(scenario="base", treatment=2, date="2024-02-29", LAID=4),
            dict(scenario="base", treatment=1, HWAM=5)]
    assert len(checked_rows(rows)) == 5


@pytest.mark.parametrize("value", ["bad", "nan", "inf", float("nan"), float("inf"), True])
def test_measurements_must_be_finite_numbers(value):
    with pytest.raises(DSSATCheckError, match="finite number"):
        checked_rows([dict(scenario="base", treatment=1, HWAM=value)])


@pytest.mark.parametrize("column", ["HWAM", "ADAT"])
@pytest.mark.parametrize("value", [-99, "-99.0"])
def test_explicit_missing_values_are_check_problems(column, value):
    with pytest.raises(DSSATCheckError, match="missing measurement"):
        checked_rows([dict(scenario="base", treatment=1, **{column: value})])


@pytest.mark.parametrize("value", [None, "", 0, -1, 1.5, True, [], "x"])
def test_treatment_requires_a_positive_integer(value):
    with pytest.raises(DSSATCheckError, match="treatment"):
        checked_rows([dict(scenario="base", treatment=value, HWAM=10)])


@pytest.mark.parametrize("rows", [[], {}, [None], [dict(HWAM=1)],
                                  [dict(scenario="base", treatment=1, HWAM="")]])
def test_empty_malformed_and_missing_key_rows_raise_check_error(rows):
    with pytest.raises(DSSATCheckError):
        checked_rows(rows)


@pytest.mark.parametrize("text", ["", "# comments only\n", "scenario,treatment,HWAM\n",
                                  'scenario,treatment,HWAM\nbase,1,"unterminated\n'])
def test_unusable_csv_raises_check_error(tmp_path, text):
    with pytest.raises(DSSATCheckError):
        checked_rows(write_csv(tmp_path, text))


def test_missing_file_and_wrong_source_raise_check_error(tmp_path):
    for source in (tmp_path / "absent.csv", object(), []):
        with pytest.raises(DSSATCheckError, match="Cannot read observed data"):
            checked_rows(source)


def test_csv_and_checks_do_not_import_pandas(tmp_path, monkeypatch):
    original = builtins.__import__

    def without_pandas(name, *args, **kwargs):
        if name.split(".")[0] == "pandas":
            raise AssertionError("pandas must not be imported for CSV input")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_pandas)
    path = tmp_path / "observed.csv"
    write_observed_template(path)
    assert checked_rows(path)


def test_real_dataframe_matches_csv_without_mutation(tmp_path):
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame([dict(scenario="base", treatment=1, HWAM=6000, ADAT="2024-02-29"),
                          dict(scenario="base", treatment=1, date="2024-06-01", LAID=2.5)])
    frame["MDAT"] = pd.Series([pd.NA, pd.NA], dtype="string")
    before = frame.copy(deep=True)
    path = tmp_path / "observed.csv"
    frame.to_csv(path, index=False)
    assert checked_rows(frame) == checked_rows(path)
    pd.testing.assert_frame_equal(frame, before)


def test_dataframe_reports_all_invalid_cells():
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame([dict(scenario=pd.NA, treatment=None, HWAM="oops"),
                          dict(scenario="base", treatment=1, date="bad", LAID=-99)])
    with pytest.raises(DSSATCheckError) as caught:
        checked_rows(frame)
    for expected in ("scenario", "treatment", "non-numeric", "bad date", "missing measurement"):
        assert expected in str(caught.value)


@pytest.mark.parametrize("crop", ["maize", "wheat"])
def test_numeric_columns_from_known_output_fixtures_are_accepted(tmp_path, crop):
    root = Path(__file__).parent / "fixtures" / "output_files"
    summary = dssatlab.read_summary(root / "summary" / crop)[0]
    growth = dssatlab.read_plant_growth(root / "plant_growth" / crop)[0]
    for output, daily in ((summary, False), (growth, True)):
        values = {name: value.isoformat() if isinstance(value, date) else value
                  for name, value in output.items()
                  if isinstance(value, (int, float, date)) and name != "DATE"}
        row = dict(scenario="base", treatment=1, **values)
        if daily:
            row["date"] = output["DATE"].isoformat()
        path = tmp_path / "observed.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        assert checked_rows(path)
