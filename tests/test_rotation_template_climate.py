"""Rotation climate fields use generated weather and retain calendar checks."""

import pytest

from dssatlab import DSSATCheckError
from dssatlab.filex import _section_row
from test_climate import needed_table, replace_cell
from test_rotation_dates import _EXACT_CASES, _mutated_rotation
from test_rotation_simulation import data, rows, rotation, installed, fake_dssat, sim
from test_simulation_run import snapshot
from test_template_climate import climate, controls


@pytest.mark.parametrize("method", ["W", "S"])
@pytest.mark.parametrize("form", ["str", "path", "list"])
def test_climate_rotation_with_replicates_checks_and_runs(
        sim, installed, climate, tmp_path, method, form):
    lower = climate.with_name("ufga.cli")
    climate.rename(lower)
    before = lower.read_bytes()
    sim.weather = {"str": str(lower), "path": lower, "list": [lower]}[form]
    sim.management = controls(method)
    sim.management["treatments"][1]["controls"].update(
        replicates=2, years=5, random_seed=12345)
    original = snapshot(tmp_path)
    assert sim.check(False) == []
    assert snapshot(tmp_path) == original
    assert installed.calls == []

    folder = sim.run().run_dir.parent
    text = (folder / "UFGA7801.SQX").read_text()
    assert _section_row(text, "FIELDS", "L", 1, ("WSTA",))["WSTA"] == "UFGA"
    coordinates = text.split("@L ...........XCRD", 1)[1].splitlines()[1]
    assert [float(coordinates[left:right]) for left, right in
            ((2, 18), (18, 34), (34, 44))] == [-82.37, 29.63, 10]
    for level in range(1, 5):
        general = _section_row(text, "SIMULATION CONTROLS", "N", level, ("GENERAL",))
        assert general["NREPS"] == "2" and general["RSEED"] == "12345"
        assert general["NYERS"] == ("5" if level == 1 else "1")
        assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("WTHER",))["WTHER"] == method
    assert (folder / "UFGA.CLI").read_bytes() == before == lower.read_bytes()
    assert not list(folder.glob("*.WTH"))
    assert len(installed.calls) == 1
    assert installed.calls[0][0][-2:] == ["Q", "DSSBatch.v48"]


@pytest.mark.parametrize("explicit", [False, True])
def test_climate_rotation_with_measured_weather_reports_spec_message(sim, installed, climate, explicit):
    sim.weather = climate
    sim.management = controls("M") if explicit else None
    message = (
        "Field 1 weather is a climate file, but treatment 1 uses WTHER M. "
        "Checked the treatment's weather source. Set controls weather_source W or S, "
        "or supply weather data rows.")
    assert sim.check(False) == [message]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [message]
    assert installed.calls == []


@pytest.mark.parametrize("method", ["W", "S"])
def test_rows_rotation_with_generated_weather_reports_spec_message(sim, method):
    sim.management = controls(method)
    assert sim.check(False) == [
        f"Treatment 1 uses generated weather (WTHER {method}), but field 1 weather is data rows. "
        "Checked the field's weather source. Supply the station's .CLI file for this field."]


@pytest.mark.parametrize("method,column", [("W", "PDW"), ("S", "RTOT")])
def test_climate_rotation_checks_required_table(sim, installed, climate, method, column):
    sim.weather, sim.management = climate, controls(method)
    replace_cell(climate, needed_table(method), 7, column, "bad")
    problems = sim.check(False)
    assert len(problems) == 1
    assert all(detail in problems[0] for detail in (needed_table(method), "month 7", column, "bad"))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert installed.calls == []


@pytest.mark.parametrize("case,message", _EXACT_CASES)
def test_climate_rotation_keeps_calendar_order_checks(sim, installed, climate, case, message):
    sim.weather, sim.management = climate, controls("W")
    sim.filex_template = _mutated_rotation(sim.filex_template, case)
    assert sim.check(False) == [message]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [message]
    assert installed.calls == []


@pytest.mark.parametrize("field", ["planting", "harvest_date", "end_date"])
def test_climate_rotation_keeps_invalid_template_dates(sim, installed, climate, field):
    sim.weather, sim.management = climate, controls("W")
    component = sim.filex_template["rotation"][1 if field == "end_date" else 0]
    if field == "planting":
        component[field]["date"] = "1978-02-30"
    else:
        component[field] = "1978-02-30"
    problems = sim.check(False)
    assert any(field in p and "valid ISO calendar date" in p for p in problems), problems
    assert all("weather range" not in p and "covered by weather" not in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert installed.calls == []


def component_management(sim):
    return dict(
        planting=dict(sim.filex_template["rotation"][0]["planting"], date="1978-03-16"),
        irrigation=[dict(date="1978-04-01", amount=20, method="IR001")],
        fertilizer=[dict(date="1978-04-02", material="FE005", application="AP001", depth=5, n=40)],
        residues=[dict(date="1978-04-03", material="RE001", amount=100)],
        tillage=[dict(date="1978-04-04", implement="TI001", depth=10)],
        harvest=[dict(date="1978-08-01")])


def test_climate_rotation_skips_daily_management_coverage(sim, climate):
    sim.weather, sim.management = climate, controls("W")
    entry = component_management(sim)
    entry.pop("residues")  # Rotation templates use RESID N and cannot edit that code.
    sim.management["treatments"][1].update(rotation={1: entry})
    sim.management["treatments"][1]["controls"].update(start_date="1978-03-01", years=5)
    assert sim.check(False) == []


@pytest.mark.parametrize("section", ["planting", "irrigation", "fertilizer", "residues", "tillage", "harvest"])
def test_climate_rotation_keeps_invalid_management_dates(sim, climate, section):
    sim.weather, sim.management = climate, controls("W")
    entry = component_management(sim)
    sim.management["treatments"][1].update(rotation={1: entry})
    event = entry[section] if section == "planting" else entry[section][0]
    event["date"] = "1978-02-30"
    problems = sim.check(False)
    assert any(section in p and "valid ISO calendar date" in p for p in problems), problems
    assert all("weather range" not in p and "covered by weather" not in p for p in problems)
