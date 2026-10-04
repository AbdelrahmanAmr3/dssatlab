"""Environment checks and IPENV columns through Simulation."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, write_management_template
from dssatlab.filex import _section_row
from test_filex_template import data, rows
from test_initial_conditions import FIXTURE
from test_rotation_data import sim as rotation_sim
from test_rotation_template import rotation
from test_simulation_run import fake_dssat, inputs, snapshot
from test_simulation_template import installed


HEADER = "@E ODATE EDAY  ERAD  EMAX  EMIN  ERAIN ECO2  EDEW  EWIND ENVNAME"
FIELDS = ("day_length", "srad", "tmax", "tmin", "rain", "co2", "dew_point", "wind")
KINDS = ("add", "subtract", "multiply", "replace")


@pytest.fixture
def sim(inputs):
    inputs.filex.write_bytes(FIXTURE.read_bytes())
    return Simulation(inputs.filex, 2, inputs.rows, management={"treatments": {2: {
        "environment": [dict(date="1982-02-25", srad={"multiply": 0.5})]}}})


def events(sim):
    return sim.management["treatments"][2]["environment"]


def copied(sim, fake_dssat):
    return (Path(fake_dssat.calls[0][1]) / sim.filex.name).read_bytes()


def section(text):
    return text.split("*ENVIRONMENT MODIFICATIONS", 1)[1].split("\n*", 1)[0]


def assert_problem(sim, event, variable, correction):
    assert any(f"environment, event {event}" in p and f"'{variable}'" in p
               and correction in p for p in sim.check(False))


@pytest.mark.parametrize("value", [None, {}, "off", True])
def test_environment_requires_a_list(sim, value):
    sim.management["treatments"][2]["environment"] = value
    assert any("environment" in p and "list of event dicts" in p for p in sim.check(False))


@pytest.mark.parametrize("value", [None, 1, []])
def test_environment_events_require_dicts(sim, value):
    events(sim)[0] = value
    assert any("environment, event 1" in p and "expected a dict" in p for p in sim.check(False))


def test_environment_date_is_required(sim):
    del events(sim)[0]["date"]
    assert_problem(sim, 1, "date", "Add 'date'")


@pytest.mark.parametrize("value", ["bad", "1982-02-30", "19820225", date(1982, 2, 25)])
def test_environment_date_requires_quoted_iso_calendar_date(sim, value):
    events(sim)[0]["date"] = value
    assert_problem(sim, 1, "date", "valid ISO calendar date as a quoted YYYY-MM-DD string")


@pytest.mark.parametrize("day", ["1982-02-25", "1982-02-24"])
def test_environment_dates_are_strictly_ascending(sim, day):
    events(sim).append(dict(date=day, tmax={"add": 2}))
    assert_problem(sim, 2, "date", "strictly ascending")


def test_environment_event_needs_at_least_one_variable(sim):
    events(sim)[0] = dict(date="1982-02-25")
    assert any("environment, event 1" in p and "at least one variable" in p
               and "srad" in p for p in sim.check(False))


@pytest.mark.parametrize("key", ["srda", "kind", "ENVNAME"])
def test_environment_unknown_variables_and_keys_are_rejected(sim, key):
    events(sim)[0][key] = {"add": 1}
    assert_problem(sim, 1, key, "unknown key")


@pytest.mark.parametrize("value", [1, None, [], {}, {"add": 1, "multiply": 2}])
def test_environment_change_requires_exactly_one_kind(sim, value):
    events(sim)[0]["srad"] = value
    assert_problem(sim, 1, "srad", "exactly one")


@pytest.mark.parametrize("kind", ["ADD", "offset", "value"])
def test_environment_unknown_kinds_are_rejected(sim, kind):
    events(sim)[0]["srad"] = {kind: 1}
    assert_problem(sim, 1, "srad", f"unknown key '{kind}'")


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True, "1"])
def test_environment_values_are_finite_numbers(sim, field, value):
    events(sim)[0] = dict(date="1982-02-25", **{field: {"add": value}})
    assert_problem(sim, 1, field, "finite number")


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [-0.01, 9.996, 10])
def test_environment_multiply_range(sim, field, value):
    events(sim)[0] = dict(date="1982-02-25", **{field: {"multiply": value}})
    assert_problem(sim, 1, field, "0 to 9.99")


@pytest.mark.parametrize("field", [f for f in FIELDS if f != "co2"])
@pytest.mark.parametrize("kind", ["add", "subtract", "replace"])
@pytest.mark.parametrize("value", [-9.91, 99.91])
def test_environment_other_value_ranges_include_replace_temperatures(sim, field, kind, value):
    events(sim)[0] = dict(date="1982-02-25", **{field: {kind: value}})
    assert_problem(sim, 1, field, "-9.9 to 99.9")


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("value", [-90, 10000, 0.5])
def test_environment_co2_is_whole_and_in_range(sim, kind, value):
    events(sim)[0] = dict(date="1982-02-25", co2={kind: value})
    assert_problem(sim, 1, "co2", "whole number from -89 to 9999")


@pytest.mark.parametrize("field", FIELDS)
def test_environment_values_must_fit_four_character_cell(sim, field):
    kind, value = ("replace", 99.123) if field != "co2" else ("add", 10 ** 400)
    events(sim)[0] = dict(date="1982-02-25", **{field: {kind: value}})
    assert_problem(sim, 1, field, "4-character" if field != "co2" else "finite number")


@pytest.mark.parametrize("kind,value", [("multiply", 0), ("multiply", 9.99),
                                      ("add", -9.9), ("subtract", 99.9), ("replace", 99.9)])
def test_environment_value_range_endpoints_are_accepted(sim, kind, value):
    events(sim)[0] = dict(date="1982-02-25", **{field: {kind: value}
                        for field in FIELDS if field != "co2"})
    assert sim.check(False) == []


@pytest.mark.parametrize("kind,value", [("add", -89), ("replace", 9999.0),
                                      ("multiply", 0), ("multiply", 9)])
def test_environment_co2_whole_number_endpoints_are_accepted(sim, kind, value):
    events(sim)[0] = dict(date="1982-02-25", co2={kind: value})
    assert sim.check(False) == []


def test_environment_event_dates_need_no_weather_coverage(sim, fake_dssat):
    events(sim)[0]["date"] = "1981-01-01"
    events(sim).append(dict(date="1983-01-01", tmax={"add": 2}))
    assert sim.check(False) == []
    sim.run()
    text = section(copied(sim, fake_dssat).decode("latin-1"))
    assert " 1 81001" in text and " 1 83001" in text


@pytest.mark.parametrize("highest", [0, 9, 98])
def test_environment_ipenv_slices_levels_and_combined_modifier_boundaries(sim, fake_dssat, highest):
    if highest:
        text = sim.filex.read_text(encoding="latin-1")
        old = f"*ENVIRONMENT MODIFICATIONS\n{HEADER}\n{highest:2d} 82054" + " A   0" * 8 + "\n\n"
        sim.filex.write_text(text.replace("*SIMULATION CONTROLS", old + "*SIMULATION CONTROLS"), encoding="latin-1")
    events(sim)[0].update(day_length={"multiply": 9.99}, srad={"multiply": 0.25},
        tmax={"replace": 99.9}, tmin={"replace": -9.9}, rain={"subtract": 99.9},
        co2={"replace": 9999}, dew_point={"add": -9.9}, wind={"add": 99.9})
    events(sim).append(dict(date="1982-02-26", co2={"add": -89}))
    assert sim.check(False) == []
    sim.run()
    text = copied(sim, fake_dssat).decode("latin-1").replace("\r\n", "\n")
    written = [line for line in section(text).splitlines() if line[:3].strip().isdigit()][-2:]
    assert len(written) == 2
    for row, day in zip(written, ["82056", "82057"]):
        assert len(row) == 56  # I3, I5 and eight 6-character modifier cells; no ENVNAME.
        assert row[:3] == f"{highest + 1:2d} "
        assert int(row[:2]) == int(row[:3]) == highest + 1
        assert row[3:8] == day
    for n, expected in enumerate(["M9.99", "M0.25", "R99.9", "R-9.9", "S99.9", "R9999", "A-9.9", "A99.9"]):
        start = 8 + n * 6
        assert written[0][start] == " " and written[0][start + 1:start + 6] == expected
    assert written[1][39:44] == "A -89"
    assert _section_row(text, "TREATMENTS", "N", 2, ("ME",))["ME"] == str(highest + 1)


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
@pytest.mark.parametrize("following", ["HARVEST DETAILS", "SIMULATION CONTROLS"])
def test_environment_inserted_in_order_omissions_unchanged_and_checks_write_nothing(sim, fake_dssat, newline, following):
    text = sim.filex.read_text(encoding="latin-1")
    if following == "HARVEST DETAILS":
        text = text.replace("*SIMULATION CONTROLS", "*HARVEST DETAILS\n@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME\n\n*SIMULATION CONTROLS")
    original = text.encode("latin-1").replace(b"\n", newline)
    sim.filex.write_bytes(original)
    before, data_before = snapshot(sim.filex.parent), deepcopy(sim.management)
    assert sim.check(False) == []
    assert snapshot(sim.filex.parent) == before
    sim.run()
    written = copied(sim, fake_dssat)
    text = written.decode("latin-1").replace(newline.decode(), "\n")
    assert text.index("*ENVIRONMENT MODIFICATIONS") < text.index("*" + following)
    row = section(text).splitlines()[2]
    assert row == " 1 82056 A   0 M 0.5" + " A   0" * 6
    block = newline.join([b"*ENVIRONMENT MODIFICATIONS", HEADER.encode(), row.encode(), b""]) + newline
    restored = written.replace(block, b"", 1)
    old = next(s for s in original.splitlines() if s.startswith(b" 2 1 0 0"))
    assert restored.replace(old[:64] + b"  1" + old[67:], old, 1) == original
    assert sim.filex.read_bytes() == original and sim.management == data_before


def test_environment_existing_level_appended_only_selected_treatment_repointed(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    old = f"*ENVIRONMENT MODIFICATIONS\n{HEADER}\n 3 82054" + " A   0" * 8 + "\n\n"
    text = text.replace("*SIMULATION CONTROLS", old + "*SIMULATION CONTROLS")
    for number in (1, 2):
        row = next(s for s in text.splitlines() if s.startswith(f" {number} 1 0 0"))
        text = text.replace(row, row[:64] + "  3" + row[67:])
    sim.filex.write_bytes(text.encode("latin-1"))
    sim.management["treatments"][1] = {"environment": deepcopy(events(sim))}
    sim.run()
    written = copied(sim, fake_dssat).decode("latin-1").replace("\r\n", "\n")
    assert old.strip() in written and section(written).count(HEADER) == 1
    assert " 4 82056" in section(written)
    for number in range(1, 7):
        expected = "4" if number == 2 else "3" if number == 1 else "0"
        assert _section_row(written, "TREATMENTS", "N", number, ("ME",))["ME"] == expected


def test_environment_empty_list_only_sets_selected_me_to_zero(sim, fake_dssat):
    original = sim.filex.read_bytes()
    row = next(s for s in original.splitlines() if s.startswith(b" 2 1 0 0"))
    inherited = original.replace(row, row[:64] + b"  3" + row[67:])
    sim.filex.write_bytes(inherited)
    sim.management["treatments"][2]["environment"] = []
    assert sim.check(False) == []
    sim.run()
    assert copied(sim, fake_dssat) == original and sim.filex.read_bytes() == inherited


def test_environment_omitted_section_keeps_inherited_bytes(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    old = f"*ENVIRONMENT MODIFICATIONS\n{HEADER}\n 3 82054" + " A   0" * 8 + "\n\n"
    text = text.replace("*SIMULATION CONTROLS", old + "*SIMULATION CONTROLS")
    row = next(s for s in text.splitlines() if s.startswith(" 2 1 0 0"))
    sim.filex.write_bytes(text.replace(row, row[:64] + "  3" + row[67:]).encode("latin-1"))
    sim.management = {"treatments": {2: {}}}
    original = sim.filex.read_bytes()
    sim.run()
    assert copied(sim, fake_dssat) == original


def test_environment_reuses_unreferenced_level_and_preserves_other_levels(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    old = "*ENVIRONMENT MODIFICATIONS\n" + HEADER + "\n"
    for level in (1, 10, 99):
        old += f"{level:3d}82054" + " A   0" * 8 + "\n"
    text = text.replace("*SIMULATION CONTROLS", old + "\n*SIMULATION CONTROLS")
    for number, level in ((1, 10), (2, 99)):
        row = next(s for s in text.splitlines() if s.startswith(f" {number} 1 0 0"))
        text = text.replace(row, row[:64] + f"{level:3d}" + row[67:])
    sim.filex.write_bytes(text.encode("latin-1"))
    assert sim.check(False) == []
    sim.run()
    written = copied(sim, fake_dssat).decode("latin-1")
    block = section(written)
    assert "  182054" not in block and " 1082054" in block and " 9982054" in block
    assert " 1 82056" in block
    assert _section_row(written, "TREATMENTS", "N", 1, ("ME",))["ME"] == "10"
    assert _section_row(written, "TREATMENTS", "N", 2, ("ME",))["ME"] == "1"


def test_environment_bad_cell_rejected_before_run_or_writes(sim, fake_dssat):
    events(sim)[0]["tmax"] = {"add": 1.234}
    before = snapshot(sim.filex.parent)
    assert_problem(sim, 1, "tmax", "4-character")
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert snapshot(sim.filex.parent) == before and fake_dssat.calls == []


def test_filex_template_simulation_writes_environment_and_soil_analysis(data, rows, installed):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], management={"treatments": {1: {
        "environment": [dict(date="2021-03-01", srad={"multiply": 0.5})],
        "soil_analysis": dict(date="2021-03-01", layers=[dict(depth=30, extractable_p=12)])}}})
    assert sim.check(False) == []
    result = sim.run()
    text = (result.run_dir.parent / "TEST2101.MZX").read_text()
    treatment = _section_row(text, "TREATMENTS", "N", 1, ("ME", "SA"))
    assert treatment["ME"] == treatment["SA"] == "1"
    assert " 1 21060 A   0 M 0.5" in section(text)
    assert text.index("*SOIL ANALYSIS") < text.index("*ENVIRONMENT MODIFICATIONS") < text.index("*SIMULATION CONTROLS")


def test_rotation_components_reject_environment(rotation_sim):
    rotation_sim.management["treatments"][1]["rotation"] = {3: {"environment": []}}
    assert any("rotation component 3: unknown key 'environment'" in p and "Use only" in p
               for p in rotation_sim.check(False))


def test_management_template_both_examples_are_uncommented_checked_and_written(sim, tmp_path, fake_dssat):
    pytest.importorskip("yaml")
    path = tmp_path / "management.yaml"
    write_management_template(path, filex=sim.filex)
    lines, active = [], False
    for line in path.read_text().splitlines():
        if line.startswith(("    # soil_analysis:", "    # environment:")):
            active = True
        elif active and not line.startswith("    #   "):
            active = False
        lines.append(line.replace("    # ", "    ", 1) if active else line)
    for name in ("soil_analysis", "environment"):
        assert any(s.startswith(f"    {name}:") for s in lines)
    path.write_text("\n".join(lines) + "\n")
    sim.weather = [dict(sim.weather[0], date=(date(1982, 2, 25) + timedelta(days=i)).isoformat())
                   for i in range(35)]
    sim.management = path
    assert sim.check(False) == []
    sim.run()
    text = copied(sim, fake_dssat).decode("latin-1")
    assert "*SOIL ANALYSIS" in text and "*ENVIRONMENT MODIFICATIONS" in text
