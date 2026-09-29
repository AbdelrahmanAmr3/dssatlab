"""Management data checks and reports through Simulation.check() only."""

from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
import subprocess

import pytest

from dssatlab import Simulation


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
    assert "soil" not in report
    assert "crop-specific fields are checked by dssat at run time" in report


@pytest.mark.parametrize("field", REQUIRED)
def test_missing_required_field_names_location_and_action(simulation, planting, capsys, field):
    del planting[field]
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0].lower() for word in ("treatment 1", "planting", field, "missing", "add"))
    report = capsys.readouterr().out
    assert "planting: REJECTED" in report and problems[0] in report


@pytest.mark.parametrize("data,word", [
    ([], "dict"), (42, "dict"), ("missing.yaml", "dict"), (Path("missing.yaml"), "dict"),
    ({}, "treatments"), ({"treatment": {}}, "unknown"),
    ({"treatments": []}, "dict"), ({"treatments": None}, "dict"),
    ({"treatments": {1: []}}, "dict"), ({"treatments": {1: None}}, "dict"),
    ({"treatments": {1: {"plantng": {}}}}, "plantng"),
    ({"treatments": {1: {"irrigation": []}}}, "irrigation"),
    ({"treatments": {1: {"fertilizer": []}}}, "fertilizer"),
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


def test_optional_fields_and_dates_outside_weather_pass_without_repair(simulation, planting):
    planting.update(emergence_date="2024-02-29", emergence_population=7, row_direction=90,
                    planting_material_weight=10, transplant_age=20, transplant_environment=25,
                    plants_per_hill=2, sprout_length=0, date="1980-01-01", method="x")
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
