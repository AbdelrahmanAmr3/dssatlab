"""Forecast checks through Simulation, with contiguous historical weather rows."""

import pytest

from dssatlab import DSSATCheckError, Simulation
from dssatlab.weather import _parse_weather, write_weather_file
from test_filex_check import SAMPLE, filex
from test_season_coverage import weather
from test_sequence import sequence
from test_simulation_start import PLANTING


SIMDATES = "\n@N SIMDATES   HDATE XDATE YDATE FODAT\n 1 SD    -99     -99     -99 1982057\n"
METHODS = "\n@N METHODS     WTHER\n 1 ME              M\n"


@pytest.fixture
def forecast(filex):
    path = filex(text=SAMPLE + METHODS + SIMDATES)
    path = path.rename(path.with_suffix(".FCX"))
    return Simulation(path, "01", weather("1981-02-25", "1982-02-25"))


def edit(sim, old, new):
    text = sim.filex.read_text(encoding="latin-1")
    assert old in text
    sim.filex.write_text(text.replace(old, new), encoding="latin-1")


def experiment(**entry):
    return {"treatments": {"01": entry}}


def coverage_message(years, first, last, supplied_first, supplied_last, override=False):
    label = "Controls years" if override else "FileX NYERS"
    return (f"{label} {years}: the forecast needs weather from {first} through {last}, "
            f"outside weather range ({supplied_first} to {supplied_last}). "
            "Supply weather covering the date range, or fewer years.")


@pytest.mark.parametrize("suffix", [".FCX", ".fcx", ".FcX"])
def test_filex_fodat_used_without_override_and_check_writes_nothing(forecast, suffix):
    forecast.filex = forecast.filex.rename(forecast.filex.with_suffix(suffix))
    before = {p: p.read_bytes() for p in forecast.filex.parent.iterdir()}
    assert forecast.check(False) == []
    assert {p: p.read_bytes() for p in forecast.filex.parent.iterdir()} == before


@pytest.mark.parametrize("row", ["", " 1 SD", " 1 SD    -99     -99     -99     -99",
                                 " 1 SD    -99     -99     -99 XXXXXXX",
                                 " 1 SD    -99     -99     -99 1982366"])
def test_missing_or_invalid_filex_fodat(forecast, row):
    edit(forecast, SIMDATES, "\n@N SIMDATES FODAT\n" + row + "\n")
    expected = (f"FileX {forecast.filex} treatment 1 has no forecast date (SIMDATES FODAT). "
                "Set controls forecast_date, e.g. 2023-05-17.")
    assert forecast.check(False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        forecast.run()
    assert error.value.problems == [expected]


def test_absent_simdates_is_missing(forecast):
    edit(forecast, SIMDATES, "")
    assert "has no forecast date (SIMDATES FODAT)" in forecast.check(False)[0]


def test_override_replaces_missing_or_earlier_filex_fodat(forecast):
    edit(forecast, "1982057", "1982001")
    forecast.management = experiment(controls={"forecast_date": "1982-02-26"})
    assert forecast.check(False) == []
    edit(forecast, "1982001", "    -99")
    assert forecast.check(False) == []


@pytest.mark.parametrize("override", [False, True])
def test_forecast_before_start_message(forecast, override):
    if override:
        forecast.management = experiment(controls={"forecast_date": "1982-01-01"})
    else:
        edit(forecast, "1982057", "1982001")
    assert forecast.check(False) == [
        "Controls forecast_date 1982-01-01 is before the start date 1982-02-25 of "
        f"FileX {forecast.filex} treatment 1. Set forecast_date on or after the start date."]


@pytest.mark.parametrize("override", [False, True])
def test_forecast_equal_to_start_needs_no_current_season_weather(forecast, override):
    if override:
        forecast.management = experiment(controls={"forecast_date": "1982-02-25"})
    else:
        edit(forecast, "1982057", "1982056")
    forecast.weather = weather("1981-02-25", "1982-02-24")
    assert forecast.check(False) == []


@pytest.mark.parametrize("override", [False, True])
def test_stock_wth_forecast_equal_to_start_matches_rows(forecast, tmp_path, override):
    if override:
        forecast.management = experiment(controls={"forecast_date": "1982-02-25"})
    else:
        edit(forecast, "1982057", "1982056")
    path = tmp_path / "UFGA8201.WTH"
    write_weather_file(_parse_weather(weather("1981-02-25", "1982-02-24"))[0], path)
    forecast.weather = path
    assert forecast.check(False) == []


@pytest.mark.parametrize("start,sdate", [("E", "82056"), ("P", "82056"),
                                         ("S", "XXXXX"), ("S", "82366")])
def test_unavailable_or_emergence_start(forecast, start, sdate):
    edit(forecast, "S 82056", f"{start} {sdate}")
    expected = (f"FileX {forecast.filex} treatment 1: "
                "a forecast needs START S or P with a valid start date.")
    assert expected in forecast.check(False)


@pytest.mark.parametrize("override", [False, True])
def test_start_p_uses_effective_planting(forecast, override):
    edit(forecast, "S 82056", "P 82056")
    forecast.filex.write_text(forecast.filex.read_text() + PLANTING)
    forecast.weather = weather("1981-02-26", "1982-02-25")
    if override:
        forecast.management = experiment(planting={
            "date": "1982-02-27", "method": "S", "distribution": "R",
            "population": 8, "row_spacing": 75, "depth": 3},
            controls={"start_date": "1982-03-02", "forecast_date": "1982-02-27"})
        forecast.weather = weather("1981-02-27", "1982-02-26")
    assert forecast.check(False) == []


def test_start_date_override_moves_coverage_and_date_comparison(forecast):
    forecast.management = experiment(controls={"start_date": "1982-03-01",
                                              "forecast_date": "1982-03-01"})
    forecast.weather = weather("1981-03-01", "1982-02-28")
    assert forecast.check(False) == []
    forecast.management["treatments"]["01"]["controls"]["forecast_date"] = "1982-02-28"
    assert "before the start date 1982-03-01" in forecast.check(False)[0]


@pytest.mark.parametrize("first,last", [("1981-02-26", "1982-02-25"),
                                       ("1981-02-25", "1982-02-24")])
def test_weather_short_at_each_end(forecast, first, last):
    forecast.weather = weather(first, last)
    assert forecast.check(False) == [coverage_message(
        1, "1981-02-25", "1982-02-25", first, last)]


def test_gap_before_forecast_reported_with_weather_problems(forecast):
    forecast.weather.pop(-2)
    problems = forecast.check(False)
    assert "Weather data: missing date 1982-02-24. Supply one row for each missing calendar day." in problems
    assert coverage_message(1, "1981-02-25", "1982-02-25",
                            "1981-02-25", "1982-02-25") in problems


@pytest.mark.parametrize("override", [False, True])
def test_years_moves_historical_start_and_never_requires_future_seasons(forecast, override):
    if override:
        forecast.management = experiment(controls={"years": 2})
    else:
        edit(forecast, "GE              1", "GE              2")
    assert forecast.check(False) == [coverage_message(
        2, "1980-02-25", "1982-02-25", "1981-02-25", "1982-02-25", override)]
    forecast.weather = weather("1980-02-25", "1982-02-25")
    assert forecast.check(False) == []
    forecast.management = experiment(controls={"years": 1})
    forecast.weather = weather("1981-02-25", "1982-02-25")
    assert forecast.check(False) == []


@pytest.mark.parametrize("start,fodat,first,last", [
    ("82365", "1983060", "1981-12-31", "1983-02-28"),
    ("80366", "1980366", "1980-01-01", "1980-12-30"),
    ("80366", "1981002", "1980-01-01", "1981-01-01"),
])
def test_cross_year_and_day_366_keep_day_of_year(forecast, start, fodat, first, last):
    edit(forecast, "82056", start)
    edit(forecast, "1982057", fodat)
    forecast.weather = weather(first, last)
    assert forecast.check(False) == []


def test_planned_operations_after_forecast_need_no_weather(forecast):
    forecast.management = experiment(
        tillage=[{"date": "1982-06-01", "implement": "TI001", "depth": 10}],
        fertilizer=[{"date": "1982-06-02", "n": 10, "material": "FE001", "application": "AP001", "depth": 5}])
    assert forecast.check(False) == []


@pytest.mark.parametrize("method,override", [("S", False), ("W", False), ("G", False),
                                            ("S", True), ("W", True)])
def test_effective_wther_measured_only(forecast, method, override):
    if override:
        forecast.management = experiment(controls={"weather_source": method})
    else:
        edit(forecast, "ME              M", f"ME              {method}")
    assert forecast.check(False) == [
        f"FileX {forecast.filex} treatment 1, WTHER {method} in controls level 1: "
        "a forecast Simulation uses measured weather only. Set controls weather_source to M."]


def test_measured_override_replaces_inherited_generated_weather(forecast):
    edit(forecast, "ME              M", "ME              W")
    forecast.management = experiment(controls={"weather_source": "M"})
    assert forecast.check(False) == []


@pytest.mark.parametrize("mixed", [False, True])
def test_climate_source_is_a_forecast_problem(forecast, mixed):
    climate = forecast.filex.with_name("UFGA.CLI")
    forecast.weather = [climate, *forecast.weather] if mixed else climate
    expected = (f"FileX {forecast.filex} treatment 1, climate file {climate}: "
                "a forecast Simulation uses measured weather only. Supply weather data or .WTH paths.")
    assert expected in forecast.check(False)


def test_sequence_rejected_and_forecast_problems_collected_together(sequence):
    sequence.filex = sequence.filex.rename(sequence.filex.with_suffix(".FCX"))
    edit(sequence, "S 78110", "E 78110")
    edit(sequence, "ME              M", "ME              W")
    climate = sequence.filex.with_name("UFGA.CLI")
    sequence.weather = climate
    problems = sequence.check(False)
    where = f"FileX {sequence.filex} treatment 1"
    for expected in [
        f"{where} has no forecast date (SIMDATES FODAT). Set controls forecast_date, e.g. 2023-05-17.",
        f"{where}: a forecast needs START S or P with a valid start date.",
        f"{where}, climate file {climate}: a forecast Simulation uses measured weather only. "
        "Supply weather data or .WTH paths.",
        f"{where} has 6 rotation components: a forecast Simulation needs one treatment with one "
        "rotation component. Supply a .FCX with one rotation component for this treatment.",
    ]:
        assert expected in problems
    assert any("WTHER W" in p and "a forecast Simulation uses measured weather only" in p for p in problems)


def test_long_history_does_not_overflow_calendar(forecast):
    forecast.management = experiment(controls={"years": 99999})
    assert "day 56 of -98017" in forecast.check(False)[0]
