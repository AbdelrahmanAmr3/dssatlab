"""Daily weather files match the real DSSAT sample's fixed-width layout."""

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from dssatlab import weather


SAMPLE_HEADER = (
    "*WEATHER DATA : UFGA (written by dssatlab)\n"
    "\n"
    "@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n"
    "  UFGA   29.630  -82.370    10  20.9  13.0  2.00  3.00\n"
    "@DATE  SRAD  TMAX  TMIN  RAIN\n"
)


@pytest.fixture
def row():
    return dict(station="UFGA", latitude=29.630, longitude=-82.370,
                elevation=10.0, tav=20.9, amp=13.0, refht=2.0, wndht=3.0,
                date=date(1982, 1, 1), srad=5.9, tmax=24.4, tmin=15.6, rain=19.0)


@pytest.mark.parametrize("as_string", [False, True])
def test_exact_sample_and_returned_path(tmp_path, row, as_string):
    path = tmp_path / "caller-chosen-name.data"
    rows = [row]
    before = deepcopy(rows)
    result = weather.write_weather_file(rows, str(path) if as_string else path)
    expected = SAMPLE_HEADER + "82001   5.9  24.4  15.6  19.0\n"
    assert path.read_text(encoding="ascii") == expected
    assert path.read_bytes() == expected.encode("ascii")  # LF, including the last line.
    assert isinstance(result, Path)
    assert result == path
    assert list(tmp_path.iterdir()) == [path]
    assert rows == before


@pytest.mark.parametrize("day,record", [
    (date(2020, 2, 29), "20060   5.9  24.4  15.6  19.0\n"),
    (date(2020, 12, 31), "20366   5.9  24.4  15.6  19.0\n"),
    (date(2000, 1, 1), "00001   5.9  24.4  15.6  19.0\n"),
    (date(2099, 12, 31), "99365   5.9  24.4  15.6  19.0\n"),
    (date(2100, 1, 1), "00001   5.9  24.4  15.6  19.0\n"),
])
def test_date_fields(tmp_path, row, day, record):
    path = tmp_path / "weather.WTH"
    weather.write_weather_file([dict(row, date=day)], path)
    assert path.read_bytes() == (SAMPLE_HEADER + record).encode("ascii")


def test_series_crossing_new_year(tmp_path, row):
    rows = [dict(row, date=date(2021, 12, 31)), dict(row, date=date(2022, 1, 1))]
    path = tmp_path / "weather.WTH"
    weather.write_weather_file(rows, path)
    assert path.read_bytes() == (SAMPLE_HEADER
                                + "21365   5.9  24.4  15.6  19.0\n"
                                + "22001   5.9  24.4  15.6  19.0\n").encode("ascii")


def test_negative_temperatures_zero_rain_and_rounding(tmp_path, row):
    row.update(srad=5.96, tmax=-2.34, tmin=-15.66, rain=0.0)
    path = tmp_path / "weather.WTH"
    weather.write_weather_file([row], path)
    assert path.read_bytes() == (SAMPLE_HEADER
                                + "82001   6.0  -2.3 -15.7   0.0\n").encode("ascii")


@pytest.mark.parametrize("small_negative", [False, True])
def test_negative_zero_in_station_and_daily_fields(tmp_path, row, small_negative):
    row.update(latitude=-0.0001 if small_negative else -0.0,
               longitude=-0.0001 if small_negative else -0.0,
               elevation=-0.1 if small_negative else -0.0,
               tav=-0.01 if small_negative else -0.0,
               amp=-0.01 if small_negative else -0.0,
               refht=-0.001 if small_negative else -0.0,
               wndht=-0.001 if small_negative else -0.0,
               srad=-0.0, tmax=-0.01 if small_negative else -0.0,
               tmin=-0.02 if small_negative else -0.0, rain=-0.0)
    path = tmp_path / "weather.WTH"
    weather.write_weather_file([row], path)
    assert path.read_bytes() == (
        b"*WEATHER DATA : UFGA (written by dssatlab)\n"
        b"\n"
        b"@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n"
        b"  UFGA    0.000    0.000     0   0.0   0.0  0.00  0.00\n"
        b"@DATE  SRAD  TMAX  TMIN  RAIN\n"
        b"82001   0.0   0.0   0.0   0.0\n"
    )


def test_unset_optional_values(tmp_path, row):
    raw = {name: value for name, value in row.items()
           if name not in ("tav", "amp", "refht", "wndht")}
    raw["date"] = "1982-01-01"
    rows, problems = weather._parse_weather([raw])
    assert problems == []
    path = tmp_path / "weather.WTH"
    weather.write_weather_file(rows, path)
    assert path.read_bytes() == (
        b"*WEATHER DATA : UFGA (written by dssatlab)\n"
        b"\n"
        b"@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n"
        b"  UFGA   29.630  -82.370    10 -99.0 -99.0-99.00-99.00\n"
        b"@DATE  SRAD  TMAX  TMIN  RAIN\n"
        b"82001   5.9  24.4  15.6  19.0\n"
    )


def test_existing_file_is_overwritten(tmp_path, row):
    path = tmp_path / "weather.WTH"
    path.write_bytes(b"old contents" * 100)
    weather.write_weather_file([row], path)
    assert path.read_bytes() == (SAMPLE_HEADER
                                + "82001   5.9  24.4  15.6  19.0\n").encode("ascii")


def test_template_to_weather_file(tmp_path):
    template = tmp_path / "weather.csv"
    weather.write_weather_template(template)
    rows, problems = weather._parse_weather(template)
    assert problems == []
    path = tmp_path / "weather.WTH"
    weather.write_weather_file(rows, path)
    assert path.read_bytes() == (
        b"*WEATHER DATA : DEMO (written by dssatlab)\n"
        b"\n"
        b"@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n"
        b"  DEMO   45.000 -100.000   200 -99.0 -99.0-99.00-99.00\n"
        b"@DATE  SRAD  TMAX  TMIN  RAIN\n"
        b"21060  20.0  25.0  10.0   0.0\n"
        b"21061  20.0  25.0  10.0   0.0\n"
        b"21062  20.0  25.0  10.0   0.0\n"
        b"21063  20.0  25.0  10.0   0.0\n"
        b"21064  20.0  25.0  10.0   0.0\n"
        b"21065  20.0  25.0  10.0   0.0\n"
        b"21066  20.0  25.0  10.0   0.0\n"
    )
