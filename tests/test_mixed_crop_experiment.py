"""Experiment data uses each treatment's crop entry and genotype files."""

from copy import deepcopy

import pytest

from dssatlab import DSSATCheckError, Simulation
from dssatlab.filex import _section_row
from test_crop_entries import mixed
from test_filex_template import data, rows
from test_mixed_crop_simulation import inputs
from test_new_cultivar_checks import CUL, ECO, new_cultivar
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


@pytest.mark.parametrize("selected", [1, 2, 3, 4])
@pytest.mark.parametrize("number,crop", [(1, "MZ"), ("02", "SB"), (3, "MZ"), (4, "WH")])
@pytest.mark.parametrize("matching", [False, True])
def test_cultivar_crop_matches_each_experiment_data_treatment(inputs, installed, selected, number, crop, matching):
    inputs["filex_template"]["treatment_crops"] = [1, 2, 1, 3]
    edit_crop = crop if matching else ("MZ" if crop == "WH" else "WH")
    inputs["management"] = {"treatments": {number: {"cultivar": {"crop": edit_crop, "code": "ZZ0001"}}}}
    problems = Simulation(**inputs, treatment=selected).check(False)
    if matching:
        assert problems == []
    else:
        assert problems == [
            f"Management data treatment {int(number)}, cultivar: crop {edit_crop!r} differs "
            f"from treatment {int(number)}'s crop {crop!r}. Checked its .CUL file in the "
            "data directory. Keep the FileX template crop and choose a cultivar from its fixed model."]


@pytest.mark.parametrize("selected", [1, 2])
@pytest.mark.parametrize("number,missing", [(2, ("planting_material_weight", "sprout_length")),
                                           (2, ("sprout_length",)), (2, ()), (1, ())])
def test_planting_edit_requires_potato_fields_only_for_potato(inputs, installed, selected, number, missing):
    potato = inputs["filex_template"]["crops"][1]
    potato.update(crop="potato", cultivar={"code": "IB0001"}, harvest_date="2021-08-01")
    potato["planting"].update(planting_material_weight=1500, sprout_length=2)
    planting = dict(potato["planting"])
    for field in missing:
        del planting[field]
    inputs["management"] = {"treatments": {number: {"planting": planting}}}
    assert Simulation(**inputs, treatment=selected).check(False) == [
        f"Management data treatment 2, planting: missing {field!r}; treatment 2's crop is potato. "
        f"Checked the treatment's crop entry. Supply planting.{field}." for field in missing]


@pytest.fixture
def genotype_definitions(inputs, installed):
    folder = installed.executable.parent / "Genotype"
    (folder / "MZCER048.CUL").write_text(CUL, encoding="ascii")
    (folder / "MZCER048.ECO").write_text(ECO, encoding="ascii")
    (folder / "SBGRO048.CUL").write_text(
        CUL.replace("IB0035", "IB0011").replace("IB0001", "SB0001").replace("P1", "Q1"),
        encoding="ascii")
    (folder / "SBGRO048.ECO").write_text(ECO.replace("IB0001", "SB0001"), encoding="ascii")
    return folder


@pytest.mark.parametrize("selected", [1, 2, 4])
@pytest.mark.parametrize("conflicting", [False, True])
def test_same_new_cultivar_code_in_different_crops_is_independent(
        inputs, installed, genotype_definitions, selected, conflicting):
    soybean = dict(crop="SB", code="NC0001", ecotype="SB0001",
                   coefficients={"Q1": 200, "P2": 1.193, "PHINT": 43})
    inputs["management"] = {"treatments": {1: {"cultivar": new_cultivar()}, 2: {"cultivar": soybean}}}
    if conflicting:
        # A separate maize crop entry still shares the same .CUL copy.
        template = inputs["filex_template"]
        template["crops"].append(deepcopy(template["crops"][0]))
        template["treatment_crops"][3] = 4
        maize = new_cultivar()
        maize["coefficients"]["P1"] = 300
        inputs["management"]["treatments"][4] = {"cultivar": maize}
    problems = Simulation(**inputs, treatment=selected).check(False)
    if conflicting:
        assert len(problems) == 1
        assert "NC0001" in problems[0] and "conflicting definitions" in problems[0]
        assert "treatment 1" in problems[0] and "treatment 4" in problems[0]
        assert "treatment 2" not in problems[0]
        return
    assert problems == []
    folder = Simulation(**inputs, treatment=selected).run().run_dir.parent
    assert b"NC0001 NC0001                .IB0001   259 1.193    43" in (folder / "MZCER048.CUL").read_bytes()
    assert b"NC0001 NC0001                .SB0001   200 1.193    43" in (folder / "SBGRO048.CUL").read_bytes()


@pytest.mark.parametrize("selected", [1, 2])
@pytest.mark.parametrize("valid", [False, True])
def test_new_cultivar_for_treatment_two_uses_its_cul(inputs, installed, genotype_definitions, tmp_path, selected, valid):
    cultivar = dict(crop="SB", code="NC0001", ecotype="SB0001",
                    coefficients={"Q1" if valid else "P1": 200, "P2": 1.193, "PHINT": 43})
    inputs["management"] = {"treatments": {"02": {"cultivar": cultivar}}}
    sim = Simulation(**inputs, treatment=selected)
    before, original = snapshot(tmp_path), deepcopy(inputs)
    problems = sim.check(False)
    if valid:
        assert problems == []
    else:
        assert len(problems) == 2
        assert "missing required coefficients: Q1" in problems[0]
        assert "coefficient 'P1'" in problems[1] and "SBGRO048.CUL" in problems[1]
        assert "Use one of: Q1, P2, PHINT" in problems[1]
        with pytest.raises(DSSATCheckError) as error:
            sim.run()
        assert error.value.problems == problems
    assert inputs == original and snapshot(tmp_path) == before
    assert installed.calls == []


def test_controls_edit_keeps_other_crop_entry_levels(inputs, installed):
    baseline = Simulation(**inputs, treatment=2)
    assert baseline.check(False) == []
    before = (baseline.run().run_dir.parent / "TEST2101.MZX").read_text()
    inputs["management"] = {"treatments": {2: {"controls": {"water": "N", "output_interval": 2}}}}
    sim = Simulation(**inputs, treatment=1)
    assert sim.check(False) == []
    after = (sim.run().run_dir.parent / "TEST2101.MZX").read_text()
    before_controls = before.split("*SIMULATION CONTROLS", 1)[1]
    after_controls = after.split("*SIMULATION CONTROLS", 1)[1]
    for number in (1, 3, 4):
        level = int(_section_row(before, "TREATMENTS", "N", number, ("SM",))["SM"])
        assert _section_row(after, "TREATMENTS", "N", number, ("SM",))["SM"] == str(level)
        assert [line for line in after_controls.splitlines() if line.startswith(f"{level:2d} ")] == [
            line for line in before_controls.splitlines() if line.startswith(f"{level:2d} ")]
    level = int(_section_row(after, "TREATMENTS", "N", 2, ("SM",))["SM"])
    assert _section_row(after, "SIMULATION CONTROLS", "N", level, ("WATER",))["WATER"] == "N"
    assert _section_row(after, "SIMULATION CONTROLS", "N", level, ("FROPT",))["FROPT"] == "2"
    assert _section_row(after, "SIMULATION CONTROLS", "N", level, ("SYMBI",))["SYMBI"] == "Y"
    assert next(line for line in after.splitlines() if line.startswith(f"{level:2d} GE"))[71:79] == "CRGRO048"
