"""Template simulations check in memory and run with isolated generated inputs."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, core
from dssatlab.filex import _section_row
from test_filex_template import data, rows
from test_simulation_run import fake_dssat, snapshot


@pytest.fixture
def installed(fake_dssat, monkeypatch, tmp_path):
    folder = fake_dssat.executable.parent / "Genotype"
    folder.mkdir()
    for prefix, code in (("MZCER048", "IB0035"), ("WHCER048", "IB0488")):
        (folder / f"{prefix}.CUL").write_text(f"@VAR#  NAME\n{code} Example\nZZ0001 Override\n")
        for suffix in ("ECO", "SPE"):
            (folder / f"{prefix}.{suffix}").write_text(f"{prefix} {suffix}")
    (folder / "MZIXM048.CUL").write_text("@VAR# NAME\nXX9999 Other model\n")
    monkeypatch.setattr(core, "_discover", lambda os_name: fake_dssat.executable)
    monkeypatch.setattr(core, "_os_name", lambda: "windows")
    monkeypatch.chdir(tmp_path)
    return fake_dssat


@pytest.mark.parametrize("both", [False, True])
@pytest.mark.parametrize("method", ["check", "run"])
def test_exactly_one_filex_source_required(both, method, data, rows):
    sim = Simulation(filex="unused.MZX" if both else None, weather=rows[0],
                     filex_template=data if both else None, soil=rows[1])
    with pytest.raises(DSSATCheckError, match="exactly one.*filex.*filex_template"):
        getattr(sim, method)()


def test_template_requires_soil(data, rows, installed, tmp_path):
    sim = Simulation(filex_template=data, weather=rows[0])
    before = snapshot(tmp_path)
    assert any("soil" in p.lower() and "required" in p for p in sim.check())
    with pytest.raises(DSSATCheckError, match="[Ss]oil.*required"):
        sim.run()
    assert snapshot(tmp_path) == before
    assert not list(tmp_path.glob("dssat_sim_*"))


@pytest.mark.parametrize("crop,code,word", [
    ("soybean", "IB0035", "unsupported crop"),
    ("maize", "XX9999", "Closest codes"),
])
def test_template_reports_independent_problems_without_writes(
        data, rows, installed, monkeypatch, crop, code, word):
    data.update(crop=crop, cultivar={"code": code}, treatment_name="")
    rows[0][0]["rain"] = -1
    rows[1][0]["sbdm"] = 10
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={"treatments": {1: {"controls": {"water": "bad"}}}})

    def forbidden(*args, **kwargs):
        raise AssertionError("checks must write nothing")

    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(core, "_save_path", forbidden)
    problems = sim.check(verbose=False)
    for expected in (word, "treatment_name", "rain", "sbdm", "water"):
        assert any(expected in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert installed.calls == []


@pytest.mark.parametrize("crop,code,prefix,extension", [
    ("maize", "IB0035", "MZCER048", "MZX"),
    ("wheat", "IB0488", "WHCER048", "WHX"),
])
@pytest.mark.parametrize("source_form", ["dict", "yaml"])
@pytest.mark.parametrize("explicit", [False, True])
def test_template_run_generates_inputs_and_uses_bare_filename(
        data, rows, installed, tmp_path, crop, code, prefix, extension, source_form, explicit):
    data.update(crop=crop, cultivar={"code": code})
    source = data
    parent = tmp_path
    if source_form == "yaml":
        yaml = pytest.importorskip("yaml")
        parent = tmp_path / "user inputs"
        parent.mkdir()
        source = parent / "filex.yaml"
        source.write_text(yaml.safe_dump(data))
    before, original = snapshot(tmp_path), deepcopy((data, rows))
    sim = Simulation(filex_template=source, weather=rows[0], soil=rows[1],
                     executable=installed.executable.parent if explicit else None)
    assert sim.check() == []
    assert snapshot(tmp_path) == before
    result = sim.run()
    folder = result.run_dir.parent
    filename = f"TEST2101.{extension}"
    assert folder.parent == parent
    assert {p.name for p in folder.iterdir()} == {
        filename, "TEST2101.WTH", "SOIL.SOL", result.run_dir.name,
        f"{prefix}.CUL", f"{prefix}.ECO", f"{prefix}.SPE"}
    for suffix in ("CUL", "ECO", "SPE"):
        name = f"{prefix}.{suffix}"
        assert (folder / name).read_bytes() == (installed.executable.parent / "Genotype" / name).read_bytes()
    text = (folder / filename).read_text()
    assert _section_row(text, "FIELDS", "L", 1, ("WSTA",))["WSTA"] == "TEST"
    assert "SOIL123456" in text and code in text
    assert "SOIL123456" in (folder / "SOIL.SOL").read_text()
    assert "21060" in (folder / "TEST2101.WTH").read_text()
    command, cwd, _ = installed.calls[0]
    assert command == [str(installed.executable), "C", filename, "1"]
    assert cwd == folder
    assert (data, rows) == original
    for path, content in before.items():
        assert snapshot(tmp_path)[path] == content


@pytest.mark.parametrize("crop,code,extension", [
    ("maize", "IB0035", "MZX"), ("wheat", "IB0488", "WHX")])
def test_experiment_overrides_apply_to_template(data, rows, installed, crop, code, extension):
    data.update(crop=crop, cultivar={"code": code})
    entry = dict(planting=dict(data["planting"], population=8),
                 cultivar={"crop": "MZ" if crop == "maize" else "WH", "code": "ZZ0001"},
                 initial_conditions=dict(date="2021-03-01", layers=[
                     dict(depth=30, water=0.2, nh4=1, no3=2)]),
                 controls=dict(start_date="2021-03-01", output_interval=2))
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={"treatments": {1: entry}}, name="own site")
    assert sim.check(verbose=False) == []
    result = sim.run()
    text = (result.run_dir.parent / f"TEST2101.{extension}").read_text()
    treatment = _section_row(text, "TREATMENTS", "N", 1, ("MP", "IC", "CU", "SM"))
    assert treatment["TNAME"] == "own site"
    assert _section_row(text, "PLANTING DETAILS", "P", int(treatment["MP"]), ("PPOP",))["PPOP"] == "8"
    assert _section_row(text, "CULTIVARS", "C", int(treatment["CU"]), ("INGENO",))["INGENO"] == "ZZ0001"
    assert treatment["IC"] != "0"
    assert _section_row(text, "SIMULATION CONTROLS", "N", int(treatment["SM"]), ("FROPT",))["FROPT"] == "2"


@pytest.mark.parametrize("entry,word", [
    ({"planting": {"population": 1234567}}, "PPOP"),
    ({"cultivar": {"crop": "MZ", "code": "XX9999"}}, "MZCER048.CUL"),
    ({"cultivar": {"crop": "WH", "code": "IB0035"}}, "template crop"),
    ({"initial_conditions": {"date": "2021-03-01", "layers": [
        {"depth": 40, "water": 0.2, "nh4": 1, "no3": 2}]}}, "depth"),
])
def test_experiment_checks_use_skeleton_and_fixed_genotype(data, rows, installed, entry, word):
    if "planting" in entry:
        entry = {"planting": dict(data["planting"], **entry["planting"])}
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={"treatments": {1: entry}})
    assert any(word in p for p in sim.check(verbose=False))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert installed.calls == []


def test_template_start_must_be_covered(data, rows, installed):
    data["planting"]["date"] = "2021-02-28"
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1])
    assert any("start" in p and "weather" in p for p in sim.check())


@pytest.mark.parametrize("treatment", [2, "2", True, None])
def test_template_only_has_treatment_one(data, rows, installed, treatment):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], treatment=treatment)
    assert any("treatment" in p.lower() and "1" in p for p in sim.check())


def test_start_coverage_and_skeleton_edit_problems_are_reported_together(data, rows, installed):
    data["planting"]["date"] = "2021-02-28"
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], management={
        "treatments": {1: {"planting": dict(data["planting"], date="2021-03-01", population=1234567)}}})
    problems = sim.check(verbose=False)
    assert any("start" in p and "weather" in p for p in problems)
    assert any("PPOP" in p for p in problems)


def test_control_start_override_changes_weather_filename(data, rows, installed):
    data["planting"]["date"] = "2022-01-01"
    weather = [dict(rows[0][0], date=date(2021, 12, 31) + timedelta(days=i)) for i in range(2)]
    sim = Simulation(filex_template=data, weather=weather, soil=rows[1], management={
        "treatments": {1: {"controls": {"start_date": "2021-12-31"}}}})
    assert sim.check(verbose=False) == []
    result = sim.run()
    assert (result.run_dir.parent / "TEST2101.WTH").is_file()
    text = (result.run_dir.parent / "TEST2201.MZX").read_text()
    treatment = _section_row(text, "TREATMENTS", "N", 1, ("SM",))
    assert _section_row(text, "SIMULATION CONTROLS", "N", int(treatment["SM"]), ("SDATE",))["SDATE"] == "21365"


@pytest.mark.parametrize("management,name,word", [
    ({"treatments": {2: {"irrigation": []}}}, None, "treatment number 2"),
    ({"treatments": {1: {"irrigation": []}}}, "x" * 27, "26-character"),
])
def test_skeleton_treatment_and_identity_checks(data, rows, installed, management, name, word):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management=management, name=name)
    assert any(word in p for p in sim.check(verbose=False))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert installed.calls == []


def test_missing_install_reports_other_input_problems(data, rows, installed, monkeypatch):
    monkeypatch.setattr(core, "_discover", lambda os_name: None)
    data["treatment_name"] = ""
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1])
    problems = sim.check()
    assert any("data directory" in p for p in problems)
    assert any("treatment_name" in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sim.run()


def test_template_construction_only_stores_inputs(data, rows, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("construction must only store inputs")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(core, "_discover", forbidden)
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1])
    assert sim.filex_template is data
    assert sim.soil is rows[1] and sim.weather is rows[0]


def test_missing_genotype_files_are_reported_before_writing(data, rows, installed, tmp_path):
    for suffix in ("ECO", "SPE"):
        (installed.executable.parent / "Genotype" / f"MZCER048.{suffix}").unlink()
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1])
    before = snapshot(tmp_path)
    problems = sim.check()
    for suffix in ("ECO", "SPE"):
        assert any(f"MZCER048.{suffix}" in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert snapshot(tmp_path) == before
    assert not list(tmp_path.glob("dssat_sim_*"))


def test_simulation_template_run_loads_management_yaml_once(data, rows, installed, monkeypatch, tmp_path):
    pytest.importorskip("yaml")
    from dssatlab import management_file

    yaml_file = tmp_path / "mgmt.yaml"
    yaml_file.write_text("treatments:\n  1:\n    planting:\n      date: '2021-03-01'\n      method: 'S'\n      distribution: 'R'\n      population: 8\n      row_spacing: 75.0\n      depth: 4.0\n", encoding="utf-8")

    load_calls = []
    real_load = management_file._load_management

    def counting_load(source):
        load_calls.append(source)
        return real_load(source)

    monkeypatch.setattr(management_file, "_load_management", counting_load)
    monkeypatch.setattr("dssatlab.simulation._load_management", counting_load)
    monkeypatch.setattr("dssatlab.filex_skeleton._load_management", counting_load)

    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], management=yaml_file)
    result = sim.run()
    assert result.returncode == 0
    assert len(load_calls) == 1
    assert load_calls[0] == yaml_file
