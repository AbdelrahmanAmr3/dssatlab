"""Experiment templates and shape checks through the public Simulation interface."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import sys
import shutil

import pytest

import dssatlab
from dssatlab import DSSATError, Simulation, run_treatments
from dssatlab.filex import _section_row
from test_filex_template import data, rows
from test_simulation_template import installed
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
    if writer_name == "write_experiment_template":
        text = dest.read_text(encoding="utf-8")
        assert "# years: 9" in text and "Number of seasons (DSSAT NYERS)" in text
        dest.write_text(text.replace("# years: 9", "years: 9"), encoding="utf-8")
        start = date.fromisoformat(weather[0]["date"])
        weather = [dict(weather[0], date=start + timedelta(days=i)) for i in range(9 * 366)]
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


@pytest.mark.parametrize("prefill", [False, True])
def test_new_cultivar_template_loads_checks_and_writes(tmp_path, sim_inputs, fake_dssat, prefill):
    yaml = pytest.importorskip("yaml")
    filex, weather = sim_inputs
    source = filex.parent / "MZCER048.CUL"
    original = source.read_bytes()
    source.with_suffix(".ECO").write_text("@ECO# ECONAME\nIB0001 Example\n", encoding="ascii")
    dest = tmp_path / "experiment.yaml"
    dssatlab.write_experiment_template(dest, filex=filex if prefill else None)
    text = dest.read_text(encoding="utf-8").replace('code: "IB0035"', 'code: "NC0001"')
    for field in ("ecotype", "name", "coefficients"):
        text = text.replace(f"      # {field}:", f"      {field}:")
    dest.write_text(text, encoding="utf-8")
    entry = yaml.safe_load(text)["treatments"][1]["cultivar"]
    assert entry["ecotype"] == "IB0001"
    assert entry["name"] == "New maize"
    assert entry["coefficients"] == {
        "P1": 259, "P2": 1.193, "P5": 947.1, "G2": 924.3, "G3": 8.168, "PHINT": 43,
    }
    sim = Simulation(filex, 1, weather, management=dest, executable=fake_dssat.executable)
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    line = next(line for line in (folder / source.name).read_bytes().splitlines()
                if line.startswith(b"NC0001"))
    assert line[7:23] == b"New maize       "
    assert line[30:36] == b"IB0001"
    written = (folder / filex.name).read_text(encoding="latin-1")
    level = int(_section_row(written, "TREATMENTS", "N", 1, ("CU",))["CU"])
    assert _section_row(written, "CULTIVARS", "C", level, ("INGENO",))["INGENO"] == "NC0001"
    assert source.read_bytes() == original


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


@pytest.mark.parametrize("template", [False, True])
@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("years", [None, 9])
def test_seasons_follow_existing_controls_path(sim_inputs, data, rows, installed, template, batch, years):
    filex, weather = sim_inputs
    kwargs = dict(filex_template=data, weather=rows[0], soil=rows[1]) if template else dict(
        filex=filex, weather=weather)
    controls = {"water": "N"}
    if years is not None:
        controls["years"] = years
        first = kwargs["weather"][0]
        start = date.fromisoformat(str(first["date"]))
        kwargs["weather"] = [dict(first, date=start + timedelta(days=i))
                             for i in range(years * 366)]
    kwargs["management"] = {"treatments": {1: {"controls": controls}}}
    if batch:
        result = run_treatments(**kwargs, treatments=[1])["base", 1]
    else:
        result = Simulation(**kwargs, treatment=1).run()
    written = next(result.run_dir.parent.glob("*.MZX")).read_bytes()
    text = written.decode("latin-1")
    treatment = _section_row(text, "TREATMENTS", "N", 1, ("SM",))
    level = int(treatment["SM"])
    assert level == 2
    section = written.split(b"*SIMULATION CONTROLS")[1]
    base = [row for row in section.splitlines() if row.startswith(b" 1 ")]
    copied = [row for row in section.splitlines() if row.startswith(b" 2 ")]
    expected = [b" 2" + row[2:] for row in base]
    expected[0] = expected[0][:15] + str(years or 1).encode().rjust(5) + expected[0][20:]
    expected[1] = expected[1][:19] + b"N" + expected[1][20:]
    assert copied == expected
    assert len(installed.calls) == 1
