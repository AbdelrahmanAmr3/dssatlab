"""New cultivar problems through both public Simulation.check paths."""

import pytest

from dssatlab import DSSATCheckError, Simulation
from test_cultivar import cultivar_inputs, simulation
from test_filex_template import data, rows
from test_management_file import sim_inputs
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


CUL = ("*CULTIVARS\n"
       "@VAR#  VRNAME.......... EXPNO   ECO#    P1    P2 PHINT\n"
       "IB0035 Example             . IB0001 259.0 1.193 43.00\n")
ECO = ("*ECOTYPES\n!IB9999 comment\n@ECO#  ECONAME\n"
       "IB0001 Example\nIB0002 Another\n")


def new_cultivar():
    return dict(crop="MZ", code="NC0001", ecotype="IB0001",
                coefficients={"P1": 259, "P2": 1.193, "PHINT": 43})


@pytest.fixture(params=["copied", "template"])
def inputs(request, cultivar_inputs, data, rows, installed):
    if request.param == "copied":
        sim = simulation(cultivar_inputs, new_cultivar())
        path = cultivar_inputs[0].parent / "MZCER048.CUL"
    else:
        sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                         executable=installed.executable,
                         management={"treatments": {1: {"cultivar": new_cultivar()}}})
        path = installed.executable.parent / "Genotype/MZCER048.CUL"
    path.write_text(CUL, encoding="ascii")
    path.with_suffix(".ECO").write_text(ECO, encoding="ascii")
    return sim, path


def definition(sim):
    return sim.management["treatments"][1]["cultivar"]


@pytest.mark.parametrize("treatment", [1, 2])
@pytest.mark.parametrize("different", [
    {"crop": "SB"}, {"ecotype": "IB0002"}, {"name": "Another name"},
    {"coefficients": {"P1": 320, "P2": 1.193, "PHINT": 43}},
])
def test_template_rejects_conflicting_new_code_definitions(
        data, rows, installed, tmp_path, treatment, different):
    source = installed.executable.parent / "Genotype/MZCER048.CUL"
    source.write_bytes(CUL.encode("ascii"))
    source.with_suffix(".ECO").write_bytes(ECO.encode("ascii"))
    del data["treatment_name"]
    data["treatments"] = ["First", "Second"]
    first = new_cultivar()
    first["coefficients"]["P1"] = 200
    second = {**first, **different}
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], treatment=treatment,
                     executable=installed.executable,
                     management={"treatments": {1: {"cultivar": first},
                                                "2": {"cultivar": second}}})

    before = snapshot(tmp_path)
    problems = sim.check(False)
    assert any("NC0001" in p and "treatment 1" in p and "treatment 2" in p
               and "conflicting" in p and "Checked" in p
               and "crop, ecotype, name and coefficients" in p
               and "Use" in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert snapshot(tmp_path) == before
    assert not list(tmp_path.glob("dssat_sim_*"))


@pytest.mark.parametrize("name", [None, "New cultivar", "1234567890123456", ""])
def test_valid_new_cultivar_checks_without_writes(inputs, tmp_path, name):
    sim, _ = inputs
    if name is not None:
        definition(sim)["name"] = name
    before = snapshot(tmp_path)
    assert sim.check(False) == []
    assert snapshot(tmp_path) == before


def test_missing_coefficients_listed_in_one_problem(inputs):
    sim, _ = inputs
    definition(sim)["coefficients"] = {"P1": 200}
    problems = sim.check(False)
    assert len(problems) == 1
    assert "missing" in problems[0] and "P2, PHINT" in problems[0]


@pytest.mark.parametrize("value", [None, [], {}, "P1"])
def test_new_coefficient_shape(inputs, value):
    sim, _ = inputs
    definition(sim)["coefficients"] = value
    assert any("field 'coefficients'" in p and "non-empty dict" in p for p in sim.check(False))


@pytest.mark.parametrize("value,words", [
    (True, ["finite number"]), ("300", ["finite number"]),
    (None, ["finite number"]), (float("nan"), ["finite number"]),
    (float("inf"), ["finite number"]),
    (1e-7, ["exponent notation", "plain decimal"]),
    (1234567.5, ["needs 9 characters", "holds 5"]),
])
def test_new_coefficient_values_reuse_existing_checks(inputs, value, words):
    sim, _ = inputs
    definition(sim)["coefficients"]["P1"] = value
    assert any("coefficient 'P1'" in p and all(w in p for w in words) for p in sim.check(False))


@pytest.mark.parametrize("name", ["Q1", "p1", "ECO#", "VAR#"])
def test_unknown_new_coefficient_lists_valid_names(inputs, name):
    sim, _ = inputs
    definition(sim)["coefficients"][name] = 300
    assert any(f"coefficient {name!r}" in p and "Use one of: P1, P2, PHINT" in p
               for p in sim.check(False))


@pytest.mark.parametrize("code", ["!C0001", "@C0001", "*C0001", "$C0001"])
def test_new_code_cannot_be_skipped_by_dssat(inputs, code):
    sim, _ = inputs
    definition(sim)["code"] = code
    assert any("code" in p and "starting with" in p and "!" in p for p in sim.check(False))


@pytest.mark.parametrize("code", ["DL0001", "DL9999"])
def test_changed_cultivar_codes_reserved(inputs, code):
    sim, _ = inputs
    definition(sim)["code"] = code
    assert any(code in p and "reserved" in p for p in sim.check(False))


@pytest.mark.parametrize("code", ["DL0000", "DLABCD", "HYP_HS"])
def test_non_reserved_codes_accepted(inputs, code):
    sim, _ = inputs
    definition(sim)["code"] = code
    assert sim.check(False) == []


@pytest.mark.parametrize("header", [
    "@VAR# NAME EXPNO ECO# P1 P2 PHINT\n",
    "@VAR#  VRNAME.......... EXPNO   XXXX    P1    P2 PHINT\n",
])
def test_new_cultivar_requires_fixed_ecotype_layout(inputs, header):
    sim, path = inputs
    path.write_text(CUL.replace(CUL.splitlines(keepends=True)[1], header))
    assert any("layout" in p and "ECO#" in p and "31-36" in p for p in sim.check(False))


@pytest.mark.parametrize("value", [None, 123456, "IB001", "IB00001", "IB 001", "IB000é", "IB00\t1"])
def test_new_ecotype_format(inputs, value):
    sim, _ = inputs
    definition(sim)["ecotype"] = value
    assert any("ecotype" in p and "six printable ASCII" in p for p in sim.check(False))


@pytest.mark.parametrize("code", ["IB0099", "IB9999"])
def test_unknown_ecotype_names_file_and_closest_codes(inputs, code):
    sim, path = inputs
    definition(sim)["ecotype"] = code
    assert any("missing from .ECO" in p and str(path.with_suffix(".ECO")) in p
               and "Closest codes: " in p and "IB0001" in p and "IB0002" in p
               for p in sim.check(False))


@pytest.mark.parametrize("value", [None, 42, "12345678901234567", "café", "new\nname", "\x7f"])
def test_new_name_format_and_width(inputs, value):
    sim, _ = inputs
    definition(sim)["name"] = value
    assert any("name" in p and "16" in p and "printable ASCII" in p for p in sim.check(False))


@pytest.mark.parametrize("fields", [{"ecotype": "IB0001"}, {"name": "New name"},
                                   {"ecotype": "IB0001", "name": "New name"}])
def test_existing_code_conflicts_with_new_fields(inputs, fields):
    sim, _ = inputs
    definition(sim).clear()
    definition(sim).update(crop="MZ", code="IB0035", **fields)
    assert any("existing cultivar" in p and "Remove" in p and all(f in p for f in fields)
               for p in sim.check(False))


@pytest.mark.parametrize("extra", [
    "@VAR# OTHER\nNC0001 Later table\n", "@OTHER\nNC0001 Readable row\n",
])
def test_code_in_later_readable_row_is_existing(inputs, extra):
    sim, path = inputs
    path.write_text(CUL + extra)
    assert any("existing cultivar" in p and "NC0001" in p for p in sim.check(False))


def test_first_table_defines_new_coefficients(inputs):
    sim, path = inputs
    path.write_text(CUL + "@VAR#  VRNAME.......... EXPNO   ECO#    Q1\n"
                   "OT0001 Other               . IB0001   200\n")
    assert sim.check(False) == []


@pytest.mark.parametrize("missing", [("ecotype",), ("coefficients",), ("ecotype", "coefficients")])
def test_incomplete_definition_keeps_unknown_code_and_hint(inputs, missing):
    sim, _ = inputs
    for field in missing:
        definition(sim).pop(field)
    problems = sim.check(False)
    assert any("NC0001" in p and "missing from .CUL" in p for p in problems)
    assert any("new cultivar" in p and "ecotype" in p and "coefficients" in p
               and "P1, P2, PHINT" in p for p in problems)


def test_missing_required_sibling_ecotype_file(inputs):
    sim, path = inputs
    path.with_suffix(".ECO").unlink()
    assert any("MZCER048.ECO" in p and "missing" in p for p in sim.check(False))


def test_copied_soybean_requires_sibling_ecotype(cultivar_inputs):
    filex, _ = cultivar_inputs
    (filex.parent / "SBGRO048.CUL").write_text(CUL)
    cultivar = new_cultivar()
    cultivar["crop"] = "SB"
    assert any("SBGRO048.ECO" in p and "missing" in p
               for p in simulation(cultivar_inputs, cultivar).check(False))


@pytest.mark.parametrize("stem,crop", [("RICER048", "RI"), ("SCCAN048", "SC")])
def test_no_ecotype_file_for_rice_or_unknown_stem_checks_format_only(cultivar_inputs, stem, crop):
    filex, _ = cultivar_inputs
    (filex.parent / f"{stem}.CUL").write_text(CUL)
    cultivar = new_cultivar()
    cultivar["crop"] = crop
    assert simulation(cultivar_inputs, cultivar).check(False) == []
    cultivar["ecotype"] = "bad"
    assert any("six printable ASCII" in p for p in simulation(cultivar_inputs, cultivar).check(False))
