"""Sweeps generate scenarios and label every Summary row."""
from copy import deepcopy
from pathlib import Path

import pytest
import dssatlab as lab
from test_simulation_run import fake_dssat, inputs
from test_scenarios import batch_inputs
from test_filex_template import data, rows
from test_simulation_template import installed

SUMMARY = Path(__file__).parent / "fixtures/output_files/summary/two_treatments/Summary.OUT"


def test_sweep_public_api():
    assert callable(getattr(lab, "run_sweep", None))
    assert "run_sweep" in lab.__all__


@pytest.mark.parametrize("source_form", ["dict", "yaml", "none"])
def test_grid_merge_and_rows(batch_inputs, fake_dssat, monkeypatch, tmp_path, source_form):
    from dssatlab import scenarios
    controls = (Path(__file__).parent / "fixtures/controls/UFGA8201.MZX").read_text()
    text = batch_inputs.filex.read_text().split("*SIMULATION CONTROLS")[0]
    batch_inputs.filex.write_text(text + "*SIMULATION CONTROLS" +
                                controls.split("*SIMULATION CONTROLS")[1])
    base = {"treatments": {"01": {"controls": {"water": "Y", "nitrogen": "N"},
                                     "irrigation": []}, 5: {"fertilizer": []}}}
    source = base
    if source_form == "yaml":
        yaml = pytest.importorskip("yaml")
        source = tmp_path / "management.yaml"
        source.write_text(yaml.safe_dump(base))
    elif source_form == "none":
        source = None
    factors = {"controls": {"dry": {"water": "N"}, "wet": {"water": "Y"}},
               "fertilizer": {0: [], 60.5: []}}
    original = deepcopy((base, factors))
    received = []
    check = scenarios.Simulation._check_inputs
    def record(sim, *args, **kwargs):
        received.append((sim.name, sim.treatment, deepcopy(sim.management)))
        return check(sim, *args, **kwargs)
    monkeypatch.setattr(scenarios.Simulation, "_check_inputs", record)
    fake_dssat.outputs["Summary.OUT"] = SUMMARY.read_bytes()
    result = lab.run_sweep(batch_inputs.filex, batch_inputs.rows, factors=factors,
                           treatments=[1, 3], management=source, executable=fake_dssat.executable)
    names = ["base", "dry 0", "dry 60.5", "wet 0", "wet 60.5"]
    assert [(r["scenario"], r["treatment"]) for r in result] == [
        (name, t) for name in names for t in (1, 3) for _ in range(2)]
    assert all(isinstance(r["run_dir"], Path) and r["run_dir"].is_dir() for r in result)
    assert all(r["controls"] is None and r["fertilizer"] is None for r in result[:4])
    assert result[8]["fertilizer"] == 60.5
    assert isinstance(result[8]["fertilizer"], float)
    assert list(result[4])[-5:] == ["scenario", "treatment", "controls", "fertilizer", "run_dir"]
    changed = next(m for name, t, m in received if name == "dry 0" and t == 1)
    key = 1 if source_form == "none" else "01"
    assert changed["treatments"][key]["controls"] == {"water": "N"}
    assert changed["treatments"][3] == {"controls": {"water": "N"}, "fertilizer": []}
    if source_form != "none":
        assert changed["treatments"][key]["irrigation"] == []
        assert changed["treatments"][5] == base["treatments"][5]
        assert 1 not in changed["treatments"]
    assert (base, factors) == original


@pytest.mark.parametrize("factors,message", [
    (None, "Sweep factors: supply a non-empty dict of experiment data sections to labelled values, such as {'fertilizer': {0: [], 60: [...]}}."),
    ({}, "Sweep factors: supply a non-empty dict of experiment data sections to labelled values, such as {'fertilizer': {0: [], 60: [...]}}."),
    ({"weather": {"x": []}}, "Sweep factor 'weather' is not an experiment data section. Use one of: planting, irrigation, fertilizer, residues, tillage, harvest, cultivar, initial_conditions, controls, rotation."),
    ({"fertilizer": {}}, "Sweep factor 'fertilizer': supply a non-empty dict of labels to complete section values."),
    ({"fertilizer": []}, "Sweep factor 'fertilizer': supply a non-empty dict of labels to complete section values."),
    ({"controls": {"base": {}}}, "Sweep scenario name 'base' is reserved for the unchanged inputs. Use another label."),
    ({"controls": {1: {}, "1": {}}}, "Sweep scenario name '1' is given by more than one combination. Use labels that stay distinct when joined by spaces."),
    ({"controls": {"a b": {}, "a": {}}, "fertilizer": {"c": [], "b c": []}}, "Sweep scenario name 'a b c' is given by more than one combination. Use labels that stay distinct when joined by spaces."),
])
def test_sweep_messages(factors, message, monkeypatch):
    from dssatlab import sweep
    monkeypatch.setattr(sweep, "run_treatments", lambda **kwargs: pytest.fail("must not run"))
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_sweep("unused.MZX", factors=factors, treatments=[1])
    assert message in error.value.problems


@pytest.mark.parametrize("label", ["", "\n", True, None, float("nan"), float("inf"), (1,)])
def test_bad_labels(label):
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_sweep("unused.MZX", factors={"controls": {label: {}}}, treatments=[1])
    assert f"Sweep factor 'controls', label {label!r}: use a non-empty string or a finite number." in error.value.problems


def test_load_and_factor_problems_collected(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    from dssatlab import sweep
    monkeypatch.setattr(sweep, "run_treatments", lambda **kwargs: pytest.fail("must not run"))
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_sweep("unused.MZX", treatments=[1], management=tmp_path / "missing.yaml",
                      factors={"wrong": {}, "controls": {True: {}}})
    assert len(error.value.problems) == 4
    assert any("Management file" in p for p in error.value.problems)


def test_all_copied_filex_treatments(batch_inputs, fake_dssat):
    fake_dssat.outputs["Summary.OUT"] = SUMMARY.read_bytes()
    result = lab.run_sweep(batch_inputs.filex, batch_inputs.rows,
                          factors={"controls": {1: {}}})
    assert [(r["scenario"], r["treatment"]) for r in result[::2]] == [
        (name, t) for name in ("base", "1") for t in (1, 3, 5)]
    assert all(r["controls"] == 1 and type(r["controls"]) is int for r in result[6:])


def test_all_template_treatments(data, rows, installed, tmp_path):
    yaml = pytest.importorskip("yaml")
    data["treatments"] = [data.pop("treatment_name"), "Second"]
    source = tmp_path / "template.yaml"
    source.write_text(yaml.safe_dump(data))
    installed.outputs["Summary.OUT"] = SUMMARY.read_bytes()
    result = lab.run_sweep(filex_template=source, weather=rows[0], soil=rows[1],
                          factors={"controls": {"dry": {"water": "N"}}},
                          executable=installed.executable)
    assert [(r["scenario"], r["treatment"]) for r in result[::2]] == [
        ("base", 1), ("base", 2), ("dry", 1), ("dry", 2)]


@pytest.mark.parametrize("output", [None, b"bad summary"])
def test_summary_errors(batch_inputs, fake_dssat, output):
    fake_dssat.outputs = {} if output is None else {"Summary.OUT": output}
    with pytest.raises(lab.DSSATOutputError):
        lab.run_sweep(batch_inputs.filex, batch_inputs.rows, treatments=[1],
                      factors={"controls": {"same": {}}})


@pytest.mark.parametrize("section", ["planting", "irrigation", "fertilizer", "cultivar",
                                      "initial_conditions", "controls", "rotation"])
def test_complete_sections_and_top_level_keys_pass_through(section, monkeypatch):
    from dssatlab import sweep
    base = {"treatments": {"01": {"irrigation": []}, 3: {}}, "kept": {"nested": [1]}}
    value = {"whole": [1, 2]}
    original = deepcopy((base, value))
    calls = []
    def record(**kwargs):
        calls.append(kwargs)
        return {}
    monkeypatch.setattr(sweep, "run_treatments", record)
    assert lab.run_sweep("file.MZX", weather="weather.csv", soil="soil.csv",
                         executable="dscsm048", treatments=("01",), management=base,
                         factors={section: {"value": value}}) == []
    assert len(calls) == 1
    call = calls[0]
    assert call["filex"] == "file.MZX" and call["weather"] == "weather.csv"
    assert call["soil"] == "soil.csv" and call["executable"] == "dscsm048"
    assert call["treatments"] == ("01",) and call["management"] is base
    merged = call["scenarios"]["value"]["management"]
    assert merged["kept"] == base["kept"]
    assert merged["treatments"]["01"][section] == value
    assert merged["treatments"][3] == {}
    merged["kept"]["nested"].append(2)
    merged["treatments"]["01"][section]["whole"].append(3)
    assert (base, value) == original


def test_selected_treatment_does_not_change_aliased_entry(monkeypatch):
    from dssatlab import sweep
    shared = {"fertilizer": [], "irrigation": []}
    base = {"treatments": {1: shared, 2: shared}}
    original = deepcopy(base)
    fertilizer = [{"date": "1982-04-07", "material": "FE001",
                   "application": "AP001", "depth": 10, "n": 60}]
    calls = []

    def record(**kwargs):
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(sweep, "run_treatments", record)
    assert lab.run_sweep("file.MZX", treatments=[1], management=base,
                         factors={"fertilizer": {60: fertilizer}}) == []
    merged = calls[0]["scenarios"]["60"]["management"]
    assert merged["treatments"][1]["fertilizer"] == fertilizer
    assert merged["treatments"][2] == original["treatments"][2]
    assert base == original
    assert base["treatments"][1] is base["treatments"][2] is shared


def test_name_errors_collected_with_shape_errors(monkeypatch):
    from dssatlab import sweep
    monkeypatch.setattr(sweep, "run_treatments", lambda **kwargs: pytest.fail("must not run"))
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_sweep("unused.MZX", treatments=[1],
                      factors={"unknown": {"base": {}, 1: {}, "1": {}}})
    assert len(error.value.problems) == 3
    assert any("reserved" in p for p in error.value.problems)
    assert any("more than one combination" in p for p in error.value.problems)


def test_section_and_name_checks_precede_runs(batch_inputs, fake_dssat):
    with pytest.raises(lab.DSSATCheckError) as error:
        lab.run_sweep(batch_inputs.filex, batch_inputs.rows, treatments=[1, 3],
                      factors={"planting": {"x" * 40: {}, "short": {}}})
    for name in ("x" * 40, "short"):
        for treatment in (1, 3):
            assert any(f"Scenario {name!r}, treatment {treatment}:" in p
                       for p in error.value.problems)
    assert fake_dssat.calls == []


def test_first_failure_stops_sweep(batch_inputs, fake_dssat):
    fake_dssat.returncode = 7
    with pytest.raises(lab.DSSATRunError, match="Scenario 'base', treatment 1"):
        lab.run_sweep(batch_inputs.filex, batch_inputs.rows, treatments=[1, 3],
                      factors={"controls": {"same": {}}})
    assert len(fake_dssat.calls) == 1
