"""Irrigation edits observed at the fake DSSAT subprocess boundary."""

from copy import deepcopy

import pytest

from dssatlab import DSSATCheckError, Simulation
from test_planting_run import TREATMENT, seen
from test_simulation_run import SAMPLE, fake_dssat, inputs, snapshot


HEADER = "@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME"
EVENT_HEADER = "@I IDATE  IROP IRVAL"
CONTROL = " 7     1   -99   -99   -99   -99   -99   -99    -99"
EVENT = " 9 82057 IR001    10"
SECTION = ("*IRRIGATION AND WATER MANAGEMENT\n" + HEADER + "\n" + CONTROL
           + "\n! keep caf\xe9\n" + EVENT_HEADER + "\n" + EVENT + "\n\n")


@pytest.fixture
def irrigation_sim(inputs):
    text = SAMPLE.replace(TREATMENT, TREATMENT.replace(" 2 ", " 1 ", 1) + "\n" + TREATMENT)
    inputs.filex.write_bytes(text.replace("*SIMULATION CONTROLS", SECTION + "*SIMULATION CONTROLS").encode("latin-1"))
    events = [dict(date="1982-02-25", amount=20, method="IR001"),
              dict(date="1982-02-26", amount=12.5, method="IR003")]
    return Simulation(inputs.filex, "02", inputs.rows,
                      management={"treatments": {"02": {"irrigation": events}}})


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_irrigation_goes_into_correct_blocks_and_only_selected_treatment(irrigation_sim, seen, newline):
    sim = irrigation_sim
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"\n", newline))
    original = sim.filex.read_bytes()
    before, management = snapshot(sim.filex.parent), deepcopy(sim.management)
    result = sim.run()
    expected = original.replace(TREATMENT.encode(), (TREATMENT[:49] + " 10" + TREATMENT[52:]).encode())
    expected = expected.replace(EVENT.encode() + newline, EVENT.encode() + newline
                                + HEADER.encode() + newline
                                + b"10     1   -99   -99   -99   -99   -99   -99    -99" + newline
                                + EVENT_HEADER.encode() + newline
                                + b"10 82056 IR001    20" + newline + b"10 82057 IR003  12.5" + newline)
    assert seen == [expected]
    assert (result.run_dir.parent / sim.filex.name).read_bytes() == expected
    assert snapshot(sim.filex.parent) == before
    assert sim.management == management


@pytest.mark.parametrize("events", [None, []])
def test_omitted_keeps_level_and_empty_repoints_to_zero(irrigation_sim, seen, events):
    sim = irrigation_sim
    sim.management = {"treatments": {2: {} if events is None else {"irrigation": events}}}
    original = sim.filex.read_bytes()
    sim.run()
    expected = original if events is None else original.replace(
        TREATMENT.encode(), (TREATMENT[:49] + "  0" + TREATMENT[52:]).encode())
    assert seen == [expected]
    assert sim.filex.read_bytes() == original


def test_missing_irrigation_created_before_controls(irrigation_sim, seen):
    sim = irrigation_sim
    original = sim.filex.read_bytes().replace(SECTION.encode("latin-1"), b"")
    sim.filex.write_bytes(original)
    sim.run()
    written = seen[0]
    assert written.index(b"*IRRIGATION") < written.index(HEADER.encode()) < written.index(EVENT_HEADER.encode()) < written.index(b"*SIMULATION CONTROLS")
    assert b" 1 82056 IR001    20\n 1 82057 IR003  12.5" in written
    assert written[written.index(b"*SIMULATION CONTROLS"):] == original[original.index(b"*SIMULATION CONTROLS"):]
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("column", ["MI", "I", "EFIR", "IDEP", "ITHR", "IEPT", "IOFF", "IAME", "IAMT", "IRNAME", "IDATE", "IROP", "IRVAL"])
def test_irrigation_missing_columns_fail_before_writing(irrigation_sim, seen, column):
    sim = irrigation_sim
    token = " MI " if column == "MI" else "@I " if column == "I" else column
    sim.filex.write_bytes(sim.filex.read_bytes().replace(token.encode(), b"?" * len(token)))
    before, listing = snapshot(sim.filex.parent), list(sim.filex.parent.iterdir())
    problems = sim.check()
    section = "TREATMENTS" if column == "MI" else "IRRIGATION"
    assert any(section in p and column in p and "Supply" in p for p in problems)
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == []
    assert snapshot(sim.filex.parent) == before
    assert list(sim.filex.parent.iterdir()) == listing


def test_repeated_blocks_use_highest_level_across_both_blocks(irrigation_sim, seen):
    sim = irrigation_sim
    extra = HEADER + "\n" + CONTROL.replace(" 7 ", " 3 ", 1) + "\n" + EVENT_HEADER + "\n" + EVENT.replace(" 9 ", " 3 ", 1) + "\n"
    original = sim.filex.read_bytes().replace(b"*SIMULATION CONTROLS", extra.encode() + b"*SIMULATION CONTROLS")
    sim.filex.write_bytes(original)
    sim.run()
    added = [line for line in seen[0].splitlines(keepends=True) if line.startswith(b"10 ")]
    assert len(added) == 3
    restored = seen[0]
    new_block = HEADER.encode() + b"\n" + added[0] + EVENT_HEADER.encode() + b"\n" + b"".join(added[1:])
    restored = restored.replace(new_block, b"")
    assert restored.replace((TREATMENT[:49] + " 10" + TREATMENT[52:]).encode(), TREATMENT.encode()) == original


@pytest.mark.parametrize("failure", ["control_header", "event_header", "amount"])
def test_irrigation_unwritable_layout_checked(irrigation_sim, seen, failure):
    sim = irrigation_sim
    if failure.endswith("header"):
        header = HEADER if failure == "control_header" else EVENT_HEADER
        sim.filex.write_bytes(sim.filex.read_bytes().replace(header.encode(), b"! no header"))
    else:
        sim.management["treatments"]["02"]["irrigation"][0]["amount"] = 1234567
    assert sim.check()
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == []


def test_new_irrigation_has_its_own_header_pair(irrigation_sim, seen):
    """DSSAT consumes all events following the selected control block."""
    irrigation_sim.run()
    lines = seen[0].decode("latin-1").splitlines()
    control = next(i for i, line in enumerate(lines) if line.startswith("10     1"))
    assert lines[control - 1] == HEADER
    assert lines[control + 1] == EVENT_HEADER
    assert lines[control + 2:control + 4] == ["10 82056 IR001    20", "10 82057 IR003  12.5"]
