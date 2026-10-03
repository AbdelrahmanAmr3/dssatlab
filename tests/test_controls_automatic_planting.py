"""Automatic planting fields and effective windows through Simulation checks/runs."""

from copy import deepcopy
from datetime import date
from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATCheckError, Simulation, write_experiment_template
from dssatlab.filex import _section_row
from test_controls_automatic_irrigation import automatic_sim
from test_controls_options import option_sim
from test_filex_template import data, rows
from test_management_file import sim_inputs
from test_simulation_run import fake_dssat
from test_simulation_template import installed
from test_season_coverage import weather


# Field -> column, accepted value, written value, rejected value, correction.
FIELDS = {
    "auto_planting_first": ("PFRST", "1982-02-25", "82056", "1982-02-30",
        "a valid ISO calendar date as a quoted YYYY-MM-DD string"),
    "auto_planting_last": ("PLAST", "1982-03-10", "82069", "1982-2-25",
        "a valid ISO calendar date as a quoted YYYY-MM-DD string"),
    "auto_planting_soil_water_low": ("PH2OL", 35, "35", -1, "a number from 0 to 100"),
    "auto_planting_soil_water_high": ("PH2OU", 90, "90", 101, "a number from 0 to 100"),
    "auto_planting_soil_water_depth": ("PH2OD", 25, "25", 0, "a number above 0"),
    "auto_planting_max_temperature": ("PSTMX", 35.5, "35.5", "35", "a finite number"),
    "auto_planting_min_temperature": ("PSTMN", -5, "-5", True, "a finite number"),
}
DATES = ("auto_planting_first", "auto_planting_last")
NUMBERS = tuple(field for field in FIELDS if field not in DATES)


def test_template_planting_window_uses_legacy_crossover(data, rows, installed):
    data['planting']['date'] = '2000-01-01'
    data['harvest_date'] = '2000-01-02'
    sim = Simulation(filex_template=data, soil=rows[1],
                     weather=weather('1999-12-30', '2000-01-02', station='TEST'),
                     management={'treatments': {1: {'controls': {
                         'years': 1, 'start_date': '1999-12-30', 'planting_management': 'A',
                         'auto_planting_first': '1999-12-31'}}}})
    assert sim.check(False) == []


def _controls(sim, values):
    sim.management["treatments"][1]["controls"] = values


def _stock(sim, *, plant="A", first="82056", last="82070"):
    text = sim.filex.read_text(encoding="latin-1")
    text = text.replace(" 1 MA              R", f" 1 MA              {plant}")
    text = text.replace("82056 82056    40", f"{first} {last}    40")
    sim.filex.write_text(text, encoding="latin-1")


@pytest.mark.parametrize("field", FIELDS)
def test_each_field_writes_only_its_cell(automatic_sim, fake_dssat, field):
    sim = automatic_sim
    column, value, encoded, _, _ = FIELDS[field]
    _controls(sim, {field: value})
    original, inputs = sim.filex.read_bytes(), deepcopy(sim.management)
    assert sim.check(verbose=False) == []
    sim.run()
    written = (Path(fake_dssat.calls[-1][1]) / sim.filex.name).read_bytes()
    text = written.decode("latin-1")
    assert _section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"] == "2"
    assert _section_row(text, "TREATMENTS", "N", 2, ("SM",))["SM"] == "1"
    assert _section_row(text, "SIMULATION CONTROLS", "N", 2, ("PLANTING", column))[column] == encoded
    expected, header = [], b""
    base = original.split(b"*SIMULATION CONTROLS")[1].splitlines()
    for row in base:
        if row.startswith(b"@N"):
            header = row
        elif row.startswith(b" 1 "):
            changed = b" 2" + row[2:]
            if b"PLANTING" in header.split():
                right = header.index(column.encode()) + len(column)
                changed = changed[:right - 6] + encoded.encode().rjust(6) + changed[right:]
            expected.append(changed)
    assert [row for row in written.splitlines() if row.startswith(b" 2 ")
            and not row.startswith(b" 2 1 ")] == expected
    assert all(row in written.splitlines() for row in base)
    assert sim.filex.read_bytes() == original
    assert sim.management == inputs


def _assert_rejected(sim, fake_dssat, field, value):
    column, _, _, _, instruction = FIELDS[field]
    _controls(sim, {field: value})
    expected = (f"Management data treatment 1, controls, field {field!r}: found {value!r}. "
                f"Supply {instruction} (DSSAT {column}).")
    original, listing = sim.filex.read_bytes(), sorted(sim.filex.parent.iterdir())
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert not fake_dssat.calls
    assert sim.filex.read_bytes() == original
    assert sorted(sim.filex.parent.iterdir()) == listing


@pytest.mark.parametrize("field", FIELDS)
def test_each_field_rejects_with_exact_message(automatic_sim, fake_dssat, field):
    _assert_rejected(automatic_sim, fake_dssat, field, FIELDS[field][3])


@pytest.mark.parametrize("field", NUMBERS)
@pytest.mark.parametrize("bad", [True, False, "1", None, [], float("nan"), float("inf")])
def test_numbers_reject_bools_and_nonfinite_values(automatic_sim, fake_dssat, field, bad):
    _assert_rejected(automatic_sim, fake_dssat, field, bad)


@pytest.mark.parametrize("field", DATES)
@pytest.mark.parametrize("bad", [True, 82056, date(1982, 2, 25), None, "1982-02-25 "])
def test_dates_require_quoted_iso_strings(automatic_sim, fake_dssat, field, bad):
    _assert_rejected(automatic_sim, fake_dssat, field, bad)


@pytest.mark.parametrize("field,value", [
    (field, value) for field in NUMBERS[:2] for value in (0, 100, 25.5)
] + [(NUMBERS[2], 0.5), (NUMBERS[3], -100), (NUMBERS[4], 100)])
def test_numeric_boundaries_accepted(automatic_sim, field, value):
    _controls(automatic_sim, {field: value})
    assert automatic_sim.check(verbose=False) == []


@pytest.mark.parametrize("field,bad", [(NUMBERS[0], 101), (NUMBERS[1], -1), (NUMBERS[2], -1)])
def test_other_numeric_boundaries_rejected(automatic_sim, fake_dssat, field, bad):
    _assert_rejected(automatic_sim, fake_dssat, field, bad)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("missing", ["block", "column", "selected_row"])
def test_missing_layout_keeps_existing_error(automatic_sim, field, missing):
    sim = automatic_sim
    column, value, _, _, _ = FIELDS[field]
    text = sim.filex.read_text(encoding="latin-1")
    if missing == "column":
        text = text.replace(column, "X" * len(column))
    elif missing == "block":
        text = text.replace("@N PLANTING", "@N XXXXXXXX")
    else:
        text = text.replace(" 1 PL ", " 7 PL ")
    sim.filex.write_text(text, encoding="latin-1")
    _controls(sim, {field: value})
    assert sim.check(verbose=False) == [
        f"Management data treatment 1, controls: FileX {sim.filex}: "
        f"SIMULATION CONTROLS level 1 has no row with columns PLANTING/{column}. "
        "Supply the needed headers and selected level rows."]


@pytest.mark.parametrize("plant", ["A", "F"])
@pytest.mark.parametrize("controls", [
    {"auto_planting_first": "1982-03-12", "auto_planting_last": "1982-03-11"},
    {"auto_planting_first": "1982-03-12"},
    {"auto_planting_last": "1982-02-25"},
    {"planting_management": "A"},
])
def test_effective_first_after_last_is_problem(automatic_sim, fake_dssat, plant, controls):
    sim = automatic_sim
    _stock(sim, plant=plant, first="82057" if "auto_planting_last" in controls else "82071",
           last="82070")
    _controls(sim, controls)
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert "auto_planting_first" in problems[0] and "auto_planting_last" in problems[0]
    assert "after" in problems[0] and "Supply" in problems[0]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert not fake_dssat.calls


@pytest.mark.parametrize("controls,first", [
    ({"auto_planting_first": "1982-02-25", "start_date": "1982-02-26"}, "82056"),
    ({"planting_management": "A"}, "82055"),
    ({"start_date": "1982-02-26"}, "82056"),
])
def test_effective_first_before_start_including_start_change_alone(automatic_sim, controls, first):
    _stock(automatic_sim, first=first)
    _controls(automatic_sim, controls)
    problems = automatic_sim.check(verbose=False)
    assert len(problems) == 1
    assert "auto_planting_first" in problems[0] and "before simulation start date" in problems[0]
    assert "Supply" in problems[0]


@pytest.mark.parametrize("field,value", [(DATES[0], "1982-02-24"), (DATES[1], "1982-04-01")])
def test_given_date_outside_weather_range(automatic_sim, field, value):
    _stock(automatic_sim)
    _controls(automatic_sim, {field: value})
    problems = automatic_sim.check(verbose=False)
    assert any(f"field '{field}': date '{value}' is outside weather range "
               "(1982-02-25 to 1982-03-31)" in p for p in problems)


@pytest.mark.parametrize("plant,controls", [
    ("R", {"planting_management": "R"}),
    ("R", {"auto_planting_first": "1982-04-01"}),
    ("A", {"planting_management": "R", "start_date": "1982-02-26"}),
    ("A", {}), ("F", {"auto_planting_soil_water_low": 30}),
    ("A", {"water": "N"}),
])
def test_unused_or_untriggered_stock_window_is_not_a_problem(automatic_sim, plant, controls):
    _stock(automatic_sim, plant=plant, first="82055", last="82054")
    _controls(automatic_sim, controls)
    assert automatic_sim.check(verbose=False) == []


def test_only_given_dates_need_weather_coverage(automatic_sim):
    _stock(automatic_sim, last="82150")
    _controls(automatic_sim, {"planting_management": "A"})
    assert automatic_sim.check(verbose=False) == []


def test_start_override_without_a_management_block_keeps_existing_behavior(sim_inputs):
    filex, weather = sim_inputs
    sim = Simulation(filex, 1, weather, management={"treatments": {
        1: {"controls": {"start_date": "1982-02-26"}}}})
    assert sim.check(verbose=False) == []


@pytest.mark.parametrize("plant", ["A", "F"])
def test_management_override_activates_a_stock_window(automatic_sim, plant):
    _stock(automatic_sim, plant="R", first="82071", last="82070")
    _controls(automatic_sim, {"planting_management": plant})
    problems = automatic_sim.check(verbose=False)
    assert len(problems) == 1 and "after auto_planting_last" in problems[0]


def test_inherited_window_in_an_earlier_year_is_compared_with_start(automatic_sim):
    _stock(automatic_sim, first="81056", last="82070")
    _controls(automatic_sim, {"planting_management": "A"})
    problems = automatic_sim.check(verbose=False)
    assert len(problems) == 1
    assert "'1981-02-25' is before simulation start date '1982-02-25'" in problems[0]


def test_window_reads_the_treatments_selected_sm_level(automatic_sim):
    _stock(automatic_sim, first="82071", last="82070")
    text = automatic_sim.filex.read_text(encoding="latin-1")
    header, body = text.split("*SIMULATION CONTROLS", 1)
    lines = header.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if line.startswith(" 1 1 0 0"))
    lines[index] = lines[index].rstrip("\n")[:-1] + "7\n"
    other = body.replace("\n 1 ", "\n 7 ").replace("82071 82070", "82056 82070")
    automatic_sim.filex.write_text("".join(lines) + "*SIMULATION CONTROLS" + body + other,
                                   encoding="latin-1")
    _controls(automatic_sim, {"start_date": "1982-02-26"})
    problems = automatic_sim.check(verbose=False)
    assert len(problems) == 1 and "before simulation start date" in problems[0]


def test_template_documents_all_fields_and_loads(automatic_sim, tmp_path):
    pytest.importorskip("yaml")
    fixture = Path(__file__).parent / "fixtures/cultivar/MZCER048.CUL"
    shutil.copyfile(fixture, automatic_sim.filex.parent / fixture.name)
    path = tmp_path / "experiment.yaml"
    write_experiment_template(path)
    text = path.read_text(encoding="utf-8")
    for field, (column, _, _, _, instruction) in FIELDS.items():
        line = next(line for line in text.splitlines() if f"# {field}:" in line)
        assert f"DSSAT {column}" in line and instruction in line
    automatic_sim.management = path
    assert automatic_sim.check(verbose=False) == []
    for field in FIELDS:
        text = text.replace(f"# {field}:", f"{field}:")
    path.write_text(text, encoding="utf-8")
    assert automatic_sim.check(verbose=False) == []


@pytest.mark.parametrize("plant", ["A", "F"])
def test_l2_window_writes_dates_and_keeps_template_defaults(data, rows, installed, plant):
    controls = {"planting_management": plant,
                "auto_planting_first": "2021-03-01", "auto_planting_last": "2021-03-01"}
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={"treatments": {1: {"controls": controls}}})
    assert sim.check(verbose=False) == []
    result = sim.run()
    text = next(result.run_dir.parent.glob("*.MZX")).read_text(encoding="latin-1")
    assert _section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"] == "2"
    for level, expected in [(1, "R"), (2, plant)]:
        assert _section_row(text, "SIMULATION CONTROLS", "N", level,
                            ("MANAGEMENT", "PLANT"))["PLANT"] == expected
    window = _section_row(text, "SIMULATION CONTROLS", "N", 2, ("PLANTING", "PFRST", "PLAST"))
    assert window["PFRST"] == window["PLAST"] == "21060"
