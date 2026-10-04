"""Cultivar coefficient edits through checked simulations and sweeps."""
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, run_sweep
from dssatlab.filex import _section_row
from test_cultivar import cultivar_inputs, simulation
from test_management_file import sim_inputs
from test_simulation_run import fake_dssat
from test_filex_template import data, rows
from test_simulation_template import installed


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("value,formatted", [(300, b"   300"), (300.0, b" 300.0"),
                                             (12.25, b" 12.25"), (-2, b"    -2")])
@pytest.mark.parametrize("occupied", [False, True])
def test_changed_line(cultivar_inputs, fake_dssat, newline, value, formatted, occupied):
    filex, _ = cultivar_inputs
    path = filex.parent / "MZCER048.CUL"
    original = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline)
    if occupied:
        original += b"DL0001 Existing cultivar" + newline
    path.write_bytes(original)
    sim = simulation(cultivar_inputs, dict(crop="MZ", code="IB0035", coefficients={"P1": value}))
    assert sim.check(False) == []
    result = sim.run()
    folder = result.run_dir.parent
    lines = original.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if line.startswith(b"IB0035"))
    code = b"DL0002" if occupied else b"DL0001"
    changed = code + lines[index][6:36] + formatted + lines[index][42:]
    assert (folder / path.name).read_bytes() == b"".join(lines[:index + 1] + [changed] + lines[index + 1:])
    assert path.read_bytes() == original
    text = (folder / filex.name).read_text()
    level = int(_section_row(text, "TREATMENTS", "N", 1, ("CU",))["CU"])
    assert _section_row(text, "CULTIVARS", "C", level, ("INGENO", "CNAME")) == {
        "C": str(level), "CR": "MZ", "INGENO": code.decode(), "CNAME": "-99"}


@pytest.mark.parametrize("coefficients", [None, [], {}, "P1"])
def test_coefficient_shape(cultivar_inputs, coefficients):
    from dssatlab.weather import _show_value
    sim = simulation(cultivar_inputs, dict(crop="MZ", code="IB0035", coefficients=coefficients))
    message = ("Management data treatment 1, cultivar, field 'coefficients': found "
               f"{_show_value(coefficients)}. Supply a non-empty dict of .CUL coefficient names "
               "to numbers, such as {'P1': 300}.")
    assert message in sim.check(False)
    with pytest.raises(DSSATCheckError):
        sim.run()


@pytest.mark.parametrize("value", [True, "300", None, float("nan"), float("inf")])
def test_bad_coefficient_number(cultivar_inputs, value):
    from dssatlab.weather import _show_value
    sim = simulation(cultivar_inputs, dict(crop="MZ", code="IB0035", coefficients={"P1": value}))
    assert (f"Management data treatment 1, cultivar, coefficient 'P1': found {_show_value(value)}. "
            "Supply a finite number in DSSAT's units, not a string or boolean.") in sim.check(False)


@pytest.mark.parametrize("name", ["Q1", "p1", "VAR#", "VRNAME..........", "EXPNO", "ECO#"])
def test_unknown_coefficient(cultivar_inputs, name):
    path = cultivar_inputs[0].parent / "MZCER048.CUL"
    sim = simulation(cultivar_inputs, dict(crop="MZ", code="IB0035", coefficients={name: 300}))
    assert (f"Management data treatment 1, cultivar, coefficient {name!r}: not a coefficient in "
            f"{path}. Use one of: P1, P2, P5, G2, G3, PHINT.") in sim.check(False)


@pytest.mark.parametrize("value,message", [
    (1234567.5, "1234567.5 needs 9 characters; the P1 column in MZCER048.CUL holds 5. "
                "Supply a value with fewer digits."),
    (1e-7, "1e-07 is written in exponent notation, which the P1 column in MZCER048.CUL "
           "cannot hold. Supply a plain decimal value."),
])
def test_unrepresentable_coefficient(cultivar_inputs, value, message):
    sim = simulation(cultivar_inputs, dict(crop="MZ", code="IB0035", coefficients={"P1": value}))
    assert f"Management data treatment 1, cultivar, coefficient 'P1': {message}" in sim.check(False)


def test_missing_eco(cultivar_inputs):
    path = cultivar_inputs[0].parent / "MZCER048.CUL"
    path.write_bytes(path.read_bytes().replace(b"ECO#", b"XXXX"))
    sim = simulation(cultivar_inputs, dict(crop="MZ", code="IB0035", coefficients={"P1": 300}))
    assert (f"Management data treatment 1, cultivar: .CUL file {path} has no ECO# column, "
            "so coefficients cannot be located. Remove 'coefficients' or supply a standard .CUL file.") in sim.check(False)


@pytest.mark.parametrize("short", [False, True])
def test_multiple_fields_first_source_and_padding(cultivar_inputs, fake_dssat, short):
    filex, _ = cultivar_inputs
    path = filex.parent / "MZCER048.CUL"
    lines = path.read_bytes().splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if line.startswith(b"IB0035"))
    source = lines[index].rstrip(b"\r\n")
    source = source[:36] if short else source + b" trailing \xe9\x85tail"
    lines[index] = source + b"\n"
    lines.insert(index + 1, b"IB0035 Duplicate must stay unchanged\n")
    original = b"".join(lines)
    path.write_bytes(original)
    sim = simulation(cultivar_inputs, dict(crop="MZ", code="IB0035",
                                           coefficients={"G2": 800, "P1": 300}))
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    expected = b"DL0001" + source[6:]
    expected = expected.ljust(60)
    expected = expected[:36] + b"   300" + expected[42:54] + b"   800" + expected[60:]
    assert (folder / path.name).read_bytes() == b"".join(
        lines[:index + 1] + [expected + b"\n"] + lines[index + 1:])
    assert path.read_bytes() == original


def test_sweep_checks_all_coefficients_before_run(cultivar_inputs, fake_dssat):
    filex, weather = cultivar_inputs
    with pytest.raises(DSSATCheckError) as error:
        run_sweep(filex, weather, treatments=[1], factors={"cultivar": {
            value: dict(crop="MZ", code="IB0035", coefficients={"Q1": value, "P1": True})
            for value in (200, 320)}})
    for value in (200, 320):
        for name in ("Q1", "P1"):
            assert any(f"Scenario '{value}', treatment 1:" in p and
                       f"coefficient '{name}'" in p for p in error.value.problems)
    assert fake_dssat.calls == []


def test_template_two_changed_cultivars(data, rows, installed):
    source = installed.executable.parent / "Genotype" / "MZCER048.CUL"
    fixture = Path(__file__).parent / "fixtures/cultivar/MZCER048.CUL"
    source.write_bytes(fixture.read_bytes())
    del data["treatment_name"]
    data["treatments"] = ["First", "Second"]
    management = {"treatments": {i: {"cultivar": dict(crop="MZ", code="IB0035", coefficients={"P1": i * 200})}
                                 for i in (1, 2)}}
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], management=management)
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    text = (folder / "TEST2101.MZX").read_text()
    for i in (1, 2):
        level = int(_section_row(text, "TREATMENTS", "N", i, ("CU",))["CU"])
        assert _section_row(text, "CULTIVARS", "C", level, ("INGENO",))["INGENO"] == f"DL{i:04d}"
    assert source.read_bytes() == fixture.read_bytes()
    assert (folder / source.name).read_bytes().count(b"DL000") == 2


def test_sweep_coefficients(cultivar_inputs, fake_dssat):
    filex, weather = cultivar_inputs
    source = (filex.parent / "MZCER048.CUL").read_bytes()
    fake_dssat.outputs["Summary.OUT"] = (Path(__file__).parent /
        "fixtures/output_files/summary/two_treatments/Summary.OUT").read_bytes()
    result = run_sweep(filex, weather, treatments=[1], executable=fake_dssat.executable,
                      factors={"cultivar": {p: dict(crop="MZ", code="IB0035", coefficients={"P1": p})
                                           for p in (200, 259, 320)}})
    assert {row["cultivar"] for row in result} == {None, 200, 259, 320}
    for row in result:
        contents = (row["run_dir"].parent / "MZCER048.CUL").read_bytes()
        assert contents.count(b"DL0001") == (row["cultivar"] is not None)
        if row["cultivar"] is not None:
            assert isinstance(row["cultivar"], int)
    assert (filex.parent / "MZCER048.CUL").read_bytes() == source
