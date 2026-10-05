"""Controls-only start dates respect inherited recorded planting dates (#317)."""

from copy import deepcopy
from datetime import date

import pytest

from dssatlab import DSSATCheckError, Simulation
from dssatlab.filex_skeleton import write_filex
from test_filex_template import data, rows
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


@pytest.fixture
def template_sim(data, rows, installed):
    weather = [dict(rows[0][0], date=date(2021, 3, day)) for day in range(1, 5)]
    return Simulation(filex_template=data, weather=weather, soil=rows[1], management={
        "treatments": {"01": {"controls": {"start_date": "2021-03-02"}}}})


@pytest.fixture
def copied_sim(template_sim, installed, tmp_path):
    sim = template_sim
    sim.filex = write_filex(sim.filex_template, sim.weather, sim.soil, tmp_path,
                           data_dir=installed.executable.parent)
    sim.filex_template = None
    return sim


@pytest.fixture(params=["copied_sim", "template_sim"], ids=["copied", "template"])
def inherited_sim(request):
    return request.getfixturevalue(request.param)


def test_start_after_inherited_planting_is_a_problem(inherited_sim, installed, tmp_path, capsys):
    sim = inherited_sim
    label = sim.filex if sim.filex is not None else "template"
    expected = ("Controls start_date 2021-03-02 is after the planting date 2021-03-01 "
                f"recorded in FileX {label} treatment 1. Set start_date on or before planting.")
    before, inputs = snapshot(tmp_path), deepcopy(sim.management)
    assert sim.check(verbose=True) == [expected]
    assert expected in capsys.readouterr().out
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert snapshot(tmp_path) == before
    assert sim.management == inputs
    assert installed.calls == []


def test_start_equal_to_inherited_planting_passes(inherited_sim):
    inherited_sim.management["treatments"]["01"]["controls"]["start_date"] = "2021-03-01"
    assert inherited_sim.check(verbose=False) == []


@pytest.mark.parametrize("plant", ["A", "F"])
def test_automatic_planting_uses_window_only(inherited_sim, plant):
    controls = inherited_sim.management["treatments"]["01"]["controls"]
    controls.update(planting_management=plant, auto_planting_first="2021-03-02",
                    auto_planting_last="2021-03-03")
    assert inherited_sim.check(verbose=False) == []
    controls["auto_planting_first"] = "2021-03-01"
    problems = inherited_sim.check(verbose=False)
    assert len(problems) == 1
    assert "before simulation start date" in problems[0]
    assert "recorded in FileX" not in problems[0]


def test_explicit_planting_keeps_existing_check(inherited_sim):
    sim = inherited_sim
    sim.management["treatments"]["01"]["planting"] = dict(
        date="2021-03-01", method="S", distribution="R", population=8,
        row_spacing=75, depth=3)
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert "planting date '2021-03-01' is before simulation start date '2021-03-02'" in problems[0]
    assert "recorded in FileX" not in problems[0]
    sim.management["treatments"]["01"]["planting"]["date"] = "2021-03-03"
    assert sim.check(verbose=False) == []


def test_omitted_start_date_adds_no_problem(inherited_sim):
    inherited_sim.management["treatments"]["01"]["controls"] = {"water": "N"}
    assert inherited_sim.check(verbose=False) == []


@pytest.mark.parametrize("plant", ["A", "F"])
def test_inherited_automatic_code_adds_no_recorded_planting_problem(copied_sim, plant):
    path = copied_sim.filex
    text = path.read_text(encoding="latin-1").replace(" 1 MA              R", f" 1 MA              {plant}")
    text = text.replace(" 1 PL          21060 21060", " 1 PL          21061 21062")
    path.write_text(text, encoding="latin-1")
    assert copied_sim.check(verbose=False) == []
    copied_sim.management["treatments"]["01"]["controls"]["planting_management"] = "R"
    assert any("recorded in FileX" in p for p in copied_sim.check(verbose=False))


@pytest.mark.parametrize("start", ["P", "E"])
def test_non_s_start_does_not_use_start_override(copied_sim, start):
    path = copied_sim.filex
    path.write_text(path.read_text(encoding="latin-1").replace("S 21060", f"{start} 21060"),
                    encoding="latin-1")
    assert copied_sim.check(verbose=False) == []


@pytest.mark.parametrize("pdate", ["-99", "21000", "bad"])
def test_unreadable_inherited_date_adds_no_comparison(copied_sim, pdate):
    path = copied_sim.filex
    text = path.read_text(encoding="latin-1")
    text = text.replace(" 1 21060   -99", f" 1 {pdate:>5}   -99")
    path.write_text(text, encoding="latin-1")
    assert copied_sim.check(verbose=False) == []


@pytest.mark.parametrize("start", ["2021-03-02", "2021-03-04"])
@pytest.mark.parametrize("source", ["copied", "template"])
def test_selected_treatment_uses_its_planting_and_controls_levels(template_sim, installed,
                                                                 tmp_path, source, start):
    sim = template_sim
    first = dict(crop="maize", cultivar={"code": "IB0035"},
                 planting=sim.filex_template["planting"])
    sim.filex_template = {"crops": [first, dict(first, planting=dict(first["planting"],
        date="2021-03-03"))], "treatments": ["First", "Second"], "treatment_crops": [1, 2]}
    if source == "copied":
        sim.filex = write_filex(sim.filex_template, sim.weather, sim.soil, tmp_path,
                               data_dir=installed.executable.parent)
        sim.filex_template = None
    sim.treatment = "02"
    sim.management = {"treatments": {"02": {"controls": {"start_date": start}}}}
    label = sim.filex if sim.filex is not None else "template"
    expected = ([] if start == "2021-03-02" else [
        "Controls start_date 2021-03-04 is after the planting date 2021-03-03 "
        f"recorded in FileX {label} treatment 2. Set start_date on or before planting."])
    assert sim.check(verbose=False) == expected
