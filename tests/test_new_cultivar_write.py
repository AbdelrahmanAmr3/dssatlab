"""New cultivar lines stay in each simulation copy under the user's code."""

from pathlib import Path
import shutil

import pytest

from dssatlab import Simulation, run_sweep
from dssatlab.filex import _section_row
from test_cultivar import cultivar_inputs
from test_filex_template import data, rows
from test_management_file import sim_inputs
from test_new_cultivar_checks import CUL, ECO, inputs, new_cultivar
from test_simulation_run import fake_dssat
from test_simulation_template import installed


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("name,padded", [
    (None, b"NC0001          "), ("", b"                "),
    ("1234567890123456", b"1234567890123456"),
])
@pytest.mark.parametrize("following", [
    b"\n! trailing comment\n@VAR# OTHER\nOT0001 Later table\n",
    b"\n! trailing comment\n@OTHER\nOT0001 Another table\n",
    b"\n*NEXT SECTION\n", b"",
])
def test_new_line_exact_bytes_and_first_table_placement(tmp_path, newline, name, padded, following):
    from dssatlab.cultivar_coefficients import _new_cultivar

    source = tmp_path / "MZCER048.CUL"
    first = CUL.encode("ascii").replace(b"\n", newline)
    # Comments with six printable characters must not be mistaken for rows.
    last = b"IB0060 Last cultivar"
    before = first + b"! note\xe9\n$ note\n".replace(b"\n", newline) + last
    after = following.replace(b"\n", newline)
    original = before + after
    source.write_bytes(original)
    folder = tmp_path / "simulation"
    folder.mkdir()
    copied = folder / source.name
    shutil.copyfile(source, copied)
    cultivar = dict(crop="MZ", code="NC0001", ecotype="IB0002",
                    coefficients={"PHINT": 43.0, "P2": -2.5, "P1": 300})
    if name is not None:
        cultivar["name"] = name

    assert _new_cultivar(folder / "TEST2101.MZX", cultivar) == cultivar
    expected = b"NC0001 " + padded + b"      .IB0002   300  -2.5  43.0" + newline
    suffix = after[len(newline):] if after else b""
    assert copied.read_bytes() == before + newline + expected + suffix
    assert source.read_bytes() == original


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_new_cultivar_runs_keep_user_code(inputs, newline):
    sim, source = inputs
    original = CUL.encode("ascii").replace(b"\n", newline)
    source.write_bytes(original)
    siblings = {path: path.read_bytes() for path in (source, source.with_suffix(".ECO"),
                source.with_suffix(".SPE")) if path.exists()}
    filex_original = Path(sim.filex).read_bytes() if sim.filex is not None else None

    folder = sim.run().run_dir.parent
    assert (folder / source.name).read_bytes() == original + (
        b"NC0001 NC0001                .IB0001   259 1.193    43" + newline)
    text = next(folder.glob("*.MZX")).read_text()
    level = int(_section_row(text, "TREATMENTS", "N", 1, ("CU",))["CU"])
    assert _section_row(text, "CULTIVARS", "C", level, ("INGENO",))["INGENO"] == "NC0001"
    for path, contents in siblings.items():
        assert path.read_bytes() == contents
        if path != source:
            assert (folder / path.name).read_bytes() == contents
    if filex_original is not None:
        assert Path(sim.filex).read_bytes() == filex_original


def test_template_reuses_one_new_line_for_identical_definitions(data, rows, installed):
    source = installed.executable.parent / "Genotype/MZCER048.CUL"
    source.write_bytes(CUL.encode("ascii"))
    source.with_suffix(".ECO").write_bytes(ECO.encode("ascii"))
    del data["treatment_name"]
    data["treatments"] = ["First", "Second"]
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={"treatments": {i: {"cultivar": new_cultivar()} for i in (1, 2)}})

    folder = sim.run().run_dir.parent
    assert (folder / source.name).read_bytes().count(b"NC0001 NC0001") == 1
    text = (folder / "TEST2101.MZX").read_text()
    for treatment in (1, 2):
        level = int(_section_row(text, "TREATMENTS", "N", treatment, ("CU",))["CU"])
        assert _section_row(text, "CULTIVARS", "C", level, ("INGENO",))["INGENO"] == "NC0001"
    assert source.read_bytes() == CUL.encode("ascii")


def test_sweep_same_new_code_has_each_scenarios_definition(cultivar_inputs, fake_dssat):
    filex, weather = cultivar_inputs
    source = filex.parent / "MZCER048.CUL"
    source.write_bytes(CUL.encode("ascii"))
    source.with_suffix(".ECO").write_bytes(ECO.encode("ascii"))
    fake_dssat.outputs["Summary.OUT"] = (Path(__file__).parent /
        "fixtures/output_files/summary/two_treatments/Summary.OUT").read_bytes()
    definitions = {p: {**new_cultivar(), "coefficients": {"P1": p, "P2": 1.193, "PHINT": 43}}
                   for p in (200, 320)}

    result = run_sweep(filex, weather, treatments=[1], executable=fake_dssat.executable,
                      factors={"cultivar": definitions})
    assert {row["cultivar"] for row in result} == {None, 200, 320}
    expected = {200: b"   200", 320: b"   320"}
    for row in result:
        folder = row["run_dir"].parent
        contents = (folder / source.name).read_bytes()
        p1 = row["cultivar"]
        if p1 is None:
            assert contents == CUL.encode("ascii")
        else:
            assert contents == CUL.encode("ascii") + (
                b"NC0001 NC0001                .IB0001" + expected[p1] + b" 1.193    43\n")
            text = (folder / filex.name).read_text()
            level = int(_section_row(text, "TREATMENTS", "N", 1, ("CU",))["CU"])
            assert _section_row(text, "CULTIVARS", "C", level, ("INGENO",))["INGENO"] == "NC0001"
    assert source.read_bytes() == CUL.encode("ascii")
