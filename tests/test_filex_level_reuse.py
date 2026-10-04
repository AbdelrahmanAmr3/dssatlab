"""An edit at level 99 replaces only levels free after repointing."""

import pytest

from dssatlab.filex_write import _write_management
from dssatlab.filex_write import _event_text, _planting_text
from dssatlab.cultivar import _cultivar_text


CASES = [
    pytest.param("planting", "MP", "PLANTING DETAILS", {
        "date": "1982-02-25", "population": 8, "method": "S",
        "distribution": "R", "row_spacing": 75, "depth": 4,
    }, [
        ("@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE"
         "  PENV  PLPH  SPRL                        PLNAME",
         " 82057   -99   7.2   7.2     S     R    61     0     7   -99"
         "   -99   -99   -99     0                        -99"),
    ], ["82056 -99 8 8 S R 75 -99 4 -99 -99 -99 -99 -99 -99"], id="planting"),
    pytest.param("irrigation", "MI", "IRRIGATION AND WATER MANAGEMENT", [
        {"date": "1982-02-25", "amount": 20, "method": "IR001"},
    ], [
        ("@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME",
         "     1   -99   -99   -99   -99   -99   -99    -99"),
        ("@I IDATE  IROP IRVAL", " 82057 IR001    10"),
    ], ["1 -99 -99 -99 -99 -99 -99 -99", "82056 IR001 20"], id="irrigation"),
    pytest.param("cultivar", "CU", "CULTIVARS", {"crop": "MZ", "code": "IB0060"}, [
        ("@C CR INGENO CNAME", " MZ IB0035 OLD"),
    ], ["MZ IB0060 -99"], id="cultivar"),
    pytest.param("initial_conditions", "IC", "INITIAL CONDITIONS", {
        "date": "1982-02-25", "previous_crop": "WH", "residue_mass": 1250,
        "layers": [{"depth": 15, "water": 0.25, "nh4": 1, "no3": 2}],
    }, [
        ("@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME",
         "    MZ 82057   -99   -99   -99   -99   -99   900   -99   -99   -99   -99    -99"),
        ("@C  ICBL  SH2O  SNH4  SNO3", "    30   0.3     0   3.5"),
    ], ["WH 82056 -99 -99 -99 -99 -99 1250 -99 -99 -99 -99 -99",
        "15 0.25 1 2"], id="initial-conditions"),
    pytest.param("controls", "SM", "SIMULATION CONTROLS", {"output_interval": 2}, [
        ("@N GENERAL START SDATE FROPT", " GE          S 82056     1"),
        ("@N OUTPUTS FROPT", " OU          1"),
        ("@N METHODS", " ME"),
    ], ["GE S 82056 1", "OU 2", "ME"], id="controls"),
]


def filex_text(section, blocks, highest=99):
    treatments = "*TREATMENTS\n@N R MP MI CU IC SM\n" + "".join(
        f"{number:3d}1" + f"{number:3d}" * 5 + "\n" for number in range(1, 100))
    body = "*" + section + "\n" + "".join(
        header + "\n" + "".join(f"{level:2d}" + row + "\n"
                                  for level in range(1, highest + 1))
        for header, row in blocks)
    if section != "SIMULATION CONTROLS":
        # Old rows of the chosen level also occur under repeated headers.
        body += "".join(header + "\n 3" + row + "\n" for header, row in blocks)
    return treatments + body + "! keep caf\xe9\n*END\n! final comment without newline\xff"


def level_rows(text, section, level):
    body = text.split("*" + section + "\n", 1)[1].split("*", 1)[0]
    return [line for line in body.splitlines() if line[:2].strip() == str(level)]


@pytest.mark.parametrize("key,column,section,data,blocks,expected", CASES)
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_reuses_only_level_freed_by_this_edit(
        tmp_path, key, column, section, data, blocks, expected, newline):
    original = filex_text(section, blocks)
    path = tmp_path / "TEST8201.MZX"
    path.write_bytes(original.replace("\n", newline).encode("latin-1"))
    _write_management(path, 3, {"treatments": {3: {key: data}}})
    written = path.read_bytes().decode("latin-1").replace(newline, "\n")
    assert [row[2:].split() for row in level_rows(written, section, 3)] == [
        row.split() for row in expected]
    assert written.split("*" + section, 1)[0] == original.split("*" + section, 1)[0]
    # Every other level and its order survive, even when its headers repeat.
    for level in (1, 2, 4, 98, 99):
        assert level_rows(written, section, level) == level_rows(original, section, level)
    assert written.endswith("! keep caf\xe9\n*END\n! final comment without newline\xff")


@pytest.mark.parametrize("key,column,section,data,blocks,expected",
                         [case for case in CASES if case.id != "controls"])
def test_reused_level_drops_zero_padded_rows(tmp_path, key, column, section, data, blocks, expected):
    original = filex_text(section, blocks)
    padded = "".join(header + "\n03" + row + "\n" for header, row in blocks)
    original = original.replace("! keep", padded + "! keep", 1)
    path = tmp_path / "TEST8201.MZX"
    path.write_bytes(original.encode("latin-1"))
    _write_management(path, 3, {"treatments": {3: {key: data}}})
    written = path.read_bytes().decode("latin-1")
    body = written.split("*" + section + "\n", 1)[1].split("*", 1)[0]
    assert not any(line.startswith("03") for line in body.splitlines())
    assert [row[2:].split() for row in level_rows(written, section, 3)] == [
        row.split() for row in expected]


@pytest.mark.parametrize("key,column,section,data,blocks,expected", CASES)
def test_shared_level_is_protected_and_lowest_free_level_is_used(
        tmp_path, key, column, section, data, blocks, expected):
    original = filex_text(section, blocks)
    original = original.replace("  51" + "  5" * 5, "  51" + "  3" * 5)
    path = tmp_path / "TEST8201.MZX"
    path.write_bytes(original.encode("latin-1"))
    _write_management(path, 3, {"treatments": {3: {key: data}}})
    written = path.read_bytes().decode("latin-1")
    target = next(line for line in written.splitlines() if line.startswith("  31"))
    field = ["MP", "MI", "CU", "IC", "SM"].index(column)
    assert target[4 + field * 3:7 + field * 3] == "  5"
    assert level_rows(written, section, 3) == level_rows(original, section, 3)
    assert [row[2:].split() for row in level_rows(written, section, 5)] == [
        row.split() for row in expected]
    assert "  51" + "  3" * 5 in written


@pytest.mark.parametrize("key,column,section,data,blocks,expected", CASES)
def test_no_free_level_preserves_existing_overflow_problem(
        tmp_path, key, column, section, data, blocks, expected):
    original = filex_text(section, blocks).replace(
        "*" + section, "1001" + "  3" * 5 + "\n*" + section, 1)
    path = tmp_path / "TEST8201.MZX"
    path.write_bytes(original.encode("latin-1"))
    width = 3 if key == "irrigation" else 2
    with pytest.raises(ValueError, match=f"value '100' does not fit its {width}-character field"):
        _write_management(path, 3, {"treatments": {3: {key: data}}})
    assert path.read_bytes() == original.encode("latin-1")


NEW_ROWS = {
    "planting": ["99 82056   -99     8     8     S     R    75   -99     4   -99"
                 "   -99   -99   -99   -99                           -99"],
    "irrigation": ["99     1   -99   -99   -99   -99   -99   -99    -99",
                   "99 82056 IR001    20"],
    "cultivar": ["99 MZ IB0060   -99"],
    "initial_conditions": [
        "99    WH 82056   -99   -99   -99   -99   -99  1250   -99   -99   -99   -99    -99",
        "99    15  0.25     1     2"],
    "controls": ["99 GE          S 82056     1", "99 OU          2", "99 ME"],
}


@pytest.mark.parametrize("key,column,section,data,blocks,expected", CASES)
def test_below_99_matches_original_append_bytes(tmp_path, key, column, section, data, blocks, expected):
    original = filex_text(section, blocks, highest=98)
    target = "  31" + "  3" * 5
    field = ["MP", "MI", "CU", "IC", "SM"].index(column)
    changed = target[:4 + field * 3] + " 99" + target[7 + field * 3:]
    added = NEW_ROWS[key]
    if key in ("irrigation", "initial_conditions", "controls"):
        added = [line for (header, _), row in zip(blocks, added) for line in (header, row)]
    if key == "controls":
        added = ["", *added]
    expected_bytes = original.replace(target, changed, 1).replace(
        "! keep caf\xe9", "\n".join(added) + "\n! keep caf\xe9").encode("latin-1")
    path = tmp_path / "TEST8201.MZX"
    path.write_bytes(original.encode("latin-1"))
    _write_management(path, 3, {"treatments": {3: {key: data}}})
    assert path.read_bytes() == expected_bytes


@pytest.mark.parametrize("key,column,section,data,blocks,expected", CASES[:3])
@pytest.mark.parametrize("shared", [False, True])
def test_other_rotation_components_keep_their_levels(
        tmp_path, key, column, section, data, blocks, expected, shared):
    original = filex_text(section, blocks)
    components = "*TREATMENTS\n@N R MP MI CU IC SM\n" + "".join(
        f" 1{number:2d}" + f"{number:3d}" * 5 + "\n" for number in range(1, 100))
    if shared:
        components = components.replace(" 1 1" + "  1" * 5, " 1 1" + " 10" * 5)
    original = components + "*" + section + original.split("*" + section, 1)[1]
    path = tmp_path / "TEST8201.SQX"
    path.write_bytes(original.encode("latin-1"))
    writer = {"planting": _planting_text, "irrigation": _event_text, "cultivar": _cultivar_text}[key]
    written = writer(path.read_bytes().decode("latin-1"), 1, data, rotation=10)
    reused = 1 if shared else 10
    target = " 110" + " 10" * 5
    field = ["MP", "MI", "CU", "IC", "SM"].index(column)
    changed = target[:4 + field * 3] + f"{reused:3d}" + target[7 + field * 3:]
    assert written.split("*" + section, 1)[0] == components.replace(target, changed, 1)
    assert [row[2:].split() for row in level_rows(written, section, reused)] == [
        row.split() for row in expected]
    if shared:
        assert level_rows(written, section, 10) == level_rows(original, section, 10)
    assert path.read_bytes() == original.encode("latin-1")


@pytest.mark.parametrize("key,column,section,data,blocks,expected",
                         [case for case in CASES if case.id == "irrigation"])
def test_reused_level_drops_rows_under_abbreviated_header(
        tmp_path, key, column, section, data, blocks, expected):
    original = filex_text(section, blocks).replace("*" + section, "*IRRIGATION", 1)
    path = tmp_path / "TEST8201.MZX"
    path.write_bytes(original.encode("latin-1"))
    _write_management(path, 3, {"treatments": {3: {key: data}}})
    written = path.read_bytes().decode("latin-1")
    assert [row[2:].split() for row in level_rows(written, "IRRIGATION", 3)] == [
        row.split() for row in expected]
