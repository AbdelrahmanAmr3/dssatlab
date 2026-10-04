"""NASA POWER files become editable weather templates, checked as usual."""

import csv
from datetime import date
import io
from pathlib import Path

import pytest

import dssatlab
from dssatlab import weather


@pytest.fixture
def power_text():
    return (Path(__file__).parent / "data" / "power_daily.csv").read_text(
        encoding="utf-8-sig")


def change_table(text, change):
    header, table = text.split("-END HEADER-\n")
    rows = list(csv.reader(io.StringIO(table)))
    change(rows)
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    return header + "-END HEADER-\n" + stream.getvalue()


def remove_column(text, name):
    def change(rows):
        index = rows[0].index(name)
        for row in rows:
            row.pop(index)
    return change_table(text, change)


def import_text(tmp_path, text, **kwargs):
    source = tmp_path / "power.csv"
    source.write_text(text, encoding="utf-8")
    return dssatlab.import_nasa_power(source, tmp_path / "weather.csv",
                                     station="UFGA", **kwargs)


def read_template(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def weather_problems(path):
    problems = dssatlab.Simulation("missing.MZX", 1, path).check()
    filex = [p for p in problems if p.startswith("Cannot read FileX ")]
    assert len(filex) == 1
    return [p for p in problems if p not in filex]


def test_real_daily_file_writes_template_and_passes_checks(tmp_path, power_text):
    path = import_text(tmp_path, power_text)
    assert path == tmp_path / "weather.csv"
    assert isinstance(path, Path)
    rows = read_template(path)
    assert len(rows) == 3
    assert rows[0] == dict(
        station="UFGA", latitude="29.63", longitude="-82.37", elevation="25.35",
        date="1984-01-01", srad="13.3", tmax="11.39", tmin="-4.18", rain="0.0",
        tav="-99", amp="-99", refht="-99", wndht="-99")
    assert [row["date"] for row in rows] == [
        "1984-01-01", "1984-01-02", "1984-01-03"]
    template = tmp_path / "example.csv"
    dssatlab.write_weather_template(template)
    assert list(rows[0]) == list(read_template(template)[0])
    parsed, problems = weather._parse_weather(path)
    assert problems == []
    assert parsed[-1]["date"] == date(1984, 1, 3)
    assert parsed[-1]["srad"] == 13.26
    assert weather_problems(path) == []
    assert (tmp_path / "power.csv").read_text(encoding="utf-8") == power_text


@pytest.mark.parametrize("keep_doy", [False, True])
def test_calendar_dates_write_same_template(tmp_path, power_text, keep_doy):
    expected = import_text(tmp_path, power_text).read_bytes()
    (tmp_path / "weather.csv").unlink()

    def change(rows):
        rows[0][1:2] = ["DOY", "MO", "DY"] if keep_doy else ["MO", "DY"]
        for row in rows[1:]:
            day = row[1]
            row[1:2] = [day, "1", day] if keep_doy else ["1", day]

    path = import_text(tmp_path, change_table(power_text, change))
    assert path.read_bytes() == expected


def test_older_precipitation_column_is_accepted(tmp_path, power_text):
    expected = import_text(tmp_path, power_text).read_bytes()
    (tmp_path / "weather.csv").unlink()
    path = import_text(tmp_path, power_text.replace("PRECTOTCORR", "PRECTOT"))
    assert path.read_bytes() == expected


@pytest.mark.parametrize("marker", ["-999", "-777"])
def test_header_fill_marker_is_missing_on_the_same_day(tmp_path, power_text, marker):
    text = power_text.replace("-999", marker).replace(
        "1984,2,13.14", f"1984,2,{marker}.0")
    path = import_text(tmp_path, text)
    assert read_template(path)[1]["srad"] == "-99"
    problems = weather_problems(path)
    assert len(problems) == 1
    assert "1984-01-02" in problems[0] and "'srad'" in problems[0]
    assert "-99" in problems[0]


def test_coordinate_overrides_include_zero(tmp_path, power_text):
    path = import_text(tmp_path, power_text, latitude=0, longitude=12.5, elevation=0)
    for row in read_template(path):
        assert [row[name] for name in ("latitude", "longitude", "elevation")] == [
            "0", "12.5", "0"]


@pytest.mark.parametrize("keyword,fragment", [
    ("latitude", "latitude  29.63"), ("longitude", "longitude -82.37"),
    ("elevation", "elevation from MERRA-2: Average for 0.5 x 0.625 degree lat/lon region = 25.35 meters"),
])
def test_missing_coordinate_names_keyword_and_can_be_supplied(
        tmp_path, power_text, keyword, fragment):
    text = power_text.replace(fragment, "")
    with pytest.raises(dssatlab.DSSATError, match=keyword):
        import_text(tmp_path, text)
    assert not (tmp_path / "weather.csv").exists()
    path = import_text(tmp_path, text, **{keyword: 0})
    assert read_template(path)[0][keyword] == "0"


@pytest.mark.parametrize("station", ["", "ABC", "ABCDE", "A B1", "éB12", None, 1234])
def test_invalid_station_is_rejected(tmp_path, power_text, station):
    source = tmp_path / "power.csv"
    source.write_text(power_text, encoding="utf-8")
    with pytest.raises(dssatlab.DSSATError, match="station.*four ASCII letters or digits"):
        dssatlab.import_nasa_power(source, tmp_path / "weather.csv", station=station)
    assert not (tmp_path / "weather.csv").exists()


def test_station_is_required(tmp_path):
    with pytest.raises(TypeError, match="station"):
        dssatlab.import_nasa_power(tmp_path / "power.csv", tmp_path / "weather.csv")


@pytest.mark.parametrize("directory", [False, True])
def test_existing_path_refused_like_weather_writer(tmp_path, power_text, directory):
    source = tmp_path / "power.csv"
    source.write_text(power_text, encoding="utf-8")
    path = tmp_path / "weather.csv"
    if directory:
        path.mkdir()
    else:
        path.write_bytes(b"user data")
    with pytest.raises(dssatlab.DSSATError) as template_error:
        dssatlab.write_weather_template(path)
    with pytest.raises(dssatlab.DSSATError) as import_error:
        dssatlab.import_nasa_power(str(source), str(path), station="UFGA")
    assert str(import_error.value) == str(template_error.value)
    if not directory:
        assert path.read_bytes() == b"user data"


@pytest.mark.parametrize("broken,reason", [
    (lambda t: t.split("-END HEADER-\n")[1], "header block"),
    (lambda t: t.replace("-END HEADER-", ""), "header block"),
    (lambda t: remove_column(t, "YEAR"), "YEAR"),
    (lambda t: remove_column(t, "DOY"), "DOY or MO and DY"),
    (lambda t: remove_column(t, "ALLSKY_SFC_SW_DWN"), "ALLSKY_SFC_SW_DWN"),
    (lambda t: remove_column(t, "T2M_MAX"), "T2M_MAX"),
    (lambda t: remove_column(t, "T2M_MIN"), "T2M_MIN"),
    (lambda t: remove_column(t, "PRECTOTCORR"), "PRECTOTCORR or PRECTOT"),
    (lambda t: t.replace("Daily Data", "Monthly Data").replace("DOY", "MO"), "daily"),
    (lambda t: t.replace("DOY,", "HR,"), "hourly"),
    (lambda t: t.replace("1984,2,", "1984,367,"), "date"),
    (lambda t: t.replace("1984,2,", "1984,0,"), "date"),
    (lambda t: t.replace("1984,2,", "1984,no-day,"), "date"),
    (lambda t: t.replace("YEAR,DOY", "YEAR,MO,DY").replace("1984,", "1984,2,").replace("1984,2,2,", "1984,2,30,"), "date"),
    (lambda t: t.replace("YEAR,DOY", "YEAR,DOY,MO,DY").replace("1984,", "1984,1,1,"), "disagree"),
    (lambda t: t.rsplit("\n", 2)[0] + ",extra\n", "values"),
    (lambda t: t.split("1984,1,")[0], "daily rows"),
])
def test_invalid_daily_layout_reports_missing_part(tmp_path, power_text, broken, reason):
    with pytest.raises(dssatlab.DSSATError) as caught:
        import_text(tmp_path, broken(power_text))
    message = str(caught.value)
    assert message.startswith(f"{tmp_path / 'power.csv'} is not a NASA POWER daily CSV: ")
    assert reason in message
    assert "Checked the header block and the column row." in message
    assert "Download daily data with ALLSKY_SFC_SW_DWN, T2M_MAX, T2M_MIN and PRECTOTCORR" in message
    assert "fill the weather template yourself." in message
    assert not (tmp_path / "weather.csv").exists()


@pytest.mark.parametrize("unit", ["kW-hr/m^2/day", "W/m^2"])
def test_wrong_solar_unit_names_unit_and_ag_download(tmp_path, power_text, unit):
    with pytest.raises(dssatlab.DSSATError) as caught:
        import_text(tmp_path, power_text.replace("MJ/m^2/day", unit))
    assert "ALLSKY_SFC_SW_DWN" in str(caught.value)
    assert unit in str(caught.value)
    assert "AG community" in str(caught.value)
    assert not (tmp_path / "weather.csv").exists()


def test_import_does_not_check_or_repair_weather_values(tmp_path, power_text):
    text = power_text.replace("1984,2,13.14,15.54,-0.7,0.0", "1984,2,80,bad,-0.7,-2")
    path = import_text(tmp_path, text)
    assert [read_template(path)[1][name] for name in ("srad", "tmax", "rain")] == [
        "80", "bad", "-2"]
    assert len(weather_problems(path)) == 3
