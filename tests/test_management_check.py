"""Management data checks and reports through Simulation.check() only."""

from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
import subprocess

import pytest

from dssatlab import DSSATCheckError, Simulation


SAMPLE = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 RAINFED LOW NITROGEN       1  1  0  1  1  1  1  0  0  0  0  0  1
 2 1 0 0 RAINFED HIGH NITROGEN      1  1  0  1  1  1  2  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910214 Field section

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 N X IRRIGATION
"""
REQUIRED = ("date", "method", "distribution", "population", "row_spacing", "depth")
OPTIONAL_NUMBERS = ("emergence_population", "row_direction", "planting_material_weight",
                    "transplant_age", "transplant_environment", "plants_per_hill", "sprout_length")


@pytest.fixture
def planting():
    return dict(date="1982-02-25", method="S", distribution="R",
                population=8, row_spacing=75.0, depth=0)


@pytest.fixture
def simulation(tmp_path, planting):
    path = tmp_path / "UFGA8201.MZX"
    path.write_text(SAMPLE, encoding="latin-1")
    weather = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                    date="1982-02-25", srad=20, tmax=25, tmin=10, rain=0)]
    return Simulation(path, 1, weather, management={"treatments": {1: {"planting": planting}}})


@pytest.mark.parametrize("key", [1, "1", "01", 2, "2"])
def test_valid_planting_reports_ok_for_every_treatment(simulation, planting, capsys, key):
    simulation.management = {"treatments": {key: {"planting": planting}}}
    assert simulation.check() == []
    report = capsys.readouterr().out.lower()
    assert f"treatment {int(key)}: ok" in report
    assert "planting: ok" in report
    assert report.index("weather") < report.index("filex") < report.index("management")
    assert "soil data" not in report
    assert "crop-specific fields are checked by dssat at run time" in report


@pytest.mark.parametrize("field", REQUIRED)
def test_missing_required_field_names_location_and_action(simulation, planting, capsys, field):
    del planting[field]
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0].lower() for word in ("treatment 1", "planting", field, "missing", "add"))
    report = capsys.readouterr().out
    assert "planting: REJECTED" in report and problems[0] in report


@pytest.mark.parametrize("first,second", [(1, "1"), (1, "01"), ("1", "01"), ("01", 1),
                                         (2, "02")])
def test_duplicate_treatment_numbers_reject_second_entry(simulation, capsys, first, second):
    simulation.management = {"treatments": {first: {}, second: {}}}
    before = deepcopy(simulation.management)
    problems = simulation.check()
    assert problems == [
        f"Management data treatment {int(first)}: duplicate treatment number for keys "
        f"{first!r} and {second!r}. Keep one entry per treatment number."
    ]
    report = capsys.readouterr().out
    assert report.index(f"Treatment {int(first)}: OK") < report.index(
        f"Treatment {int(first)}: REJECTED")
    assert problems[0] in report
    assert simulation.management == before
    with pytest.raises(DSSATCheckError) as error:
        simulation.run()
    assert error.value.problems == problems


@pytest.mark.parametrize("data,word", [
    ([], "dict"), (42, "dict"),
    ({}, "treatments"), ({"treatment": {}}, "unknown"),
    ({"treatments": []}, "dict"), ({"treatments": None}, "dict"),
    ({"treatments": {1: []}}, "dict"), ({"treatments": {1: None}}, "dict"),
    ({"treatments": {1: {"plantng": {}}}}, "plantng"),
    ({"treatments": {1: {}}, "extra": 1}, "extra"),
])
def test_wrong_structure_is_rejected(simulation, capsys, data, word):
    simulation.management = data
    problems = simulation.check()
    assert any(word in p and "Management data" in p for p in problems)
    report = capsys.readouterr().out
    assert all(p in report for p in problems)


@pytest.mark.parametrize("key", [True, 1.0, None, "one", "1.0", " 1", "", "١",
                                 pytest.param(10 ** 5000, id="huge-int")])
def test_invalid_treatment_key(simulation, planting, key):
    simulation.management = {"treatments": {key: {"planting": planting}}}
    assert any("treatment" in p.lower() and "int or digit string" in p for p in simulation.check())


@pytest.mark.parametrize("key", [0, -1, 3, "99"])
def test_absent_treatment_rejected_even_when_not_selected(simulation, planting, key):
    simulation.management["treatments"][key] = {"planting": dict(planting, depth=-1)}
    problems = simulation.check()
    assert any(str(key) in p and "does not exist" in p and "FileX" in p for p in problems)
    assert any(str(key) in p and "depth" in p for p in problems)


@pytest.mark.parametrize("value", [None, {}, [], 42])
def test_explicit_empty_or_wrong_planting_rejected(simulation, value):
    simulation.management["treatments"][1]["planting"] = value
    assert any("planting" in p and "non-empty dict" in p for p in simulation.check())


@pytest.mark.parametrize("field", ["plant_date", "Population", 3])
def test_unknown_planting_fields_rejected(simulation, planting, field):
    planting[field] = 1
    assert any(str(field) in p and "unknown" in p and "planting" in p for p in simulation.check())


@pytest.mark.parametrize("field", ["date", "emergence_date"])
@pytest.mark.parametrize("value", ["19820225", "1982-W08-4", "1982-2-25", "1982-02-30",
    "1982-02-25T00:00:00", " 1982-02-25", "", None, False, 19820225,
    date(1982, 2, 25), datetime(1982, 2, 25)])
def test_dates_require_quoted_iso_calendar_strings(simulation, planting, field, value):
    planting[field] = value
    assert any(field in p and "YYYY-MM-DD" in p and "quote" in p.lower()
               and "treatment 1" in p.lower() for p in simulation.check())


@pytest.mark.parametrize("field", ["population", "row_spacing", "depth"] + list(OPTIONAL_NUMBERS))
@pytest.mark.parametrize("value", [None, True, "8", "oops", float("nan"), float("inf"),
                                 pytest.param(10 ** 5000, id="huge-int")])
def test_planting_numbers_must_be_finite_numbers(simulation, planting, field, value):
    planting[field] = value
    assert any(field in p and "finite number" in p and "planting" in p for p in simulation.check())


@pytest.mark.parametrize("field,value", [("population", 0), ("population", -1),
    ("row_spacing", 0), ("row_spacing", -1), ("depth", -0.1)])
def test_numeric_ranges(simulation, planting, field, value):
    planting[field] = value
    assert any(field in p and "Supply" in p for p in simulation.check())


@pytest.mark.parametrize("field", ["method", "distribution"])
@pytest.mark.parametrize("value", ["", "SS", "IR001", "1", "é", None, True, 1, " R"])
def test_codes_require_one_ascii_letter(simulation, planting, field, value):
    planting[field] = value
    assert any(field in p and "single ASCII letter" in p for p in simulation.check())


def test_optional_fields_pass_without_repair(simulation, planting):
    planting.update(emergence_date="2024-02-29", emergence_population=7, row_direction=90,
                    planting_material_weight=10, transplant_age=20, transplant_environment=25,
                    plants_per_hill=2, sprout_length=0, date="1982-02-25", method="x")
    before = deepcopy(simulation.management)
    assert simulation.check() == []
    assert simulation.management == before


@pytest.mark.parametrize("data", [{"treatments": {}}, {"treatments": {2: {}}}])
def test_omitted_treatment_or_planting_is_valid(simulation, capsys, data):
    simulation.management = data
    assert simulation.check() == []
    assert "Management data: OK" in capsys.readouterr().out


def test_all_inputs_reported_together_in_order(simulation, planting, capsys):
    simulation.soil = [dict(soil_id="IBMZ910214", salb=0.13, slro=60, sldr=0.5,
        slpf=1, slb=5, slll=0.1, sdul=0.24, ssat=0.45, srgf=1)]
    assert simulation.check() == []
    report = capsys.readouterr().out
    assert report.index("Weather data: OK") < report.index("Soil data: OK") < report.index("FileX: OK")
    simulation.weather[0]["rain"] = -1
    simulation.soil[0]["slb"] = -1
    simulation.filex.write_text(SAMPLE.replace("82056", "bad!!"), encoding="latin-1")
    simulation.management["treatments"][2] = {"planting": dict(planting, population=0, depth=-1)}
    problems = simulation.check()
    assert len(problems) == 5
    for word in ("rain", "slb", "SDATE", "population", "depth"):
        assert any(word in p for p in problems)
    report = capsys.readouterr().out
    for label in ("Weather data", "Soil data", "FileX", "Management data", "Treatment 2"):
        assert f"{label}: REJECTED" in report
    assert "Treatment 1: OK" in report and "planting: OK" in report
    assert all(p in report for p in problems)


def test_missing_filex_skips_membership_but_checks_all_shapes(simulation, planting):
    simulation.filex = simulation.filex.with_name("missing.MZX")
    simulation.management["treatments"][99] = {"planting": dict(planting, depth=-1)}
    problems = simulation.check()
    assert sum("Cannot read FileX" in p for p in problems) == 1
    assert any("99" in p and "depth" in p for p in problems)
    assert not any("does not exist" in p for p in problems)


def test_without_management_stays_quiet_unless_verbose(simulation, capsys):
    simulation.management = None
    assert simulation.check() == []
    assert capsys.readouterr().out == ""
    assert simulation.check(verbose=True) == []
    assert "Weather data: OK" in capsys.readouterr().out
    simulation.weather[0]["rain"] = -1
    problems = simulation.check()
    assert capsys.readouterr().out == ""
    assert simulation.check(verbose=True) == problems
    assert "Weather data: REJECTED" in capsys.readouterr().out


def test_construction_defers_reads_and_checks_write_nothing(simulation, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Construction must not read; checks must not write or run DSSAT")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        missing = Simulation(tmp_path / "missing.MZX", 1, [], management=object())
    assert missing.check()
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    original = deepcopy(simulation.management)
    monkeypatch.setattr(subprocess, "run", forbidden)
    assert simulation.check() == []
    assert simulation.management == original
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before
    simulation.management["treatments"][1]["planting"]["depth"] = -1
    assert any("depth" in p for p in simulation.check())
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before


@pytest.fixture(params=["irrigation", "fertilizer"])
def events(request, simulation):
    section = request.param
    event = (dict(date="1982-02-25", amount=12.5, method="IR001")
             if section == "irrigation" else
             dict(date="1982-02-25", material="FE001", application="AP001", depth=0, n=30))
    simulation.management["treatments"][1][section] = [event]
    return section, event


def test_events_report_every_event_without_mutation(simulation, events, capsys, tmp_path, monkeypatch):
    section, event = events
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1982-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in (25, 26, 27)
    ]
    simulation.management["treatments"][1][section] += [
        dict(event, date="1982-02-26"), dict(event, date="1982-02-27")]
    before = deepcopy(simulation.management)
    files = {p: p.read_bytes() for p in tmp_path.rglob("*")}

    def forbidden(*args, **kwargs):
        pytest.fail("Checks must not write files or run DSSAT")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    assert simulation.check() == []
    report = capsys.readouterr().out
    assert f"{section}: OK" in report
    for number in (1, 2, 3):
        assert f"event {number}: OK" in report
    assert simulation.management == before
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == files


def test_event_missing_fields_all_reported(simulation, events, capsys):
    section, event = events
    required = list(event)
    event.clear()
    problems = simulation.check()
    assert len(problems) == len(required)
    for field in required:
        assert any(all(word in p for word in ("treatment 1", section, "event 1", field,
                                              "missing", "Add")) for p in problems)
    report = capsys.readouterr().out
    assert "event 1: REJECTED" in report
    assert all(p in report for p in problems)


@pytest.mark.parametrize("value", [None, {}, "events", 1, ()])
def test_event_section_requires_list(simulation, events, capsys, value):
    section, _ = events
    simulation.management["treatments"][1][section] = value
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("treatment 1", section, "list", "Supply"))
    assert problems[0] in capsys.readouterr().out


@pytest.mark.parametrize("value", [None, [], "event", 1])
def test_event_requires_dict_and_later_events_are_checked(simulation, events, capsys, value):
    section, event = events
    simulation.management["treatments"][1][section] = [value, dict(event)]
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("treatment 1", section, "event 1", "dict"))
    report = capsys.readouterr().out
    assert "event 1: REJECTED" in report and "event 2: OK" in report


@pytest.mark.parametrize("field", ["extra", "Amount", 3])
def test_event_unknown_fields(simulation, events, field):
    section, event = events
    event[field] = 1
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("treatment 1", section, "event 1", str(field), "unknown"))


@pytest.mark.parametrize("value", ["19820225", "1982-W08-4", "1982-2-25", "1982-02-30",
    "1982-02-25T00:00:00", " 1982-02-25", "", None, False, 19820225,
    date(1982, 2, 25), datetime(1982, 2, 25)])
def test_event_dates_are_quoted_iso_strings(simulation, events, value):
    section, event = events
    event["date"] = value
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("treatment 1", section, "event 1", "date",
                                               "YYYY-MM-DD", "quote"))


@pytest.mark.parametrize("value", ["", "I001", "IR01", "IR0001", "IR\u0660\u0660\u0661", "\u00e9R001", "IR001\n",
                                  " IR001", "IR001 ", None, True, 1])
def test_event_codes_require_two_ascii_letters_and_three_digits(simulation, events, value):
    section, event = events
    fields = ("method",) if section == "irrigation" else ("material", "application")
    for field in fields:
        event[field] = value
    problems = simulation.check()
    assert len(problems) == len(fields)
    for field in fields:
        assert any(all(word in p for word in ("treatment 1", section, "event 1", field,
                                              "two ASCII letters", "three digits")) for p in problems)


@pytest.mark.parametrize("value", [-0.1, None, True, "8", float("nan"), float("inf"),
                                  -float("inf"), pytest.param(10 ** 5000, id="huge-int")])
def test_event_numbers_reject_negative_or_nonfinite_values(simulation, events, value):
    section, event = events
    fields = ("amount",) if section == "irrigation" else ("depth", "n", "p", "k")
    for field in fields:
        event[field] = value
    problems = simulation.check()
    assert len(problems) == len(fields)
    for field in fields:
        assert any(all(word in p for word in ("treatment 1", section, "event 1", field, "Supply"))
                   for p in problems)


@pytest.mark.parametrize("value", [0, 0.5])
def test_event_numeric_boundaries_and_optional_nutrients(simulation, events, value):
    section, event = events
    fields = ("amount",) if section == "irrigation" else ("depth", "n", "p", "k")
    event.update(dict.fromkeys(fields, value))
    if section == "irrigation" and value == 0:
        problems = simulation.check()
        assert len(problems) == 1
        assert "above zero, in mm" in problems[0]
    else:
        assert simulation.check() == []


@pytest.mark.parametrize("amount", [0, 0.0, -0.0, -1])
def test_irrigation_amount_must_be_above_zero(simulation, amount, capsys, tmp_path, monkeypatch):
    simulation.management["treatments"][1]["irrigation"] = [
        dict(date="1982-02-25", amount=amount, method="IR001")]
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}

    def forbidden(*args, **kwargs):
        pytest.fail("Rejected management must not run DSSAT")

    monkeypatch.setattr(subprocess, "run", forbidden)
    problems = simulation.check()
    assert problems == [
        f"Management data treatment 1, irrigation, event 1, field 'amount': found {amount!r}. "
        "Supply a number above zero, in mm."
    ]
    assert problems[0] in capsys.readouterr().out
    with pytest.raises(DSSATCheckError) as error:
        simulation.run()
    assert error.value.problems == problems
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before


def test_event_empty_and_omitted_sections_have_distinct_meanings(simulation, events, capsys):
    section, _ = events
    simulation.management["treatments"][1][section] = []
    simulation.management["treatments"][2] = {}
    assert simulation.check() == []
    report = capsys.readouterr().out
    assert f"{section}: OK (empty list; none for this treatment)" in report
    assert f"{section}: OK (omitted; keeps the FileX Level)" in report


def test_event_and_planting_problems_reported_across_treatments(simulation, planting, capsys):
    planting["depth"] = -1
    simulation.management["treatments"][2] = {
        "irrigation": [dict(date="bad", amount=-1, method="IR001"),
                       dict(date="1982-02-25", amount=1, method="IR001")],
        "fertilizer": [dict(date="1982-02-25", material="bad", application="AP001", depth=0, n=-1)],
    }
    problems = simulation.check()
    assert len(problems) == 5
    report = capsys.readouterr().out
    for label in ("Management data", "Treatment 1", "Treatment 2", "planting", "irrigation", "fertilizer"):
        assert f"{label}: REJECTED" in report
    assert "event 2: OK" in report
    assert all(p in report for p in problems)


def test_planting_before_simulation_start_date_rejected(simulation, planting, capsys):
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1982-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in range(20, 29)
    ]
    planting["date"] = "1982-02-24"
    problems = simulation.check()
    assert len(problems) == 1
    assert "1982-02-24" in problems[0] and "1982-02-25" in problems[0]
    assert all(word in problems[0].lower() for word in ("planting date", "before", "simulation start date"))
    report = capsys.readouterr().out
    assert "planting: REJECTED" in report
    assert problems[0] in report

    planting["date"] = "1982-02-25"
    assert simulation.check() == []
    planting["date"] = "1982-02-26"
    assert simulation.check() == []

    simulation.management["treatments"][2] = {"planting": dict(planting, date="1982-02-20")}
    assert simulation.check() == []


def test_planting_start_date_check_keeps_uncovered_start_year(simulation, planting, capsys):
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1990-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in range(20, 28)
    ]
    planting["date"] = "1990-02-25"
    problems = simulation.check()
    assert len(problems) == 1
    assert "FileX SDATE '82056' is 1982-02-25" in problems[0]
    assert "not covered by weather data" in problems[0]
    assert not any("planting" in p.lower() for p in problems)
    report = capsys.readouterr().out
    assert "check was skipped" not in report
    assert "planting: OK" in report

    # verbose=False prints nothing
    problems_quiet = simulation.check(verbose=False)
    assert problems_quiet == problems
    assert capsys.readouterr().out == ""


def test_planting_start_date_check_survives_weather_unreadable(simulation, planting, capsys, tmp_path):
    simulation.weather = tmp_path / "nonexistent.csv"
    problems = simulation.check()
    assert len(problems) == 1
    assert "Cannot read weather data" in problems[0]
    report = capsys.readouterr().out
    assert "planting-date-versus-start-date check was skipped" not in report

    # verbose=False prints nothing
    problems_quiet = simulation.check(verbose=False)
    assert problems_quiet == problems
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("sdate,years,reason", [
    ("21xx1", [2021], "SDATE '21xx1' is not a DSSAT date (yyddd)"),
    ("21366", [2021], "day 366 does not exist in 2021"),
    ("21001", [1921, 2021], None),
])
@pytest.mark.parametrize("planting_problem", ["none", "shape", "field", "entry", "writer"])
def test_start_skip_reason_survives_other_problems(simulation, planting, capsys,
                                                sdate, years, reason, planting_problem):
    simulation.filex.write_text(SAMPLE.replace("82056", sdate))
    simulation.weather = [dict(simulation.weather[0], date=f"{year}-01-01") for year in years]
    planting["date"] = f"{years[-1]}-01-01"
    if planting_problem == "shape":
        simulation.management["treatments"][1]["planting"] = []
    elif planting_problem == "field":
        planting["date"] = "bad"
    elif planting_problem == "entry":
        simulation.management["treatments"][1]["typo"] = 1
    elif planting_problem == "writer":
        planting["population"] = 1234567
    simulation.check()
    report = capsys.readouterr().out
    if reason is not None:
        assert "check was skipped" in report
        assert reason in report
    else:
        assert "SDATE" not in report
        assert "ambiguous start year" not in report
        if planting_problem == "none":
            assert "check was skipped" not in report


def test_unselected_treatment_reports_start_check_skip(simulation, planting, capsys):
    simulation.management["treatments"][2] = {"planting": dict(planting)}
    assert simulation.check() == []
    report = capsys.readouterr().out.split("Treatment 2:")[1]
    assert "check was skipped" in report
    assert "selected treatment" in report


def test_bad_planting_date_reports_start_check_skip(simulation, planting, capsys):
    planting["date"] = "bad"
    assert simulation.check()
    report = capsys.readouterr().out
    assert "check was skipped" in report
    assert "planting date is missing or invalid" in report


@pytest.mark.parametrize("section", ["planting", "irrigation", "fertilizer"])
@pytest.mark.parametrize("target_date", ["1982-02-19", "1982-03-01"])
def test_date_outside_weather_range_rejected(simulation, planting, section, target_date, capsys):
    simulation.filex.write_text(SAMPLE.replace("82056", "82051"), encoding="latin-1")
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1982-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in range(20, 29)
    ]
    if section == "planting":
        planting["date"] = target_date
    elif section == "irrigation":
        simulation.management["treatments"][1]["irrigation"] = [
            dict(date=target_date, amount=10, method="IR001")
        ]
    else:
        simulation.management["treatments"][1]["fertilizer"] = [
            dict(date=target_date, material="FE001", application="AP001", depth=0, n=20)
        ]
    problems = simulation.check()
    assert any(target_date in p and "outside weather range" in p and "1982-02-20 to 1982-02-28" in p
               for p in problems)
    report = capsys.readouterr().out
    assert f"{section}: REJECTED" in report


def test_dates_on_weather_boundaries_pass(simulation, planting):
    simulation.filex.write_text(SAMPLE.replace("82056", "82051"), encoding="latin-1")
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1982-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in range(20, 29)
    ]
    planting["date"] = "1982-02-20"
    simulation.management["treatments"][1]["irrigation"] = [
        dict(date="1982-02-20", amount=10, method="IR001"),
        dict(date="1982-02-28", amount=15, method="IR001"),
    ]
    assert simulation.check() == []


def test_non_selected_treatment_dates_outside_weather_pass(simulation, planting):
    simulation.management["treatments"][2] = {
        "planting": dict(planting, date="1999-01-01"),
        "irrigation": [dict(date="1999-01-02", amount=10, method="IR001")],
        "fertilizer": [dict(date="1999-01-03", material="FE001", application="AP001", depth=0, n=20)],
    }
    assert simulation.check() == []


@pytest.mark.parametrize("section", ["irrigation", "fertilizer"])
def test_duplicate_dates_in_one_list_rejected(simulation, section, capsys):
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1982-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in (25, 26)
    ]
    event = (dict(date="1982-02-25", amount=10, method="IR001") if section == "irrigation" else
             dict(date="1982-02-25", material="FE001", application="AP001", depth=0, n=20))
    simulation.management["treatments"][1][section] = [dict(event), dict(event)]
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("duplicate date", "1982-02-25", "events 1 and 2"))
    report = capsys.readouterr().out
    assert "event 1: OK" in report
    assert "event 2: REJECTED" in report
    assert problems[0] in report


@pytest.mark.parametrize("section", ["irrigation", "fertilizer"])
def test_out_of_order_events_rejected(simulation, section, capsys):
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1982-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in (25, 26)
    ]
    event = (dict(amount=10, method="IR001") if section == "irrigation" else
             dict(material="FE001", application="AP001", depth=0, n=20))
    simulation.management["treatments"][1][section] = [
        dict(event, date="1982-02-26"),
        dict(event, date="1982-02-25"),
    ]
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("1982-02-25", "not in ascending order"))
    report = capsys.readouterr().out
    assert "event 1: OK" in report
    assert "event 2: REJECTED" in report


def test_duplicate_dates_and_order_checked_across_all_treatments(simulation):
    simulation.management["treatments"][2] = {
        "irrigation": [
            dict(date="1982-02-26", amount=10, method="IR001"),
            dict(date="1982-02-25", amount=10, method="IR001"),
        ]
    }
    problems = simulation.check()
    assert len(problems) == 1
    assert "treatment 2" in problems[0].lower() and "not in ascending order" in problems[0]


def test_unparsed_event_dates_skipped_for_order_and_duplicates(simulation):
    simulation.management["treatments"][1]["irrigation"] = [
        dict(date="1982-02-25", amount=10, method="IR001"),
        dict(date="not-a-date", amount=10, method="IR001"),
        dict(date="1982-02-25", amount=10, method="IR001"),
    ]
    problems = simulation.check()
    assert len(problems) == 2
    assert any("YYYY-MM-DD" in p and "event 2" in p for p in problems)
    assert any("duplicate date" in p and "event 3" in p and "events 1 and 3" in p for p in problems)
    assert not any("not in ascending order" in p for p in problems)


def test_fertilizer_and_irrigation_before_planting_allowed(simulation, planting):
    simulation.filex.write_text(SAMPLE.replace("82056", "82032"), encoding="latin-1")
    simulation.weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=f"1982-02-{day:02d}", srad=20, tmax=25, tmin=10, rain=0)
        for day in range(1, 29)
    ]
    planting["date"] = "1982-02-20"
    simulation.management["treatments"][1]["fertilizer"] = [
        dict(date="1982-02-05", material="FE001", application="AP001", depth=0, n=30)
    ]
    simulation.management["treatments"][1]["irrigation"] = [
        dict(date="1982-02-10", amount=25.0, method="IR001")
    ]
    assert simulation.check() == []


def test_unreadable_weather_keeps_start_bound_and_skips_coverage(simulation, tmp_path, planting):
    planting["date"] = "1980-01-01"
    simulation.weather = tmp_path / "missing_weather.csv"
    problems = simulation.check()
    assert len(problems) == 2
    assert "Cannot read weather data" in problems[0]
    assert "before simulation start date '1982-02-25'" in problems[1]
    assert not any("outside weather range" in p for p in problems)


def test_empty_weather_keeps_start_bound_and_skips_coverage(simulation, planting):
    planting["date"] = "1980-01-01"
    simulation.weather = []
    problems = simulation.check()
    assert len(problems) == 2
    assert "no daily rows" in problems[0]
    assert "before simulation start date '1982-02-25'" in problems[1]
    assert not any("outside weather range" in p for p in problems)


def test_unreadable_filex_or_start_skips_dependent_checks(simulation, tmp_path, planting):
    planting["date"] = "1982-02-25"
    # Missing FileX: start date cannot be read
    simulation.filex = tmp_path / "missing.MZX"
    problems = simulation.check()
    assert len(problems) == 1
    assert "Cannot read FileX" in problems[0]
    assert not any("before simulation start date" in p for p in problems)

    # Invalid SDATE in FileX: start date cannot be read
    path = tmp_path / "UFGA8201.MZX"
    path.write_text(SAMPLE.replace("82056", "bad!!"), encoding="latin-1")
    simulation.filex = path
    problems = simulation.check()
    assert len(problems) == 1
    assert "SDATE 'bad!!' is invalid" in problems[0]
    assert not any("before simulation start date" in p for p in problems)


def test_uncovered_weather_year_keeps_start_date_check(simulation, planting):
    simulation.weather = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                               date="2024-05-10", srad=20, tmax=25, tmin=10, rain=0)]
    planting["date"] = "2024-05-10"
    problems = simulation.check()
    assert len(problems) == 1
    assert "FileX SDATE '82056' is 1982-02-25" in problems[0]
    assert "not covered by weather data" in problems[0]
    assert not any("before simulation start date" in p for p in problems)
