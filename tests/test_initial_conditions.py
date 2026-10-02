"""Initial conditions checked and copied through the public Simulation seam."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, write_experiment_template
from test_simulation_run import fake_dssat, inputs, snapshot, soil_rows


FIXTURE = Path(__file__).parent / "fixtures" / "initial_conditions" / "UFGA8201.MZX"
HEADER = "@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME"
LAYERS = "@C  ICBL  SH2O  SNH4  SNO3"


def section(text):
    return text.split("*INITIAL CONDITIONS", 1)[1].split("\n*", 1)[0]


@pytest.fixture
def sim(inputs):
    inputs.filex.write_bytes(FIXTURE.read_bytes())
    data = dict(date="1982-02-25", previous_crop="WH", residue_mass=1250,
                layers=[dict(depth=15, water=0.25, nh4=1, no3=2),
                        dict(depth=30, water=0.3, nh4=0, no3=3.5)])
    return Simulation(inputs.filex, "02", inputs.rows,
                      management={"treatments": {"02": {"initial_conditions": data}}})


def conditions(sim):
    return sim.management["treatments"]["02"]["initial_conditions"]


def copied(sim, fake_dssat):
    return (Path(fake_dssat.calls[0][1]) / sim.filex.name).read_bytes()


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_new_level_only_repoints_selected_treatment_and_preserves_original(sim, fake_dssat, newline):
    original = sim.filex.read_text(encoding="latin-1").encode("latin-1").replace(b"\n", newline)
    sim.filex.write_bytes(original)
    before = snapshot(sim.filex.parent)
    sim.management["treatments"][1] = {"initial_conditions": dict(conditions(sim), residue_mass=900)}
    data_before = deepcopy(sim.management)
    assert sim.check() == []
    assert snapshot(sim.filex.parent) == before
    result = sim.run()
    written = copied(sim, fake_dssat)
    block = section(written.decode("latin-1").replace(newline.decode(), "\n"))
    added = block[block.rindex(HEADER):].splitlines()[:5]
    assert added[1] == " 2    WH 82056   -99   -99   -99   -99   -99  1250   -99   -99   -99   -99    -99"
    assert added[2:] == [LAYERS, " 2    15  0.25     1     2", " 2    30   0.3     0   3.5"]
    # Remove exactly the new header pair and restore IC: every other byte must match.
    restored = written.replace(newline.join(line.encode() for line in added) + newline, b"", 1)
    old_treatment = next(line for line in original.splitlines() if line.startswith(b" 2 1 0 0"))
    new_treatment = old_treatment[:43] + b"  2" + old_treatment[46:]
    assert new_treatment in restored
    assert restored.replace(new_treatment, old_treatment, 1) == original
    assert sim.filex.read_bytes() == original
    assert snapshot(sim.filex.parent) == before
    assert sim.management == data_before
    assert (result.run_dir.parent / sim.filex.name).read_bytes() == written


@pytest.mark.parametrize("management", [None, {"treatments": {2: {}}}])
def test_omitted_section_keeps_filex_bytes(sim, fake_dssat, management):
    sim.management = management
    original = sim.filex.read_bytes()
    sim.run()
    assert copied(sim, fake_dssat) == original == sim.filex.read_bytes()


def test_missing_section_is_inserted_and_optional_fields_use_missing_marker(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    start, end = text.index("*INITIAL CONDITIONS"), text.index("*PLANTING DETAILS")
    sim.filex.write_text(text[:start] + text[end:], encoding="latin-1")
    data = conditions(sim)
    del data["previous_crop"], data["residue_mass"]
    data["date"] = "2000-02-29"
    sim.run()
    written = copied(sim, fake_dssat).decode("latin-1")
    assert written.index("*INITIAL CONDITIONS") < written.index("*SIMULATION CONTROLS")
    assert section(written).splitlines()[2].split() == ["1", "-99", "00060"] + ["-99"] * 11


def test_repeated_blocks_choose_highest_level_and_preserve_comments(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    block = section(text)
    repeats = block.replace("\n 1 ", "\n 7 ") + block.replace("\n 1 ", "\n 3 ")
    text = text.replace("*PLANTING DETAILS", repeats + "! caf\xe9\n*PLANTING DETAILS")
    sim.filex.write_bytes(text.encode("latin-1"))
    sim.run()
    written = copied(sim, fake_dssat).decode("latin-1")
    assert "\n 8    WH 82056" in written
    assert "\n 8    15  0.25" in written
    added = section(written).rsplit(HEADER, 1)[1].splitlines()[:5]
    restored = written.replace(HEADER + "\n".join(added) + "\n", "", 1)
    old_treatment = next(line for line in text.splitlines() if line.startswith(" 2 1 0 0"))
    new_treatment = old_treatment[:43] + "  8" + old_treatment[46:]
    assert restored.replace(new_treatment, old_treatment, 1) == text
    assert sim.filex.read_bytes() == text.encode("latin-1")


@pytest.mark.parametrize("field,value,expected", [
    ("depth", 0, "positive"), ("depth", -1, "positive"),
    ("water", -0.1, "0 to 1"), ("water", 1.1, "0 to 1"),
    ("nh4", -1, "0 or greater mg/kg"), ("no3", -99, "0 or greater mg/kg"),
    ("water", float("nan"), "finite"), ("nh4", float("inf"), "finite"),
    ("no3", True, "boolean"), ("depth", "15", "number"),
])
def test_layer_value_problems_prevent_any_writes(sim, fake_dssat, field, value, expected):
    conditions(sim)["layers"][0][field] = value
    before = snapshot(sim.filex.parent)
    problems = sim.check()
    assert any(field in p and "layer 1" in p and expected in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert snapshot(sim.filex.parent) == before and fake_dssat.calls == []
    assert not list(sim.filex.parent.glob("dssat_sim_*"))


@pytest.mark.parametrize("depth", [15, 10])
def test_equal_or_descending_depths_rejected(sim, depth):
    conditions(sim)["layers"][1]["depth"] = depth
    assert any("layer 2" in p and "strictly ascending" in p for p in sim.check())


@pytest.mark.parametrize("field,value,word", [
    ("date", "1982-02-30", "calendar"), ("date", date(1982, 2, 25), "quote"),
    ("previous_crop", "MAIZE", "crop code"), ("previous_crop", False, "crop code"),
    ("previous_crop", "M\n", "crop code"), ("residue_mass", -1, "nonnegative"),
    ("residue_mass", "1", "number"), ("residue_mass", float("inf"), "finite"),
    ("layers", [], "non-empty"), ("layers", None, "list"),
])
def test_section_fields_are_checked(sim, field, value, word):
    conditions(sim)[field] = value
    assert any(field in p and word in p for p in sim.check())


def test_water_endpoints_and_zero_nitrogen_are_allowed(sim, fake_dssat):
    conditions(sim)["layers"] = [dict(depth=15, water=0, nh4=0, no3=0),
                                dict(depth=30, water=1, nh4=0, no3=0)]
    assert sim.check() == []
    sim.run()
    assert b" 2    30     1     0     0" in copied(sim, fake_dssat)


def test_soil_profile_depth_is_checked_for_selected_treatment(sim, soil_rows):
    sim.soil = soil_rows
    assert sim.check() == []  # Equal profile depth is allowed.
    conditions(sim)["layers"][1]["depth"] = 31
    assert any("31 cm" in p and "soil profile depth 30.0 cm" in p for p in sim.check())
    # Compare the maximum even when a later row is out of order.
    conditions(sim)["layers"][0]["depth"] = 35
    problems = sim.check()
    assert any("35 cm" in p and "soil profile depth" in p for p in problems)
    assert any("ascending" in p for p in problems)
    sim.management["treatments"][1] = {"initial_conditions": deepcopy(conditions(sim))}
    conditions(sim)["layers"] = [dict(depth=15, water=0.2, nh4=0, no3=0)]
    assert any("ascending" in p for p in sim.check())  # All treatments still checked.
    sim.management["treatments"][1]["initial_conditions"]["layers"].reverse()
    assert sim.check() == []  # soil= describes only the selected treatment.


def test_no_soil_skips_profile_comparison_and_bad_soil_keeps_independent_checks(sim):
    conditions(sim)["layers"][1]["depth"] = 999
    assert sim.check() == []
    sim.soil = []
    conditions(sim)["layers"][0]["no3"] = -1
    problems = sim.check()
    assert any("Soil data" in p for p in problems)
    assert any("no3" in p for p in problems)
    assert not any("exceeds" in p for p in problems)


@pytest.mark.parametrize("old,new,word", [("ICDAT", "BADDT", "ICDAT"),
    ("SNH4", "BADN", "SNH4"), (LAYERS, "! removed header", "ICBL"),
    ("SA IC MP", "SA XX MP", "IC")])
def test_unwritable_layout_is_reported_during_check(sim, old, new, word):
    sim.filex.write_bytes(sim.filex.read_bytes().replace(old.encode(), new.encode()))
    assert any(word in p and "header" in p for p in sim.check())


def test_column_overflow_rejected_without_rounding(sim):
    conditions(sim)["layers"][0]["water"] = 0.1234567
    assert any("SH2O" in p and "does not fit" in p for p in sim.check())


def test_all_treatments_and_fields_reported_at_once(sim, capsys):
    data = conditions(sim)
    data.update(date="bad", previous_crop="BAD", residue_mass=-1, typo=0)
    data["layers"] = [dict(depth=15, water=-1, nh4=-1, no3=-1),
                      dict(depth=10, water=2, nh4=True, no3="bad", n03=1)]
    sim.management["treatments"][1] = {"initial_conditions": deepcopy(data)}
    problems = sim.check()
    for treatment in (1, 2):
        for word in ("date", "previous_crop", "residue_mass", "typo", "ascending", "water", "nh4", "no3", "n03"):
            assert any(f"treatment {treatment}" in p and word in p for p in problems)
    report = capsys.readouterr().out
    assert all(p in report for p in problems)


def test_template_initial_conditions_load_check_and_apply(sim, tmp_path, fake_dssat, capsys):
    pytest.importorskip("yaml")
    template = tmp_path / "experiment.yaml"
    # The shared fixture adds an odd-cased MZCER048.cUl; two .CUL files for one crop are rejected.
    for old in sim.filex.parent.iterdir():
        if old.suffix.lower() == ".cul":
            old.unlink()
    cul = Path(__file__).parent / "fixtures" / "cultivar" / "MZCER048.CUL"
    (sim.filex.parent / cul.name).write_bytes(cul.read_bytes())
    write_experiment_template(template, filex=sim.filex)
    # Keep the full strict-loader path; the supplied weather covers all template events.
    sim.weather = [dict(sim.weather[0], date=(date(1982, 2, 25) + timedelta(days=i)).isoformat())
                   for i in range(35)]
    sim.management = template
    assert sim.check() == []
    assert "initial_conditions: OK (shape only" not in capsys.readouterr().out
    sim.run()
    assert b" 2    MZ 82056" in copied(sim, fake_dssat)
