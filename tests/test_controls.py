"""Controls checks and copied FileX behaviour through Simulation."""

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, write_experiment_template
from test_simulation_run import fake_dssat
from test_management_file import sim_inputs


FIXTURE = Path(__file__).parent / "fixtures" / "controls" / "UFGA8201.MZX"


@pytest.fixture
def sim(sim_inputs):
    filex, weather = sim_inputs
    filex.write_bytes(FIXTURE.read_bytes())
    return Simulation(filex, "03", weather, management={"treatments": {3: {"controls": {
        "start_date": "1982-02-26", "water": "N", "nitrogen": "N", "output_interval": 5,
    }}}})


def copied(sim, fake_dssat):
    sim.run()
    return (Path(fake_dssat.calls[-1][1]) / sim.filex.name).read_bytes()


def test_all_controls_applied_and_every_other_byte_preserved(sim, fake_dssat, capsys):
    original, inputs = sim.filex.read_bytes(), deepcopy(sim.management)
    assert sim.check() == []
    assert "controls: OK" in capsys.readouterr().out
    written = copied(sim, fake_dssat)
    original_lines = original.splitlines(keepends=True)
    treatment = next(line for line in original_lines if line.startswith(b" 3 1 0 0"))
    expected_treatment = treatment[:70] + b"  2" + treatment[73:]
    assert expected_treatment in written
    rows = [line for line in written.split(b"*SIMULATION CONTROLS")[1].splitlines()
            if line.startswith(b" 2 ")]
    base = [line for line in original.split(b"*SIMULATION CONTROLS")[1].splitlines()
            if line.startswith(b" 1 ")]
    assert len(rows) == len(base) == 10
    expected = [b" 2" + row[2:] for row in base]
    expected[0] = expected[0].replace(b"82056", b"82057")
    expected[1] = expected[1][:19] + b"N" + expected[1][20:25] + b"N" + expected[1][26:]
    expected[4] = expected[4][:37] + b"5" + expected[4][38:]
    assert rows == expected
    # The existing file survives as an exact prefix apart from the one SM cell.
    assert written.startswith(original.rstrip(b"\r\n").replace(treatment, expected_treatment))
    assert sim.filex.read_bytes() == original
    assert sim.management == inputs


@pytest.mark.parametrize("management", [None, {"treatments": {}},
    {"treatments": {3: {}}}, {"treatments": {3: {"controls": {}}}},
    {"treatments": {1: {"controls": {"water": "N"}}}}])
def test_omitted_empty_or_other_treatment_controls_keep_exact_copy(sim, fake_dssat, management):
    sim.management = management
    original = sim.filex.read_bytes()
    assert copied(sim, fake_dssat) == original == sim.filex.read_bytes()


@pytest.mark.parametrize("field,value,old,new", [
    ("start_date", "1982-03-01", b"82056", b"82060"),
    ("water", "N", b"OP              Y", b"OP              N"),
    ("nitrogen", "N", b"OP              Y     Y", b"OP              Y     N"),
    ("output_interval", 3, b"OU              N     Y     Y     1", b"OU              N     Y     Y     3"),
])
def test_each_field_keeps_all_omitted_fields(sim, fake_dssat, field, value, old, new):
    sim.management["treatments"][3]["controls"] = {field: value}
    base = sim.filex.read_bytes().split(b"*SIMULATION CONTROLS")[1].splitlines()
    expected = [b" 2" + line[2:].replace(old, new) for line in base if line.startswith(b" 1 ")]
    written = copied(sim, fake_dssat).split(b"*SIMULATION CONTROLS")[1]
    assert [line for line in written.splitlines() if line.startswith(b" 2 ")] == expected


@pytest.mark.parametrize("field,value", [
    ("start_date", "1982-02-30"), ("start_date", "82-02-25"),
    ("start_date", date(1982, 2, 25)), ("start_date", None),
    ("water", "y"), ("water", "yes"), ("water", True), ("water", 1),
    ("nitrogen", "n"), ("nitrogen", "X"), ("nitrogen", False), ("nitrogen", []),
    ("output_interval", 0), ("output_interval", -1), ("output_interval", True),
    ("output_interval", 1.0), ("output_interval", "1"), ("output_interval", float("inf")),
    ("output_interval", 1000000), ("misspelled", 1),
    pytest.param("output_interval", 10 ** 5000, id="huge-interval"),
])
def test_bad_values_reported_before_any_write(sim, fake_dssat, field, value):
    sim.management["treatments"][3]["controls"] = {field: value}
    original, listing = sim.filex.read_bytes(), sorted(sim.filex.parent.iterdir())
    problems = sim.check()
    assert any("controls" in p and (field in p or "FROPT" in p) for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert not fake_dssat.calls
    assert sim.filex.read_bytes() == original
    assert sorted(sim.filex.parent.iterdir()) == listing


@pytest.mark.parametrize("old,new,word", [
    (b" SM", b" XX", "SM"), (b" SDATE", b" XXXXX", "SDATE"),
    (b" WATER", b" XXXXX", "WATER"), (b" NITRO", b" XXXXX", "NITRO"),
    (b" FROPT", b" XXXXX", "FROPT"), (b" 1 OP", b" 7 OP", "OPTIONS"),
    (b" 1 OU", b" 7 OU", "OUTPUTS"), (b" 1 GE", b"99 GE", "row N= 1"),
    (b"@N METHODS", b"@X METHODS", "N column"),
    (b" 1 PL", b"99 PL", "does not fit"),
    (b" 1 OP              Y     Y     N     N     N     N     N     Y     M", b" 1 OP", "truncated"),
])
def test_missing_or_unwritable_layout_reported(sim, fake_dssat, old, new, word):
    sim.filex.write_bytes(sim.filex.read_bytes().replace(old, new))
    assert any(word in p for p in sim.check())
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert not fake_dssat.calls


@pytest.mark.parametrize("start,valid", [("1982-02-26", True), ("1982-02-25", False),
                                           ("2082-02-26", False)])
def test_override_replaces_old_weather_check_with_exact_calendar_date(sim, start, valid):
    sim.weather = [row for row in sim.weather if row["date"] >= "1982-02-26"]
    sim.management["treatments"][3]["controls"] = {"start_date": start}
    problems = sim.check()
    assert (problems == []) == valid
    if not valid:
        assert any("start_date" in p and "covered by weather" in p for p in problems)


@pytest.mark.parametrize("start,valid", [("1982-02-25", True), ("1982-02-27", False)])
def test_override_drives_planting_check_even_when_base_start_is_later(sim, start, valid):
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"S 82056", b"S 82060"))
    sim.management["treatments"][3] = {
        "controls": {"start_date": start},
        "planting": {"date": "1982-02-26", "method": "S", "distribution": "R",
                     "population": 7, "row_spacing": 60, "depth": 5},
    }
    problems = sim.check()
    assert (problems == []) == valid
    if not valid:
        assert any("before simulation start" in p and start in p for p in problems)


def test_all_treatment_and_other_input_problems_collected(sim):
    entry = {"controls": {"start_date": "bad", "water": "Q", "nitrogen": False,
                           "output_interval": 0, "typo": 2}}
    sim.management = {"treatments": {1: entry, 3: entry, 5: entry}}
    sim.weather[0]["rain"] = -5
    problems = sim.check()
    for number in (1, 3, 5):
        for field in entry["controls"]:
            assert any(f"treatment {number}" in p and field in p for p in problems)
    assert any("rain" in p for p in problems)


def test_template_loads_checks_and_writes_controls(sim, tmp_path, fake_dssat):
    pytest.importorskip("yaml")
    path = tmp_path / "experiment.yaml"
    # The shared fixture adds an odd-cased MZCER048.cUl; two .CUL files for one crop are rejected.
    for old in sim.filex.parent.iterdir():
        if old.suffix.lower() == ".cul":
            old.unlink()
    cul = Path(__file__).parent / "fixtures" / "cultivar" / "MZCER048.CUL"
    (sim.filex.parent / cul.name).write_bytes(cul.read_bytes())
    write_experiment_template(path, filex=sim.filex)
    sim.management = path
    assert sim.check() == []
    assert b" 2 GE" in copied(sim, fake_dssat)


def test_start_override_names_weather_file_for_new_year(sim, fake_dssat):
    sim.weather = [dict(sim.weather[0], date="1983-01-01")]
    sim.management["treatments"][3]["controls"] = {"start_date": "1983-01-01"}
    assert b"S 83001" in copied(sim, fake_dssat)
    folder = Path(fake_dssat.calls[0][1])
    assert (folder / "UFGA8301.WTH").exists()
    assert not (folder / "UFGA8201.WTH").exists()


@pytest.mark.parametrize("grouped_rows", [False, True])
def test_selected_level_cloned_using_highest_number_across_blocks(sim, fake_dssat, grouped_rows):
    prefix, controls = sim.filex.read_bytes().split(b"*SIMULATION CONTROLS")
    treatment = next(line for line in prefix.splitlines(keepends=True) if line.startswith(b" 3 1"))
    prefix = prefix.replace(treatment, treatment[:70] + b"  7" + treatment[73:])
    other = controls.replace(b" 1 ", b" 7 ").replace(b"2150", b"9999").replace(b"82056", b"82060")
    if grouped_rows:
        combined = []
        for first, second in zip(controls.splitlines(keepends=True), other.splitlines(keepends=True)):
            combined.append(first)
            if second.startswith(b" 7 "):
                combined.append(second)
        controls = b"".join(combined)
    else:
        controls += other
    original = prefix + b"*SIMULATION CONTROLS" + controls + b"! final comment without newline\xff"
    sim.filex.write_bytes(original)
    sim.management["treatments"][3]["controls"] = {"water": "N"}
    written = copied(sim, fake_dssat)
    expected = [b" 8" + row[2:].replace(b"OP              Y", b"OP              N")
                for row in other.splitlines() if row.startswith(b" 7 ")]
    assert [row for row in written.splitlines() if row.startswith(b" 8 ")] == expected
    assert written.endswith(b"! final comment without newline\xff")
    assert sim.filex.read_bytes() == original


@pytest.mark.parametrize("old_start", [b"S XXXXX", b"P 82056"])
def test_valid_override_replaces_sdate_but_preserves_start_switch(sim, fake_dssat, old_start):
    sim.filex.write_bytes(sim.filex.read_bytes().replace(b"S 82056", old_start))
    assert sim.check() == []
    assert old_start[:1] + b" 82057" in copied(sim, fake_dssat)


def test_valid_override_still_drives_checks_when_another_control_is_bad(sim):
    sim.management["treatments"][3] = {
        "controls": {"start_date": "1982-04-01", "water": "invalid"},
        "planting": {"date": "1982-02-26", "method": "S", "distribution": "R",
                     "population": 7, "row_spacing": 60, "depth": 5},
    }
    problems = sim.check()
    assert any("water" in p and "invalid" in p for p in problems)
    assert any("start_date" in p and "covered by weather" in p for p in problems)
    assert any("before simulation start" in p and "1982-04-01" in p for p in problems)


def test_omitted_controls_with_planting_keeps_controls_bytes(sim, fake_dssat):
    sim.management["treatments"][3] = {"planting": {
        "date": "1982-02-26", "method": "S", "distribution": "R",
        "population": 7, "row_spacing": 60, "depth": 5,
    }}
    original = sim.filex.read_bytes().split(b"*SIMULATION CONTROLS")[1]
    assert copied(sim, fake_dssat).split(b"*SIMULATION CONTROLS")[1] == original


IRRIGATION = ("\n*IRRIGATION AND WATER MANAGEMENT\n"
              "@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME\n"
              " 1     1   -99   -99   -99   -99   -99   -99 -99\n"
              "@I IDATE  IROP IRVAL\n"
              " 1 82063 IR001    13\n")


@pytest.mark.parametrize("start, valid", [("1982-03-04", True), ("1982-03-05", False)])
def test_start_after_the_filex_first_irrigation_is_a_check_problem(sim, start, valid):
    sim.filex.write_bytes(sim.filex.read_bytes() + IRRIGATION.encode("latin-1"))
    sim.management = {"treatments": {3: {"controls": {"start_date": start}}}}
    problems = sim.check(verbose=False)
    assert (problems == []) is valid
    if not valid:
        assert any("first irrigation date 1982-03-04" in p and "IPIRR" in p for p in problems)
