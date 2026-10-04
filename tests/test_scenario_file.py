"""Scenario YAML and template behavior at the batch boundary."""

import sys

import pytest

import dssatlab as lab
from dssatlab.management_file import _load_management
from test_scenarios import batch_inputs
from test_simulation_run import fake_dssat, inputs


@pytest.mark.parametrize("with_filex", [False, True])
def test_template_loads_strictly_and_passes_every_treatment_check(
        tmp_path, batch_inputs, fake_dssat, with_filex):
    pytest.importorskip("yaml")
    path = tmp_path / "scenarios.yaml"
    assert lab.write_scenario_template(path, filex=batch_inputs.filex if with_filex else None) is None
    scenarios, problems = _load_management(path)
    assert problems == []
    assert scenarios
    for overrides in scenarios.values():
        assert not set(overrides) - {"weather", "soil", "management"}
        for treatment in [1, 3, 5]:
            sim = lab.Simulation(batch_inputs.filex, treatment, batch_inputs.rows, **overrides)
            assert sim.check() == []
    content = path.read_text(encoding="utf-8")
    assert "#" in content
    for field in ("weather", "soil", "management"):
        assert field in content
    if with_filex:
        assert "treatments=[1, 3, 5]" in content
        assert "UFGA" not in content and "IBMZ" not in content and "82056" not in content
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios=path)
    assert len(results) == (1 + len(set(scenarios) - {"base"})) * 3


def test_template_refuses_existing_path_without_changing_it(tmp_path):
    path = tmp_path / "scenarios.yaml"
    path.write_bytes(b"user data")
    with pytest.raises(lab.DSSATError, match="already exists"):
        lab.write_scenario_template(str(path))
    assert path.read_bytes() == b"user data"


def test_yaml_overrides_and_explicit_empty_base(batch_inputs, fake_dssat, tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "scenarios.yaml"
    weather_path = batch_inputs.weather.as_posix()
    path.write_text(f'base: {{}}\nchanged:\n  weather: "{weather_path}"\n'
                    '  soil: null\n  management:\n    treatments:\n      1: {}\n', encoding="utf-8")
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios=path)
    assert list(results) == [("base", 1), ("base", 3), ("base", 5),
                            ("changed", 1), ("changed", 3), ("changed", 5)]


@pytest.mark.parametrize("content,fragment", [
    ("a: {}\na: {}\n", "duplicate key"),
    ("a:\n  soil: null\n  soil: null\n", "duplicate key"),
    ("a: !!python/object:builtins.object {}\n", "invalid YAML"),
    ("a: [unfinished\n", "invalid YAML"),
    ("- list\n", "mapping"),
    ("", "mapping"),
    ("a: {}\n---\nb: {}\n", "invalid YAML"),
    ('a:\n  management:\n    treatments:\n      1:\n        planting:\n'
     '          date: 1982-02-26\n          method: S\n          distribution: R\n'
     '          population: 8\n          row_spacing: 75\n          depth: 4\n', "quote the date"),
])
def test_strict_yaml_problems_prevent_all_runs(tmp_path, batch_inputs, fake_dssat, content, fragment):
    pytest.importorskip("yaml")
    path = tmp_path / "scenarios.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(lab.DSSATCheckError, match=fragment) as exc:
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios=path)
    assert all("scenario" in p.lower() and "treatment" in p for p in exc.value.problems)
    assert fake_dssat.calls == []


def test_yaml_requires_optional_pyyaml_but_dict_and_template_do_not(
        tmp_path, batch_inputs, fake_dssat, monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)
    path = tmp_path / "scenarios.yaml"
    lab.write_scenario_template(path)
    with pytest.raises(lab.DSSATCheckError, match="pip install pyyaml") as exc:
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios=path)
    assert "Scenario file" in str(exc.value)
    assert fake_dssat.calls == []
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios={"repeat": {}})
    assert len(results) == 6
