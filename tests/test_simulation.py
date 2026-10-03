"""Weather checks through the public Simulation and weather template."""
import csv
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

import dssatlab


@pytest.fixture
def rows():
    return [dict(station="AB12", latitude=45, longitude=-100, elevation=200,
                 date=day, srad=20, tmax=25, tmin=10, rain=0)
            for day in ("2021-03-01", "2021-03-02", "2021-03-03")]


def check(weather):
    problems = dssatlab.Simulation("missing.MZX", 1, weather).check()
    # These tests isolate weather checks; ticket #14 also reports the absent FileX.
    filex_problems = [p for p in problems if p.startswith("Cannot read FileX ")]
    assert len(filex_problems) == 1
    return [p for p in problems if p not in filex_problems]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("form", ["rows", "csv"])
@pytest.mark.parametrize("values,empty", [
    ([50, None, ""], 2), ([None, "", "  "], 3),
])
def test_empty_par_is_one_column_problem(tmp_path, rows, form, values, empty):
    for row, value in zip(rows, values):
        row["par"] = value
    source = rows if form == "rows" else write_csv(tmp_path / "weather.csv", rows)
    assert check(source) == [
        f"Weather column 'par' is empty on {empty} rows. "
        "Supply par on every row or drop the column."
    ]


@pytest.mark.parametrize("filled_row", [0, 2])
def test_missing_par_keys_are_counted(rows, filled_row):
    rows[filled_row]["par"] = 50
    assert check(rows) == [
        "Weather column 'par' is empty on 2 rows. "
        "Supply par on every row or drop the column."
    ]


@pytest.mark.parametrize("value", [0, 100])
def test_par_inclusive_boundaries_pass(rows, value):
    assert check([dict(row, par=value) for row in rows]) == []


@pytest.mark.parametrize("value,reason", [
    (100.1, "0 to 100"), (-0.1, "0 to 100"),
    (float("nan"), "finite number"), (float("inf"), "finite number"),
    ("nan", "finite number"), ("inf", "finite number"),
])
def test_invalid_par_is_rejected(tmp_path, rows, value, reason):
    rows = [dict(row, par=50) for row in rows]
    rows[1]["par"] = value
    for source in (rows, write_csv(tmp_path / "weather.csv", rows)):
        problems = check(source)
        assert len(problems) == 1
        assert "row 3" in problems[0] and "'par'" in problems[0]
        assert reason in problems[0] and "mol/m2 per day" in problems[0]


def test_construction_stores_inputs_without_work(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("construction must not access files")

    monkeypatch.setattr(Path, "open", forbidden)
    filex, treatment, weather = tmp_path / "absent.MZX", object(), object()
    simulation = dssatlab.Simulation(filex, treatment, weather)
    assert simulation.filex is filex
    assert simulation.treatment is treatment
    assert simulation.weather is weather
    assert simulation.check()
    with pytest.raises(dssatlab.DSSATCheckError, match="exactly one"):
        dssatlab.Simulation(None, None, None).check()


@pytest.mark.parametrize("form", ["rows", "path", "str"])
def test_valid_weather_is_unchanged_and_checks_write_nothing(tmp_path, rows, form):
    path = write_csv(tmp_path / "weather.csv", rows)
    weather = {"rows": rows, "path": path, "str": str(path)}[form]
    before_rows, before_bytes = deepcopy(rows), path.read_bytes()
    before = sorted(tmp_path.rglob("*"))
    assert check(weather) == []
    assert rows == before_rows
    assert path.read_bytes() == before_bytes
    assert sorted(tmp_path.rglob("*")) == before


def test_csv_saved_by_excel_with_a_byte_order_mark_is_accepted(tmp_path, rows):
    path = write_csv(tmp_path / "weather.csv", rows)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())  # "CSV UTF-8" from Excel
    assert check(path) == []


def test_column_order_and_numeric_strings(tmp_path, rows):
    rows = [dict(reversed([(key, str(value)) for key, value in row.items()]))
            for row in rows]
    assert check(rows) == []
    assert check(write_csv(tmp_path / "weather.csv", rows)) == []


@pytest.mark.parametrize("column", ["station", "latitude", "longitude", "elevation",
                                    "date", "srad", "tmax", "tmin", "rain"])
def test_missing_columns_named(rows, column):
    for row in rows:
        del row[column]
    assert any("missing" in p.lower() and column in p for p in check(rows))


def test_unknown_and_wrong_case_columns_named(tmp_path, rows):
    for row in rows:
        row["Date"] = row.pop("date")
        row["humidity"] = 50
    problems = check(write_csv(tmp_path / "weather.csv", rows))
    assert any("missing" in p.lower() and "'date'" in p for p in problems)
    assert any("unknown" in p.lower() and "Date" in p for p in problems)
    assert any("humidity" in p and "valid" in p.lower() for p in problems)


@pytest.mark.parametrize("column", ["latitude", "longitude", "elevation", "srad",
                                    "tmax", "tmin", "rain"])
@pytest.mark.parametrize("value", ["", None, "oops", "nan", float("inf"), "-inf"])
def test_invalid_numbers_report_column_row_and_action(rows, column, value):
    rows[1][column] = value
    assert any(column in p and "row 3" in p and "finite number" in p
               for p in check(rows))


@pytest.mark.parametrize("column,low,high,unit", [
    ("srad", 0, 45, "MJ/m2 per day"), ("tmax", -60, 60, "degrees C"),
    ("tmin", -60, 60, "degrees C"), ("rain", 0, 1000, "mm"),
    ("latitude", -90, 90, "degrees"), ("longitude", -180, 180, "degrees"),
    ("elevation", -500, 9000, "m"),
])
def test_ranges_reject_outside_and_accept_boundaries(rows, column, low, high, unit):
    for value in (low - 1, high + 1):
        bad = deepcopy(rows[:1])
        bad[0][column] = value
        assert any(column in p and "row 2" in p and str(value) in p
                   and f"{low} to {high}" in p and unit in p for p in check(bad))
    for value in (low, high):
        good = deepcopy(rows[:1])
        good[0][column] = value
        if column in ("tmax", "tmin"):
            good[0]["tmax"] = good[0]["tmin"] = value
        assert check(good) == []


@pytest.mark.parametrize("value", ["20210302", "2021-W09-2", "2021-3-02",
                                   "2021-02-30", "2021-02-29", "", None,
                                   "2021-03-02T00:00:00", " 2021-03-02", 20210302])
def test_invalid_dates(rows, value):
    rows[1]["date"] = value
    assert any("date" in p and "row 3" in p and "YYYY-MM-DD" in p for p in check(rows))


@pytest.mark.parametrize("days", [("2020-02-28", "2020-02-29", "2020-03-01"),
                                  ("2020-12-31", "2021-01-01", "2021-01-02")])
def test_valid_leap_day_and_multiple_years(rows, days):
    for row, day in zip(rows, days):
        row["date"] = day
    assert check(rows) == []


def test_date_order_duplicates_and_missing_ranges(rows):
    days = ["2021-03-10", "2021-03-04", "2021-03-04", "2021-03-02"]
    weather = [dict(rows[0], date=day) for day in days]
    problems = check(weather)
    assert sum("ascending" in p for p in problems) == 1
    assert any("row 3" in p and "ascending" in p for p in problems)
    assert any("duplicate" in p.lower() and "2021-03-04" in p
               and "rows 3 and 4" in p for p in problems)
    assert any("missing dates 2021-03-05 to 2021-03-09" in p for p in problems)
    assert any("missing date 2021-03-03" in p for p in problems)
    assert [row["date"] for row in weather] == days


def test_tmax_below_tmin(rows):
    rows[1]["tmax"] = 9
    assert any("row 3" in p and "tmax" in p and "tmin" in p for p in check(rows))
    rows[1]["tmax"] = 10
    assert check(rows) == []


@pytest.mark.parametrize("station", ["ABC", "ABCDE", "AB/C", "AB C", "éBCD", 1234, None])
def test_station_characters(rows, station):
    rows[0]["station"] = station
    assert any("station" in p and "row 2" in p and "four" in p for p in check(rows))


@pytest.mark.parametrize("column,value", [("station", "XY99"), ("latitude", 46),
                                          ("longitude", -99), ("elevation", 201)])
def test_station_metadata_must_be_identical(rows, column, value):
    rows[1][column] = value
    assert any(column in p and "row 3" in p and "identical" in p for p in check(rows))


@pytest.mark.parametrize("column", ["tav", "amp", "refht", "wndht"])
def test_optional_numbers_and_defaults(rows, column):
    for value in ("", None, "   ", -99, 10000, "-12345"):
        for row in rows:
            row[column] = value
        assert check(rows) == []
    for value in ("oops", "nan", "inf"):
        rows[1][column] = value
        assert any(column in p and "row 3" in p and "finite number" in p
                   for p in check(rows))


@pytest.mark.parametrize("weather", [None, 42, {}, (), [None], [42], []])
def test_unsupported_or_empty_weather_returns_problems(weather):
    assert check(weather)


@pytest.mark.parametrize("content", [b"\xff", b'"unclosed', b"", b"station,date\n"])
def test_unreadable_or_empty_csv(tmp_path, content):
    path = tmp_path / "weather.csv"
    assert len(check(path)) == 1
    path.write_bytes(content)
    assert check(path)
    if content == b"\xff":
        assert len(check(path)) == 1
        assert "UTF-8" in check(path)[0]


def test_bad_rows_and_csv_column_counts(tmp_path, rows):
    broken = deepcopy(rows)
    del broken[1]["rain"]
    broken[2]["extra"] = 1
    assert any("rain" in p and "row 3" in p for p in check(broken))
    assert any("extra" in p and "row 4" in p for p in check(broken))
    path = write_csv(tmp_path / "weather.csv", rows)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("too,many,fields,1,2,3,4,5,6,7\n")
    assert any("row 5" in p and "columns" in p for p in check(path))


def test_multiple_kinds_report_every_problem(rows):
    weather = [dict(rows[0], date=(date(2021, 1, 1) + timedelta(days=i)).isoformat(),
                    rain=-1, srad="bad") for i in range(47)]
    problems = check(weather)
    assert sum("rain" in p and "row " in p for p in problems) == 47
    assert sum("srad" in p and "row " in p for p in problems) == 47
    assert len(problems) == 94


def test_write_weather_template_passes_and_never_overwrites(tmp_path):
    path = tmp_path / "weather.csv"
    dssatlab.write_weather_template(path)
    original = path.read_bytes()
    assert check(path) == []
    with path.open(encoding="utf-8", newline="") as stream:
        example = list(csv.DictReader(stream))
    assert len(example) == 7
    assert set(example[0]) == {"station", "latitude", "longitude", "elevation",
                               "date", "srad", "tmax", "tmin", "rain",
                               "tav", "amp", "refht", "wndht"}
    with pytest.raises(dssatlab.DSSATError, match="exists.*another path"):
        dssatlab.write_weather_template(str(path))
    assert path.read_bytes() == original


def test_check_error_lists_every_problem():
    problems = ["rain is negative", "date is missing"]
    error = dssatlab.DSSATCheckError(problems)
    assert isinstance(error, dssatlab.DSSATError)
    assert error.problems == problems
    assert "2" in str(error).splitlines()[0]
    assert str(error).splitlines()[1:] == problems


def test_template_rejects_existing_directory(tmp_path):
    with pytest.raises(dssatlab.DSSATError, match="exists.*another path"):
        dssatlab.write_weather_template(tmp_path)


def test_bad_weather_checks_write_nothing(tmp_path, rows):
    rows[1]["rain"] = -1
    path = write_csv(tmp_path / "weather.csv", rows)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert check(path)
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    assert sorted(tmp_path.rglob("*")) == [path]


def test_duplicate_headers_and_physical_csv_lines(tmp_path, rows):
    path = write_csv(tmp_path / "weather.csv", rows)
    text = path.read_text(encoding="utf-8")
    header, *records = text.splitlines()
    path.write_text(header + ",rain\n" + "\n".join(r + ",0" for r in records),
                    encoding="utf-8")
    assert any("rain" in p and "repeated" in p and "line 1" in p for p in check(path))
    path.write_text(text.replace("AB12,45", '"AB\n12",45', 1)
                    .replace("2021-03-02", "bad-date"), encoding="utf-8")
    assert any("date" in p and "row 4" in p for p in check(path))


@pytest.mark.parametrize("kind", ["date", "duplicate", "gap"])
def test_every_date_problem_is_reported(rows, kind):
    days = [(date(2021, 1, 1) + timedelta(days=2 * i)).isoformat() for i in range(48)]
    if kind == "date":
        days = ["bad"] * 47
    elif kind == "duplicate":
        days = ["2021-01-01"] * 48
    problems = check([dict(rows[0], date=day) for day in days])
    assert len(problems) >= 47
    assert not any("more rows" in p for p in problems)


@pytest.mark.parametrize("column", ["rain", "station", "date", "unknown"])
def test_unrepresentable_integer_returns_problem(rows, column):
    value = 10 ** 5000
    if column == "unknown":
        rows[0][value] = 1
    else:
        rows[0][column] = value
    assert any("row 2" in p and column in p for p in check(rows))


def test_parse_sdate_and_simulation_start_date():
    from dssatlab.sequence import _parse_sdate, _simulation_start_date

    assert _parse_sdate("82056") == (82, 56)
    assert _parse_sdate("00001") == (0, 1)
    assert _parse_sdate("82000") == (82, 0)
    assert _parse_sdate("bad") is None
    assert _parse_sdate("1234") is None
    assert _parse_sdate("123456") is None
    assert _parse_sdate(12345) is None

    sdate = "82056"
    days_unique = [date(1982, 2, 25)]
    d, reason = _simulation_start_date(sdate, days_unique)
    assert d == date(1982, 2, 25)
    assert reason is None

    d, reason = _simulation_start_date(sdate, [])
    assert d == date(1982, 2, 25)
    assert reason is None

    d, reason = _simulation_start_date(sdate, [date(1982, 1, 1), date(2082, 1, 1)])
    assert d == date(1982, 2, 25)
    assert reason is None

    d, reason = _simulation_start_date(sdate, [date(1990, 1, 1)])
    assert d == date(1982, 2, 25)
    assert reason is None

    d, reason = _simulation_start_date(None, days_unique)
    assert d is None
    assert "START is not S" in reason
