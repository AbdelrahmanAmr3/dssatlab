"""Simulation options use checked codes and preserve the copied controls level."""

from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATCheckError, Simulation, run_sweep, write_experiment_template
from dssatlab import experiment
from dssatlab.filex import _section_row
from test_filex_template import data, rows
from test_management_file import sim_inputs
from test_simulation_run import fake_dssat
from test_simulation_template import installed


# The spec's table also pins the writer/check table, including code order in errors.
OPTIONS = {
    "water": ("OPTIONS", "WATER", ("Y", "N")),
    "nitrogen": ("OPTIONS", "NITRO", ("Y", "N")),
    "photosynthesis": ("METHODS", "PHOTO", ("C", "R", "L", "V")),
    "co2": ("OPTIONS", "CO2", ("M", "W", "D", "R")),
    "symbiosis": ("OPTIONS", "SYMBI", ("Y", "N", "U")),
    "phosphorus": ("OPTIONS", "PHOSP", ("Y", "N")),
    "potassium": ("OPTIONS", "POTAS", ("Y", "N")),
    "tillage": ("OPTIONS", "TILL", ("Y", "N")),
    "evapotranspiration": ("METHODS", "EVAPO", ("F", "R", "S", "T")),
    "infiltration": ("METHODS", "INFIL", ("R", "S", "N")),
    "soil_organic_matter": ("METHODS", "MESOM", ("G", "P")),
    "soil_evaporation": ("METHODS", "MESEV", ("R", "S")),
    "soil_layers": ("METHODS", "MESOL", (1, 2, 3)),
    "residue": ("MANAGEMENT", "RESID", ("N", "R", "D")),
    "harvest_management": ("MANAGEMENT", "HARVS", ("A", "M", "R", "D")),
}
NEW_OPTIONS = {field: spec for field, spec in OPTIONS.items()
               if field not in ("water", "nitrogen")}

CONTROL_ROWS = """@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2
 1 OP              Y     Y     N     N     N     N     N     N     M
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              M     M     E     R     S     C     R     1     G     R     2
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              R     R     R     N     M
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              N     Y     Y     1     Y     N     Y     Y     N     N     Y     N     Y     A

@  AUTOMATIC MANAGEMENT
@N RESIDUES    RIPCN RTIME RIDEP
 1 RE            100     1    20
"""


@pytest.fixture
def option_sim(sim_inputs):
    filex, weather = sim_inputs
    filex.write_text(filex.read_text(encoding="latin-1") + CONTROL_ROWS,
                     encoding="latin-1")
    return Simulation(filex, 1, weather, management={"treatments": {1: {"controls": {}}}})


def test_option_table_matches_spec():
    assert {field: experiment._CONTROL_OPTIONS[field] for field in OPTIONS} == OPTIONS


@pytest.mark.parametrize("field,value", [
    (field, value) for field, (_, _, codes) in OPTIONS.items() for value in codes
])
def test_code_written_and_other_cells_preserved(option_sim, fake_dssat, field, value):
    sim = option_sim
    sim.management["treatments"][1]["controls"] = {field: value}
    original, inputs = sim.filex.read_bytes(), deepcopy(sim.management)
    assert sim.check(verbose=False) == []
    sim.run()
    written = (Path(fake_dssat.calls[-1][1]) / sim.filex.name).read_bytes()
    text = written.decode("latin-1")
    assert _section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"] == "2"
    assert _section_row(text, "TREATMENTS", "N", 2, ("SM",))["SM"] == "1"
    block, column, _ = OPTIONS[field]
    assert _section_row(text, "SIMULATION CONTROLS", "N", 2,
                        (block, column))[column] == str(value)
    base = original.split(b"*SIMULATION CONTROLS")[1].splitlines()
    expected, header = [], b""
    for row in base:
        if row.startswith(b"@N"):
            header = row
        elif row.startswith(b" 1 "):
            changed = b" 2" + row[2:]
            if block.encode() in header.split():
                right = header.index(column.encode()) + len(column)
                changed = changed[:right - 6] + str(value).encode().rjust(6) + changed[right:]
            expected.append(changed)
    copied = [row for row in written.split(b"*SIMULATION CONTROLS")[1].splitlines()
              if row.startswith(b" 2 ")]
    assert copied == expected
    assert all(row in written.splitlines() for row in base)
    assert sim.filex.read_bytes() == original
    assert sim.management == inputs


@pytest.mark.parametrize("field", ["water", "nitrogen"])
@pytest.mark.parametrize("bad", ["y", "X", True, 1, []])
def test_water_and_nitrogen_keep_exact_messages(option_sim, field, bad):
    option_sim.management["treatments"][1]["controls"] = {field: bad}
    assert option_sim.check(verbose=False) == [
        f"Management data treatment 1, controls, field {field!r}: found {bad!r}. "
        'Supply the quoted string "Y" or "N".'
    ]


@pytest.mark.parametrize("bad", ["G", "junk"])
def test_harvest_management_rejects_inactive_and_unknown_codes(option_sim, bad):
    option_sim.management["treatments"][1]["controls"] = {"harvest_management": bad}
    assert option_sim.check(verbose=False) == [
        f"Management data treatment 1, controls, field 'harvest_management': found {bad!r}. "
        'Supply one of "A", "M", "R", "D" (DSSAT HARVS).'
    ]


@pytest.mark.parametrize("field", NEW_OPTIONS)
@pytest.mark.parametrize("bad", ["X", "lowercase", True, False, 1, 1.0, None, [], {}])
def test_rejected_codes_have_exact_message_before_writing(option_sim, fake_dssat, field, bad):
    if field == "soil_layers" and type(bad) is int:
        bad = 4
    elif bad == "lowercase":
        bad = str(NEW_OPTIONS[field][2][0]).lower() if field != "soil_layers" else "1"
    sim = option_sim
    sim.management["treatments"][1]["controls"] = {field: bad}
    _, column, codes = NEW_OPTIONS[field]
    choices = ", ".join(f'"{code}"' if isinstance(code, str) else str(code) for code in codes)
    expected = (f"Management data treatment 1, controls, field {field!r}: found {bad!r}. "
                f"Supply one of {choices} (DSSAT {column}).")
    original, listing = sim.filex.read_bytes(), sorted(sim.filex.parent.iterdir())
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert not fake_dssat.calls
    assert sim.filex.read_bytes() == original
    assert sorted(sim.filex.parent.iterdir()) == listing


@pytest.mark.parametrize("field", NEW_OPTIONS)
@pytest.mark.parametrize("missing", ["column", "block", "selected_row"])
def test_missing_layout_uses_existing_error(option_sim, fake_dssat, field, missing):
    block, column, codes = NEW_OPTIONS[field]
    sim = option_sim
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
    sim.management["treatments"][1]["controls"] = {field: codes[-1]}
    expected = (f"Management data treatment 1, controls: FileX {sim.filex}: "
                f"SIMULATION CONTROLS level 1 has no row with columns {block}/{column}. "
                "Supply the needed headers and selected level rows.")
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert not fake_dssat.calls


def test_template_documents_options_and_loads_with_them(option_sim, tmp_path):
    pytest.importorskip("yaml")
    sim = option_sim
    fixture = Path(__file__).parent / "fixtures/cultivar/MZCER048.CUL"
    shutil.copyfile(fixture, sim.filex.parent / fixture.name)
    path = tmp_path / "experiment.yaml"
    write_experiment_template(path)
    text = path.read_text(encoding="utf-8")
    assert 'RESID "R"' in text and 'HARVS "R" or "M"' in text
    assert 'controls tillage "Y" applies tillage (TILL)' in text
    for field, (_, column, codes) in NEW_OPTIONS.items():
        line = next(line for line in text.splitlines() if f"# {field}:" in line and "DSSAT" in line)
        assert f"DSSAT {column}" in line
        assert all((f'"{code}"' if isinstance(code, str) else str(code)) in line for code in codes)
    sim.management = path
    assert sim.check(verbose=False) == []
    # The documented examples must also pass when a user uncomments them all.
    for field in NEW_OPTIONS:
        text = text.replace(f"      # {field}:", f"      {field}:")
    path.write_text(text, encoding="utf-8")
    assert sim.check(verbose=False) == []


@pytest.mark.parametrize("controls,expected", [({}, "C"), ({"photosynthesis": "L"}, "L")])
def test_l2_run_keeps_default_or_writes_photo(data, rows, installed, controls, expected):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={"treatments": {1: {"controls": controls}}},
                     executable=installed.executable)
    assert sim.check(verbose=False) == []
    result = sim.run()
    text = next(result.run_dir.parent.glob("*.MZX")).read_text(encoding="latin-1")
    level = int(_section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"])
    assert level == (2 if controls else 1)
    assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("METHODS", "PHOTO"))["PHOTO"] == expected
    assert _section_row(text, "SIMULATION CONTROLS", "N", 1, ("METHODS", "PHOTO"))["PHOTO"] == "C"


def test_photosynthesis_whole_section_sweep(option_sim, fake_dssat):
    sim = option_sim
    sim.management["treatments"][1]["controls"] = {"water": "N"}
    original = deepcopy(sim.management)
    factors = {"controls": {"C": {"photosynthesis": "C"}, "L": {"photosynthesis": "L"}}}
    summary = Path(__file__).parent / "fixtures/output_files/summary/two_treatments/Summary.OUT"
    fake_dssat.outputs["Summary.OUT"] = summary.read_bytes()
    result = run_sweep(sim.filex, sim.weather, treatments=[1], management=sim.management,
                       factors=factors, executable=fake_dssat.executable)
    assert [(row["scenario"], row["controls"]) for row in result[::2]] == [
        ("base", None), ("C", "C"), ("L", "L")]
    assert len(fake_dssat.calls) == 3
    for (_, folder, _), photo, water in zip(fake_dssat.calls, ("C", "C", "L"), ("N", "Y", "Y")):
        text = (Path(folder) / sim.filex.name).read_text(encoding="latin-1")
        level = int(_section_row(text, "TREATMENTS", "N", 1, ("SM",))["SM"])
        assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("METHODS", "PHOTO"))["PHOTO"] == photo
        assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("OPTIONS", "WATER"))["WATER"] == water
    assert sim.management == original
