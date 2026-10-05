"""Experiment data dates must survive FileX's two-digit-year encoding."""

import pytest

from dssatlab import Simulation
from dssatlab.experiment import _check_date
from test_filex_check import filex


def range_problem(location, value):
    return (f"{location}: {value} cannot be written in a FileX: DSSAT stores two-digit years "
            "and reads 00-35 as 2000-2035 and 36-99 as 1936-1999. "
            "Use a date from 1936-01-01 to 2035-12-31.")


@pytest.mark.parametrize("value,rejected", [
    ("1935-12-31", True), ("1936-01-01", False),
    ("2035-12-31", False), ("2036-01-01", True),
])
def test_shared_date_check_filex_range(value, rejected):
    assert _check_date(value, "experiment date") == (
        [range_problem("experiment date", value)] if rejected else [])


@pytest.fixture
def simulation(filex):
    weather = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                    date="1990-01-01", srad=20, tmax=25, tmin=10, rain=0)]
    sim = Simulation(filex(sdate="90001"), 1, weather)
    with sim.filex.open("a", encoding="latin-1") as stream:
        stream.write("@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS\n"
                     " 1 MA              R     R     R     R     M\n")
    assert sim.check(False) == []
    return sim


def test_environment_event_outside_filex_range_in_1990_simulation(simulation):
    simulation.management = {"treatments": {1: {
        "environment": [dict(date="2036-01-01", srad={"multiply": 0.5})]}}}
    assert simulation.check(False) == [range_problem(
        "Management data treatment 1, environment, event 1, field 'date'", "2036-01-01")]


@pytest.mark.parametrize("field", ["auto_planting_first", "auto_planting_last"])
@pytest.mark.parametrize("value", ["1935-12-31", "2036-01-01"])
def test_automatic_planting_preserves_range_message(simulation, field, value):
    simulation.management = {"treatments": {1: {"controls": {field: value}}}}
    assert simulation.check(False) == [range_problem(
        f"Management data treatment 1, controls, field '{field}'", value)]


@pytest.mark.parametrize("section,event,controls", [
    ("residues", dict(material="RE001", amount=1500), {"residue": "R"}),
    ("tillage", dict(implement="TI005", depth=20), {}),
    ("harvest", {}, {"harvest_management": "M"}),
])
@pytest.mark.parametrize("value", ["1935-12-31", "2036-01-01"])
def test_field_operations_preserve_range_message(simulation, section, event, controls, value):
    simulation.management = {"treatments": {1: {
        section: [dict(event, date=value)], "controls": controls}}}
    problems = simulation.check(False)
    assert problems == [range_problem(
        f"Management data treatment 1, {section}, event 1, field 'date'", value)]


@pytest.mark.parametrize("field", ["date", "emergence_date"])
def test_harvest_bounds_do_not_hide_invalid_planting_date(simulation, field):
    if field == "emergence_date":
        simulation.filex.write_text(simulation.filex.read_text().replace(
            "     S 90001", "     E 90001"), encoding="latin-1")
    planting = dict(date="1990-01-01", method="S", distribution="R",
                    population=8, row_spacing=75, depth=5)
    planting[field] = "2036-01-01"
    simulation.management = {"treatments": {1: {
        "planting": planting, "harvest": [{"date": "1990-01-01"}],
        "controls": {"harvest_management": "R"}}}}
    assert range_problem(
        f"Management data treatment 1, planting, field '{field}'", "2036-01-01"
    ) in simulation.check(False)
