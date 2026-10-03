"""Tillage and harvest mirror the residue contract through the public API."""

from copy import deepcopy
from datetime import date

import pytest

from dssatlab import DSSATCheckError
from test_controls_options import option_sim
from test_management_file import sim_inputs
from test_planting_run import TREATMENT, seen
from test_residues import EVENT, HEADER, OLD_ROW, SECTION, sim
from test_simulation_run import fake_dssat, inputs, snapshot


CASES = {
    "tillage": dict(name="TILLAGE AND ROTATIONS", factor="MT", offset=61,
        header="@T TDATE TIMPL  TDEP TNAME", old=" 7 82057 TI005    22   -99",
        event=dict(date="1982-02-25", implement="TI005", depth=20),
        row=" 8 82056 TI005    20   -99",
        full=dict(implement="ti003", depth=0), full_row=" 8 82057 ti003     0   -99"),
    "harvest": dict(name="HARVEST DETAILS", factor="MH", offset=67,
        header="@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME",
        old=" 7 82057 GS000   -99   -99   100     0   -99",
        event=dict(date="1982-02-25"), row=" 8 82056   -99   -99   -99   -99   -99   -99",
        full=dict(stage="gs003", component="IBHCS", size="IBHCS", product_percent=100,
                  byproduct_percent=0), full_row=" 8 82057 gs003 IBHCS IBHCS   100     0   -99"),
}
COMMON_CASES = {"residues": dict(name="RESIDUES AND ORGANIC FERTILIZER", offset=55,
    header=HEADER, old=OLD_ROW, event=EVENT,
    row=" 8 82056 RE001  1500   -99   -99   -99   -99   -99   -99    -99"), **CASES}
DATE_RULE = "a valid ISO calendar date as a quoted YYYY-MM-DD string"
CODE_RULE = "two ASCII letters followed by three digits for the DSSAT code"
TEXT_RULE = "1-5 printable ASCII characters without spaces"
# Literal spec expectations, independent of the production field table.
FIELDS = [
    ("tillage", "date", "TDATE", "1982-02-30", DATE_RULE, True, False),
    ("tillage", "implement", "TIMPL", "T0001", CODE_RULE, True, False),
    ("tillage", "depth", "TDEP", -1, "a number at least 0", True, True),
    ("harvest", "date", "HDATE", "1982-02-30", DATE_RULE, True, False),
    ("harvest", "stage", "HSTG", "G0003", CODE_RULE, False, False),
    ("harvest", "component", "HCOM", "A B", TEXT_RULE, False, False),
    ("harvest", "size", "HSIZE", "123456", TEXT_RULE, False, False),
    ("harvest", "product_percent", "HPC", -1, "a number from 0 to 100", False, True),
    ("harvest", "byproduct_percent", "HBPC", 101, "a number from 0 to 100", False, True),
]


def set_operation(sim, section):
    case = COMMON_CASES[section]
    block = f"*{case['name']}\n{case['header']}\n{case['old']}\n! caf\xe9\n\n"
    sim.filex.write_bytes(sim.filex.read_bytes().replace(SECTION.encode("latin-1"), block.encode("latin-1")))
    sim.management = {"treatments": {2: {section: [dict(case["event"])]}}}
    return sim


@pytest.fixture(params=CASES)
def section(request):
    return request.param


@pytest.fixture
def operation_sim(sim, section):
    return set_operation(sim, section)


@pytest.mark.parametrize("section,field,column,value,correction,required,numeric", FIELDS)
def test_field_rules(sim, capsys, section, field, column, value, correction, required, numeric):
    set_operation(sim, section).management["treatments"][2][section][0][field] = value
    expected = (f"Management data treatment 2, {section}, event 1, field '{field}': "
                f"found {value!r}. Supply {correction} (DSSAT {column}).")
    assert sim.check() == [expected]
    report = capsys.readouterr().out
    assert f"{section}: REJECTED" in report and expected in report


@pytest.mark.parametrize("section,field,column,_,correction,required,numeric", [r for r in FIELDS if r[5]])
def test_required_fields(sim, section, field, column, _, correction, required, numeric):
    del set_operation(sim, section).management["treatments"][2][section][0][field]
    assert sim.check(verbose=False) == [
        f"Management data treatment 2, {section}, event 1, field '{field}': "
        f"found None. Supply {correction} (DSSAT {column})."]


@pytest.mark.parametrize("section,field,column,_,correction,required,numeric", [r for r in FIELDS if r[6]])
@pytest.mark.parametrize("value", [True, False, "1", None, float("inf"), float("nan"), 10**400])
def test_numbers_reject_bools_and_nonfinite_values(sim, section, field, column, _, correction, required, numeric, value):
    set_operation(sim, section).management["treatments"][2][section][0][field] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1 and f"field '{field}': found " in problems[0]
    assert f"Supply {correction} (DSSAT {column})." in problems[0]


@pytest.mark.parametrize("field,column", [("component", "HCOM"), ("size", "HSIZE")])
@pytest.mark.parametrize("value", ["", "123456", " A", "A B", "A\tB", "\n", "\x7f", "\xe9", True, 123, None])
def test_harvest_text_rule(sim, field, column, value):
    set_operation(sim, "harvest").management["treatments"][2]["harvest"][0][field] = value
    assert sim.check(verbose=False) == [
        f"Management data treatment 2, harvest, event 1, field '{field}': "
        f"found {value!r}. Supply {TEXT_RULE} (DSSAT {column})."]


@pytest.mark.parametrize("value", ["!", "IBHCS", "-99", "~!0AZ"])
def test_harvest_printable_ascii_boundaries_written(sim, seen, value):
    set_operation(sim, "harvest").management["treatments"][2]["harvest"][0].update(component=value, size=value)
    assert sim.check(verbose=False) == []
    sim.run()
    row = next(line for line in seen[0].splitlines() if line.startswith(b" 8 82056"))
    assert row[14:20].strip() == row[20:26].strip() == value.encode("ascii")


@pytest.mark.parametrize("section,field", [("tillage", "implement"), ("harvest", "stage")])
@pytest.mark.parametrize("value", [True, 12345, "TI005 ", "\xe9I005", "TI\u0660\u0660\u0665"])
def test_code_rules_are_ascii(sim, section, field, value):
    set_operation(sim, section).management["treatments"][2][section][0][field] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1 and CODE_RULE in problems[0]


@pytest.mark.parametrize("value", [date(1982, 2, 25), "1982-2-25", "19820225", True])
def test_date_strings(operation_sim, section, value):
    operation_sim.management["treatments"][2][section][0]["date"] = value
    problems = operation_sim.check(verbose=False)
    assert len(problems) == 1 and DATE_RULE in problems[0]


@pytest.mark.parametrize("field", ["product_percent", "byproduct_percent"])
@pytest.mark.parametrize("value", [0, 100])
def test_percent_boundaries(sim, field, value):
    set_operation(sim, "harvest").management["treatments"][2]["harvest"][0][field] = value
    assert sim.check(verbose=False) == []


def test_unknown_key(operation_sim, section):
    operation_sim.management["treatments"][2][section][0]["typo"] = 1
    problems = operation_sim.check(verbose=False)
    assert len(problems) == 1 and f"{section}, event 1: unknown key 'typo'" in problems[0]


@pytest.mark.parametrize("events,correction", [(None, "list of event dicts"), ({}, "list of event dicts"),
                                                ([1], "dict of event fields")])
def test_shapes(operation_sim, section, events, correction):
    operation_sim.management["treatments"][2][section] = events
    problems = operation_sim.check(verbose=False)
    assert len(problems) == 1 and section in problems[0] and correction in problems[0]


def test_out_of_order_dates(operation_sim, section):
    operation_sim.management["treatments"][2][section] = [dict(CASES[section]["event"], date="1982-02-26"),
                                                         dict(CASES[section]["event"])]
    problems = operation_sim.check(verbose=False)
    assert len(problems) == 1 and "event 2, field 'date'" in problems[0]
    assert f"non-descending date order (DSSAT {section[0].upper()}DATE)" in problems[0]


@pytest.mark.parametrize("value", ["1982-02-23", "1982-02-27"])
def test_weather_range(operation_sim, section, value):
    operation_sim.management["treatments"][2][section][0]["date"] = value
    problems = operation_sim.check(verbose=False)
    assert len(problems) == 1 and "weather range (1982-02-24 to 1982-02-26)" in problems[0]
    assert f"(DSSAT {section[0].upper()}DATE)." in problems[0]


@pytest.mark.parametrize("value", ["1982-02-24", "1982-02-26"])
def test_weather_boundaries(operation_sim, section, value):
    operation_sim.management["treatments"][2][section][0]["date"] = value
    assert operation_sim.check(verbose=False) == []


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_new_levels_preserve_original(operation_sim, section, seen, capsys, newline):
    sim, case = operation_sim, CASES[section]
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"\n", newline))
    sim.management["treatments"][2][section].append(dict(case["event"], date="1982-02-26", **case["full"]))
    original, management = sim.filex.read_bytes(), deepcopy(sim.management)
    before = snapshot(sim.filex.parent)
    assert sim.check() == []
    assert f"{section}: OK" in capsys.readouterr().out
    result = sim.run()
    offset = case["offset"]
    expected = original.replace(TREATMENT.encode(), (TREATMENT[:offset] + "  8" + TREATMENT[offset+3:]).encode())
    old_row = case["old"].encode() + newline
    expected = expected.replace(old_row, old_row + case["row"].encode() + newline + case["full_row"].encode() + newline)
    assert seen == [expected]
    assert (result.run_dir.parent / sim.filex.name).read_bytes() == expected
    assert snapshot(sim.filex.parent) == before and sim.management == management


def test_same_date_events_written_in_order(operation_sim, section, seen):
    sim, case = operation_sim, CASES[section]
    sim.management["treatments"][2][section].append(dict(case["event"], **case["full"]))
    assert sim.check(verbose=False) == []
    sim.run()
    assert seen[0].index(case["row"].encode()) < seen[0].index(case["full_row"].replace("82057", "82056").encode())


@pytest.mark.parametrize("events", [None, []])
@pytest.mark.parametrize("section", COMMON_CASES)
def test_omitted_keeps_level_and_empty_sets_zero(sim, section, seen, capsys, events):
    set_operation(sim, section)
    case = COMMON_CASES[section]
    offset = case["offset"]
    old_treatment = (TREATMENT[:offset] + "  7" + TREATMENT[offset+3:]).encode()
    original = sim.filex.read_bytes().replace(TREATMENT.encode(), old_treatment)
    sim.filex.write_bytes(original)
    sim.management = {"treatments": {2: {} if events is None else {section: events}}}
    assert sim.check() == []
    status = "omitted" if events is None else "empty list"
    assert f"{section}: OK ({status}" in capsys.readouterr().out
    sim.run()
    assert seen == [original if events is None else original.replace(old_treatment, TREATMENT.encode())]
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("section", COMMON_CASES)
def test_missing_section_inserted(sim, section, seen):
    set_operation(sim, section)
    case = COMMON_CASES[section]
    block = f"*{case['name']}\n{case['header']}\n{case['old']}\n! caf\xe9\n\n"
    original = sim.filex.read_bytes().replace(block.encode("latin-1"), b"")
    sim.filex.write_bytes(original)
    sim.run()
    assert seen[0].count(("*" + case["name"]).encode()) == 1
    assert seen[0].index(case["header"].encode()) < seen[0].index(b"*SIMULATION CONTROLS")
    assert case["row"].replace(" 8 ", " 1 ", 1).encode() in seen[0]
    offset = case["offset"]
    assert (TREATMENT[:offset] + "  1" + TREATMENT[offset+3:]).encode() in seen[0]
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("section,column", [(s, c) for s, case in CASES.items()
                                          for c in [case["factor"], *case["header"].split()]])
def test_missing_writer_columns_prevent_run(sim, seen, section, column):
    set_operation(sim, section)
    token = column if column.startswith("@") else " " + column + " " if column.startswith("M") else column
    replacement = token.encode().replace(column.encode(), b"?" * len(column))
    sim.filex.write_bytes(sim.filex.read_bytes().replace(token.encode(), replacement))
    before = snapshot(sim.filex.parent)
    assert any(column.lstrip("@") in p and "Supply" in p for p in sim.check(verbose=False))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == [] and snapshot(sim.filex.parent) == before


@pytest.mark.parametrize("section,field,value", [("tillage", "depth", 1234567), ("harvest", "product_percent", 0.1234567)])
def test_column_overflow_prevents_run(sim, seen, section, field, value):
    set_operation(sim, section).management["treatments"][2][section][0][field] = value
    assert any("does not fit" in p for p in sim.check(verbose=False))
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert seen == []


@pytest.mark.parametrize("filex_code,override", [
    ("D", None), ("A", None), ("R", None), ("M", None),
    ("G", None), ("X", None), ("-99", None),
    ("M", "D"), ("M", "A"), ("D", "R"), ("A", "M"),
])
@pytest.mark.parametrize("empty", [False, True])
def test_harvest_uses_effective_management_code(option_sim, capsys, filex_code, override, empty):
    sim = option_sim
    text = sim.filex.read_text(encoding="latin-1").replace(
        " 1 MA              R     R     R     N     M",
        f" 1 MA              R     R     R     N{filex_code:>6}")
    text += "@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS\n 7 MA              R     R     R     N     D\n"
    sim.filex.write_text(text, encoding="latin-1")
    entry = sim.management["treatments"][1]
    entry["harvest"] = [] if empty else [dict(CASES["harvest"]["event"])] * 2
    if override is not None:
        entry["controls"] = {"harvest_management": override}
    original, management = sim.filex.read_bytes(), deepcopy(sim.management)
    code = override or filex_code
    expected = [] if empty or code in ("R", "M") else [
        'Management data treatment 1, harvest: harvest events need the harvest management '
        f'"R" or "M", but it is "{code}". Set controls harvest_management to "R" or "M", '
        'or remove the harvest events.']
    assert sim.check() == expected
    report = capsys.readouterr().out
    assert f"harvest: {'REJECTED' if expected else 'OK'}" in report
    assert all(problem in report for problem in expected)
    assert sim.filex.read_bytes() == original and sim.management == management


def test_tillage_has_no_management_code_check(option_sim):
    option_sim.management["treatments"][1]["tillage"] = [dict(CASES["tillage"]["event"])]
    assert option_sim.check(verbose=False) == []


@pytest.mark.parametrize('section,event,column,field,fix', [
    ('residues', dict(date='1982-02-25', material='RE001', amount=1500), 'RESID', 'residue', '"R"'),
    ('harvest', dict(date='1982-02-25'), 'HARVS', 'harvest_management', '"R" or "M"'),
])
@pytest.mark.parametrize('empty', [False, True])
def test_missing_management_code(option_sim, section, event, column, field, fix, empty):
    sim = option_sim
    sim.filex.write_text(sim.filex.read_text().replace(' 1 MA              R     R     R     N     M', ''))
    sim.management['treatments'][1][section] = [] if empty else [event]
    kind = 'residue' if section == 'residues' else 'harvest'
    dates = ' (reported dates)' if section == 'residues' else ''
    expected = (f'Management data treatment 1, {section}: {kind} events need the {kind} '
                f'management {fix}{dates}, but it could not be read (checked controls {field} '
                f'and the FileX SM level column {column}). Set controls {field} to {fix}, '
                f'or remove the {section} events.')
    assert sim.check(False) == ([] if empty else [expected])
