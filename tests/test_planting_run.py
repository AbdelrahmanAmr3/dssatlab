"""Planting edits observed at the fake DSSAT subprocess boundary."""

from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from dssatlab import DSSATCheckError, Simulation
from dssatlab.filex_write import _insert_section
from test_simulation_run import SAMPLE, fake_dssat, inputs, snapshot


HEADER = ("@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE"
          "  PENV  PLPH  SPRL                        PLNAME")
OLD_ROW = (" 1 82057   -99   7.2   7.2     S     R    61     0     7   -99"
           "   -99   -99   -99     0                        -99")
TREATMENT = " 2 1 0 0 RAINFED HIGH NITROGEN      1  1  0  1  1  1  2  0  0  0  0  0  1"


@pytest.fixture
def planting_sim(inputs):
    text = SAMPLE.replace(TREATMENT, TREATMENT.replace(" 2 ", " 1 ", 1) + "\n" + TREATMENT)
    text = text.replace("*SIMULATION CONTROLS", "*PLANTING DETAILS\n" + HEADER + "\n"
                        + OLD_ROW + "\n! keep this comment: caf\xe9\n"
                        + OLD_ROW.replace(" 1 ", " 7 ", 1) + "\n\n*SIMULATION CONTROLS")
    inputs.filex.write_bytes(text.encode("latin-1"))
    planting = dict(date="1982-02-25", population=8, method="S",
                    distribution="R", row_spacing=75, depth=4)
    return Simulation(inputs.filex, "02", inputs.rows,
                      management={"treatments": {"02": {"planting": planting}}})


@pytest.fixture
def seen(fake_dssat, monkeypatch):
    original_run = subprocess.run
    seen = []

    def read_filex(command, *, cwd, **kwargs):
        seen.append((Path(cwd) / command[2]).read_bytes())
        return original_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", read_filex)
    return seen


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_appends_level_repoints_only_selected_and_preserves_bytes(planting_sim, seen, newline):
    sim = planting_sim
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"\n", newline))
    before = snapshot(sim.filex.parent)
    original = sim.filex.read_bytes()
    management = deepcopy(sim.management)
    sim.management["treatments"][1] = {"planting": dict(
        sim.management["treatments"]["02"]["planting"], population=9)}
    result = sim.run()
    new_row = (" 8 82056   -99     8     8     S     R    75   -99     4   -99"
               "   -99   -99   -99   -99                           -99").encode()
    expected = original.replace(TREATMENT.encode(),
                                (TREATMENT[:46] + "  8" + TREATMENT[49:]).encode())
    old_last = OLD_ROW.replace(" 1 ", " 7 ", 1).encode() + newline
    expected = expected.replace(old_last, old_last + new_row + newline)
    assert seen == [expected]
    assert (result.run_dir.parent / sim.filex.name).read_bytes() == expected
    assert snapshot(sim.filex.parent) == before
    assert sim.management["treatments"]["02"] == management["treatments"]["02"]


def test_dates_optional_fields_and_explicit_emergence_population(planting_sim, seen):
    sim = planting_sim
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"82056", b"02072"))
    sim.weather = [dict(sim.weather[0], date="2002-03-13")]
    sim.management["treatments"]["02"]["planting"].update(
        date="2002-03-13", emergence_date="2002-03-14", emergence_population=7.5,
        row_direction=90, planting_material_weight=10, transplant_age=20,
        transplant_environment=25, plants_per_hill=2, sprout_length=0)
    sim.run()
    row = next(line for line in seen[0].decode("latin-1").splitlines() if line.startswith(" 8 "))
    assert row.split() == ["8", "02072", "02073", "8", "7.5", "S", "R", "75",
                           "90", "4", "10", "20", "25", "2", "0", "-99"]


def test_repeated_header_uses_highest_level_and_preserves_mixed_endings(planting_sim, seen):
    sim = planting_sim
    original = sim.filex.read_bytes().replace(
        b"\n*SIMULATION CONTROLS",
        ("\n" + HEADER + "\r\n" + OLD_ROW.replace(" 1 ", " 3 ", 1)
         + "\r\n! trailing comment\n*SIMULATION CONTROLS").encode())
    original = original.rstrip(b"\n") + b"\r\n! final comment without newline\xff"
    sim.filex.write_bytes(original)
    sim.run()
    written_lines = seen[0].splitlines(keepends=True)
    added = [line for line in written_lines if line.startswith(b" 8 ")]
    assert len(added) == 1
    assert written_lines.index(added[0]) > next(
        i for i, line in enumerate(written_lines) if line.startswith(b" 3 82057"))
    restored = seen[0].replace(added[0], b"").replace(
        (TREATMENT[:46] + "  8" + TREATMENT[49:]).encode(), TREATMENT.encode())
    assert restored == original
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("management", [None, {"treatments": {}},
    {"treatments": {2: {}}}])
def test_no_planting_keeps_exact_copy(planting_sim, seen, management):
    sim = planting_sim
    sim.management = management
    original = sim.filex.read_bytes()
    sim.run()
    assert seen == [original]
    assert sim.filex.read_bytes() == original


def test_other_treatment_is_checked_but_not_written(planting_sim, seen):
    sim = planting_sim
    entry = sim.management["treatments"].pop("02")
    sim.management["treatments"][1] = entry
    original = sim.filex.read_bytes()
    sim.run()
    assert seen == [original]
    entry["planting"]["population"] = 0
    with pytest.raises(DSSATCheckError, match="population"):
        sim.run()
    assert len(seen) == 1


def test_missing_section_inserted_before_controls(planting_sim, seen):
    sim = planting_sim
    original = sim.filex.read_bytes()
    start, end = original.index(b"*PLANTING DETAILS"), original.index(b"*SIMULATION CONTROLS")
    original = original[:start] + original[end:]
    sim.filex.write_bytes(original)
    sim.run()
    written = seen[0]
    assert written.index(b"*PLANTING DETAILS") < written.index(b"*SIMULATION CONTROLS")
    assert written[:start] == original[:start]  # MP stays 1: first new planting level
    assert written[written.index(b"*SIMULATION CONTROLS"):] == original[start:]
    assert b" 1 82056   -99     8     8" in written
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("column", ["MP", "P", "PDATE", "EDATE", "PPOP", "PPOE", "PLME",
    "PLDS", "PLRS", "PLRD", "PLDP", "PLWT", "PAGE", "PENV", "PLPH", "SPRL"])
def test_missing_columns_rejected_before_writing(planting_sim, seen, column):
    sim = planting_sim
    old = " MP " if column == "MP" else "@P " if column == "P" else column
    sim.filex.write_bytes(sim.filex.read_bytes().replace(old.encode(), b"?" * len(old)))
    before = snapshot(sim.filex.parent)
    listing = list(sim.filex.parent.iterdir())
    problems = sim.check()
    section = "TREATMENTS" if column == "MP" else "PLANTING DETAILS"
    assert any(section in p and column in p and "Supply" in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert seen == []
    assert snapshot(sim.filex.parent) == before
    assert list(sim.filex.parent.iterdir()) == listing


@pytest.mark.parametrize("failure", ["header", "population"])
def test_unwritable_layout_rejected_by_check(planting_sim, seen, failure):
    sim = planting_sim
    if failure == "header":
        sim.filex.write_bytes(sim.filex.read_bytes().replace(HEADER.encode(), b"! no header"))
    else:
        sim.management["treatments"]["02"]["planting"]["population"] = 1234567
    assert sim.check()
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == []


def test_insertion_helper_accepts_multiple_blocks_without_planting_assumptions():
    original = ["! caf\xe9\r\n", "*SIMULATION CONTROLS\r\n", "@N GENERAL\r\n"]
    body = ["@I  EFIR", " 1     1", "@I IDATE  IROP IRVAL", " 1 82057 IR001    10"]
    inserted = _insert_section(original, "IRRIGATION AND WATER MANAGEMENT", body)
    assert inserted == [original[0], "*IRRIGATION AND WATER MANAGEMENT\r\n",
                        *(line + "\r\n" for line in body), "\r\n", *original[1:]]
