"""Stock weather reads preserve DSSAT's spans and weather calendar rule."""

from datetime import date
from pathlib import Path

import pytest

from dssatlab.weather_files import _read_stock_weather, _walk_weather_files
from dssatlab.weather import _parse_weather


def test_stock_weather_term_describes_copy_and_checked_daily_columns():
    text = (Path(__file__).parents[1] / "CONTEXT.md").read_text(encoding="utf-8")
    term = text.split("**Stock weather file**:")[1].split("**Daily PAR**:")[0]
    assert "under its upper-case name" in term
    assert "srad, tmax, tmin and rain" in term


def read(source, start=date(1976, 1, 1)):
    return _read_stock_weather(source, start)


def weather_file(tmp_path, name="UFGA7601.WTH", codes=("76001",), *,
                 wide=False, par=True):
    path = tmp_path / name
    label = "@  DATE" if wide else "@DATE"
    # Adjacent signed station values and reordered daily columns defeat split().
    header = label + "   RAIN  DEWP   TMIN   SRAD   TMAX" + ("    PAR" if par else "")
    lines = [
        ("$WEATHER" if wide else "*WEATHER DATA") + " : a small test fixture", "",
        "@ INSI      LONG      LAT  ELEV   TAV",
        "  XXXX   -82.370   29.630    10 -99.0", header,
    ]
    for code in codes:
        lines.append(code + "    0.0 junk!   15.0  20.0N   25.0" + ("  50.0N" if par else ""))
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def test_reader_needs_only_source_and_start_date(tmp_path):
    path = weather_file(tmp_path, 'UFGA4001.WTH', ('1940069', '1940070'), wide=True)
    before = path.read_bytes()
    rows, problems = _read_stock_weather(path, date(1940, 3, 9))
    assert problems == []
    assert [row['date'] for row in rows] == [date(1940, 3, 9), date(1940, 3, 10)]
    assert path.read_bytes() == before


@pytest.mark.parametrize("wide,code,start", [
    (False, "76001", date(1976, 1, 1)),
    (True, "1976001", date(2076, 1, 1)),
])
def test_header_spans_flags_and_ignored_columns(tmp_path, wide, code, start):
    path = weather_file(tmp_path, name="ufga7601.wth", wide=wide, codes=(code,))
    before = path.read_bytes()
    rows, problems = read(str(path), start=start)
    assert problems == []
    assert rows == [dict(station="UFGA", longitude=-82.370, latitude=29.630,
                         elevation=10.0, date=date(1976, 1, 1), rain=0.0,
                         tmin=15.0, srad=20.0, tmax=25.0)]
    assert _parse_weather(rows)[1] == []
    assert path.read_bytes() == before


def test_adjacent_numeric_values_are_read_by_spans(tmp_path):
    path = tmp_path / "UFGA.WTH"
    path.write_text(
        "@ INSI      LAT     LONG  ELEV\n"
        "  UFGA  -90.000 -180.000  -500\n"
        "@DATE  SRAD  TMAX  TMIN   RAIN\n"
        "76001  20.0 -10.0 -60.0N1000.0\n", encoding="ascii")
    rows, problems = read(path)
    assert problems == []
    assert rows[0] == dict(station="UFGA", latitude=-90.0, longitude=-180.0,
                           elevation=-500.0, date=date(1976, 1, 1),
                           srad=20.0, tmax=-10.0, tmin=-60.0, rain=1000.0)
    assert _parse_weather(rows)[1] == []


@pytest.mark.parametrize("codes,start,expected", [
    (("99365", "00001"), date(1999, 12, 31),
     [date(1999, 12, 31), date(2000, 1, 1)]),
    (("99365", "00001"), date(2099, 12, 31),
     [date(2099, 12, 31), date(2100, 1, 1)]),
    (("00059", "00060", "00061"), date(2000, 2, 28),
     [date(2000, 2, 28), date(2000, 2, 29), date(2000, 3, 1)]),
    (("40001", "40002"), date(1940, 1, 1),
     [date(1940, 1, 1), date(1940, 1, 2)]),
    (("41001", "41002"), date(2041, 1, 1),
     [date(2041, 1, 1), date(2041, 1, 2)]),
])
def test_five_digit_dates_use_weather_century(tmp_path, codes, start, expected):
    path = weather_file(tmp_path, "UFGA.WTH", codes)
    rows, problems = read(path, start=start)
    assert problems == []
    assert [row["date"] for row in rows] == expected
    assert _parse_weather(rows)[1] == []


@pytest.mark.parametrize("wide,code,start", [
    (False, "00000", date(2000, 1, 1)),
    (False, "01366", date(2001, 1, 1)),
    (False, "00366", date(2101, 1, 1)),
    (True, "2001366", date(2001, 1, 1)),
    (True, "xxxxxxx", date(2001, 1, 1)),
])
def test_invalid_weather_date_is_one_file_problem(tmp_path, wide, code, start):
    path = weather_file(tmp_path, "UFGA.WTH", (code,), wide=wide)
    rows, problems = read(path, start=start)
    assert len(problems) == 1
    assert all(value in problems[0] for value in (str(path), code, "date", "Supply"))
    assert rows == []


def test_files_keep_given_order_and_duplicates_for_existing_checks(tmp_path):
    first = weather_file(tmp_path, "UFGA7601.WTH", ("76366",))
    second = weather_file(tmp_path, "UFGA7701.WTH", ("76366", "77001"))
    rows, problems = read([first, second], start=date(1976, 12, 31))
    assert problems == []
    assert [row["date"] for row in rows] == [date(1976, 12, 31),
                                            date(1976, 12, 31), date(1977, 1, 1)]
    checks = _parse_weather(rows)[1]
    assert len(checks) == 1
    assert "duplicate date 1976-12-31" in checks[0]
    rows, problems = read([second, first], start=date(1976, 12, 31))
    assert problems == []
    assert [row["date"] for row in rows] == [date(1976, 12, 31),
                                            date(1977, 1, 1), date(1976, 12, 31)]


def test_century_carries_across_yearly_files(tmp_path):
    first = weather_file(tmp_path, "UFGA9901.WTH", ("99365",))
    second = weather_file(tmp_path, "UFGA0001.WTH", ("00001",))
    rows, problems = read([first, second], start=date(1999, 12, 31))
    assert problems == []
    assert [row["date"] for row in rows] == [date(1999, 12, 31), date(2000, 1, 1)]


@pytest.mark.parametrize("name", [
    "UFGA7601.WTH", "UFGA7701.WTH", "ufga.wth", "UFGA7609.WTH", "UFGA.WTH",
])
def test_reader_decodes_names_before_selection(tmp_path, name):
    path = weather_file(tmp_path, name, par=False)
    rows, problems = read(path)
    assert problems == []
    assert "par" not in rows[0]


@pytest.mark.parametrize("name,station,expected", [
    ("UFGA7609.WTH", "UFGA", "UFGA7601.WTH"),
    ("UFGA7801.WTH", "UFGA", "UFGA7601.WTH"),
    ("OTHER.WTH", "UFGA7609", "UFGA7609.WTH"),
])
def test_wrong_name_reports_file_and_requested_name_once(tmp_path, name, station, expected):
    path = weather_file(tmp_path, name)
    _, problems, _ = _walk_weather_files([path], station, "76001", date(1976, 1, 1), date(1976, 1, 1))
    assert len(problems) == 1
    assert all(value in problems[0] for value in (name, expected, "Checked", "Supply"))


def test_uppercase_name_collision_in_two_folders_is_one_problem(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    first = weather_file(a, "ufga7601.wth")
    second = weather_file(b, "UFGA7601.WTH")
    _, problems = read([first, second])
    assert len(problems) == 1
    assert all(value in problems[0] for value in (str(first), str(second), "UFGA7601.WTH", "Supply"))


@pytest.mark.parametrize("column", ["LAT", "LONG", "ELEV", "SRAD", "TMAX", "TMIN", "RAIN"])
def test_missing_required_column_is_one_file_problem(tmp_path, column):
    path = weather_file(tmp_path)
    # Keep other spans unchanged so only this column is missing.
    path.write_text(path.read_text().replace(column, "X" * len(column)))
    rows, problems = read(path)
    assert rows == []
    assert len(problems) == 1
    assert all(value in problems[0] for value in (str(path), column, "missing", "Supply"))


def test_missing_file_is_one_problem(tmp_path):
    path = tmp_path / "UFGA7601.WTH"
    rows, problems = read(path)
    assert rows == []
    assert len(problems) == 1
    assert str(path) in problems[0] and "read" in problems[0] and "Supply" in problems[0]


def test_required_missing_value_is_left_for_weather_checks(tmp_path):
    path = weather_file(tmp_path)
    path.write_text(path.read_text().replace("  20.0N", "  -99.0"))
    rows, problems = read(path)
    assert problems == []
    checks = _parse_weather(rows)[1]
    assert len(checks) == 1
    assert "srad" in checks[0] and "allowed range" in checks[0]


def test_initial_record_before_century_boundary_covers_start(tmp_path):
    path = weather_file(tmp_path, "UFGA.WTH", ("99365", "00001", "00002"))
    rows, problems = read(path, start=date(2000, 1, 1))
    assert problems == []
    assert [row["date"] for row in rows] == [date(1999, 12, 31),
                                           date(2000, 1, 1), date(2000, 1, 2)]
    assert _parse_weather(rows)[1] == []


def test_ccpa_flags_in_separator_columns(tmp_path):
    path = tmp_path / "CCPA8001.WTH"
    path.write_text(
        "@ INSI      LAT     LONG  ELEV\n"
        "  CCPA   10.000  -85.000    10\n"
        "@DATE  SRAD  TMAX  TMIN  RAIN\n"
        "80001  19.8N 29.1N 19.0N  0.0N\n", encoding="ascii")
    rows, problems = read(path, start=date(1980, 1, 1))
    assert problems == []
    assert rows[0] == dict(station="CCPA", latitude=10.0, longitude=-85.0,
                           elevation=10.0, date=date(1980, 1, 1),
                           srad=19.8, tmax=29.1, tmin=19.0, rain=0.0)
    assert _parse_weather(rows)[1] == []


@pytest.mark.parametrize("marker,wide,rejected", [
    ("*WEATHER DATA", True, True), ("$WEATHER", True, False),
    ("$WEATHER", False, True), ("*WEATHER DATA", False, False),
])
def test_weather_marker_matches_date_width(tmp_path, marker, wide, rejected):
    path = weather_file(tmp_path, wide=wide, codes=("1976001" if wide else "76001",))
    text = path.read_text()
    path.write_text(marker + text[text.index(" :"):], encoding="ascii")
    rows, problems = read(path)
    assert len(problems) == int(rejected)
    if rejected:
        assert rows == []
        assert all(part in problems[0] for part in (str(path), "DATE", "$WEATHER", "Supply"))
    else:
        assert rows[0]["date"] == date(1976, 1, 1)
