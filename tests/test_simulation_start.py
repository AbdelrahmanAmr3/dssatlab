"""Effective START P planting dates drive coverage checks."""

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


@pytest.mark.parametrize("start,day", [("P", "1982-02-26")])
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
    assert any("FileX start year 82 day 056" in p for p in sim.check(False))


def test_start_p_last_season_needs_weather(filex):
    text = (SAMPLE + PLANTING).replace("GE              1", "GE              2")
    sim = Simulation(filex(start="P", text=text), 1, weather("1982-02-25", "1982-12-31"))
    assert any("season 2 starts on 1983-02-26" in p for p in sim.check(False))


def test_start_p_sequence_needs_weather(sequence):
    sequence.filex.write_text(sequence.filex.read_text().replace("S 78110", "P 78110"))
    sequence.management = experiment(controls={"years": 2})
    sequence.weather = weather("1978-04-20", "1978-12-31")
    assert any("the sequence runs from" in p for p in sequence.check(False))


@pytest.mark.parametrize("start,field,original", [("P", "date", "1982-02-26")])
def test_planting_override_is_effective_start(filex, start, field, original):
    planting = dict(date="1982-02-26", method="S",
                    distribution="R", population=8, row_spacing=75, depth=3)
    planting[field] = "1982-03-03"
    sim = Simulation(filex(start=start, text=SAMPLE + PLANTING), 1,
                     weather("1982-02-25", "1982-03-02"),
                     management=experiment(planting=planting))
    start_problem(sim.check(False), date(1982, 3, 3))
    assert not any("not covered by weather data" in p and original in p for p in sim.check(False))


@pytest.mark.parametrize("start,day", [("P", "1982-02-26")])
@pytest.mark.parametrize("wide", [False, True])
def test_stock_missing_start_day_keeps_effective_year(filex, tmp_path, start, day, wide):
    missing = date.fromisoformat(day)
    code = f"{missing.year if wide else missing.year % 100:0{4 if wide else 2}d}{missing.timetuple().tm_yday + 1:03d}"
    source = weather_file(tmp_path, "UFGA8201.WTH", [code], wide=wide)
    sim = Simulation(filex(start=start, text=SAMPLE + PLANTING), 1, source)
    start_problem(sim.check(False), missing)


def test_start_p_irrigation_ignores_controls_start_date(filex):
    text = SAMPLE + PLANTING + IRRIGATION.replace("40057", "82056")
    sim = Simulation(filex(start="P", text=text), 1, weather("1982-02-25", "1982-03-10"),
                     management=experiment(controls={"start_date": "1982-02-25"}))
    assert sim.check(False) == [
        "Simulation start date '1982-02-26' is after the FileX's first irrigation date "
        "1982-02-25; DSSAT stops with error IPIRR. Start on or before that date, "
        "or give irrigation in the management data."]


def test_automatic_planting_ignores_sdate_override_under_p(filex):
    window = AUTOMATIC.replace("40057", "82057").replace("40070", "82070")
    sim = Simulation(filex(start="P", text=SAMPLE + window + PLANTING), 1,
                     weather("1982-02-25", "1982-03-10"),
                     management=experiment(controls={"start_date": "1982-03-02"}))
    assert sim.check(False) == []


def test_start_p_sequence_first_component_planting_override(sequence):
    sequence.filex.write_text(sequence.filex.read_text().replace("S 78110", "P 78110"))
    sequence.management = experiment(controls={"years": 2}, rotation={"01": {"planting": {
        "date": "1978-05-01", "method": "S", "distribution": "R",
        "population": 8, "row_spacing": 75, "depth": 3}}})
    sequence.weather = weather("1978-04-20", "1978-12-31")
    assert any("the sequence runs from 1978-05-01" in p for p in sequence.check(False))
