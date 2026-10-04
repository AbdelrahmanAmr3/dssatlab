"""Weather controls, sequence edits and batch input selection through public seams."""

from copy import deepcopy
from pathlib import Path
import re

import pytest

from dssatlab import (DSSATCheckError, run_treatments,
                      write_experiment_template, write_management_template)
from dssatlab.filex import _section_row
from dssatlab.sequence import _rotation_components
from test_climate import UFGA
from test_controls import sim
from test_management_file import sim_inputs
from test_sequence import sequence
from test_season_coverage import weather
from test_simulation_run import fake_dssat, inputs
from test_simulation_stock_weather import stock_file


def climate(tmp_path):
    path = tmp_path / "ufga.cli"
    path.write_text(UFGA)
    return path


@pytest.mark.parametrize("key,value,column,allowed", [
    ("weather_source", value, "WTHER", '"M", "W", "S"')
    for value in ("G", "m", "", None, True, 1, [])
] + [
    (key, value, column, f"{low} to 99999")
    for key, column, low in (("replicates", "NREPS", 1), ("random_seed", "RSEED", 0))
    for value in (low - 1, 100000, True, "1", 1.0, None, [])
])
def test_bad_control_values_name_key_range_and_treatment(sim, fake_dssat, key, value, column, allowed):
    sim.management = {"treatments": {3: {"controls": {key: value}}}}
    before = sim.filex.read_bytes()
    problems = sim.check(False)
    assert any("treatment 3" in p and key in p and column in p and allowed in p
               and "Checked" in p and "Supply" in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert sim.filex.read_bytes() == before
    assert not fake_dssat.calls


@pytest.mark.parametrize("method", ["M", "W", "S"])
def test_replicates_above_one_are_a_problem_outside_a_sequence(sim, tmp_path, method):
    sim.management = {"treatments": {3: {"controls": {"weather_source": method, "replicates": 3}}}}
    if method != "M":
        sim.weather = climate(tmp_path)
    problems = sim.check(False)
    assert len(problems) == 1
    assert "DSSAT ignores NREPS outside a sequence" in problems[0]
    assert "Checked" in problems[0] and "Set replicates to 1" in problems[0]


def test_replicate_context_is_checked_when_another_control_is_bad(sim):
    sim.management = {"treatments": {3: {"controls": {"replicates": 3, "random_seed": -1}}}}
    problems = sim.check(False)
    assert len(problems) == 2
    assert any("random_seed" in p for p in problems)
    assert any("DSSAT ignores NREPS outside a sequence" in p for p in problems)


@pytest.mark.parametrize("method", ["M", "W", "S"])
@pytest.mark.parametrize("copied", [False, True])
def test_sequence_replicates_need_generated_weather(sequence, tmp_path, method, copied):
    sequence.weather = weather("1978-04-20", "1980-04-28")
    if copied:
        text = sequence.filex.read_text().replace(" 1 GE              1     1", " 1 GE              1     3")
        text = re.sub(r"(?m)^( *\d+ ME {14})M", rf"\g<1>{method}", text)
        sequence.filex.write_text(text)
    else:
        sequence.management = {"treatments": {1: {"controls": {"weather_source": method, "replicates": 3}}}}
    if method != "M":
        sequence.weather = climate(tmp_path)
    problems = sequence.check(False)
    assert len(problems) == (1 if method == "M" else 0)
    if method == "M":
        assert "every replicate repeats the same rows" in problems[0]
        assert "Checked" in problems[0]


@pytest.mark.parametrize("method", ["W", "S"])
@pytest.mark.parametrize("seed", [0, 99999])
def test_sequence_writes_weather_controls_to_every_used_level(sequence, tmp_path, fake_dssat, method, seed):
    sequence.weather = climate(tmp_path)
    sequence.management = {"treatments": {1: {"controls": {
        "weather_source": method, "replicates": 99999, "random_seed": seed,
    }}}}
    before, edits = sequence.filex.read_bytes(), deepcopy(sequence.management)
    assert sequence.check(False) == []
    result = sequence.run()
    text = (result.run_dir.parent / sequence.filex.name).read_text()
    components = _rotation_components(None, 1, text=text)
    for component in components:
        level = int(component["SM"])
        assert level > 2  # Both original levels survive unchanged.
        general = _section_row(text, "SIMULATION CONTROLS", "N", level, ("GENERAL",))
        methods = _section_row(text, "SIMULATION CONTROLS", "N", level, ("WTHER",))
        assert general["NREPS"] == "99999" and general["RSEED"] == str(seed)
        assert methods["WTHER"] == method
        row = next(line for line in text.splitlines() if line.startswith(f"{level:2} GE"))
        assert row[21:26] == "99999"
        assert row[39:44] == f"{seed:5}"
        row = next(line for line in text.splitlines() if line.startswith(f"{level:2} ME"))
        assert row[15:20] == f"{method:>5}"
    assert sequence.filex.read_bytes() == before and sequence.management == edits


def test_override_unifies_mixed_sequence_and_replaces_copied_replicates(sequence, tmp_path, fake_dssat):
    sequence.filex.write_text(sequence.filex.read_text().replace(" 2 ME              M", " 2 ME              S")
                             .replace(" 1 GE              1     1", " 1 GE              1     3"))
    sequence.management = {"treatments": {1: {"controls": {
        "weather_source": "W", "replicates": 3, "random_seed": 1234,
    }}}}
    sequence.weather = climate(tmp_path)
    assert sequence.check(False) == []
    sequence.run()
    sequence.management["treatments"][1]["controls"] = {"weather_source": "M", "replicates": 1}
    sequence.weather = weather("1978-04-20", "1980-04-28")
    assert sequence.check(False) == []


def test_mixed_generated_sequence_sources_are_a_problem(sequence, tmp_path):
    text = sequence.filex.read_text().replace(" 1 ME              M", " 1 ME              W")
    sequence.filex.write_text(text.replace(" 2 ME              M", " 2 ME              S"))
    sequence.weather = climate(tmp_path)
    assert any("different WTHER" in p for p in sequence.check(False))


def test_seasonal_copied_replicates_and_seed_remain_unchanged(sim, tmp_path, fake_dssat):
    text = sim.filex.read_text().replace(" 1 GE              1     1", " 1 GE              1     3")
    sim.filex.write_text(text)
    sim.management = {"treatments": {3: {"controls": {"weather_source": "S"}}}}
    sim.weather = climate(tmp_path)
    assert sim.check(False) == []
    result = sim.run()
    text = (result.run_dir.parent / sim.filex.name).read_text()
    level = int(_section_row(text, "TREATMENTS", "N", 3, ("SM",))["SM"])
    row = _section_row(text, "SIMULATION CONTROLS", "N", level, ("GENERAL",))
    assert row["NREPS"] == "3" and row["RSEED"] == "2150"


@pytest.mark.parametrize("overrides", [False, True])
def test_batch_gives_each_treatment_only_its_weather_input(inputs, tmp_path, fake_dssat, overrides):
    text = inputs.filex.read_text()
    row = next(line for line in text.splitlines() if line.startswith(" 2 1"))
    text = text.replace(row, row + "\n" + " 3" + row[2:-1] + "2")
    text += "\n@N GENERAL     NYERS NREPS START SDATE RSEED\n 2 GE              1     1     S 82056  2150\n"
    text += "@N METHODS     WTHER\n 1 ME              M\n 2 ME              S\n"
    inputs.filex.write_text(text)
    source, cli = stock_file(tmp_path, "UFGA8201.WTH"), climate(tmp_path)
    data = {"treatments": {2: {"controls": {"weather_source": "S"}},
                           3: {"controls": {"weather_source": "M"}}}} if overrides else None
    results = run_treatments(inputs.filex, [source, cli], management=data)
    assert list(results) == [("base", 2), ("base", 3)]
    for (_, treatment), result in results.items():
        folder = result.run_dir.parent
        generated = treatment == (2 if overrides else 3)
        assert [p.name for p in folder.glob("*.CLI")] == (["UFGA.CLI"] if generated else [])
        assert [p.name for p in folder.glob("*.WTH")] == ([] if generated else ["UFGA8201.WTH"])


@pytest.mark.parametrize("method,unused", [("M", "climate file"), ("S", "weather data")])
def test_batch_rejects_input_unused_by_selected_treatments(sim, tmp_path, fake_dssat, method, unused):
    sim.management = {"treatments": {3: {"controls": {"weather_source": method}}}}
    source = stock_file(tmp_path, "UFGA8201.WTH")
    with pytest.raises(DSSATCheckError) as error:
        run_treatments(sim.filex, [source, climate(tmp_path)], treatments=[3], management=sim.management)
    assert any(unused in p and "unused" in p and "Checked all run treatments" in p for p in error.value.problems)
    assert not fake_dssat.calls


@pytest.mark.parametrize("writer", [write_management_template, write_experiment_template])
def test_uncommented_controls_example_loads_checks_and_writes(sim, tmp_path, fake_dssat, writer):
    pytest.importorskip("yaml")
    path = tmp_path / "management.yaml"
    if writer is write_experiment_template:
        cul = Path(__file__).parent / "fixtures/cultivar/MZCER048.CUL"
        (sim.filex.parent / cul.name).write_bytes(cul.read_bytes())
    writer(path, filex=sim.filex)
    text = path.read_text()
    for key in ("controls", "weather_source", "replicates", "random_seed"):
        text = text.replace(f"# {key}:", f"{key}:")
    path.write_text(text)
    sim.management = path
    assert sim.check(False) == []
    result = sim.run()
    text = (result.run_dir.parent / sim.filex.name).read_text()
    level = int(_section_row(text, "TREATMENTS", "N", 3, ("SM",))["SM"])
    assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("RSEED",))["RSEED"] == "0"
