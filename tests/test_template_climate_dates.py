"""Climate fields skip daily coverage while preserving calendar validation."""

import pytest

from dssatlab import DSSATCheckError, Simulation
from test_simulation_run import fake_dssat
from test_simulation_template import data, installed, rows
from test_template_climate import climate, controls
from test_template_climate_integration import template


def entry_for(template):
    return template["crops"][1] if "crops" in template else template


def management(template, method="W"):
    selected = 2 if "crops" in template else 1
    return selected, {"treatments": {selected: {
        "planting": dict(entry_for(template)["planting"], date="2021-03-05"),
        "irrigation": [dict(date="2021-04-01", amount=20, method="IR001")],
        "fertilizer": [dict(date="2021-04-02", material="FE005", application="AP001", depth=5, n=40)],
        "residues": [dict(date="2021-04-03", material="RE001", amount=100)],
        "tillage": [dict(date="2021-04-04", implement="TI001", depth=10)],
        "harvest": [dict(date="2021-08-01")],
        "controls": dict(weather_source=method, start_date="2020-12-01", years=5,
                         residue="R", harvest_management="R", planting_management="A",
                         auto_planting_first="2021-03-01", auto_planting_last="2021-03-10"),
    }}}


@pytest.mark.parametrize("method", ["W", "S"])
def test_climate_skips_coverage_for_template_and_all_management_dates(
        template, rows, installed, climate, method):
    entry_for(template)["harvest_date"] = "2021-08-01"
    selected, edits = management(template, method)
    sim = Simulation(filex_template=template, weather=climate, soil=rows[1],
                     treatment=selected, management=edits)
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    # The FileX name retains the template's planting year after a start-date edit.
    assert (folder / "UFGA2101.MZX").is_file()
    assert not list(folder.glob("*.WTH"))


@pytest.mark.parametrize("field,value,word", [
    ("planting", "2021-02-30", "valid ISO calendar date"),
    ("harvest_date", "2021-02-30", "valid ISO calendar date"),
    ("harvest_date", "2021-02-28", "not after the planting date"),
])
def test_climate_preserves_template_date_validity_and_order(
        template, rows, installed, climate, field, value, word):
    entry = entry_for(template)
    if field == "planting":
        entry["planting"]["date"] = value
    else:
        entry[field] = value
    selected = 2 if "crops" in template else 1
    sim = Simulation(filex_template=template, weather=climate, soil=rows[1],
                     treatment=selected, management=controls("W", selected))
    problems = sim.check(False)
    assert problems and any(word in p for p in problems), problems
    assert all("weather range" not in p and "covered by weather" not in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert installed.calls == []


@pytest.mark.parametrize("section", ["planting", "irrigation", "fertilizer", "residues",
                                     "tillage", "harvest", "start_date", "auto_planting_first"])
def test_climate_preserves_invalid_management_dates(
        template, rows, installed, climate, section):
    selected, edits = management(template)
    entry = edits["treatments"][selected]
    if section == "planting":
        entry[section]["date"] = "2021-02-30"
    elif section in ("start_date", "auto_planting_first"):
        entry["controls"][section] = "2021-02-30"
    else:
        entry[section][0]["date"] = "2021-02-30"
    sim = Simulation(filex_template=template, weather=climate, soil=rows[1],
                     treatment=selected, management=edits)
    problems = sim.check(False)
    assert any(section in p and "valid ISO calendar date" in p for p in problems), problems
    assert all("weather range" not in p and "covered by weather" not in p for p in problems)


@pytest.mark.parametrize("section", ["irrigation", "fertilizer", "residues", "tillage", "harvest",
                                     "auto_planting_first", "planting"])
def test_climate_preserves_management_date_order(
        template, rows, installed, climate, section):
    selected, edits = management(template)
    entry = edits["treatments"][selected]
    if section == "auto_planting_first":
        entry["controls"][section] = "2021-03-11"
        word = "after auto_planting_last"
    elif section == "planting":
        entry[section]["date"] = "2020-11-30"
        word = "before simulation start date"
    else:
        event = dict(entry[section][0], date="2021-03-20")
        entry[section].append(event)
        word = "ascending order" if section in ("irrigation", "fertilizer") else "non-descending date order"
    sim = Simulation(filex_template=template, weather=climate, soil=rows[1],
                     treatment=selected, management=edits)
    problems = sim.check(False)
    assert any(section in p and word in p for p in problems), problems
    assert all("weather range" not in p and "covered by weather" not in p for p in problems)
