"""Tests for YAML management template writer and strict YAML loading."""

from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys

import pytest

import dssatlab
from dssatlab import DSSATCheckError, DSSATError, Simulation, write_management_template
from test_simulation_run import fake_dssat, inputs, snapshot


SAMPLE_FILEX = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 RAINFED LOW NITROGEN       1  1  0  1  1  1  1  0  0  0  0  0  1
 2 1 0 0 RAINFED HIGH NITROGEN      1  1  0  1  1  1  2  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910214 Field section

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 N X IRRIGATION
"""


@pytest.fixture
def sim_inputs(tmp_path):
    filex_path = tmp_path / "UFGA8201.MZX"
    filex_path.write_text(SAMPLE_FILEX, encoding="latin-1")
    start = date(1982, 2, 25)
    weather = [
        dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
             date=(start + timedelta(days=i)).isoformat(),
             srad=20, tmax=25, tmin=10, rain=0)
        for i in range(35)
    ]
    return filex_path, weather


# --- Template writer tests ---


def test_write_management_template_creates_file_and_returns_none(tmp_path):
    dest = tmp_path / "management.yaml"
    ret = write_management_template(dest)
    assert ret is None
    assert dest.exists()
    content = dest.read_text(encoding="utf-8")

    # Document every planting field and unit
    planting_fields = [
        "date", "method", "distribution", "population", "row_spacing", "depth",
        "emergence_date", "emergence_population", "row_direction",
        "planting_material_weight", "transplant_age", "transplant_environment",
        "plants_per_hill", "sprout_length",
    ]
    for field in planting_fields:
        assert field in content

    # Document irrigation fields
    for field in ["irrigation", "amount", "method"]:
        assert field in content

    # Document fertilizer fields
    for field in ["fertilizer", "material", "application", "depth", "n", "p", "k"]:
        assert field in content

    # Document units
    for unit in ["plants/m2", "cm", "mm", "kg/ha", "degrees C"]:
        assert unit in content


def test_write_management_template_existing_file_raises_dssat_error(tmp_path):
    dest = tmp_path / "management.yaml"
    dest.write_text("existing", encoding="utf-8")
    with pytest.raises(DSSATError) as exc_info:
        write_management_template(dest)
    assert f"Management template path {dest} already exists" in str(exc_info.value)
    # Also test as string path
    with pytest.raises(DSSATError) as exc_info_str:
        write_management_template(str(dest))
    assert f"Management template path {dest} already exists" in str(exc_info_str.value)


def test_write_management_template_loads_back_and_passes_checks(tmp_path, sim_inputs, capsys):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    dest = tmp_path / "management.yaml"
    write_management_template(dest)

    sim = Simulation(filex_path, 1, weather, management=dest)
    problems = sim.check()
    assert problems == []

    report = capsys.readouterr().out
    assert "Treatment 1: OK" in report
    assert "planting: OK" in report
    assert "irrigation: OK" in report
    assert "fertilizer: OK" in report


# --- Strict YAML loading tests ---


def test_unreadable_file_rejected_as_check_problem(tmp_path, sim_inputs):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    missing = tmp_path / "nonexistent.yaml"
    sim = Simulation(filex_path, 1, weather, management=missing)
    problems = sim.check()
    assert len(problems) == 1
    assert str(missing) in problems[0]
    assert "cannot read file" in problems[0].lower()

    # run() must raise DSSATCheckError for it
    with pytest.raises(DSSATCheckError) as exc_info:
        sim.run()
    assert problems[0] in str(exc_info.value)


def test_directory_as_management_path_rejected(tmp_path, sim_inputs):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    sim = Simulation(filex_path, 1, weather, management=tmp_path)
    problems = sim.check()
    assert len(problems) == 1
    assert str(tmp_path) in problems[0]
    assert "cannot read file" in problems[0].lower()


def test_invalid_yaml_syntax_rejected(tmp_path, sim_inputs):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text("treatments:\n  1: [unterminated", encoding="utf-8")
    sim = Simulation(filex_path, 1, weather, management=yaml_file)
    problems = sim.check()
    assert len(problems) == 1
    assert str(yaml_file) in problems[0]
    assert "invalid yaml" in problems[0].lower()

    with pytest.raises(DSSATCheckError):
        sim.run()


def test_multi_document_yaml_rejected(tmp_path, sim_inputs):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    yaml_file = tmp_path / "multi.yaml"
    yaml_file.write_text("treatments: {}\n---\ntreatments: {}\n", encoding="utf-8")
    sim = Simulation(filex_path, 1, weather, management=yaml_file)
    problems = sim.check()
    assert len(problems) == 1
    assert str(yaml_file) in problems[0]
    assert "invalid yaml" in problems[0].lower()


@pytest.mark.parametrize("content", [
    "",
    "   \n# only comments\n",
    "- item1\n- item2\n",
    '"just a string"\n',
    "42\n",
])
def test_non_mapping_documents_rejected(tmp_path, sim_inputs, content):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    yaml_file = tmp_path / "non_mapping.yaml"
    yaml_file.write_text(content, encoding="utf-8")
    sim = Simulation(filex_path, 1, weather, management=yaml_file)
    problems = sim.check()
    assert len(problems) == 1
    assert str(yaml_file) in problems[0]
    assert "expected a yaml mapping document" in problems[0].lower()

    with pytest.raises(DSSATCheckError):
        sim.run()


@pytest.mark.parametrize("yaml_content,duplicate_name", [
    ("treatments: {}\ntreatments: {}\n", "treatments"),
    ("treatments:\n  1: {}\n  1: {}\n", "1"),
    ("treatments:\n  1:\n    planting: {}\n    planting: {}\n", "planting"),
    ("treatments:\n  1:\n    planting:\n      date: '1982-02-26'\n      date: '1982-02-27'\n      method: 'S'\n      distribution: 'R'\n      population: 7.2\n      row_spacing: 75.0\n      depth: 5.0\n", "date"),
    ("treatments:\n  1:\n    irrigation:\n      - date: '1982-03-15'\n        amount: 30.0\n        amount: 40.0\n        method: 'IR001'\n", "amount"),
])
def test_duplicate_keys_rejected(tmp_path, sim_inputs, yaml_content, duplicate_name):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    yaml_file = tmp_path / "dup.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    sim = Simulation(filex_path, 1, weather, management=yaml_file)
    problems = sim.check()
    assert len(problems) == 1
    assert str(yaml_file) in problems[0]
    assert "duplicate key" in problems[0].lower()
    assert duplicate_name in problems[0]

    with pytest.raises(DSSATCheckError):
        sim.run()


@pytest.mark.parametrize("bad_date_yaml,value_str", [
    ("date: 1982-02-26", "datetime.date(1982, 2, 26)"),
    ("date: no", "False"),
    ("date: yes", "True"),
    ("date: 19820226", "19820226"),
])
def test_unquoted_dates_rejected_with_quote_message(tmp_path, sim_inputs, bad_date_yaml, value_str):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs
    yaml_content = f"""treatments:
  1:
    planting:
      {bad_date_yaml}
      method: "S"
      distribution: "R"
      population: 7.2
      row_spacing: 75.0
      depth: 5.0
"""
    yaml_file = tmp_path / "unquoted.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    sim = Simulation(filex_path, 1, weather, management=yaml_file)
    problems = sim.check()
    assert any(value_str in p and "quote the date" in p for p in problems)


# --- Equivalence tests ---


def test_yaml_and_equivalent_dict_give_same_problems_and_report(tmp_path, sim_inputs, capsys):
    pytest.importorskip("yaml")
    filex_path, weather = sim_inputs

    # Valid data
    valid_yaml = """treatments:
  1:
    planting:
      date: "1982-02-26"
      method: "S"
      distribution: "R"
      population: 7.2
      row_spacing: 75.0
      depth: 5.0
    irrigation:
      - date: "1982-03-15"
        amount: 30.0
        method: "IR001"
    fertilizer:
      - date: "1982-03-20"
        material: "FE001"
        application: "AP001"
        depth: 5.0
        n: 50.0
"""
    valid_dict = {
        "treatments": {
            1: {
                "planting": {
                    "date": "1982-02-26",
                    "method": "S",
                    "distribution": "R",
                    "population": 7.2,
                    "row_spacing": 75.0,
                    "depth": 5.0,
                },
                "irrigation": [
                    {"date": "1982-03-15", "amount": 30.0, "method": "IR001"}
                ],
                "fertilizer": [
                    {"date": "1982-03-20", "material": "FE001", "application": "AP001",
                     "depth": 5.0, "n": 50.0}
                ],
            }
        }
    }

    yaml_file = tmp_path / "valid.yaml"
    yaml_file.write_text(valid_yaml, encoding="utf-8")

    sim_yaml = Simulation(filex_path, 1, weather, management=yaml_file)
    probs_yaml = sim_yaml.check()
    report_yaml = capsys.readouterr().out

    sim_dict = Simulation(filex_path, 1, weather, management=valid_dict)
    probs_dict = sim_dict.check()
    report_dict = capsys.readouterr().out

    assert probs_yaml == probs_dict == []
    assert report_yaml == report_dict

    # Invalid data (bad population, negative depth, unquoted date, etc.)
    invalid_yaml = """treatments:
  1:
    planting:
      date: 1982-02-26
      method: "S"
      distribution: "R"
      population: -5.0
      row_spacing: 75.0
      depth: -1.0
"""
    invalid_dict = {
        "treatments": {
            1: {
                "planting": {
                    "date": date(1982, 2, 26),
                    "method": "S",
                    "distribution": "R",
                    "population": -5.0,
                    "row_spacing": 75.0,
                    "depth": -1.0,
                }
            }
        }
    }

    bad_yaml_file = tmp_path / "bad.yaml"
    bad_yaml_file.write_text(invalid_yaml, encoding="utf-8")

    sim_bad_yaml = Simulation(filex_path, 1, weather, management=bad_yaml_file)
    probs_bad_yaml = sim_bad_yaml.check()
    report_bad_yaml = capsys.readouterr().out

    sim_bad_dict = Simulation(filex_path, 1, weather, management=invalid_dict)
    probs_bad_dict = sim_bad_dict.check()
    report_bad_dict = capsys.readouterr().out

    assert probs_bad_yaml == probs_bad_dict
    assert report_bad_yaml == report_bad_dict


# --- Missing PyYAML and zero-import tests ---


def test_missing_pyyaml_gives_install_hint(tmp_path, sim_inputs, monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)
    filex_path, weather = sim_inputs
    yaml_file = tmp_path / "valid.yaml"
    yaml_file.write_text("treatments: {}\n", encoding="utf-8")

    sim = Simulation(filex_path, 1, weather, management=yaml_file)
    problems = sim.check()
    assert len(problems) == 1
    assert str(yaml_file) in problems[0]
    assert "PyYAML is not installed" in problems[0]
    assert "pip install pyyaml" in problems[0]

    with pytest.raises(DSSATCheckError) as exc_info:
        sim.run()
    assert "pip install pyyaml" in str(exc_info.value)


def test_dict_management_works_without_pyyaml(sim_inputs, monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)
    filex_path, weather = sim_inputs
    planting = dict(date="1982-02-25", method="S", distribution="R",
                    population=8, row_spacing=75.0, depth=0)
    sim = Simulation(filex_path, 1, weather, management={"treatments": {1: {"planting": planting}}})
    assert sim.check() == []


def test_importing_package_never_imports_yaml():
    env = dict(sys.modules.get("os", __import__("os")).environ, PYTHONPATH="src")
    cmd = [sys.executable, "-c", "import sys, dssatlab; assert 'yaml' not in sys.modules; assert 'write_management_template' in dssatlab.__all__"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr


def test_dict_management_never_imports_yaml(tmp_path):
    env = dict(sys.modules.get("os", __import__("os")).environ, PYTHONPATH="src")
    code = """
import sys
from dssatlab import Simulation
sim = Simulation('dummy.mzx', 1, [], management={'treatments': {}})
assert 'yaml' not in sys.modules
"""
    cmd = [sys.executable, "-c", code]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr


# --- End-to-end run test with YAML file ---


def test_simulation_run_with_yaml_management(inputs, fake_dssat, monkeypatch, tmp_path):
    pytest.importorskip("yaml")
    from test_planting_run import HEADER, OLD_ROW, TREATMENT

    seen = []
    original_run = subprocess.run

    def record_run(command, *, cwd, **kwargs):
        seen.append((Path(cwd) / command[2]).read_bytes())
        return original_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", record_run)

    text = SAMPLE_FILEX.replace(TREATMENT, TREATMENT.replace(" 2 ", " 1 ", 1) + "\n" + TREATMENT)
    text = text.replace("*SIMULATION CONTROLS", "*PLANTING DETAILS\n" + HEADER + "\n"
                        + OLD_ROW + "\n\n*SIMULATION CONTROLS")
    inputs.filex.write_bytes(text.encode("latin-1"))

    yaml_content = """treatments:
  "02":
    planting:
      date: "1982-02-25"
      method: "S"
      distribution: "R"
      population: 8
      row_spacing: 75.0
      depth: 4.0
"""
    yaml_file = tmp_path / "plan.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    sim = Simulation(inputs.filex, "02", inputs.rows, management=yaml_file)
    result = sim.run()
    assert result.returncode == 0
    assert seen, "DSSAT was called"


@pytest.mark.parametrize("operation", ["check", "run"])
def test_simulation_run_loads_management_yaml_once(inputs, fake_dssat, monkeypatch, tmp_path, operation):
    pytest.importorskip("yaml")
    from test_planting_run import HEADER, OLD_ROW, TREATMENT
    from dssatlab import management_file

    text = SAMPLE_FILEX.replace(TREATMENT, TREATMENT.replace(" 2 ", " 1 ", 1) + "\n" + TREATMENT)
    text = text.replace("*SIMULATION CONTROLS", "*PLANTING DETAILS\n" + HEADER + "\n"
                        + OLD_ROW + "\n\n*SIMULATION CONTROLS")
    inputs.filex.write_bytes(text.encode("latin-1"))

    yaml_content = """treatments:
  "02":
    planting:
      date: "1982-02-25"
      method: "S"
      distribution: "R"
      population: 8
      row_spacing: 75.0
      depth: 4.0
"""
    yaml_file = tmp_path / "plan.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    load_calls = []
    real_load = management_file._load_management

    def counting_load(source):
        load_calls.append(source)
        return real_load(source)

    monkeypatch.setattr(management_file, "_load_management", counting_load)
    monkeypatch.setattr("dssatlab.simulation._load_management", counting_load)

    sim = Simulation(inputs.filex, "02", inputs.rows, management=yaml_file)
    if operation == "check":
        assert sim.check(verbose=False) == []
    else:
        result = sim.run()
        assert result.returncode == 0
    assert len(load_calls) == 1
    assert load_calls[0] == yaml_file


def test_simulation_run_writes_checked_content_when_yaml_file_edited_between_checks_and_write(
        inputs, fake_dssat, monkeypatch, tmp_path):
    pytest.importorskip("yaml")
    from test_planting_run import HEADER, OLD_ROW, TREATMENT

    text = SAMPLE_FILEX.replace(TREATMENT, TREATMENT.replace(" 2 ", " 1 ", 1) + "\n" + TREATMENT)
    text = text.replace("*SIMULATION CONTROLS", "*PLANTING DETAILS\n" + HEADER + "\n"
                        + OLD_ROW + "\n\n*SIMULATION CONTROLS")
    inputs.filex.write_bytes(text.encode("latin-1"))

    yaml_content = """treatments:
  "02":
    planting:
      date: "1982-02-25"
      method: "S"
      distribution: "R"
      population: 8
      row_spacing: 75.0
      depth: 4.0
"""
    yaml_file = tmp_path / "plan.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    sim = Simulation(inputs.filex, "02", inputs.rows, management=yaml_file)

    original_check_inputs = sim._check_inputs

    def check_inputs_and_tamper(*args, **kwargs):
        res = original_check_inputs(*args, **kwargs)
        # Edit the file on disk after checks have loaded/checked the YAML:
        yaml_file.write_text("corrupted / invalid YAML: [[[", encoding="utf-8")
        return res

    monkeypatch.setattr(sim, "_check_inputs", check_inputs_and_tamper)

    result = sim.run()
    assert result.returncode == 0
    sim_filex = result.run_dir.parent / inputs.filex.name
    content = sim_filex.read_text(encoding="latin-1")
    assert "8.0" in content or "  8  " in content or "4.0" in content


@pytest.mark.skipif(not Path(r"C:\DSSAT48\Maize\UFGA8201.MZX").exists(),
                    reason="DSSAT48 installation not found")
def test_template_passes_checks_against_real_ufga8201_mzx(tmp_path):
    pytest.importorskip("yaml")
    ufga = Path(r"C:\DSSAT48\Maize\UFGA8201.MZX")
    start = date(1982, 2, 25)
    weather = [
        dict(station="UFGA", latitude=29.638, longitude=-82.3689, elevation=40,
             date=(start + timedelta(days=i)).isoformat(),
             srad=20, tmax=25, tmin=10, rain=0)
        for i in range(35)
    ]
    mgmt_file = tmp_path / "mgmt.yaml"
    write_management_template(mgmt_file)
    sim = Simulation(ufga, 1, weather, management=mgmt_file)
    assert sim.check() == []

