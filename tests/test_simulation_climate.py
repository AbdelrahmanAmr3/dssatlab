"""Generated weather inputs are selected by the run treatment's WTHER."""

import pytest
import re

from dssatlab import DSSATCheckError, Simulation
from test_climate import DTCM, UFGA
from dssatlab.filex import _section_row
from test_simulation_run import fake_dssat, inputs, soil_rows
from test_simulation_template import data, installed, rows
from test_simulation_stock_weather import stock_file
from test_sequence import sequence, change_component


def set_method(filex, method):
    filex.write_text(filex.read_text() +
                    f"\n@N METHODS     WTHER\n 1 ME              {method}\n")


@pytest.mark.parametrize("method,source,expected", [
    ("M", "weather", []),
    ("M", "climate", ["needs weather data", "climate file", "unused"]),
    ("M", "both", ["climate file", "unused"]),
    ("M", "neither", ["needs weather data"]),
    ("W", "weather", ["UFGA.CLI", "Weather/Climate", "weather data", "unused"]),
    ("W", "climate", []),
    ("W", "both", ["weather data", "unused"]),
    ("W", "neither", ["UFGA.CLI", "Weather/Climate"]),
    ("S", "weather", ["UFGA.CLI", "Weather/Climate", "weather data", "unused"]),
    ("S", "climate", []),
    ("S", "both", ["weather data", "unused"]),
    ("S", "neither", ["UFGA.CLI", "Weather/Climate"]),
])
def test_weather_input_matrix(inputs, tmp_path, method, source, expected):
    set_method(inputs.filex, method)
    climate = tmp_path / "ufga.cli"
    climate.write_text(UFGA)
    weather = stock_file(tmp_path, "UFGA8201.WTH")
    supplied = {"weather": weather, "climate": climate,
                "both": [weather, climate], "neither": None}[source]
    problems = Simulation(inputs.filex, 2, supplied).check(False)
    if not expected:
        assert problems == []
    else:
        message = "\n".join(problems)
        for detail in expected:
            assert detail in message
        assert all("Checked " in problem for problem in problems)


def test_unsupported_weather_method_lists_supported_methods(inputs):
    set_method(inputs.filex, "G")
    problems = Simulation(inputs.filex, 2, inputs.rows).check(False)
    assert any("WTHER 'G'" in p and "M, W, S" in p for p in problems)


def test_run_copies_climate_bytes_under_uppercase_name(inputs, fake_dssat, tmp_path):
    inputs.filex.write_text(inputs.filex.read_text().replace("UFGA       -99", "DTCM       -99"))
    set_method(inputs.filex, "S")
    climate = tmp_path / "dtcm.cli"
    climate.write_bytes(DTCM.replace("\n", "\r\n").encode("ascii"))
    before = climate.read_bytes()
    result = Simulation(inputs.filex, 2, climate).run()
    folder = result.run_dir.parent
    assert (folder / "DTCM.CLI").read_bytes() == before
    assert not list(folder.glob("*.WTH"))
    assert climate.read_bytes() == before


def test_climate_filename_must_match_wsta_first_four_characters(inputs, tmp_path):
    set_method(inputs.filex, "S")
    path = tmp_path / "UFGA1234.CLI"
    path.write_text(UFGA)
    problems = Simulation(inputs.filex, 2, path).check(False)
    assert any("UFGA1234.CLI" in p and "UFGA.CLI" in p for p in problems)


def test_two_climate_files_are_a_problem(inputs, tmp_path):
    set_method(inputs.filex, "S")
    paths = [tmp_path / name for name in ("UFGA.CLI", "DTCM.CLI")]
    for path, text in zip(paths, (UFGA, DTCM)):
        path.write_text(text)
    assert any("one climate file" in p for p in Simulation(inputs.filex, 2, paths).check(False))


def test_template_rejects_climate_mixed_with_rows(data, rows, installed, tmp_path):
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA)
    sim = Simulation(filex_template=data, weather=[path, tmp_path / "UFGA7801.WTH"], soil=rows[1])
    assert any("mixes a climate file with other weather" in p for p in sim.check(False))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert installed.calls == []


@pytest.mark.parametrize("method,table", [("W", "WGEN PARAMETERS"), ("S", "MONTHLY AVERAGES")])
def test_simulation_checks_required_climate_table(inputs, tmp_path, method, table):
    set_method(inputs.filex, method)
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA.replace("*" + table, "*OTHER"))
    assert any(table in p for p in Simulation(inputs.filex, 2, path).check(False))


def test_generated_weather_skips_weather_coverage_with_experiment_edits(inputs, tmp_path):
    set_method(inputs.filex, "S")
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA)
    data = {"treatments": {2: {"controls": {"years": 10, "start_date": "1982-02-25"}}}}
    assert Simulation(inputs.filex, 2, path, management=data).check(False) == []


def test_generated_weather_run_keeps_station_and_edits_supplied_soil_identity(
        inputs, fake_dssat, tmp_path, soil_rows):
    set_method(inputs.filex, "S")
    climate = tmp_path / "UFGA.CLI"
    climate.write_text(UFGA)
    soil = [dict(row, soil_id="HOME123456") for row in soil_rows]
    data = {"treatments": {2: {"controls": {"years": 10}}}}
    sim = Simulation(inputs.filex, 2, climate, soil=soil, management=data)
    assert sim.check(False) == []
    result = sim.run()
    copied = (result.run_dir.parent / inputs.filex.name).read_text()
    field = _section_row(copied, "FIELDS", "L", 1, ("WSTA", "ID_SOIL"))
    assert field["WSTA"] == "UFGA"
    assert field["ID_SOIL"] == "HOME123456"
    assert "*HOME123456" in (result.run_dir.parent / "SOIL.SOL").read_text()


def mixed_sequence(sim):
    text = sim.filex.read_text()
    text = re.sub(r"(?m)^ 1 [3-6] 1 0 .*\n", "", text)
    text = text.replace(" 2 ME              M", " 2 ME              S")
    # A fixed first harvest makes the measured period knowable before DSSAT runs.
    text = text.replace(" 1 MA              R     R     R     N     M",
                        " 1 MA              R     R     R     N     R")
    sim.filex.write_text(text)
    change_component(sim, 0, "MH", 1)


@pytest.mark.parametrize("second", ["W", "S"])
def test_mixed_sequence_weather_sources_are_a_problem(sequence, tmp_path, second):
    mixed_sequence(sequence)
    sequence.filex.write_text(sequence.filex.read_text().replace(" 2 ME              S", f" 2 ME              {second}"))
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA)
    sequence.weather = [stock_file(tmp_path, "UFGA7801.WTH", [r["date"] for r in sequence.weather]), path]
    problems = sequence.check(False)
    assert any("Sequence treatment 1" in p and "different WTHER" in p and "Checked" in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sequence.run()


@pytest.mark.parametrize("entries", [None, [], {"\u00b2": {}}, {1: {"rotation": {"\u00b2": {}}}}])
def test_mixed_sequence_reports_malformed_experiment_data(sequence, tmp_path, entries):
    mixed_sequence(sequence)
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA)
    daily = stock_file(tmp_path, "UFGA7801.WTH", [r["date"] for r in sequence.weather])
    sequence.weather = [daily, path]
    sequence.management = {"treatments": entries}
    assert sequence.check(False)
    with pytest.raises(DSSATCheckError):
        sequence.run()


@pytest.mark.parametrize("method", ["W", "S"])
@pytest.mark.parametrize("sdate", ["82366", "82000"])
def test_generated_weather_still_checks_calendar_start_date(inputs, tmp_path, method, sdate):
    set_method(inputs.filex, method)
    inputs.filex.write_text(inputs.filex.read_text().replace("S 82056", f"S {sdate}"))
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA)
    assert any("SDATE" in p for p in Simulation(inputs.filex, 2, path).check(False))


@pytest.mark.parametrize("station", ["BAD", None])
def test_bad_weather_station_with_management_override_reports_problems(inputs, station):
    data = {"treatments": {2: {"controls": {"years": 1}}}}
    rows = [dict(row) for row in inputs.rows]
    for row in rows:
        row.pop("station", None) if station is None else row.update(station=station)
    problems = Simulation(inputs.filex, 2, rows, management=data).check(False)
    assert problems
