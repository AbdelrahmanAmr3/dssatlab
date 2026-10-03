"""Management codes and automatic irrigation edit only named controls cells."""

from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATCheckError, Simulation, run_sweep, write_experiment_template
from dssatlab.filex import _section_row
from test_controls_options import option_sim
from test_filex_template import data, rows
from test_management_file import sim_inputs
from test_simulation_run import fake_dssat
from test_simulation_template import installed


# Field -> block, column, accepted, rejected, exact correction instruction.
FIELDS = {
    "irrigation_management": ("MANAGEMENT", "IRRIG", "A", "a",
        'one of "A", "N", "F", "R", "D", "P", "W"'),
    "planting_management": ("MANAGEMENT", "PLANT", "A", "a",
        'one of "A", "F", "R"'),
    "auto_irrigation_depth": ("IRRIGATION", "IMDEP", 45, 0, "a number above 0"),
    "auto_irrigation_threshold": ("IRRIGATION", "ITHRL", 60, -1, "a number from 0 to 100"),
    "auto_irrigation_refill": ("IRRIGATION", "ITHRU", 90, 101, "a number from 0 to 100"),
    "auto_irrigation_method": ("IRRIGATION", "IMETH", "IR002", "IR02",
        "two ASCII letters followed by three digits for the DSSAT code"),
    "auto_irrigation_amount": ("IRRIGATION", "IRAMT", 20, 0, "a number above 0"),
    "auto_irrigation_efficiency": ("IRRIGATION", "IREFF", 0.75, 1.5,
        "a number above 0 and at most 1"),
}
NUMBERS = [field for field, spec in FIELDS.items() if isinstance(spec[2], (int, float))]
AUTOMATIC_ROWS = """@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          82056 82056    40   100    30    40    10
@N IRRIGATION  IMDEP ITHRL ITHRU IROFF IMETH IRAMT IREFF
 1 IR             30    50   100 GS000 IR001    10     1
@N NITROGEN    NMDEP NMTHR NAMNT NCODE NAOFF
 1 NI             30    50    25 FE001 GS000
@N HARVEST     HFRST HLAST HPCNP HPCNR
 1 HA              0   -99   100     0
"""


@pytest.fixture
def automatic_sim(option_sim):
    option_sim.filex.write_bytes(option_sim.filex.read_bytes() + AUTOMATIC_ROWS.encode("ascii"))
    return option_sim


@pytest.mark.parametrize("field", FIELDS)
def test_each_field_written_with_other_cells_preserved(automatic_sim, fake_dssat, field):
    sim = automatic_sim
    block, column, value, _, _ = FIELDS[field]
    sim.management["treatments"][1]["controls"] = {field: value}
    if field == "irrigation_management":
        sim.management["treatments"][1]["irrigation"] = []
    original, inputs = sim.filex.read_bytes(), deepcopy(sim.management)
    assert sim.check(verbose=False) == []
    sim.run()
    written = (Path(fake_dssat.calls[-1][1]) / sim.filex.name).read_bytes()
    text = written.decode("latin-1")
    assert _section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"] == "2"
    assert _section_row(text, "TREATMENTS", "N", 2, ("SM",))["SM"] == "1"
    assert _section_row(text, "SIMULATION CONTROLS", "N", 2, (block, column))[column] == str(value)
    expected, header = [], b""
    base = original.split(b"*SIMULATION CONTROLS")[1].splitlines()
    for row in base:
        if row.startswith(b"@N"):
            header = row
        elif row.startswith(b" 1 "):
            changed = b" 2" + row[2:]
            if block.encode() in header.split():
                right = header.index(column.encode()) + len(column)
                changed = changed[:right - 6] + str(value).encode().rjust(6) + changed[right:]
            expected.append(changed)
    assert [row for row in written.splitlines() if row.startswith(b" 2 ")
            and not row.startswith(b" 2 1 ")] == expected
    assert all(row in written.splitlines() for row in base)
    assert sim.filex.read_bytes() == original
    assert sim.management == inputs


@pytest.mark.parametrize("field", FIELDS)
def test_rejected_value_has_exact_message(automatic_sim, fake_dssat, field):
    _assert_rejected(automatic_sim, fake_dssat, field, FIELDS[field][3])


def _assert_rejected(sim, fake_dssat, field, value):
    _, column, _, _, instruction = FIELDS[field]
    sim.management["treatments"][1]["controls"] = {field: value}
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


@pytest.mark.parametrize("field", NUMBERS)
@pytest.mark.parametrize("bad", [True, False, "1", None, [], float("nan"), float("inf")])
def test_numbers_reject_bools_and_nonfinite_values(automatic_sim, fake_dssat, field, bad):
    _assert_rejected(automatic_sim, fake_dssat, field, bad)


@pytest.mark.parametrize("field,codes", [
    ("irrigation_management", "ANFRDPW"), ("planting_management", "AFR")])
def test_management_codes_are_case_sensitive_strings(automatic_sim, fake_dssat, field, codes):
    automatic_sim.management["treatments"][1]["irrigation"] = []
    for code in codes:
        automatic_sim.management["treatments"][1]["controls"] = {field: code}
        assert automatic_sim.check(verbose=False) == []
    for bad in [*codes.lower(), True, False, 1, 1.0, None, []]:
        _assert_rejected(automatic_sim, fake_dssat, field, bad)


@pytest.mark.parametrize("method", ["IR001", "ir001", "Ab123"])
def test_method_uses_irrigation_event_rule(automatic_sim, method):
    automatic_sim.management["treatments"][1]["controls"] = {"auto_irrigation_method": method}
    assert automatic_sim.check(verbose=False) == []


@pytest.mark.parametrize("bad", [True, 1, "İR001", "IR００１", "IR001 ", "I0001"])
def test_method_rejects_non_ascii_and_wrong_shape(automatic_sim, fake_dssat, bad):
    _assert_rejected(automatic_sim, fake_dssat, "auto_irrigation_method", bad)


@pytest.mark.parametrize("field,value", [
    (field, value) for field in ("auto_irrigation_threshold", "auto_irrigation_refill")
    for value in (0, 100, 25.5)
] + [("auto_irrigation_depth", 0.5), ("auto_irrigation_amount", 0.5),
     ("auto_irrigation_efficiency", 1)])
def test_numeric_boundaries_accepted(automatic_sim, field, value):
    automatic_sim.management["treatments"][1]["controls"] = {field: value}
    assert automatic_sim.check(verbose=False) == []


@pytest.mark.parametrize("field,bad", [
    ("auto_irrigation_depth", -1), ("auto_irrigation_amount", -1),
    ("auto_irrigation_threshold", 101), ("auto_irrigation_refill", -1),
    ("auto_irrigation_efficiency", 0), ("auto_irrigation_efficiency", -0.5),
])
def test_other_range_boundaries_rejected(automatic_sim, fake_dssat, field, bad):
    _assert_rejected(automatic_sim, fake_dssat, field, bad)


@pytest.mark.parametrize("field", NUMBERS)
def test_column_width_error_keeps_existing_message(automatic_sim, fake_dssat, field):
    sim = automatic_sim
    column = FIELDS[field][1]
    width = 7 if column == "IMDEP" else 6
    sim.management["treatments"][1]["controls"] = {field: 0.123456}
    expected = (f"Management data treatment 1, controls: FileX {sim.filex}: "
                f"SIMULATION CONTROLS column {column}: value '0.123456' does not fit "
                f"its {width}-character field. The field needs one leading blank. Supply a shorter "
                "value that fits the FileX column without rounding or truncation.")
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert not fake_dssat.calls


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("missing", ["block", "column", "selected_row"])
def test_missing_layout_uses_existing_error(automatic_sim, fake_dssat, field, missing):
    sim = automatic_sim
    block, column, value, _, _ = FIELDS[field]
    text = sim.filex.read_text(encoding="latin-1")
    if missing == "column":
        text = text.replace(column, "X" * len(column))
    elif missing == "block":
        text = text.replace("@N " + block, "@N " + "X" * len(block))
    else:
        lines = text.splitlines(keepends=True)
        index = next(i for i, line in enumerate(lines) if line.startswith("@N " + block))
        lines[index + 1] = " 7" + lines[index + 1][2:]
        text = "".join(lines)
    sim.filex.write_text(text, encoding="latin-1")
    sim.management["treatments"][1]["controls"] = {field: value}
    expected = (f"Management data treatment 1, controls: FileX {sim.filex}: "
                f"SIMULATION CONTROLS level 1 has no row with columns {block}/{column}. "
                "Supply the needed headers and selected level rows.")
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert not fake_dssat.calls


def test_template_documents_every_field_and_loads(automatic_sim, tmp_path):
    pytest.importorskip("yaml")
    fixture = Path(__file__).parent / "fixtures/cultivar/MZCER048.CUL"
    shutil.copyfile(fixture, automatic_sim.filex.parent / fixture.name)
    path = tmp_path / "experiment.yaml"
    write_experiment_template(path)
    text = path.read_text(encoding="utf-8")
    for field, (_, column, _, _, instruction) in FIELDS.items():
        line = next(line for line in text.splitlines() if f"# {field}:" in line)
        assert f"DSSAT {column}" in line
        if field.endswith("management"):
            assert all(code in line for code in instruction.removeprefix("one of ").split(", "))
        else:
            assert instruction in line
    assert "EFIR applies to the irrigation level's events" in text
    assert "IREFF applies to automatic irrigation" in text
    automatic_sim.management = path
    assert automatic_sim.check(verbose=False) == []
    for field in FIELDS:
        text = text.replace(f"# {field}:", f"{field}:")
    path.write_text(text, encoding="utf-8")
    assert automatic_sim.check(verbose=False) == []


@pytest.mark.parametrize("controls,expected", [({}, "R"), ({"irrigation_management": "A"}, "A")])
def test_l2_run_writes_irrig_and_keeps_defaults(data, rows, installed, controls, expected):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={"treatments": {1: {"controls": controls}}},
                     executable=installed.executable)
    assert sim.check(verbose=False) == []
    result = sim.run()
    text = next(result.run_dir.parent.glob("*.MZX")).read_text(encoding="latin-1")
    level = int(_section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"])
    assert level == (2 if controls else 1)
    assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("MANAGEMENT", "IRRIG"))["IRRIG"] == expected
    defaults = _section_row(text, "SIMULATION CONTROLS", "N", 1, ("MANAGEMENT", "IRRIG", "PLANT"))
    assert defaults["IRRIG"] == defaults["PLANT"] == "R"
    irrigation = _section_row(text, "SIMULATION CONTROLS", "N", level, ("IRRIGATION", "IMDEP"))
    assert [irrigation[column] for column in ("IMDEP", "ITHRL", "ITHRU", "IROFF", "IMETH", "IRAMT", "IREFF")] == [
        "30", "50", "100", "GS000", "IR001", "10", "1"]


def test_threshold_whole_controls_section_sweep(automatic_sim, fake_dssat):
    sim = automatic_sim
    sim.management["treatments"][1]["controls"] = {"water": "N"}
    sim.management["treatments"][1]["irrigation"] = []
    original = deepcopy(sim.management)
    factors = {"controls": {f"T{threshold}": {"irrigation_management": "A",
        "auto_irrigation_threshold": threshold} for threshold in (30, 70)}}
    summary = Path(__file__).parent / "fixtures/output_files/summary/two_treatments/Summary.OUT"
    fake_dssat.outputs["Summary.OUT"] = summary.read_bytes()
    result = run_sweep(sim.filex, sim.weather, treatments=[1], management=sim.management,
                       factors=factors, executable=fake_dssat.executable)
    assert [(row["scenario"], row["controls"]) for row in result[::2]] == [
        ("base", None), ("T30", "T30"), ("T70", "T70")]
    assert len(fake_dssat.calls) == 3
    for (_, folder, _), threshold, irrig, water in zip(
            fake_dssat.calls, ("50", "30", "70"), ("R", "A", "A"), ("N", "Y", "Y")):
        text = (Path(folder) / sim.filex.name).read_text(encoding="latin-1")
        level = int(_section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"])
        for block, column, expected in [("IRRIGATION", "ITHRL", threshold),
                                        ("MANAGEMENT", "IRRIG", irrig), ("OPTIONS", "WATER", water)]:
            assert _section_row(text, "SIMULATION CONTROLS", "N", level, (block, column))[column] == expected
    assert sim.management == original
