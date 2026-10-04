"""Stock weather structure is checked before dates follow DSSAT's selection."""

import pytest

from test_simulation_run import fake_dssat
from test_simulation_stock_weather import stock_file
from test_stock_weather import weather_file
from test_weather_selection import days, period


@pytest.mark.parametrize("reverse", [False, True])
def test_stock_century_rollover_passes_in_both_list_orders(tmp_path, fake_dssat, reverse):
    sim = period(tmp_path, "99365", "00366")
    sim.executable = fake_dssat.executable
    first = stock_file(tmp_path, "UFGA9901.WTH", days=days("1999-12-31", "1999-12-31"))
    second = stock_file(tmp_path, "UFGA0001.WTH", days=days("2000-01-01", "2000-12-31"))
    sim.weather = [second, first] if reverse else [first, second]
    assert sim.check(False) == []


def test_stock_preliminary_read_ignores_unselected_dates(tmp_path, fake_dssat):
    sim = period(tmp_path, "82055", "82057")
    sim.executable = fake_dssat.executable
    selected = stock_file(tmp_path, "UFGA8201.WTH")
    unused = weather_file(tmp_path, "UFGA0001.WTH", ("xxxxx", "00366"))
    sim.weather = [unused, selected]
    assert sim.check(False) == []


def test_stock_preliminary_read_keeps_uppercase_collision_message(tmp_path, fake_dssat):
    sim = period(tmp_path, "82055", "82057")
    sim.executable = fake_dssat.executable
    other = tmp_path / "other"
    other.mkdir()
    first = stock_file(tmp_path, "ufga8201.wth")
    second = stock_file(other, "UFGA8201.WTH")
    sim.weather = [first, second]
    assert sim.check(False) == [
        f"Stock weather files {first} and {second} have the same file name UFGA8201.WTH "
        "after upper-casing. Supply only one file with each name for the simulation folder."
    ]


def test_stock_preliminary_read_keeps_unreadable_message(tmp_path, fake_dssat):
    sim = period(tmp_path, "82055", "82057")
    sim.executable = fake_dssat.executable
    missing = tmp_path / "UFGA0001.WTH"
    sim.weather = [stock_file(tmp_path, "UFGA8201.WTH"), missing]
    problems = sim.check(False)
    assert len(problems) == 1
    assert problems[0].startswith(f"Cannot read stock weather file {missing}: ")
    assert problems[0].endswith(". Supply a readable stock weather file path.")


@pytest.mark.parametrize("problem", ["header", "width"])
def test_stock_preliminary_read_checks_unselected_structure(tmp_path, fake_dssat, problem):
    sim = period(tmp_path, "82055", "82057")
    sim.executable = fake_dssat.executable
    unused = weather_file(tmp_path, "UFGA0001.WTH", ("xxxxx",))
    text = unused.read_text()
    if problem == "header":
        unused.write_text(text.replace("TMAX", "XXXX"))
        expected = (f"Stock weather file {unused}: missing required column TMAX. "
                    "Supply a stock weather file with column TMAX.")
    else:
        unused.write_text(text.replace("@DATE", "@ DATE"))
        expected = (f"Stock weather file {unused}: DATE header spans 6 characters. "
                    "Supply @DATE for YYDDD, or $WEATHER with @  DATE for YYYYDDD dates.")
    sim.weather = [unused, stock_file(tmp_path, "UFGA8201.WTH")]
    assert sim.check(False) == [expected]


@pytest.mark.parametrize("codes", [(), ("xxxxx",), ("01366",)])
def test_foreign_stock_station_uses_names_without_decoding_dates(tmp_path, fake_dssat, codes):
    sim = period(tmp_path, "82055", "82057")
    sim.executable = fake_dssat.executable
    sim.weather = weather_file(tmp_path, "xyzz8201.wth", codes)
    assert sim.check(False) == [
        "FileX WSTA 'UFGA' expects station 'UFGA', but stock weather file xyzz8201.wth "
        "has station 'XYZZ'. Make the station codes exactly equal; "
        "filenames are case-sensitive on Linux."
    ]


def test_mixed_stock_stations_still_fail(tmp_path, fake_dssat):
    sim = period(tmp_path, "82055", "82057")
    sim.executable = fake_dssat.executable
    sim.weather = [weather_file(tmp_path, "UFGA8201.WTH", ("82055",)),
                   weather_file(tmp_path, "XYZZ8201.WTH", ("82056", "82057"))]
    assert sim.check(False) == [
        "Weather data row 3, column 'station': found 'XYZZ', but row 2 has 'UFGA'. "
        "Use identical station values on every row."
    ]


def test_mixed_stock_stations_ignore_dates_in_both_list_orders(tmp_path, fake_dssat):
    sim = period(tmp_path, "99365", "00366")
    sim.executable = fake_dssat.executable
    foreign = weather_file(tmp_path, "XYZZ0001.WTH", ("00001", "00366"))
    matching = weather_file(tmp_path, "UFGA9901.WTH", ("99365",))
    expected = [
        "Weather data row 3, column 'station': found 'XYZZ', but row 2 has 'UFGA'. "
        "Use identical station values on every row."
    ]
    for paths in ([foreign, matching], [matching, foreign]):
        sim.weather = paths
        assert sim.check(False) == expected


def test_foreign_stock_station_with_structure_problem_reports_mismatch(tmp_path, fake_dssat):
    sim = period(tmp_path, "82055", "82057")
    sim.executable = fake_dssat.executable
    path = weather_file(tmp_path, "XYZZ8201.WTH", ("xxxxx",))
    path.write_text(path.read_text().replace("TMAX", "XXXX"))
    sim.weather = path
    assert sim.check(False) == [
        f"Stock weather file {path}: missing required column TMAX. "
        "Supply a stock weather file with column TMAX.",
        "FileX WSTA 'UFGA' expects station 'UFGA', but stock weather file XYZZ8201.WTH "
        "has station 'XYZZ'. Make the station codes exactly equal; "
        "filenames are case-sensitive on Linux."
    ]
