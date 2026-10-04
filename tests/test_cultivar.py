"""Cultivar checks and copied FileX behavior through Simulation."""

from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATCheckError, Simulation, write_experiment_template
from test_management_file import sim_inputs
from test_simulation_run import fake_dssat


FIXTURES = Path(__file__).parent / "fixtures" / "cultivar"


@pytest.fixture
def cultivar_inputs(sim_inputs):
    filex, weather = sim_inputs
    shutil.copyfile(FIXTURES / filex.name, filex)
    shutil.copyfile(FIXTURES / "MZCER048.CUL", filex.parent / "MZCER048.CUL")
    return filex, weather


def simulation(inputs, cultivar, treatment=1):
    filex, weather = inputs
    return Simulation(filex, treatment, weather,
                      management={"treatments": {treatment: {"cultivar": cultivar}}})


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_cultivar_adds_level_and_changes_only_selected_cu(cultivar_inputs, fake_dssat, newline):
    filex, weather = cultivar_inputs
    original = filex.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline)
    filex.write_bytes(original)
    data = {"treatments": {1: {"cultivar": {"crop": "MZ", "code": "IB0035"}},
                           "3": {"cultivar": {"crop": "MZ", "code": "IB0060"}}}}
    sim = Simulation(filex, "3", weather, management=data)
    assert sim.check() == []
    result = sim.run()
    copied = result.run_dir.parent / filex.name
    lines = copied.read_bytes().splitlines(keepends=True)
    added = next(line for line in lines if line.startswith(b" 8 MZ IB0060"))
    assert added.endswith(newline)
    selected = next(line for line in lines if line.startswith(b" 3 1 0 0"))
    assert selected[34:37] == b"  8"
    # Removing the new level and undoing exactly CU recovers every original byte.
    restored = copied.read_bytes().replace(added, b"").replace(
        selected, selected[:34] + b"  1" + selected[37:])
    assert restored == original == filex.read_bytes()
    assert (copied.parent / "MZCER048.CUL").read_bytes() == (FIXTURES / "MZCER048.CUL").read_bytes()


def test_omitted_cultivar_needs_no_cul_and_keeps_entire_filex(cultivar_inputs, fake_dssat):
    filex, weather = cultivar_inputs
    (filex.parent / "MZCER048.CUL").unlink()
    original = filex.read_bytes()
    sim = Simulation(filex, 1, weather, management={"treatments": {1: {}}})
    assert sim.check() == []
    result = sim.run()
    assert (result.run_dir.parent / filex.name).read_bytes() == original == filex.read_bytes()


def test_missing_cultivars_section_is_inserted(sim_inputs, fake_dssat):
    filex, _ = sim_inputs
    shutil.copyfile(FIXTURES / "MZCER048.CUL", filex.parent / "MZCER048.CUL")
    original = filex.read_bytes()
    result = simulation(sim_inputs, {"crop": "MZ", "code": "IB0060"}).run()
    copied = (result.run_dir.parent / filex.name).read_text()
    assert "*CULTIVARS\n@C CR INGENO CNAME\n 1 MZ IB0060   -99\n" in copied
    assert filex.read_bytes() == original


def test_codes_are_checked_only_in_the_named_crops_file(cultivar_inputs, fake_dssat):
    filex, _ = cultivar_inputs
    path = filex.parent / "SBGRO048.cUl"
    path.write_text("*SOYBEAN CULTIVAR COEFFICIENTS\n"
                    "! XX0001 is a comment, not a cultivar\n"
                    "@VAR#  VAR-NAME........ EXPNO   ECO#\n"
                    "990001 M GROUP   1          . SB0101\n"
                    "\n!IB0035 is not soybean\n")
    sim = simulation(cultivar_inputs, {"crop": "SB", "code": "990001"})
    assert sim.check() == []
    result = sim.run()
    assert " 8 SB 990001" in (result.run_dir.parent / filex.name).read_text()
    problems = simulation(cultivar_inputs, {"crop": "SB", "code": "IB0035"}).check()
    assert any("SBGRO048.cUl" in p and "990001" in p for p in problems)


def test_existing_cultivar_with_underscore_is_accepted_and_listed(cultivar_inputs, fake_dssat):
    filex, _ = cultivar_inputs
    (filex.parent / "SCCAN048.CUL").write_text(
        "*SUGARCANE CULTIVAR COEFFICIENTS\n"
        "@VAR#  VAR-NAME........ EXPNO   ECO#\n"
        "HYP_HS HYP_HS              . SC0001\n")
    sim = simulation(cultivar_inputs, {"crop": "SC", "code": "HYP_HS"})
    assert sim.check() == []
    result = sim.run()
    assert " 8 SC HYP_HS" in (result.run_dir.parent / filex.name).read_text()
    problems = simulation(cultivar_inputs, {"crop": "SC", "code": "XX9999"}).check()
    assert any("HYP_HS" in p and "SCCAN048.CUL" in p for p in problems)


def test_unreadable_cul_is_a_check_problem(cultivar_inputs, monkeypatch):
    read_text = Path.read_text

    def read(path, *args, **kwargs):
        if path.suffix == ".CUL":
            raise PermissionError("test cultivar file is unreadable")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    problems = simulation(cultivar_inputs, {"crop": "MZ", "code": "IB0035"}).check()
    assert any(".CUL" in p and "unreadable" in p for p in problems)


@pytest.mark.parametrize("cultivar,words", [
    (None, ["dict"]), ({}, ["crop", "code", "missing"]),
    ({"crop": "MZ", "code": "IB0035", "cod": "X"}, ["unknown key", "cod", "crop", "code"]),
    ({"crop": False, "code": 123456}, ["crop", "code", "string"]),
    ({"crop": "MZZ", "code": "IB0035"}, ["crop", "two"]),
    ({"crop": "MZ", "code": "IB00355"}, ["code", "six"]),
    ({"crop": "MZ", "code": "IB 035"}, ["code", "six"]),
    ({"crop": "MZ", "code": ""}, ["code", "six"]),
    ({"crop": "MZ", "code": "XX9999"}, ["XX9999", "IB0035", "IB0060", "MZCER048.CUL"]),
    ({"crop": "SB", "code": "IB0035"}, ["SB", ".CUL"]),
])
def test_cultivar_problems_prevent_any_writes(cultivar_inputs, cultivar, words):
    filex, _ = cultivar_inputs
    before = {p: p.read_bytes() for p in filex.parent.iterdir() if p.is_file()}
    sim = simulation(cultivar_inputs, cultivar)
    problems = sim.check()
    for word in words:
        assert any(word in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert {p: p.read_bytes() for p in filex.parent.iterdir() if p.is_file()} == before
    assert not list(filex.parent.glob("dssat_sim_*"))


@pytest.mark.parametrize("contents,word", [("", "header"), ("@VAR# VRNAME\n", "codes")])
def test_unusable_cul_is_reported(cultivar_inputs, contents, word):
    filex, _ = cultivar_inputs
    (filex.parent / "MZCER048.CUL").write_text(contents)
    problems = simulation(cultivar_inputs, {"crop": "MZ", "code": "IB0035"}).check()
    assert any("MZCER048.CUL" in p and word in p for p in problems)


def test_multiple_matching_cul_files_are_not_guessed(cultivar_inputs):
    filex, _ = cultivar_inputs
    shutil.copyfile(filex.parent / "MZCER048.CUL", filex.parent / "MZIXM048.CUL")
    problems = simulation(cultivar_inputs, {"crop": "MZ", "code": "IB0035"}).check()
    assert any("MZCER048.CUL" in p and "MZIXM048.CUL" in p for p in problems)


@pytest.mark.parametrize("old,new,word", [
    ("CU FL", "XX FL", "CU"),
    ("@C CR INGENO CNAME", "@C CR WRONGX CNAME", "INGENO"),
])
def test_layout_problems_are_reported_before_run(cultivar_inputs, old, new, word):
    filex, _ = cultivar_inputs
    filex.write_text(filex.read_text().replace(old, new), encoding="latin-1")
    problems = simulation(cultivar_inputs, {"crop": "MZ", "code": "IB0035"}).check()
    assert any(word in p for p in problems)


def test_all_treatments_and_other_problems_are_reported(cultivar_inputs):
    filex, weather = cultivar_inputs
    data = {"treatments": {
        1: {"cultivar": {"crop": "MZ", "code": "XX0001"}, "planting": {}},
        3: {"cultivar": {"crop": "MZ", "code": "XX0003"}},
    }}
    weather[0]["rain"] = -1
    problems = Simulation(filex, 1, weather, management=data).check()
    for word in ("rain", "planting", "XX0001", "XX0003"):
        assert any(word in p for p in problems)


def test_experiment_template_cultivar_loads_checks_and_runs(cultivar_inputs, fake_dssat, tmp_path, capsys):
    pytest.importorskip("yaml")
    filex, weather = cultivar_inputs
    # The template also sets controls, so the FileX needs a full SIMULATION CONTROLS section.
    full = (Path(__file__).parent / "fixtures" / "controls" / "UFGA8201.MZX").read_bytes()
    filex.write_bytes(filex.read_bytes().split(b"*SIMULATION CONTROLS")[0]
                      + b"*SIMULATION CONTROLS" + full.split(b"*SIMULATION CONTROLS")[1])
    path = tmp_path / "experiment.yaml"
    write_experiment_template(path, filex=filex)
    sim = Simulation(filex, 3, weather, management=path)
    assert sim.check() == []
    assert "cultivar: OK\n" in capsys.readouterr().out
    result = sim.run()
    assert b" 8 MZ IB0035" in (result.run_dir.parent / filex.name).read_bytes()


def test_missing_code_lists_only_the_closest_five(cultivar_inputs):
    filex, _ = cultivar_inputs
    (filex.parent / "MZCER048.CUL").write_text(
        "*MAIZE CULTIVAR COEFFICIENTS\n@VAR#  VAR-NAME........ EXPNO   ECO#\n"
        + "".join(f"IB{n:04d} CULTIVAR {n}          . IB0001\n" for n in range(40)))
    problems = simulation(cultivar_inputs, {"crop": "MZ", "code": "IB0099"}).check()
    message = next(p for p in problems if "missing from .CUL" in p)
    assert "IB0099" in message and "40 codes" in message
    assert message.count("IB00") <= 7  # the code asked for, five close ones, the path


def test_check_verbose_false_prints_nothing_but_default_reports(cultivar_inputs, capsys):
    sim = simulation(cultivar_inputs, {"crop": "MZ", "code": "IB0035"})
    sim.check()
    assert "Checks" in capsys.readouterr().out
    sim.check(verbose=False)
    assert capsys.readouterr().out == ""
