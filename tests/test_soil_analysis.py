"""Soil analysis checks and fixed FileX columns through Simulation."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, write_management_template
from dssatlab.filex import _section_row
from dssatlab.filex_write import _insert_section
from test_filex_template import data, rows
from test_initial_conditions import FIXTURE
from test_rotation_data import sim as rotation_sim
from test_rotation_template import rotation
from test_simulation_run import fake_dssat, inputs, snapshot
from test_simulation_template import installed


HEADER = "@A SADAT  SMHB  SMPX  SMKE  SANAME"
LAYERS = "@A  SABL  SADM  SAOC  SANI SAPHW SAPHB  SAPX  SAKE  SASC"
FIELDS = ("bulk_density", "organic_carbon", "total_nitrogen", "ph_water",
          "ph_buffer", "extractable_p", "exchangeable_k", "stable_carbon")


@pytest.fixture
def sim(inputs):
    inputs.filex.write_bytes(FIXTURE.read_bytes())
    return Simulation(inputs.filex, 2, inputs.rows, management={"treatments": {2: {
        "soil_analysis": dict(date="1982-02-25", layers=[dict(depth=15), dict(depth=30)])}}})


def analysis(sim):
    return sim.management["treatments"][2]["soil_analysis"]


def copied(sim, fake_dssat):
    return (Path(fake_dssat.calls[0][1]) / sim.filex.name).read_bytes()


def section(text):
    return text.split("*SOIL ANALYSIS", 1)[1].split("\n*", 1)[0]


@pytest.mark.parametrize("field", ["date", "layers"])
def test_required_section_fields(sim, field):
    del analysis(sim)[field]
    assert any("soil_analysis" in p and f"missing required field '{field}'" in p
               and f"Add '{field}'" in p for p in sim.check(False))


@pytest.mark.parametrize("value,word", [("bad", "YYYY-MM-DD"), ("1982-02-30", "calendar"),
                                       (date(1982, 2, 25), "quote")])
def test_required_date_is_a_quoted_iso_calendar_date(sim, value, word):
    analysis(sim)["date"] = value
    assert any("soil_analysis, field 'date'" in p and word in p for p in sim.check(False))


@pytest.mark.parametrize("value", [None, [], "OFF", True])
def test_section_requires_dict_or_quoted_off(sim, value):
    sim.management["treatments"][2]["soil_analysis"] = value
    assert any('soil_analysis: expected a dict or the quoted string "off"' in p
               for p in sim.check(False))


@pytest.mark.parametrize("value", [[], None, {}, [None]])
def test_layers_require_nonempty_list_of_dicts(sim, value):
    analysis(sim)["layers"] = value
    expected = "layer 1: expected a dict" if value == [None] else "non-empty list"
    assert any("soil_analysis" in p and expected in p for p in sim.check(False))


def test_twenty_layers_pass_and_twenty_one_fail(sim):
    analysis(sim)["layers"] = [dict(depth=i * 5, extractable_p=12) for i in range(1, 21)]
    assert not any("soil_analysis" in p for p in sim.check(False))
    analysis(sim)["layers"].append(dict(depth=105, extractable_p=12))
    assert any("21 layers" in p and "at most 20" in p for p in sim.check(False))


def test_layer_depth_is_required(sim):
    analysis(sim)["layers"][0] = {}
    assert any("layer 1" in p and "missing required field 'depth'" in p
               for p in sim.check(False))


@pytest.mark.parametrize("field", ["ph_buffer_method", "p_method", "k_method"])
@pytest.mark.parametrize("value", ["SA05", "SÅ005", "SA００５", False, "SA005\n"])
def test_method_codes_require_two_ascii_letters_and_three_digits(sim, field, value):
    analysis(sim)[field] = value
    assert any(f"soil_analysis, field '{field}'" in p and
               "two ASCII letters followed by three digits" in p for p in sim.check(False))


@pytest.mark.parametrize("field,value,expected", [
    ("depth", 0, "positive bottom-of-layer depth in cm"),
    ("depth", -1, "positive bottom-of-layer depth in cm"),
    ("bulk_density", 0, "above 0 and at most 10"),
    ("bulk_density", 10.1, "above 0 and at most 10"),
    ("organic_carbon", -1, "0 to 100"), ("organic_carbon", 101, "0 to 100"),
    ("total_nitrogen", -1, "0 to 10"), ("total_nitrogen", 10.1, "0 to 10"),
    ("ph_water", 0, "above 0 and at most 14"), ("ph_water", 14.1, "above 0 and at most 14"),
    ("ph_buffer", 0, "above 0 and at most 14"), ("ph_buffer", 14.1, "above 0 and at most 14"),
    ("extractable_p", -1, "0 to 999.99"), ("extractable_p", 1000, "0 to 999.99"),
    ("exchangeable_k", -1, "0 to 999.99"), ("exchangeable_k", 1000, "0 to 999.99"),
    ("stable_carbon", -1, "0 to 99.999"), ("stable_carbon", 100, "0 to 99.999"),
])
def test_layer_ranges_report_layer_field_and_correction(sim, field, value, expected):
    analysis(sim)["layers"][0][field] = value
    assert any(f"soil_analysis, layer 1, field '{field}'" in p and expected in p
               for p in sim.check(False))


@pytest.mark.parametrize("field", ["depth", *FIELDS])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True, "1"])
def test_layer_numbers_must_be_finite_and_not_booleans(sim, field, value):
    analysis(sim)["layers"][0][field] = value
    assert any(f"layer 1, field '{field}'" in p and "finite number" in p
               and "not a string or boolean" in p for p in sim.check(False))


@pytest.mark.parametrize("depth", [15, 10])
def test_depths_are_strictly_ascending(sim, depth):
    analysis(sim)["layers"][1]["depth"] = depth
    assert any("layer 2, field 'depth'" in p and "strictly ascending" in p
               for p in sim.check(False))


@pytest.mark.parametrize("layer", [None, 0])
def test_unknown_keys_are_reported(sim, layer):
    target = analysis(sim) if layer is None else analysis(sim)["layers"][layer]
    target["typo"] = 1
    assert any("soil_analysis" in p and "unknown key 'typo'" in p and "Use only" in p
               and (layer is None or "layer 1" in p) for p in sim.check(False))


@pytest.mark.parametrize("field", FIELDS)
def test_deeper_field_requires_first_layer_value(sim, field):
    analysis(sim)["layers"][1][field] = 1
    expected = (f"soil_analysis, layer 2, field '{field}': DSSAT reads a soil analysis column "
                f"only when the first layer has a value. Add {field} to layer 1 or remove it "
                "from the deeper layers.")
    assert any(expected in p for p in sim.check(False))


@pytest.mark.parametrize("field", ["depth", *FIELDS])
def test_too_wide_values_are_reported_before_writing(sim, fake_dssat, field):
    analysis(sim)["layers"][0][field] = 1.23456
    before = snapshot(sim.filex.parent)
    problems = sim.check(False)
    assert any(f"layer 1, field '{field}'" in p and "does not fit" in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert snapshot(sim.filex.parent) == before
    assert not list(sim.filex.parent.glob("dssat_sim_*"))


def test_range_endpoints_and_first_layer_zero_are_accepted(sim, fake_dssat):
    analysis(sim)["layers"] = [dict(depth=15, bulk_density=10, organic_carbon=100,
        total_nitrogen=10, ph_water=14, ph_buffer=14, extractable_p=0,
        exchangeable_k=0, stable_carbon=99.99), dict(depth=30, organic_carbon=0,
        total_nitrogen=0, extractable_p=1, exchangeable_k=1, stable_carbon=0)]
    assert sim.check(False) == []
    sim.run()
    assert "*SOIL ANALYSIS" in copied(sim, fake_dssat).decode("latin-1")


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_missing_section_is_inserted_and_omitted_values_are_minus99(sim, fake_dssat, newline):
    original = sim.filex.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline)
    sim.filex.write_bytes(original)
    before, data_before = snapshot(sim.filex.parent), deepcopy(sim.management)
    assert sim.check(False) == []
    assert snapshot(sim.filex.parent) == before
    sim.run()
    written = copied(sim, fake_dssat)
    text = written.decode("latin-1").replace(newline.decode(), "\n")
    assert text.index("*SOIL ANALYSIS") < text.index("*INITIAL CONDITIONS")
    assert _section_row(text, "TREATMENTS", "N", 2, ("SA",))["SA"] == "1"
    block = section(text).splitlines()[1:6]
    assert block[0] == HEADER and block[2] == LAYERS
    assert block[1][:3] == " 1 " and block[1][3:8] == "82056"
    assert block[1][8:26] == "   -99" * 3 and block[1][26:].strip() == "-99"
    assert block[3][3:8] == "   15" and block[3][8:56] == "   -99" * 8
    assert block[3][51:56] == "  -99"  # IPSLAN's (51X,F6.0), with a padded final blank.
    restored = written.replace(newline.join([b"*SOIL ANALYSIS", *(s.encode() for s in block), b""]) + newline, b"", 1)
    old = next(s for s in original.splitlines() if s.startswith(b" 2 1 0 0"))
    assert restored.replace(old[:40] + b"  1" + old[43:], old, 1) == original
    assert sim.filex.read_bytes() == original and sim.management == data_before


@pytest.mark.parametrize("highest,prefix", [(0, ""), (9, " 9 "), (9, "  9")])
def test_full_width_cells_and_level_columns(sim, fake_dssat, highest, prefix):
    if highest:
        text = sim.filex.read_text(encoding="latin-1")
        old = f"*SOIL ANALYSIS\n{HEADER}\n{prefix}82055   -99   -99   -99   -99\n{LAYERS}\n{prefix}   15" + "   -99" * 8 + "\n\n"
        sim.filex.write_text(text.replace("*INITIAL CONDITIONS", old + "*INITIAL CONDITIONS"), encoding="latin-1")
    analysis(sim).update(ph_buffer_method="SA005", p_method="IB001", k_method="SA001")
    analysis(sim)["layers"] = [dict(depth=99999, bulk_density=1.234, organic_carbon=12.34,
        total_nitrogen=0.123, ph_water=12.34, ph_buffer=12.35,
        extractable_p=999.9, exchangeable_k=888.8, stable_carbon=99.99)]
    assert sim.check(False) == []
    sim.run()
    block = section(copied(sim, fake_dssat).decode("latin-1")).rsplit(HEADER, 1)[1].splitlines()
    prefix = "10 " if highest else " 1 "
    assert block[1][:3] == block[3][:3] == prefix
    assert int(block[1][:2]) == int(block[1][:3]) == highest + 1
    assert block[1][3:8] == "82056"
    assert block[1][9:14] == "SA005" and block[1][15:20] == "IB001" and block[1][21:26] == "SA001"
    row = block[3]
    assert row[3:8] == "99999"
    for left, right, expected in [(9, 14, "1.234"), (15, 20, "12.34"), (21, 26, "0.123"),
        (27, 32, "12.34"), (33, 38, "12.35"), (39, 44, "999.9"), (45, 50, "888.8"), (51, 56, "99.99")]:
        assert row[left:right] == expected and row[left - 1] == " "


def test_existing_levels_are_appended_and_only_selected_treatment_repointed(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    old = f"*SOIL ANALYSIS\n{HEADER}\n 3 82055   -99   -99   -99   -99\n{LAYERS}\n 3    15" + "   -99" * 8 + "\n\n"
    text = text.replace("*INITIAL CONDITIONS", old + "*INITIAL CONDITIONS")
    row = next(s for s in text.splitlines() if s.startswith(" 2 1 0 0"))
    text = text.replace(row, row[:40] + "  3" + row[43:])
    sim.filex.write_text(text, encoding="latin-1")
    sim.management["treatments"][1] = {"soil_analysis": deepcopy(analysis(sim))}
    sim.run()
    written = copied(sim, fake_dssat).decode("latin-1").replace("\r\n", "\n")
    assert section(written).count(HEADER) == 2 and " 4 82056" in section(written)
    assert old.strip() in written
    for number in range(1, 7):
        expected = "4" if number == 2 else "0"
        assert _section_row(written, "TREATMENTS", "N", number, ("SA",))["SA"] == expected


def test_off_only_sets_selected_sa_to_zero(sim, fake_dssat):
    original = sim.filex.read_bytes()
    row = next(s for s in original.splitlines() if s.startswith(b" 2 1 0 0"))
    inherited = original.replace(row, row[:40] + b"  3" + row[43:])
    sim.filex.write_bytes(inherited)
    sim.management["treatments"][2]["soil_analysis"] = "off"
    sim.run()
    assert copied(sim, fake_dssat) == original
    assert sim.filex.read_bytes() == inherited


def test_omitted_section_keeps_inherited_bytes(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    old = f"*SOIL ANALYSIS\n{HEADER}\n  982055   -99   -99   -99   -99\n{LAYERS}\n  9   15" + "   -99" * 8 + "\n\n"
    text = text.replace("*INITIAL CONDITIONS", old + "*INITIAL CONDITIONS")
    row = next(s for s in text.splitlines() if s.startswith(" 2 1 0 0"))
    sim.filex.write_bytes(text.replace(row, row[:40] + "  9" + row[43:]).encode("latin-1"))
    sim.management = {"treatments": {2: {}}}
    original = sim.filex.read_bytes()
    sim.run()
    assert copied(sim, fake_dssat) == original


def test_reused_level_removes_inherited_i3_rows_and_keeps_referenced_levels(sim, fake_dssat):
    text = sim.filex.read_text(encoding="latin-1")
    old = "*SOIL ANALYSIS\n"
    for level in (1, 10, 99):
        old += f"{HEADER}\n{level:3d}82055   -99   -99   -99   -99\n{LAYERS}\n{level:3d}   15" + "   -99" * 8 + "\n"
    text = text.replace("*INITIAL CONDITIONS", old + "\n*INITIAL CONDITIONS")
    for number, level in ((1, 10), (2, 99)):
        row = next(s for s in text.splitlines() if s.startswith(f" {number} 1 0 0"))
        text = text.replace(row, row[:40] + f"{level:3d}" + row[43:])
    sim.filex.write_bytes(text.encode("latin-1"))
    assert sim.check(False) == []
    sim.run()
    written = copied(sim, fake_dssat).decode("latin-1")
    block = section(written)
    assert "  182055" not in block and "  1   15" not in block
    assert " 1082055" in block and " 10   15" in block
    assert " 9982055" in block and " 1 82056" in block
    assert _section_row(written, "TREATMENTS", "N", 1, ("SA",))["SA"] == "10"
    assert _section_row(written, "TREATMENTS", "N", 2, ("SA",))["SA"] == "1"


@pytest.mark.parametrize("following", ["INITIAL CONDITIONS", "PLANTING DETAILS",
    "IRRIGATION AND WATER MANAGEMENT", "FERTILIZERS (INORGANIC)",
    "RESIDUES AND ORGANIC FERTILIZER", "CHEMICALS", "TILLAGE AND ROTATIONS",
    "HARVEST DETAILS", "SIMULATION CONTROLS"])
@pytest.mark.parametrize("first", ["SOIL ANALYSIS", "ENVIRONMENT MODIFICATIONS"])
def test_section_order_when_both_new_sections_are_absent(following, first):
    names = [following] if following == "SIMULATION CONTROLS" else [following, "HARVEST DETAILS", "SIMULATION CONTROLS"]
    names = list(dict.fromkeys(names))
    lines = [s + "\n" for name in names for s in ["*" + name, "! preserved", ""]]
    for name in [first, "ENVIRONMENT MODIFICATIONS" if first == "SOIL ANALYSIS" else "SOIL ANALYSIS"]:
        lines = _insert_section(lines, name, ["! added"])
    text = "".join(lines)
    assert text.index("*SOIL ANALYSIS") < text.index("*" + following)
    assert text.index("*SOIL ANALYSIS") < text.index("*ENVIRONMENT MODIFICATIONS")
    assert text.index("*ENVIRONMENT MODIFICATIONS") < text.index("*HARVEST DETAILS" if "HARVEST DETAILS" in names else "*SIMULATION CONTROLS")


def test_filex_template_simulation_writes_soil_analysis(data, rows, installed):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
        management={"treatments": {1: {"soil_analysis": dict(date="2021-03-01",
            p_method="IB001", layers=[dict(depth=30, extractable_p=12.5)])}}})
    assert sim.check(False) == []
    result = sim.run()
    text = (result.run_dir.parent / "TEST2101.MZX").read_text()
    assert _section_row(text, "TREATMENTS", "N", 1, ("SA",))["SA"] == "1"
    assert "21060" in section(text) and "12.5" in section(text)


def test_rotation_components_reject_soil_analysis(rotation_sim):
    rotation_sim.management["treatments"][1]["rotation"] = {3: {"soil_analysis": "off"}}
    assert any("rotation component 3: unknown key 'soil_analysis'" in p and "Use only" in p
               for p in rotation_sim.check(False))


def test_management_template_example_is_uncommented_checked_and_written(sim, tmp_path, fake_dssat):
    pytest.importorskip("yaml")
    path = tmp_path / "management.yaml"
    write_management_template(path, filex=sim.filex)
    lines, active = [], False
    for line in path.read_text().splitlines():
        if line.startswith("    # soil_analysis:"):
            active = True
        elif active and not line.startswith("    #   "):
            active = False
        lines.append(line.replace("    # ", "    ", 1) if active else line)
    assert any(s.startswith("    soil_analysis:") for s in lines)
    path.write_text("\n".join(lines) + "\n")
    sim.weather = [dict(sim.weather[0], date=(date(1982, 2, 25) + timedelta(days=i)).isoformat())
                   for i in range(35)]
    sim.management = path
    assert sim.check(False) == []
    sim.run()
    assert "*SOIL ANALYSIS" in copied(sim, fake_dssat).decode("latin-1")
