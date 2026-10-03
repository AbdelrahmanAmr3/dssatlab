"""Fertilizer edits observed at the fake DSSAT subprocess boundary."""

from copy import deepcopy

import pytest

from dssatlab import DSSATCheckError, Simulation
from test_planting_run import TREATMENT, planting_sim, seen
from test_simulation_run import SAMPLE, fake_dssat, inputs, snapshot


HEADER = "@F FDATE  FMCD  FACD  FDEP  FAMN  FAMP  FAMK  FAMC  FAMO  FOCD FERNAME"
OLD_ROW = " 7 82057 FE001 AP001    10    27     0     0     0     0   -99 -99"
SECTION = "*FERTILIZERS (INORGANIC)\n" + HEADER + "\n" + OLD_ROW + "\n! caf\xe9\n\n"


@pytest.fixture
def fertilizer_sim(inputs):
    text = SAMPLE.replace(TREATMENT, TREATMENT.replace(" 2 ", " 1 ", 1) + "\n" + TREATMENT)
    inputs.filex.write_bytes(text.replace("*SIMULATION CONTROLS", SECTION + "*SIMULATION CONTROLS").encode("latin-1"))
    events = [dict(date="1982-02-25", material="FE001", application="AP001", depth=10, n=30),
              dict(date="1982-02-26", material="FE005", application="AP002", depth=5, n=12.5, p=20, k=3)]
    return Simulation(inputs.filex, "02", inputs.rows,
                      management={"treatments": {"02": {"fertilizer": events}}})


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_new_fertilizer_level_changes_only_selected_treatment(fertilizer_sim, seen, newline):
    sim = fertilizer_sim
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"\n", newline))
    before, management = snapshot(sim.filex.parent), deepcopy(sim.management)
    original = sim.filex.read_bytes()
    result = sim.run()
    expected = original.replace(TREATMENT.encode(), (TREATMENT[:52] + "  8" + TREATMENT[55:]).encode())
    expected = expected.replace(OLD_ROW.encode() + newline, OLD_ROW.encode() + newline
        + b" 8 82056 FE001 AP001    10    30     0     0     0     0   -99     -99" + newline
        + b" 8 82057 FE005 AP002     5  12.5    20     3     0     0   -99     -99" + newline)
    assert seen == [expected]
    assert (result.run_dir.parent / sim.filex.name).read_bytes() == expected
    assert snapshot(sim.filex.parent) == before
    assert sim.management == management


@pytest.mark.parametrize("events", [None, []])
def test_fertilizer_omitted_or_empty(fertilizer_sim, seen, events):
    sim = fertilizer_sim
    sim.management = {"treatments": {2: {} if events is None else {"fertilizer": events}}}
    original = sim.filex.read_bytes()
    sim.run()
    expected = original if events is None else original.replace(
        TREATMENT.encode(), (TREATMENT[:52] + "  0" + TREATMENT[55:]).encode())
    assert seen == [expected]
    assert sim.filex.read_bytes() == original


def test_missing_fertilizer_created_before_controls(fertilizer_sim, seen):
    sim = fertilizer_sim
    original = sim.filex.read_bytes().replace(SECTION.encode("latin-1"), b"")
    sim.filex.write_bytes(original)
    sim.run()
    assert seen[0].index(b"*FERTILIZERS") < seen[0].index(HEADER.encode()) < seen[0].index(b"*SIMULATION CONTROLS")
    assert b" 1 82056 FE001 AP001    10    30     0     0     0     0   -99     -99" in seen[0]
    assert sim.filex.read_bytes() == original


def test_short_fertilizer_title_uses_existing_section(fertilizer_sim, seen):
    sim = fertilizer_sim
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"*FERTILIZERS (INORGANIC)", b"*FERTILIZERS"))
    sim.run()
    assert seen[0].count(b"*FERTILIZERS") == 1
    assert b" 8 82056 FE001" in seen[0]


def test_repeated_fertilizer_headers_use_highest_earlier_level(fertilizer_sim, seen):
    sim = fertilizer_sim
    extra = HEADER + "\n" + OLD_ROW.replace(" 7 ", " 3 ", 1) + "\n"
    original = sim.filex.read_bytes().replace(b"*SIMULATION CONTROLS", extra.encode() + b"*SIMULATION CONTROLS")
    sim.filex.write_bytes(original)
    sim.run()
    lines = seen[0].splitlines(keepends=True)
    added = [line for line in lines if line.startswith(b" 8 ")]
    assert len(added) == 2
    assert lines.index(added[0]) > next(i for i, line in enumerate(lines) if line.startswith(b" 3 82057"))
    restored = seen[0]
    for line in added:
        restored = restored.replace(line, b"")
    assert restored.replace((TREATMENT[:52] + "  8" + TREATMENT[55:]).encode(), TREATMENT.encode()) == original


@pytest.mark.parametrize("section", ["irrigation", "fertilizer"])
def test_event_dates_keep_leading_zero_year(fertilizer_sim, seen, section):
    sim = fertilizer_sim
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"82056", b"02072"))
    sim.weather = [dict(sim.weather[0], date="2002-03-13")]
    event = (dict(date="2002-03-13", amount=20, method="IR001") if section == "irrigation"
             else dict(date="2002-03-13", material="FE001", application="AP001", depth=0, n=50))
    sim.management = {"treatments": {2: {section: [event]}}}
    sim.run()
    assert (b" 1 02072 IR001" if section == "irrigation" else b" 8 02072 FE001") in seen[0]


@pytest.mark.parametrize("column", ["MF", "F", "FDATE", "FMCD", "FACD", "FDEP", "FAMN", "FAMP", "FAMK", "FAMC", "FAMO", "FOCD", "FERNAME"])
def test_fertilizer_missing_columns_fail_before_writing(fertilizer_sim, seen, column):
    sim = fertilizer_sim
    token = " MF " if column == "MF" else "@F " if column == "F" else column
    sim.filex.write_bytes(sim.filex.read_bytes().replace(token.encode(), b"?" * len(token)))
    before, listing = snapshot(sim.filex.parent), list(sim.filex.parent.iterdir())
    problems = sim.check()
    section = "TREATMENTS" if column == "MF" else "FERTILIZERS"
    assert any(section in p and column in p and "Supply" in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == []
    assert snapshot(sim.filex.parent) == before
    assert list(sim.filex.parent.iterdir()) == listing


@pytest.mark.parametrize("section", ["irrigation", "fertilizer"])
def test_other_treatments_checked_but_not_written(fertilizer_sim, seen, section):
    sim = fertilizer_sim
    events = sim.management["treatments"]["02"]["fertilizer"] if section == "fertilizer" else [dict(date="1982-02-25", amount=20, method="IR001")]
    sim.management = {"treatments": {1: {section: events}}}
    original = sim.filex.read_bytes()
    sim.run()
    assert seen == [original]
    events[0]["n" if section == "fertilizer" else "amount"] = 1234567
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert len(seen) == 1


def test_all_three_sections_together(planting_sim, seen):
    sim = planting_sim
    entry = sim.management["treatments"]["02"]
    entry.update(irrigation=[dict(date="1982-02-25", amount=20, method="IR001")],
                 fertilizer=[dict(date="1982-02-25", material="FE001", application="AP001", depth=0, n=50)])
    original = sim.filex.read_bytes()
    sim.run()
    assert (TREATMENT[:46] + "  8  1  1" + TREATMENT[55:]).encode() in seen[0]
    assert b" 1 82056 IR001    20" in seen[0]
    assert b" 1 82056 FE001 AP001     0    50     0     0     0     0   -99     -99" in seen[0]
    assert seen[0].index(b"*IRRIGATION") < seen[0].index(b"*FERTILIZERS") < seen[0].index(b"*SIMULATION CONTROLS")
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("failure", ["header", "amount"])
def test_fertilizer_unwritable_layout_checked(fertilizer_sim, seen, failure):
    sim = fertilizer_sim
    if failure == "header":
        sim.filex.write_bytes(sim.filex.read_bytes().replace(HEADER.encode(), b"! no header"))
    else:
        sim.management["treatments"]["02"]["fertilizer"][0]["p"] = 1234567
    assert sim.check()
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == []
