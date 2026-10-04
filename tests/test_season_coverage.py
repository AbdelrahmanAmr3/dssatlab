"""Season starts are checked before any Simulation writes or runs."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, run_treatments
from dssatlab.filex import _read_filex
from test_filex_check import filex, SAMPLE
from test_filex_template import data, rows
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


def weather(start, end, station="UFGA"):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    return [dict(station=station, latitude=45, longitude=-100, elevation=200,
                 date=first + timedelta(days=i), srad=20, tmax=25, tmin=10, rain=0)
            for i in range((last - first).days + 1)]


def management(years):
    return {"treatments": {"01": {"controls": {"years": years}}}}


@pytest.mark.parametrize("override", [True, False])
@pytest.mark.parametrize("start,end,years,season_start", [
    ("1978-03-01", "1987-12-31", 11, "1988-02-29 (day 60 of 1988)"),
    ("1978-03-01", "1980-02-28", 3, "1980-02-29 (day 60 of 1980)"),
    ("1976-12-31", "1986-12-31", 12, "day 366 of 1987"),
])
def test_last_season_problem_prevents_writes_and_run(
        filex, fake_dssat, tmp_path, monkeypatch, override, start, end, years, season_start):
    day = date.fromisoformat(start)
    text = SAMPLE.replace("GE              1", f"GE          {years:5d}")
    path = filex(text=text, sdate=f"{day.year % 100:02d}{day.timetuple().tm_yday:03d}")
    sim = Simulation(path, 1, weather(start, end),
                     management=management(years) if override else None)
    prefix = "Controls years" if override else "FileX NYERS"
    expected = (f"{prefix} {years}: season {years} starts on {season_start}, "
                f"after the weather data ends ({end}). "
                "Supply weather for every season, or fewer years.")
    before = snapshot(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("checks must write nothing")

    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    problems, report = sim._check_inputs()
    assert problems == [expected]
    assert any("FileX" in line for line in report)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert snapshot(tmp_path) == before
    assert fake_dssat.calls == []


@pytest.mark.parametrize("nyers,override,end", [
    (3, None, "1980-02-29"), (11, 3, "1980-02-29"),
    (11, 1, "1978-03-01"), (1, None, "1978-03-01"),
])
def test_boundary_and_override_precedence(filex, nyers, override, end):
    path = filex(sdate="78060", text=SAMPLE.replace("GE              1", f"GE          {nyers:5d}"))
    assert Simulation(path, 1, weather("1978-03-01", end),
                      management=management(override) if override else None).check(False) == []


@pytest.mark.parametrize("old,new", [("NYERS", "XXXXX"), ("GE              1", "GE            bad"),
                                     ("GE              1", "GE            -99")])
def test_missing_or_unreadable_nyers_means_one(filex, old, new):
    path = filex(text=SAMPLE.replace(old, new))
    assert Simulation(path, 1, weather("1982-02-25", "1982-02-25")).check(False) == []


@pytest.mark.parametrize("start,sdate", [("P", "78060"), ("S", "XXXXX"), ("S", "79060")])
def test_seasons_use_resolved_start_without_weather_match(filex, start, sdate):
    sim = Simulation(filex(start=start, sdate=sdate), 1, weather("1978-03-01", "1978-03-02"),
                     management=management(11))
    assert any("season 11" in p for p in sim.check(False)) == (start == "S" and sdate == "79060")


def test_nyers_comes_from_selected_controls_level(filex):
    text = SAMPLE.replace(" 1 GE", " 2 GE").replace("GE              1", "GE             11")
    text = text.replace("  0  1\n", "  0  2\n")
    values, problems = _read_filex(filex(text=text), 3)
    assert problems == []
    assert values["NYERS"] == "11"


@pytest.mark.parametrize("selected,valid", [(1, True), (2, False)])
def test_template_uses_selected_field_weather(data, rows, installed, tmp_path, selected, valid):
    data.pop("treatment_name")
    data.update(treatments=["First", "Second"], treatment_fields=[1, 2])
    data["planting"]["date"] = "1978-03-01"
    inputs = dict(filex_template=data, soil={1: rows[1], 2: rows[1]},
                  weather={1: weather("1978-03-01", "1980-02-29", "TEST"),
                           2: weather("1978-03-01", "1980-02-28", "AMES")},
                  management={"treatments": {selected: {"controls": {"years": 3}}}})
    sim = Simulation(**inputs, treatment=selected)
    before = snapshot(tmp_path)
    problems, report = sim._check_inputs()
    assert (problems == []) is valid
    if not valid:
        assert len(problems) == 1 and "1980-02-29 (day 60 of 1980)" in problems[0]
        assert any("FileX template" in line for line in report)
        with pytest.raises(DSSATCheckError):
            sim.run()
    assert snapshot(tmp_path) == before
    assert installed.calls == []


def test_run_treatments_labels_season_problem_before_any_run(filex, fake_dssat, tmp_path):
    path = filex(sdate="78060")
    before = snapshot(tmp_path)
    with pytest.raises(DSSATCheckError) as error:
        run_treatments(path, weather("1978-03-01", "1978-03-02"), treatments=[1],
                       scenarios={"long": {"management": management(11)}})
    assert len(error.value.problems) == 1
    assert error.value.problems[0].startswith("Scenario 'long', treatment 1: Controls years 11:")
    assert snapshot(tmp_path) == before
    assert fake_dssat.calls == []


@pytest.mark.parametrize("template", [False, True])
def test_seasons_use_resolved_controls_start_override(filex, data, rows, installed, template):
    data["planting"]["date"] = "1978-03-01"
    inputs = dict(filex_template=data, soil=rows[1]) if template else dict(filex=filex(sdate="78060"))
    sim = Simulation(**inputs, weather=weather("1978-03-01", "1980-02-29"),
                     management={"treatments": {1: {"controls": {
                         "start_date": "1978-03-02", "years": 3}}}})
    assert sim.check(False) == [
        "Controls years 3: season 3 starts on 1980-03-01 (day 61 of 1980), "
        "after the weather data ends (1980-02-29). "
        "Supply weather for every season, or fewer years."]
