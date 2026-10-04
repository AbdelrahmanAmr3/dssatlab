"""Template batches use real Simulation checks and a fake DSSAT subprocess."""

from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

import dssatlab as lab
from dssatlab.filex import _section_row, read_treatment_numbers
from test_filex_template import data, rows
from test_simulation_run import fake_dssat
from test_simulation_template import installed


@pytest.fixture
def template(data):
    data["treatments"] = [data.pop("treatment_name"), "Second", "Third"]
    return data


@pytest.mark.parametrize("source_form", ["dict", "yaml"])
def test_all_template_treatments_run_in_order_beside_source(
        template, rows, installed, tmp_path, source_form):
    source, parent = template, tmp_path
    if source_form == "yaml":
        yaml = pytest.importorskip("yaml")
        parent = tmp_path / "templates"
        parent.mkdir()
        source = parent / "experiment.yaml"
        source.write_text(yaml.safe_dump(template))
    original = deepcopy(template)
    results = lab.run_treatments(filex_template=source, weather=rows[0], soil=rows[1],
                                executable=installed.executable)
    assert list(results) == [("base", 1), ("base", 2), ("base", 3)]
    assert [call[0][-1] for call in installed.calls] == ["1", "2", "3"]
    assert len({result.run_dir.parent for result in results.values()}) == 3
    for result in results.values():
        assert result.returncode == 0
        assert result.run_dir.parent.parent == parent
        assert read_treatment_numbers(result.run_dir.parent / "TEST2101.MZX") == [1, 2, 3]
    assert template == original


def test_single_treatment_name_remains_a_one_run_batch(data, rows, installed):
    results = lab.run_treatments(filex_template=data, weather=rows[0], soil=rows[1])
    assert list(results) == [("base", 1)]
    assert installed.calls[0][0][-1] == "1"


def test_selection_and_scenarios_keep_order_and_apply_experiment_data(template, rows, installed):
    management = {"treatments": {3: {"controls": {"water": "N"}}}}
    results = lab.run_treatments(filex_template=template, weather=rows[0], soil=rows[1],
                                treatments=("3", 1), scenarios={"changed": {"management": management}})
    assert list(results) == [("base", 3), ("base", 1), ("changed", 3), ("changed", 1)]
    assert [call[0][-1] for call in installed.calls] == ["3", "1", "3", "1"]
    for (scenario, selected), result in results.items():
        text = (result.run_dir.parent / "TEST2101.MZX").read_text()
        for number, name in enumerate(template["treatments"], 1):
            treatment = _section_row(text, "TREATMENTS", "N", number, ("SM",))
            assert treatment["TNAME"] == ("changed" if scenario == "changed" and number == selected else name)
        treatment = _section_row(text, "TREATMENTS", "N", 3, ("SM",))
        controls = _section_row(text, "SIMULATION CONTROLS", "N", int(treatment["SM"]), ("WATER",))
        assert controls["WATER"] == ("N" if scenario == "changed" else "Y")


@pytest.mark.parametrize("both", [False, True])
def test_exactly_one_source_is_required(template, rows, installed, both):
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_treatments(filex="unused.MZX" if both else None,
                           filex_template=template if both else None, weather=rows[0])
    assert error.value.problems == ["Supply exactly one of filex or filex_template."]
    assert installed.calls == []


@pytest.mark.parametrize("source", ["missing.yaml", 42, [], {},
    {"treatments": None}, {"treatments": 3}, {"treatments": "bad"},
    {"treatments": []}, {"treatments": ["T"] * 100},
    {"treatment_name": "One", "treatments": ["Two", "Three"]}])
def test_unreadable_or_malformed_template_reports_problems_for_treatment_one(
        source, rows, installed, tmp_path):
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_treatments(filex_template=source, weather=rows[0], soil=rows[1])
    assert error.value.problems
    assert all("Scenario 'base', treatment 1:" in p for p in error.value.problems)
    assert installed.calls == []
    assert not list(tmp_path.glob("dssat_sim_*"))


@pytest.mark.parametrize("selection", [[], [1, "01"], [True], [0], [4], ["bad"], 1])
def test_bad_template_selection_is_rejected(template, rows, installed, selection):
    with pytest.raises(lab.DSSATCheckError, match="treatment"):
        lab.run_treatments(filex_template=template, weather=rows[0], soil=rows[1],
                           treatments=selection)
    assert installed.calls == []


def test_checks_all_scenario_treatment_pairs_before_writing(template, rows, installed, tmp_path):
    scenarios = {"bad_weather": {"weather": [dict(rows[0][0], rain=-1)]},
                 "no_soil": {"soil": None}}
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_treatments(filex_template=template, weather=rows[0], soil=rows[1], scenarios=scenarios)
    for name, field in [("bad_weather", "rain"), ("no_soil", "Soil")]:
        for number in (1, 2, 3):
            assert any(f"Scenario '{name}', treatment {number}:" in p and field in p
                       for p in error.value.problems)
    assert installed.calls == []
    assert not list(tmp_path.glob("dssat_sim_*"))


def test_first_template_failure_stops_batch_and_keeps_run_directories(
        template, rows, installed, tmp_path, monkeypatch):
    original_run = subprocess.run

    def fail_second(command, *, cwd, **kwargs):
        if len(installed.calls) == 1:
            installed.returncode = 7
        return original_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fail_second)
    with pytest.raises(lab.DSSATRunError) as error:
        lab.run_treatments(filex_template=template, weather=rows[0], soil=rows[1],
                           scenarios={"extra": {}})
    assert [call[0][-1] for call in installed.calls] == ["1", "2"]
    assert "Scenario 'base', treatment 2:" in str(error.value)
    kept = list(tmp_path.glob("dssat_sim_*/dssat_run_*"))
    assert len(kept) == 2
    for directory in kept:
        assert str(directory) in str(error.value)
        assert (directory / "Summary.OUT").is_file()


def test_combined_summaries_keep_template_batch_keys(template, rows, installed):
    fixture = Path(__file__).parent / "fixtures/output_files/summary/two_treatments/Summary.OUT"
    installed.outputs["Summary.OUT"] = fixture.read_bytes()
    results = lab.run_treatments(filex_template=template, weather=rows[0], soil=rows[1],
                                scenarios={"extra": {}})
    combined = lab.combine_summaries(results)
    assert [(row["scenario"], row["treatment"], row["TRNO"]) for row in combined] == [
        ("base", 1, 1), ("base", 1, 2), ("base", 2, 1), ("base", 2, 2),
        ("base", 3, 1), ("base", 3, 2), ("extra", 1, 1), ("extra", 1, 2),
        ("extra", 2, 1), ("extra", 2, 2), ("extra", 3, 1), ("extra", 3, 2)]
    assert all(row["HWAM"] == 2295 and row["DWAP"] is None for row in combined)
