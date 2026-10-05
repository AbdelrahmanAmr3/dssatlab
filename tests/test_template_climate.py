"""Template fields take rows or one climate file, checked for the run treatment."""

import csv
from pathlib import Path

import pytest

from dssatlab import Simulation
from dssatlab.climate_file import _climate_station, _read_climate_header
from test_climate import DTCM, UFGA, needed_table, replace_cell
from test_simulation_run import fake_dssat
from test_simulation_template import data, installed, rows


@pytest.fixture
def climate(tmp_path):
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA, encoding="ascii")
    return path


def controls(method, treatment=1):
    return {"treatments": {treatment: {"controls": {"weather_source": method}}}}


def test_climate_field_needs_generated_weather(data, rows, installed, climate):
    problems = Simulation(filex_template=data, weather=climate, soil=rows[1]).check(False)
    assert problems == [
        "Field 1 weather is a climate file, but treatment 1 uses WTHER M. "
        "Checked the treatment's weather source. Set controls weather_source W or S, "
        "or supply weather data rows."]


@pytest.mark.parametrize("method", ["W", "S"])
def test_generated_weather_needs_climate_field(data, rows, installed, method):
    problems = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                          management=controls(method)).check(False)
    assert problems == [
        f"Treatment 1 uses generated weather (WTHER {method}), but field 1 weather is data rows. "
        "Checked the field's weather source. Supply the station's .CLI file for this field."]


@pytest.mark.parametrize("other", ["rows", "weather", "climate", "csv"])
@pytest.mark.parametrize("mapping", [False, True])
def test_climate_cannot_mix_with_other_weather(
        data, rows, installed, climate, tmp_path, other, mapping):
    value = {"rows": rows[0][0], "weather": tmp_path / "UFGA2101.WTH",
             "climate": climate, "csv": tmp_path / "weather.csv"}[other]
    weather = [climate, value]
    if mapping:
        weather = {"1": weather}
    problems = Simulation(filex_template=data, weather=weather, soil=rows[1],
                          management=controls("W")).check(False)
    assert problems == [
        "Field 1 weather mixes a climate file with other weather. "
        "Supply one .CLI path or only data rows."]


@pytest.mark.parametrize("method", ["W", "S"])
@pytest.mark.parametrize("form", ["str", "path", "list"])
def test_climate_path_forms_are_accepted(data, rows, installed, climate, method, form):
    # Lowercase names work too; the station dict keeps the DSSAT station uppercase.
    lower = climate.with_name("ufga.cli")
    climate.rename(lower)
    source = {"str": str(lower), "path": lower, "list": [str(lower)]}[form]
    assert Simulation(filex_template=data, weather=source, soil=rows[1],
                      management=controls(method)).check(False) == []


def test_climate_requires_exact_station_filename(data, rows, installed, climate):
    extra = climate.with_name("UFGA-extra.CLI")
    climate.rename(extra)
    problems = Simulation(filex_template=data, weather=extra, soil=rows[1],
                          management=controls("W")).check(False)
    assert len(problems) == 1
    assert "UFGA-extra.CLI" in problems[0] and "UFGA.CLI" in problems[0]
    assert "Checked @ INSI" in problems[0]


@pytest.mark.parametrize("method,column", [("W", "PDW"), ("S", "RTOT")])
def test_selected_field_checks_its_required_table(
        data, rows, installed, climate, method, column):
    replace_cell(climate, needed_table(method), 7, column, "bad")
    problems = Simulation(filex_template=data, weather=climate, soil=rows[1],
                          management=controls(method)).check(False)
    assert len(problems) == 1
    assert all(detail in problems[0] for detail in (needed_table(method), "month 7", column, "bad"))


@pytest.mark.parametrize("method,table", [("W", "MONTHLY AVERAGES"), ("S", "WGEN PARAMETERS")])
def test_selected_field_ignores_the_other_table(data, rows, installed, climate, method, table):
    climate.write_text(climate.read_text().replace("*" + table, "*UNUSED"))
    assert Simulation(filex_template=data, weather=climate, soil=rows[1],
                      management=controls(method)).check(False) == []


@pytest.mark.parametrize("selected", [1, 2])
@pytest.mark.parametrize("method", ["M", "W", "S"])
def test_other_climate_field_checks_only_header(
        data, rows, installed, climate, tmp_path, selected, method):
    data.pop("treatment_name")
    data.update(treatments=["Measured", "Generated"], treatment_fields=[1, 2])
    broken = tmp_path / "DTCM.CLI"
    broken.write_text(DTCM.split("*MONTHLY AVERAGES", 1)[0])
    # The other field has no tables, regardless of the selected field's source.
    weather = {selected: rows[0] if method == "M" else climate, 3 - selected: broken}
    soil = {1: rows[1], 2: rows[1]}
    sim = Simulation(filex_template=data, weather=weather, soil=soil, treatment=selected,
                     management=controls(method, selected))
    assert sim.check(False) == []
    broken.write_text(broken.read_text().replace("  DTCM ", "  XXXX "))
    assert any("INSI" in p and "XXXX" in p for p in sim.check(False))


def test_selected_second_field_uses_its_treatments_method(data, rows, installed, climate):
    data.pop("treatment_name")
    data.update(treatments=["Measured", "Generated"], treatment_fields=[1, 2])
    sim = Simulation(filex_template=data, weather={1: rows[0], 2: climate},
                     soil={1: rows[1], 2: rows[1]}, treatment="2", management=controls("S", "2"))
    assert sim.check(False) == []
    sim.management = controls("M", "2")
    assert sim.check(False) == [
        "Field 2 weather is a climate file, but treatment 2 uses WTHER M. "
        "Checked the treatment's weather source. Set controls weather_source W or S, "
        "or supply weather data rows."]
    sim.weather[2] = [dict(rows[0][0], station="DTCM")]
    sim.management = controls("W", "2")
    assert sim.check(False) == [
        "Treatment 2 uses generated weather (WTHER W), but field 2 weather is data rows. "
        "Checked the field's weather source. Supply the station's .CLI file for this field."]


@pytest.mark.parametrize("mapping", [False, True])
@pytest.mark.parametrize("form", [str, Path])
def test_csv_paths_still_supply_measured_weather(data, rows, installed, tmp_path, mapping, form):
    path = tmp_path / "weather.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0][0])
        writer.writeheader()
        writer.writerows(rows[0])
    source = {1: form(path)} if mapping else form(path)
    assert Simulation(filex_template=data, weather=source, soil=rows[1]).check(False) == []


def test_checked_header_supplies_station_coordinates_without_daily_rows(climate):
    climate.write_text(climate.read_text().split("*MONTHLY AVERAGES", 1)[0])
    before = climate.read_bytes()
    assert _read_climate_header(climate)[2] == []
    assert _climate_station(climate) == dict(station="UFGA", latitude=29.63,
                                            longitude=-82.37, elevation=10.0)
    assert climate.read_bytes() == before
