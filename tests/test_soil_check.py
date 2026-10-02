"""Soil data checks through the public Simulation and soil template."""

import csv
from copy import deepcopy
from pathlib import Path

import pytest

import dssatlab


REQUIRED = ("soil_id", "salb", "slro", "sldr", "slpf", "slb",
            "slll", "sdul", "ssat", "srgf")
OPTIONAL = ("slnf", "ssks", "sbdm", "sloc", "slmh", "slcl", "slsi", "slcf",
            "slni", "slhw", "slhb", "scec", "sadc", "slu1", "smhb", "smpx", "smke")
PROFILE = ("soil_id", "salb", "slro", "sldr", "slnf", "slpf",
           "slu1", "smhb", "smpx", "smke")
SAMPLE = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 RAINFED LOW NITROGEN       1  1  0  1  1  1  1  0  0  0  0  0  1
 2 1 0 0 RAINFED HIGH NITROGEN      1  2  0  1  1  1  2  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910214 Field section
 2 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  OTHER12345 Other field
@L ...........XCRD ...........YCRD .....ELEV
 1             -99             -99       -99

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 N X IRRIGATION
"""


@pytest.fixture
def simulation(tmp_path):
    path = tmp_path / "UFGA8201.MZX"
    path.write_text(SAMPLE, encoding="latin-1")
    weather = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                    date="1982-02-25", srad=20, tmax=25, tmin=10, rain=0)]
    return dssatlab.Simulation(path, 1, weather)


@pytest.fixture
def rows():
    return [dict(soil_id="IBMZ910214", salb=0.13, slro=60, sldr=0.5, slnf=1,
                 slpf=1, slb=depth, slll=0.1, sdul=0.24, ssat=0.45, srgf=1,
                 ssks=6, sbdm=1.3, sloc=1.5) for depth in (5, 15, 30)]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("form", ["rows", "path", "str"])
def test_valid_soil_is_unchanged_and_checks_write_nothing(simulation, rows, tmp_path, form):
    rows = [dict(reversed([(key, str(value)) for key, value in row.items()])) for row in rows]
    path = write_csv(tmp_path / "soil.csv", rows)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    simulation.soil = {"rows": rows, "path": path, "str": str(path)}[form]
    before_rows = deepcopy(rows)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    assert simulation.check() == []
    assert rows == before_rows
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before


@pytest.mark.parametrize("column", REQUIRED)
@pytest.mark.parametrize("form", ["rows", "csv"])
def test_missing_required_columns(simulation, rows, tmp_path, column, form):
    del rows[0][column]
    simulation.soil = rows if form == "rows" else write_csv(tmp_path / "soil.csv", rows[:1])
    assert any(column in p and "missing" in p and "Add" in p for p in simulation.check())


@pytest.mark.parametrize("column", ["SLB", "site", "country", "latitude", "longitude", "extra"])
def test_unknown_columns(simulation, rows, column):
    rows[1][column] = 1
    simulation.soil = rows
    assert any(column in p and "row 3" in p and "unknown" in p for p in simulation.check())


@pytest.mark.parametrize("column", REQUIRED[1:] + tuple(
    name for name in OPTIONAL if name not in ("slmh", "smhb", "smpx", "smke")))
@pytest.mark.parametrize("value", ["oops", "nan", float("inf"), "-inf",
                                 pytest.param(10 ** 5000, id="huge-integer")])
def test_invalid_numbers(simulation, rows, column, value):
    rows[1][column] = value
    simulation.soil = rows
    assert any(column in p and "row 3" in p and "finite number" in p for p in simulation.check())


@pytest.mark.parametrize("column", REQUIRED[1:])
@pytest.mark.parametrize("value", ["", "  ", None])
def test_empty_required_values(simulation, rows, column, value):
    rows[1][column] = value
    simulation.soil = rows
    assert any(column in p and "row 3" in p and "non-empty" in p for p in simulation.check())


@pytest.mark.parametrize("column", OPTIONAL)
def test_optional_numbers_and_defaults(simulation, rows, column):
    simulation.soil = rows
    for value in ("", None, "  ", -99, 0.6):
        for row in rows:
            row[column] = value
        assert simulation.check() == []
    rows[0].pop(column)
    rows[1][column], rows[2][column] = "", -99
    assert simulation.check() == []


@pytest.mark.parametrize("column", PROFILE)
def test_profile_values_must_be_identical(simulation, rows, column):
    rows[1][column] = "OTHER12345" if column == "soil_id" else 0.3
    simulation.soil = rows
    assert any(column in p and "row 3" in p and "identical" in p for p in simulation.check())


@pytest.mark.parametrize("value", ["", "ABCDEFGHIJK", "A B", "A-B", "é", 123, None])
def test_invalid_soil_id(simulation, rows, value):
    rows[0]["soil_id"] = value
    simulation.soil = rows
    assert any("soil_id" in p and "row 2" in p and "ASCII" in p for p in simulation.check())


@pytest.mark.parametrize("value", ["A", "a1B2c3D4e5"])
def test_soil_id_length_boundaries(simulation, rows, value):
    simulation.filex.write_text(SAMPLE.replace("IBMZ910214", f"{value:<10}"), encoding="latin-1")
    simulation.soil = [dict(row, soil_id=value) for row in rows]
    assert simulation.check() == []


@pytest.mark.parametrize("column,low,high,unit", [
    ("sbdm", 0.5, 2.5, "g/cm3"), ("sloc", 0, 100, "%"), ("srgf", 0, 1, "fraction"),
    ("ssks", 0, 500, "cm/h"), ("salb", 0, 1, "fraction"), ("slro", 0, 100, "dimensionless"),
    ("sldr", 0, 1, "fraction/day"), ("slnf", 0, 1, "factor"), ("slpf", 0, 1, "factor"),
])
def test_physical_bounds(simulation, rows, column, low, high, unit):
    simulation.soil = rows[:1]
    for value in (low - 0.1, high + 0.1):
        rows[0][column] = value
        assert any(column in p and "row 2" in p and f"{low} to {high}" in p
                   and unit in p for p in simulation.check())
    for value in (low, high):
        rows[0][column] = value
        assert simulation.check() == []


@pytest.mark.parametrize("column", ["slll", "sdul", "ssat"])
@pytest.mark.parametrize("value", [-0.1, 0, 1, 1.1])
def test_water_fractions_strict_bounds(simulation, rows, column, value):
    rows[1][column] = value
    simulation.soil = rows
    assert any(column in p and "row 3" in p and "strictly between" in p for p in simulation.check())


@pytest.mark.parametrize("values", [(0.24, 0.24, 0.45), (0.3, 0.24, 0.45),
                                    (0.1, 0.45, 0.45), (0.1, 0.5, 0.45)])
def test_water_fraction_order(simulation, rows, values):
    rows[1].update(zip(("slll", "sdul", "ssat"), values))
    simulation.soil = rows
    assert any("row 3" in p and "slll < sdul < ssat" in p for p in simulation.check())


@pytest.mark.parametrize("depths,word", [([0, 15, 30], "positive"), ([-1, 15, 30], "positive"),
                                      ([15, 5, 30], "increasing"), ([5, 15, 5], "duplicate")])
def test_layer_depths(simulation, rows, depths, word):
    for row, depth in zip(rows, depths):
        row["slb"] = depth
    simulation.soil = rows
    assert any("slb" in p and "row" in p and word in p for p in simulation.check())


@pytest.mark.parametrize("source,word", [([], "layer"), ([None], "dict"), (42, "CSV"), ({}, "CSV")])
def test_bad_soil_source(simulation, source, word):
    simulation.soil = source
    assert any("soil data" in p.lower() and word in p for p in simulation.check())


@pytest.mark.parametrize("kind", ["missing", "empty", "header", "encoding", "quotes", "duplicate", "short", "long"])
def test_bad_soil_csv(simulation, rows, tmp_path, kind):
    path = tmp_path / "soil.csv"
    if kind != "missing":
        write_csv(path, rows)
        text = path.read_text(encoding="utf-8")
        header, *records = text.splitlines()
        contents = {"empty": b"", "header": header.encode(), "encoding": b"\xff",
                    "quotes": b'"unclosed', "duplicate": (header + ",slb\n" + records[0] + ",5\n").encode(),
                    "short": (header + "\nIBMZ910214\n").encode(),
                    "long": (text + records[0] + ",extra\n").encode()}
        path.write_bytes(contents[kind])
    simulation.soil = path
    problems = simulation.check()
    assert problems and all("soil" in p.lower() for p in problems)
    if kind == "duplicate":
        assert any("slb" in p and "repeated" in p and "line 1" in p for p in problems)


@pytest.mark.parametrize("soil_id", ["OTHER12345", "ibmz910214"])
def test_filex_soil_id_mismatch(simulation, rows, soil_id):
    simulation.soil = [dict(row, soil_id=soil_id) for row in rows]
    problems = simulation.check()
    assert len(problems) == 1
    assert all(word in problems[0] for word in (soil_id, "IBMZ910214", "equal", "case-sensitive"))


@pytest.mark.parametrize("replacement", ["          ", "-99       "])
def test_unreadable_filex_soil_id_only_required_with_soil(simulation, rows, replacement):
    simulation.filex.write_text(SAMPLE.replace("IBMZ910214", replacement), encoding="latin-1")
    assert simulation.check() == []
    simulation.soil = rows
    assert any("ID_SOIL" in p and "Supply" in p for p in simulation.check())
    simulation.filex.write_text(SAMPLE.replace("ID_SOIL", "OTHER.."), encoding="latin-1")
    assert any("ID_SOIL" in p for p in simulation.check())
    simulation.soil = None
    assert simulation.check() == []


def test_selected_field_and_partial_filex_values(simulation, rows):
    simulation.treatment = 2
    simulation.soil = [dict(row, soil_id="OTHER12345") for row in rows]
    assert simulation.check() == []
    simulation.filex.write_text(SAMPLE.replace("UFGA       -99", "UFG        -99")
                               .replace("82056", "bad!!"), encoding="latin-1")
    simulation.soil[0]["sbdm"] = 10
    simulation.weather[0]["rain"] = -1
    for row in simulation.soil:
        row["soil_id"] = "IBMZ910214"
    problems = simulation.check()
    for word in ("sbdm", "rain", "WSTA", "SDATE", "ID_SOIL"):
        assert any(word in p for p in problems)


def test_construction_only_stores_soil(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("construction must not read files")
    monkeypatch.setattr(Path, "open", forbidden)
    soil, executable = object(), object()
    simulation = dssatlab.Simulation(tmp_path / "missing.MZX", 1, [], executable, soil=soil)
    assert simulation.soil is soil and simulation.executable is executable


def test_soil_template_passes_and_refuses_overwrite(simulation, tmp_path):
    path = tmp_path / "soil.csv"
    dssatlab.write_soil_template(str(path))
    simulation.soil = path
    assert simulation.check() == []
    original = path.read_bytes()
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3 and list(rows[0]) == list(REQUIRED + OPTIONAL) + ["scom"]
    assert {row["scom"] for row in rows} == {"-99"}
    assert {row["soil_id"] for row in rows} == {"IBMZ910214"}
    for destination in (path, tmp_path):
        with pytest.raises(dssatlab.DSSATError, match="exists.*another path"):
            dssatlab.write_soil_template(destination)
    assert path.read_bytes() == original


@pytest.mark.parametrize("treatment", [None, 10 ** 5000], ids=["none", "huge-integer"])
def test_soil_and_unreadable_filex_problems_are_combined(simulation, rows, treatment):
    simulation.treatment, simulation.soil = treatment, rows
    rows[1]["slb"] = -1
    problems = simulation.check()
    for word in ("treatment number", "ID_SOIL", "slb"):
        assert any(word in p for p in problems)


def test_bad_soil_checks_reread_and_write_nothing(simulation, rows, tmp_path):
    path = write_csv(tmp_path / "soil.csv", rows)
    simulation.soil = path
    assert simulation.check() == []
    rows[1]["sbdm"] = 10
    write_csv(path, rows)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    assert any("sbdm" in p and "row 3" in p for p in simulation.check())
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before


def test_soil_is_keyword_only_so_v03_positional_calls_still_work(tmp_path):
    simulation = dssatlab.Simulation(tmp_path / "x.MZX", 1, [], "dscsm048")
    assert simulation.executable == "dscsm048" and simulation.soil is None
    with pytest.raises(TypeError):
        dssatlab.Simulation(tmp_path / "x.MZX", 1, [], None, [])


def test_id_soil_read_with_tight_or_last_header_column(simulation, rows):
    simulation.soil = rows
    tight = SAMPLE.replace("ID_SOIL    FLNAME", "ID_SOIL FLNAME")
    tight = tight.replace("IBMZ910214 Field section", "IBMZ910214 Field")
    simulation.filex.write_text(tight, encoding="latin-1")
    # The ID cannot fit before the next column, but nothing else may break.
    assert not any("WSTA" in p or "SDATE" in p or "TREATMENTS" in p
                   for p in simulation.check())
    last = SAMPLE.replace("  ID_SOIL    FLNAME", "  ID_SOIL").replace(
        " Field section", "").replace(" Other field", "")
    simulation.filex.write_text(last, encoding="latin-1")
    assert simulation.check() == []
    simulation.treatment = 2
    simulation.soil = [dict(row, soil_id="OTHER12345") for row in rows]
    assert simulation.check() == []
