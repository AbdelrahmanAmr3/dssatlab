"""Ticket A: simulation start dates follow the real-DSSAT e2e22 measurements."""

from datetime import date, timedelta

import pytest

from dssatlab import Simulation
from test_filex_check import SAMPLE, filex
from test_season_coverage import weather
from test_sequence import sequence
from test_stock_weather import weather_file


PLANTING = """
*PLANTING DETAILS
@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE  PENV  PLPH  SPRL
 1 82057 82060     8     8     S     R    75     0     3   -99   -99   -99   -99   -99
"""
AUTOMATIC = """
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              A     R     R     N     M
@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          40057 40070    40   100    30    40    10
"""
IRRIGATION = """
*IRRIGATION AND WATER MANAGEMENT
@I IDATE  IROP IRVAL
 1 40057 IR001    10
"""


def experiment(**entry):
    return {"treatments": {"01": entry}}


def start_problem(problems, day):
    assert any("not covered by weather data" in p and str(day) in p for p in problems)


@pytest.mark.parametrize("yy", [35, 36, 40, 41])
@pytest.mark.parametrize("century", [1900, 2000, None], ids=["19YY", "20YY", "legacy"])
def test_report_year_cases(filex, tmp_path, yy, century):
    year = (century if century else 2000 if yy <= 35 else 1900) + yy
    day = date(year, 1, 1) + timedelta(days=55)
    wide = century is not None
    codes = [f"{year if wide else yy:0{4 if wide else 2}d}{doy:03d}" for doy in (56, 57)]
    source = weather_file(tmp_path, f"UFGA{yy:02d}01.WTH", codes, wide=wide)
    sim = Simulation(filex(sdate=f"{yy:02d}056"), 1, source)
    assert sim.check(False) == []
    # A missing day names the measured century, rather than only YYDDD.
    sim.filex.write_text(sim.filex.read_text().replace(f"{yy:02d}056", f"{yy:02d}058"))
    start_problem(sim.check(False), day + timedelta(days=2))


@pytest.mark.parametrize("start,day", [("P", "1982-02-26"), ("E", "1982-03-01")])
@pytest.mark.parametrize("override", [False, True])
def test_effective_start_day_missing_even_with_covered_sdate_override(filex, start, day, override):
    missing = date.fromisoformat(day)
    sim = Simulation(filex(start=start, text=SAMPLE + PLANTING), 1,
                     weather((missing + timedelta(days=1)).isoformat(), "1982-03-10"),
                     management=experiment(controls={"start_date": "1982-03-02"}) if override else None)
    start_problem(sim.check(False), missing)
    sim.weather = weather(day, "1982-03-10")
    assert sim.check(False) == []


def test_start_s_controls_override_replaces_sdate(filex):
    sim = Simulation(filex(), 1, weather("1982-03-02", "1982-03-03"),
                     management=experiment(controls={"start_date": "1982-03-02"}))
    assert sim.check(False) == []
    sim.management = None
    start_problem(sim.check(False), date(1982, 2, 25))


def test_start_p_last_season_needs_weather(filex):
    text = (SAMPLE + PLANTING).replace("GE              1", "GE              2")
    sim = Simulation(filex(start="P", text=text), 1, weather("1982-02-25", "1982-12-31"))
    assert any("season 2 starts on 1983-02-26" in p for p in sim.check(False))


def test_start_p_sequence_needs_weather(sequence):
    sequence.filex.write_text(sequence.filex.read_text().replace("S 78110", "P 78110"))
    sequence.management = experiment(controls={"years": 2})
    sequence.weather = weather("1978-04-20", "1978-12-31")
    assert any("the sequence runs from" in p for p in sequence.check(False))


@pytest.mark.parametrize("start,field,original", [("P", "date", "1982-02-26"),
                                                ("E", "emergence_date", "1982-03-01")])
def test_planting_override_is_effective_start(filex, start, field, original):
    planting = dict(date="1982-02-26", emergence_date="1982-03-01", method="S",
                    distribution="R", population=8, row_spacing=75, depth=3)
    planting[field] = "1982-03-03"
    sim = Simulation(filex(start=start, text=SAMPLE + PLANTING), 1,
                     weather("1982-02-25", "1982-03-02"),
                     management=experiment(planting=planting))
    start_problem(sim.check(False), date(1982, 3, 3))
    assert not any("not covered by weather data" in p and original in p for p in sim.check(False))


@pytest.mark.parametrize("year", [1940, 2040])
def test_irrigation_uses_weather_century(filex, tmp_path, year):
    text = SAMPLE.replace("82056", "40056") + IRRIGATION
    source = weather_file(tmp_path, "UFGA4001.WTH",
                          [f"{year}{doy:03d}" for doy in range(56, 71)], wide=True)
    sim = Simulation(filex(text=text, sdate="40056"), 1,
                     source,
                     management=experiment(controls={"start_date": f"{year}-02-27"}))
    problems = sim.check(False)
    assert len(problems) == 1
    assert f"first irrigation date {year}-02-26" in problems[0]


@pytest.mark.parametrize("year", [1940, 2040])
def test_automatic_planting_uses_weather_century(filex, tmp_path, year):
    source = weather_file(tmp_path, "UFGA4001.WTH",
                          [f"{year}{doy:03d}" for doy in range(56, 76)], wide=True)
    sim = Simulation(filex(text=SAMPLE + AUTOMATIC, sdate="40056"), 1,
                     source,
                     management=experiment(controls={"auto_planting_last": f"{year}-02-25"}))
    problems = sim.check(False)
    assert len(problems) == 1
    assert f"date '{year}-02-26' is after auto_planting_last '{year}-02-25'" in problems[0]


def test_start_before_first_weather_year_advances_century(filex, tmp_path):
    source = weather_file(tmp_path, "UFGA3501.WTH", ["1940001", "1940002"], wide=True)
    sim = Simulation(filex(sdate="35056"), 1, source)
    start_problem(sim.check(False), date(2035, 2, 25))
    assert not any("ambiguous start year" in p for p in sim.check(False))


def test_first_weather_century_wins_when_both_centuries_present(filex):
    sim = Simulation(filex(sdate="35056"), 1,
                     weather("1935-02-25", "2035-02-25"))
    assert sim.check(False) == []


@pytest.mark.parametrize("start,day", [("P", "1982-02-26"), ("E", "1982-03-01")])
@pytest.mark.parametrize("wide", [False, True])
def test_stock_missing_start_day_keeps_effective_year(filex, tmp_path, start, day, wide):
    missing = date.fromisoformat(day)
    code = f"{missing.year if wide else missing.year % 100:0{4 if wide else 2}d}{missing.timetuple().tm_yday + 1:03d}"
    source = weather_file(tmp_path, "UFGA8201.WTH", [code], wide=wide)
    sim = Simulation(filex(start=start, text=SAMPLE + PLANTING), 1, source)
    start_problem(sim.check(False), missing)


@pytest.mark.parametrize("start", ["S", "P", "E"])
def test_report_first_weather_day_boundary(filex, tmp_path, start):
    text = (SAMPLE + PLANTING).replace("82057", "35057").replace("82060", "35060")
    source = weather_file(tmp_path, "UFGA3501.WTH", [f"1935{doy:03d}" for doy in range(57, 62)], wide=True)
    sim = Simulation(filex(start=start, sdate="35056", text=text), 1, source)
    problems = sim.check(False)
    assert any("1935-02-25" in p and ("first weather date" in p or "not covered" in p) for p in problems)


def test_start_e_override_accepts_planting_before_emergence(filex):
    planting = dict(date="1982-02-26", emergence_date="1982-03-03", method="S",
                    distribution="R", population=8, row_spacing=75, depth=3)
    sim = Simulation(filex(start="E", text=SAMPLE + PLANTING), 1,
                     weather("1982-02-25", "1982-03-04"), management=experiment(planting=planting))
    assert sim.check(False) == []


def test_start_p_irrigation_ignores_controls_start_date(filex):
    text = SAMPLE + PLANTING + IRRIGATION.replace("40057", "82056")
    sim = Simulation(filex(start="P", text=text), 1, weather("1982-02-25", "1982-03-10"),
                     management=experiment(controls={"start_date": "1982-02-25"}))
    assert sim.check(False) == [
        "Simulation start date '1982-02-26' is after the FileX's first irrigation date "
        "1982-02-25; DSSAT stops with error IPIRR. Start on or before that date, "
        "or give irrigation in the management data."]


@pytest.mark.parametrize("start,first,expected", [("P", "82057", None),
                                                ("E", "82059", "1982-03-01")])
def test_automatic_planting_ignores_sdate_override_under_p_e(filex, start, first, expected):
    window = AUTOMATIC.replace("40057", first).replace("40070", "82070")
    sim = Simulation(filex(start=start, text=SAMPLE + window + PLANTING), 1,
                     weather("1982-02-25", "1982-03-10"),
                     management=experiment(controls={"start_date": "1982-03-02"}))
    problems = sim.check(False)
    if expected is None:
        assert problems == []
    else:
        assert len(problems) == 1
        assert f"before simulation start date '{expected}'" in problems[0]


def test_start_p_sequence_first_component_planting_override(sequence):
    sequence.filex.write_text(sequence.filex.read_text().replace("S 78110", "P 78110"))
    sequence.management = experiment(controls={"years": 2}, rotation={"01": {"planting": {
        "date": "1978-05-01", "method": "S", "distribution": "R",
        "population": 8, "row_spacing": 75, "depth": 3}}})
    sequence.weather = weather("1978-04-20", "1978-12-31")
    assert any("the sequence runs from 1978-05-01" in p for p in sequence.check(False))


def test_automatic_planting_legacy_weather_keeps_crossover_35(filex, tmp_path):
    source = weather_file(tmp_path, "UFGA3501.WTH", ["35055", "35056", "35057"])
    sim = Simulation(filex(sdate="35056", text=SAMPLE + AUTOMATIC), 1, source,
                     management=experiment(controls={"planting_management": "A"}))
    problems = sim.check(False)
    assert len(problems) == 1
    assert "date '1940-02-26' is before simulation start date '2035-02-25'" in problems[0]


@pytest.mark.parametrize("yy,year", [(35, 2035), (36, 1936), (40, 1940), (41, 1941)])
def test_template_weather_uses_its_generated_legacy_date_format(filex, yy, year):
    sim = Simulation(filex(sdate=f"{yy:02d}056"), 1,
                     weather(f"{year}-02-25", f"{year}-02-26"))
    assert sim.check(False) == []
    other_year = year + 100 if year < 2000 else year - 100
    sim.weather = weather(f"{other_year}-02-25", f"{other_year}-02-26")
    start_problem(sim.check(False), date(year, 2, 25))
