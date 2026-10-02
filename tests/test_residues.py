"""Residue checks and MR edits through Simulation's public interface."""

from copy import deepcopy
from datetime import date

import pytest

from dssatlab import DSSATCheckError, Simulation
from test_planting_run import TREATMENT, seen
from test_simulation_run import SAMPLE, fake_dssat, inputs, snapshot


HEADER = "@R RDATE  RCOD  RAMT  RESN  RESP  RESK  RINP  RDEP  RMET RENAME"
OLD_ROW = " 7 82057 RE001  1500   0.8   -99   -99   -99    15   -99    -99"
SECTION = "*RESIDUES AND ORGANIC FERTILIZER\n" + HEADER + "\n" + OLD_ROW + "\n! caf\xe9\n\n"
EVENT = dict(date="1982-02-25", material="RE001", amount=1500)
# Spec table: field, column, invalid value, correction. Expectations are literal.
FIELDS = [
    ("date", "RDATE", "1982-02-30", "a valid ISO calendar date as a quoted YYYY-MM-DD string"),
    ("material", "RCOD", "R0001", "two ASCII letters followed by three digits for the DSSAT code"),
    ("amount", "RAMT", 0, "a number above 0"),
    ("n", "RESN", -1, "a number from 0 to 100"),
    ("p", "RESP", 101, "a number from 0 to 100"),
    ("k", "RESK", -1, "a number from 0 to 100"),
    ("incorporation", "RINP", 101, "a number from 0 to 100"),
    ("depth", "RDEP", -1, "a number at least 0"),
    ("method", "RMET", "AP01", "two ASCII letters followed by three digits for the DSSAT code"),
]


@pytest.fixture
def sim(inputs):
    text = SAMPLE.replace(TREATMENT, TREATMENT.replace(" 2 ", " 1 ", 1) + "\n" + TREATMENT)
    inputs.filex.write_bytes(text.replace("*SIMULATION CONTROLS", SECTION + "*SIMULATION CONTROLS").encode("latin-1"))
    return Simulation(inputs.filex, 2, inputs.rows,
                      management={"treatments": {2: {"residues": [dict(EVENT)]}}})


@pytest.mark.parametrize("field,column,value,correction", FIELDS)
def test_rejected_fields_name_value_rule_and_column(sim, capsys, field, column, value, correction):
    sim.management["treatments"][2]["residues"][0][field] = value
    expected = (f"Management data treatment 2, residues, event 1, field '{field}': "
                f"found {value!r}. Supply {correction} (DSSAT {column}).")
    assert sim.check() == [expected]
    report = capsys.readouterr().out
    assert "residues: REJECTED" in report and expected in report


@pytest.mark.parametrize("field,column,_,correction", FIELDS[2:8])
@pytest.mark.parametrize("value", [True, False, "1", None, float("inf"), float("nan"), 10**400])
def test_numbers_reject_bools_and_nonfinite_values(sim, field, column, _, correction, value):
    sim.management["treatments"][2]["residues"][0][field] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert f"field '{field}': found " in problems[0]
    assert f"Supply {correction} (DSSAT {column})." in problems[0]


@pytest.mark.parametrize("field,column,_,correction", FIELDS[3:7])
@pytest.mark.parametrize("value", [0, 100])
def test_percent_boundaries_are_inclusive(sim, field, column, _, correction, value):
    sim.management["treatments"][2]["residues"][0][field] = value
    assert sim.check(verbose=False) == []


def test_depth_can_be_zero_and_material_codes_can_use_lowercase(sim):
    sim.management["treatments"][2]["residues"][0].update(depth=0, material="re001", method="ap001")
    assert sim.check(verbose=False) == []


@pytest.mark.parametrize("field,column,_,correction", FIELDS[:3])
def test_required_fields_rejected_when_missing(sim, field, column, _, correction):
    del sim.management["treatments"][2]["residues"][0][field]
    assert sim.check(verbose=False) == [
        f"Management data treatment 2, residues, event 1, field '{field}': "
        f"found None. Supply {correction} (DSSAT {column})."]


@pytest.mark.parametrize("field", ["material", "method"])
@pytest.mark.parametrize("value", [True, 12345, "RE001 ", "\u00e9E001", "RE\u0660\u0660\u0661"])
def test_codes_use_ascii_letters_and_digits(sim, field, value):
    sim.management["treatments"][2]["residues"][0][field] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert "two ASCII letters followed by three digits" in problems[0]


@pytest.mark.parametrize("value", [date(1982, 2, 25), "1982-2-25", "19820225", True])
def test_dates_must_be_quoted_iso_strings(sim, value):
    sim.management["treatments"][2]["residues"][0]["date"] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1 and "quoted YYYY-MM-DD string (DSSAT RDATE)" in problems[0]


def test_unknown_keys_rejected(sim):
    sim.management["treatments"][2]["residues"][0]["typo"] = 1
    problems = sim.check(verbose=False)
    assert len(problems) == 1 and "residues, event 1: unknown key 'typo'" in problems[0]


@pytest.mark.parametrize("events,correction", [(None, "list of event dicts"), ({}, "list of event dicts"),
                                                ([1], "dict of event fields")])
def test_section_and_event_shapes(sim, events, correction):
    sim.management["treatments"][2]["residues"] = events
    problems = sim.check(verbose=False)
    assert len(problems) == 1 and "residues" in problems[0] and correction in problems[0]


def test_dates_out_of_order_rejected(sim):
    sim.management["treatments"][2]["residues"] = [dict(EVENT, date="1982-02-26"), dict(EVENT)]
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert "event 2, field 'date': found '1982-02-25'. Supply" in problems[0]
    assert "non-descending date order (DSSAT RDATE)" in problems[0]


@pytest.mark.parametrize("value", ["1982-02-23", "1982-02-27"])
def test_dates_outside_weather_rejected(sim, value):
    sim.management["treatments"][2]["residues"][0]["date"] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert "weather range (1982-02-24 to 1982-02-26)" in problems[0]
    assert "(DSSAT RDATE)." in problems[0]


@pytest.mark.parametrize("value", ["1982-02-24", "1982-02-26"])
def test_weather_boundaries_accepted(sim, value):
    sim.management["treatments"][2]["residues"][0]["date"] = value
    assert sim.check(verbose=False) == []


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_new_mr_rows_and_reference_preserve_original(sim, seen, capsys, newline):
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"\n", newline))
    sim.management["treatments"][2]["residues"].append(
        dict(EVENT, date="1982-02-26", n=0.8, p=1, k=2, incorporation=100, depth=15, method="AP001"))
    original, management = sim.filex.read_bytes(), deepcopy(sim.management)
    before = snapshot(sim.filex.parent)
    assert sim.check() == []
    assert "residues: OK" in capsys.readouterr().out
    result = sim.run()
    expected = original.replace(TREATMENT.encode(), (TREATMENT[:55] + "  8" + TREATMENT[58:]).encode())
    expected = expected.replace(OLD_ROW.encode() + newline, OLD_ROW.encode() + newline
        + b" 8 82056 RE001  1500   -99   -99   -99   -99   -99   -99    -99" + newline
        + b" 8 82057 RE001  1500   0.8     1     2   100    15 AP001    -99" + newline)
    assert seen == [expected]
    assert (result.run_dir.parent / sim.filex.name).read_bytes() == expected
    assert snapshot(sim.filex.parent) == before and sim.management == management


def test_same_date_events_written_in_order(sim, seen):
    sim.management["treatments"][2]["residues"].append(dict(EVENT, material="RE002", amount=500))
    assert sim.check(verbose=False) == []
    sim.run()
    assert b" 8 82056 RE001  1500" in seen[0]
    assert seen[0].index(b" 8 82056 RE001") < seen[0].index(b" 8 82056 RE002   500")


@pytest.mark.parametrize("events", [None, []])
def test_omitted_keeps_mr_and_empty_sets_zero(sim, seen, capsys, events):
    original = sim.filex.read_bytes().replace(TREATMENT.encode(), (TREATMENT[:55] + "  7" + TREATMENT[58:]).encode())
    sim.filex.write_bytes(original)
    sim.management = {"treatments": {2: {} if events is None else {"residues": events}}}
    assert sim.check() == []
    assert ("residues: OK (omitted" if events is None else "residues: OK (empty list") in capsys.readouterr().out
    sim.run()
    expected = original if events is None else original.replace(
        (TREATMENT[:55] + "  7" + TREATMENT[58:]).encode(), TREATMENT.encode())
    assert seen == [expected] and sim.filex.read_bytes() == original


def test_missing_section_inserted(sim, seen):
    original = sim.filex.read_bytes().replace(SECTION.encode("latin-1"), b"")
    sim.filex.write_bytes(original)
    sim.run()
    assert seen[0].count(b"*RESIDUES AND ORGANIC FERTILIZER") == 1
    assert seen[0].index(HEADER.encode()) < seen[0].index(b"*SIMULATION CONTROLS")
    assert b" 1 82056 RE001  1500   -99   -99   -99   -99   -99   -99    -99" in seen[0]
    assert (TREATMENT[:55] + "  1" + TREATMENT[58:]).encode() in seen[0]
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("column", ["MR", "R", *[row[1] for row in FIELDS], "RENAME"])
def test_missing_writer_columns_checked_before_run(sim, seen, column):
    token = " MR " if column == "MR" else "@R " if column == "R" else column
    sim.filex.write_bytes(sim.filex.read_bytes().replace(token.encode(), b"?" * len(token)))
    before = snapshot(sim.filex.parent)
    assert any(column in p and "Supply" in p for p in sim.check(verbose=False))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == [] and snapshot(sim.filex.parent) == before


@pytest.mark.parametrize("field,value", [("amount", 1234567), ("n", 0.1234567)])
def test_column_overflow_is_a_prewrite_problem(sim, seen, field, value):
    sim.management["treatments"][2]["residues"][0][field] = value
    assert any("does not fit" in p for p in sim.check(verbose=False))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == []
