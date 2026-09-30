"""Experiment templates and shape checks through the public Simulation interface."""

from copy import deepcopy
from pathlib import Path
import sys
import shutil

import pytest

import dssatlab
from dssatlab import DSSATError, Simulation
from test_management_file import sim_inputs as management_inputs
from test_simulation_run import fake_dssat, inputs


SECTIONS = {
    "cultivar": {"crop": "MZ", "code": "IB0035"},
    "initial_conditions": {
        "date": "1982-02-25", "previous_crop": "MZ", "residue_mass": 0.0,
        "layers": [{"depth": 15, "water": 0.2, "nh4": 0.5, "no3": 2.0}],
    },
    "controls": {
        "start_date": "1982-02-25", "water": "Y", "nitrogen": "N", "output_interval": 1,
    },
}
WRITERS = ("write_management_template", "write_experiment_template")


@pytest.fixture(autouse=True)
def cultivar_table(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "cultivar" / "MZCER048.CUL"
    shutil.copyfile(fixture, tmp_path / fixture.name)


@pytest.fixture
def sim_inputs(management_inputs):
    filex, weather = management_inputs
    fixture = Path(__file__).parent / "fixtures" / "controls" / "UFGA8201.MZX"
    controls = fixture.read_bytes().split(b"*SIMULATION CONTROLS")[1]
    filex.write_bytes(filex.read_bytes().split(b"*SIMULATION CONTROLS")[0]
                      + b"*SIMULATION CONTROLS" + controls)
    return filex, weather


@pytest.mark.parametrize("writer_name", WRITERS)
def test_template_loads_and_passes_checks(tmp_path, sim_inputs, writer_name):
    yaml = pytest.importorskip("yaml")
    filex, weather = sim_inputs
    dest = tmp_path / "template.yaml"
    writer = getattr(dssatlab, writer_name)
    assert writer(dest) is None
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    entry = data["treatments"][1]
    assert {"planting", "irrigation", "fertilizer"} <= entry.keys()
    if writer_name == "write_experiment_template":
        for section, fields in SECTIONS.items():
            assert fields.keys() == entry[section].keys()
        assert {"depth", "water", "nh4", "no3"} == entry["initial_conditions"]["layers"][0].keys()
        assert writer_name in dssatlab.__all__
    else:
        assert entry.keys() == {"planting", "irrigation", "fertilizer"}
    # Passing the path exercises DSSATLab's strict loader, not yaml.safe_load.
    assert Simulation(filex, 1, weather, management=dest).check() == []


@pytest.mark.parametrize("writer_name", WRITERS)
def test_filex_prefills_only_treatment_numbers(tmp_path, sim_inputs, writer_name):
    yaml = pytest.importorskip("yaml")
    _, weather = sim_inputs
    filex = tmp_path / "MULTI.MZX"
    fixture = Path(__file__).parent / "fixtures" / "controls" / "UFGA8201.MZX"
    # Nonconsecutive, out-of-order numbers catch guessed ranges and sorting.
    filex.write_bytes(fixture.read_bytes().replace(b" 1 1 0 0 RAINFED", b" 7 1 0 0 RAINFED"))
    before = filex.read_bytes()
    writer = getattr(dssatlab, writer_name)
    default, prefilled = tmp_path / "default.yaml", tmp_path / "prefilled.yaml"
    writer(default)
    writer(str(prefilled), filex=str(filex))
    example = yaml.safe_load(default.read_text(encoding="utf-8"))["treatments"][1]
    data = yaml.safe_load(prefilled.read_text(encoding="utf-8"))
    assert list(data["treatments"]) == [7, 3, 5]
    assert all(entry == example for entry in data["treatments"].values())
    for number in (7, 3, 5):
        assert Simulation(filex, number, weather, management=prefilled).check() == []
    assert filex.read_bytes() == before


@pytest.mark.parametrize("writer_name", WRITERS)
@pytest.mark.parametrize("directory", [False, True])
def test_existing_destination_is_preserved(tmp_path, writer_name, directory):
    dest = tmp_path / "existing.yaml"
    if directory:
        dest.mkdir()
    else:
        dest.write_bytes(b"keep my data")
    with pytest.raises(DSSATError, match="already exists.*Choose another path"):
        getattr(dssatlab, writer_name)(dest, filex=tmp_path / "missing.MZX")
    assert dest.is_dir() if directory else dest.read_bytes() == b"keep my data"


@pytest.mark.parametrize("writer_name", WRITERS)
def test_unreadable_filex_does_not_leave_a_template(tmp_path, writer_name):
    dest = tmp_path / "template.yaml"
    with pytest.raises(DSSATError, match="Cannot read FileX"):
        getattr(dssatlab, writer_name)(dest, filex=tmp_path / "missing.MZX")
    assert not dest.exists()


def test_all_documented_fields_accepted_without_pyyaml(sim_inputs, monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)
    filex, weather = sim_inputs
    data = {"treatments": {1: deepcopy(SECTIONS), 2: {"controls": {"water": "N"}}}}
    before = deepcopy(data)
    assert Simulation(filex, 1, weather, management=data).check() == []
    assert data == before


@pytest.mark.parametrize("section", SECTIONS)
@pytest.mark.parametrize("bad", [None, [], "value"])
def test_new_sections_require_mappings(sim_inputs, section, bad):
    filex, weather = sim_inputs
    problems = Simulation(filex, 1, weather, management={"treatments": {1: {section: bad}}}).check()
    assert len(problems) == 1
    assert section in problems[0] and "dict" in problems[0]


@pytest.mark.parametrize("section,fields,missing", [
    ("cultivar", {}, "code"),
    ("initial_conditions", {"layers": []}, "date"),
    ("initial_conditions", {"date": "1982-02-25"}, "layers"),
])
def test_required_shape_fields_reported(sim_inputs, section, fields, missing):
    filex, weather = sim_inputs
    problems = Simulation(filex, 1, weather, management={"treatments": {1: {section: fields}}}).check()
    assert any(section in p and missing in p and "missing" in p for p in problems)


@pytest.mark.parametrize("layers,word", [
    ({}, "list"), ([None], "dict"),
    ([{"depth": 10, "water": 0.2, "nh4": 1}], "no3"),
])
def test_layer_shape_is_checked(sim_inputs, layers, word):
    filex, weather = sim_inputs
    entry = {"initial_conditions": {"date": "1982-02-25", "layers": layers}}
    problems = Simulation(filex, 1, weather, management={"treatments": {1: entry}}).check()
    assert any("layers" in p and word in p for p in problems)


def test_unknown_keys_reported_at_every_new_level_for_all_treatments(sim_inputs):
    filex, weather = sim_inputs
    entry = deepcopy(SECTIONS)
    entry["cultivr"] = {}
    entry["cultivar"]["cod"] = "IB0035"
    entry["initial_conditions"]["residue"] = 0
    entry["initial_conditions"]["layers"][0]["n03"] = 1
    entry["controls"]["interval"] = 1
    problems = Simulation(filex, 1, weather, management={"treatments": {1: entry, 2: entry}}).check()
    for number in (1, 2):
        for unknown, allowed in (("cultivr", "cultivar"), ("cod", "code"),
                                 ("residue", "residue_mass"), ("n03", "no3"),
                                 ("interval", "output_interval")):
            assert any(f"treatment {number}" in p and f"'{unknown}'" in p and
                       "unknown key" in p and allowed in p and "Use only" in p for p in problems)


@pytest.mark.parametrize("fragment,word", [
    ("cultivar: {code: no}", "code"),
    ('initial_conditions: {date: 1982-02-25, layers: []}', "quote"),
    ('initial_conditions: {date: "1982-02-25", layers: [], residue_mass: false}', "number"),
    ('controls: {start_date: 1982-02-25}', "quote"),
    ('controls: {water: no}', "string"),
    ('controls: {nitrogen: [Y]}', "string"),
    ('controls: {output_interval: true}', "integer"),
    ('cultivar: {code: "A", code: "B"}', "duplicate key"),
    ('controls: {water: "Y", water: "N"}', "duplicate key"),
])
def test_new_fields_use_strict_yaml_checks(tmp_path, sim_inputs, fragment, word):
    pytest.importorskip("yaml")
    filex, weather = sim_inputs
    path = tmp_path / "experiment.yaml"
    path.write_text(f"treatments:\n  1:\n    {fragment}\n", encoding="utf-8")
    problems = Simulation(filex, 1, weather, management=path).check()
    assert any(word in p for p in problems)
