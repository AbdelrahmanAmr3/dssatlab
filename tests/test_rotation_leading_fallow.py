"""Leading fallows anchor the sequence's dates without changing crop-first output."""

from copy import deepcopy

import pytest

from dssatlab import DSSATCheckError, Simulation, write_filex_template
from dssatlab.filex import _section_row
from dssatlab.filex_skeleton import write_filex
from dssatlab.filex_template import _load_filex_template
from test_filex_template import data, rows
from test_season_coverage import weather
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


@pytest.fixture
def leading(data):
    data.pop("treatment_name")
    data["planting"]["date"] = "1978-03-15"
    data["harvest_date"] = "1978-08-01"
    return dict(treatment_name="Fallow then maize", rotation=[
        dict(crop="fallow", start_date="1977-12-15", end_date="1978-03-14"),
        data, dict(crop="fallow", end_date="1978-12-14")])


@pytest.fixture
def sim(leading, rows, installed):
    return Simulation(filex_template=leading, weather=weather("1977-12-15", "1978-12-14"),
                      soil=rows[1])


@pytest.mark.parametrize("end,years", [("1978-12-14", "1"), ("1979-12-14", "2")])
def test_leading_fallow_render_and_check(sim, rows, installed, tmp_path, end, years):
    sim.filex_template["rotation"][-1]["end_date"] = end
    sim.weather = weather("1977-12-15", end)
    before = deepcopy(sim.filex_template)
    files = snapshot(tmp_path)
    assert sim.check(False) == []
    assert snapshot(tmp_path) == files
    assert installed.calls == []
    path = write_filex(sim.filex_template, *rows, tmp_path,
                       data_dir=installed.executable.parent)
    assert path.name == "TEST7701.SQX"
    text = path.read_text()
    for level in range(1, 4):
        general = _section_row(text, "SIMULATION CONTROLS", "N", level, ("NYERS",))
        assert general["SDATE"] == "77349"
        assert general["NYERS"] == (years if level == 1 else "1")
    assert _section_row(text, "TREATMENTS", "N", 1, ("MP", "MH"))["MP"] == "0"
    assert _section_row(text, "HARVEST DETAILS", "H", 1, ("HDATE",))["HDATE"] == "78073"
    assert sim.filex_template == before


@pytest.mark.parametrize("override,sdate,years", [
    (None, "77349", "1"), ("1976-12-15", "76350", "2"), ("1977-12-16", "77350", "1")])
def test_leading_fallow_run_and_controls_override(sim, installed, override, sdate, years):
    start = override or "1977-12-15"
    # A later SDATE shifts the stopping day too, so cover the extra day.
    sim.weather = weather(start, "1978-12-15")
    if override:
        sim.management = {"treatments": {1: {"controls": {"start_date": override}}}}
    before = deepcopy(sim.filex_template)
    assert sim.check(False) == []
    result = sim.run()
    folder = result.run_dir.parent
    text = (folder / "UFGA7701.SQX").read_text()
    general = _section_row(text, "SIMULATION CONTROLS", "N", 1, ("NYERS",))
    assert general["SDATE"] == sdate
    assert general["NYERS"] == years
    assert (folder / f"UFGA{sdate[:2]}01.WTH").is_file()
    assert installed.calls[0][:2] == (
        [str(installed.executable), "Q", "DSSBatch.v48"], folder)
    assert (result.run_dir / "DSSBatch.v48").is_file()
    assert sim.filex_template == before


@pytest.mark.parametrize("case,expected", [
    ("missing", "FileX template, rotation[1]: a leading fallow needs start_date. "
     "Supply start_date before end_date."),
    ("equal", "FileX template, rotation[1], start_date: 1978-03-14 is not before "
     "end_date (1978-03-14). Supply start_date before end_date."),
    ("after", "FileX template, rotation[1], start_date: 1978-03-15 is not before "
     "end_date (1978-03-14). Supply start_date before end_date."),
    ("later_crop", "FileX template, rotation[2], start_date: only a leading fallow takes "
     "start_date. Remove start_date from this component."),
    ("later_fallow", "FileX template, rotation[3], start_date: only a leading fallow takes "
     "start_date. Remove start_date from this component."),
])
def test_story_14_problems(sim, installed, tmp_path, case, expected):
    components = sim.filex_template["rotation"]
    if case == "missing":
        del components[0]["start_date"]
    elif case in ("equal", "after"):
        components[0]["start_date"] = "1978-03-14" if case == "equal" else "1978-03-15"
    else:
        components[1 if case == "later_crop" else 2]["start_date"] = "1978-03-15"
    before = snapshot(tmp_path)
    assert sim.check(False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert snapshot(tmp_path) == before
    assert installed.calls == []


@pytest.mark.parametrize("value", [None, "bad", "1978-02-30", "1978-1-15"])
def test_leading_fallow_invalid_date(sim, value):
    sim.filex_template["rotation"][0]["start_date"] = value
    problems = sim.check(False)
    assert len(problems) == 1
    assert problems[0].startswith("FileX template, rotation[1], start_date:")
    assert "quoted YYYY-MM-DD" in problems[0]


@pytest.mark.parametrize("edited", [False, True])
def test_closure_uses_leading_start_instead_of_crop_planting(sim, edited):
    sim.filex_template["rotation"][0]["start_date"] = "1978-01-15"
    sim.filex_template["rotation"][-1]["end_date"] = "1979-01-14" if edited else "1979-01-15"
    sim.weather = weather("1978-01-15", "1980-01-14")
    if edited:
        sim.management = {"treatments": {1: {"rotation": {
            3: {"harvest": [{"date": "1979-01-15"}]}}}}}
    prefix = ("Management data treatment 1, rotation component 3, harvest" if edited
              else "FileX template, rotation")
    assert sim.check(False) == [
        f"{prefix}: the last component ends on 1979-01-15 (day 15 of the year), "
        "not before the simulation start's day of the year (day 15, 1978-01-15); "
        "DSSAT would start the next cycle a year late. End the last component before "
        "day 15, for example on 1979-01-14."]


def test_leading_start_day_one_rejected(sim):
    sim.filex_template["rotation"][0]["start_date"] = "1978-01-01"
    assert sim.check(False) == [
        "FileX template, rotation: the simulation start is on day 1 of the year "
        "(1978-01-01), so the last component cannot end before it in the year; "
        "DSSAT would start the next cycle a year late. Start the leading fallow after January 1."]


def test_weather_must_cover_leading_start(sim):
    sim.weather = weather("1978-03-15", "1978-12-14")
    assert sim.check(False) == [
        "Simulation start date 1977-12-15 is not covered by weather data "
        "(1978-03-15 to 1978-12-14). Supply weather for that date."]


def test_weather_must_cover_cycle_from_leading_start(sim):
    sim.weather = weather("1977-12-15", "1978-12-13")
    assert sim.check(False) == [
        "FileX NYERS 1: the sequence runs from 1977-12-15 through 1978-12-14, "
        "after the weather data ends (1978-12-13). Supply weather through 1978-12-14, or fewer years."]


@pytest.mark.parametrize("day,valid", [("1977-12-14", False), ("1977-12-15", True),
                                       ("1978-03-14", True), ("1978-03-15", False)])
def test_leading_fallow_component_period(sim, day, valid):
    sim.weather = weather("1977-12-14", "1978-12-14")
    sim.management = {"treatments": {1: {"rotation": {
        1: {"tillage": [dict(date=day, implement="TI005", depth=20)]}}}}}
    problems = sim.check(False)
    if valid:
        assert problems == []
    else:
        assert problems
        assert all("rotation component 1, tillage" in p for p in problems)
        assert any("before simulation start date (1977-12-15)" in p if day == "1977-12-14"
                   else "after rotation component 1's harvest date (1978-03-14)" in p
                   for p in problems)


def test_commented_leading_fallow_example_loads_and_passes(tmp_path, rows, installed):
    yaml = pytest.importorskip("yaml")
    path = tmp_path / "filex.yaml"
    write_filex_template(path)
    text = path.read_text()
    assert "Only a leading fallow takes start_date, before end_date" in text
    example = text.split("# Rotation example", 1)[1].splitlines()[1:]
    data = yaml.safe_load("\n".join(line[2:] for line in example if line.startswith("# ")))
    leading_text = text.split("# For example, prepend ", 1)[1].splitlines()[0]
    data["rotation"].insert(0, yaml.safe_load(leading_text))
    data["rotation"][-1]["end_date"] = "2022-01-31"
    path.write_text(yaml.safe_dump(data))
    loaded, problems = _load_filex_template(path)
    assert problems == []
    sim = Simulation(filex_template=path, weather=weather("2021-02-01", "2022-01-31"),
                     soil=rows[1])
    assert sim.check(False) == []
    assert write_filex(loaded, *rows, tmp_path, data_dir=installed.executable.parent).is_file()
