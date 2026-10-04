"""Soil DataFrames and equivalent CSVs through Simulation.check()."""

import builtins
import csv
from copy import deepcopy
import math
import subprocess
import sys
from types import SimpleNamespace

import pytest

import dssatlab


class FakeDataFrame:
    def __init__(self, rows, columns=None):
        self.rows = rows
        self.columns = list(rows[0]) if columns is None else columns

    def to_dict(self, orient):
        assert orient == "records"
        return [dict(row) for row in self.rows]


SAMPLE = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 RAINFED LOW NITROGEN       1  1  0  1  1  1  1  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910214 Field section

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


def check(simulation, soil):
    simulation.soil = soil
    return simulation.check()


def write_csv(path, rows, columns=None):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_valid_dataframe_is_unchanged_and_imports_no_pandas(
        simulation, rows, tmp_path, monkeypatch):
    original_import = builtins.__import__

    def without_pandas(name, *args, **kwargs):
        if name.split(".")[0] == "pandas":
            pytest.fail("dssatlab must not import pandas")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_pandas)
    rows = [dict(reversed(list(row.items()))) for row in rows]
    frame = FakeDataFrame(rows)
    before_rows = deepcopy(rows)
    path = write_csv(tmp_path / "soil.csv", rows)
    before_files = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    assert check(simulation, frame) == check(simulation, path) == []
    assert rows == before_rows
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before_files
    rows[1]["slb"] = 5
    assert any("duplicate" in p and "row 3" in p for p in check(simulation, frame))


def test_package_imports_when_pandas_is_unavailable():
    script = """
import sys
class NoPandas:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'pandas':
            raise AssertionError('dssatlab must not import pandas')
sys.meta_path.insert(0, NoPandas())
import dssatlab
assert 'pandas' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_columns_and_all_row_problems_match_csv(simulation, rows, tmp_path):
    for row in rows:
        row["SLPF"] = row.pop("slpf")
    rows[0]["slll"] = "oops"
    rows[1].update(slb=5, sbdm=10, salb=0.2)
    rows[2].update(sdul=0.1, ssat=1)
    problems = check(simulation, FakeDataFrame(rows))
    assert problems == check(simulation, write_csv(tmp_path / "soil.csv", rows))
    for words in (("missing", "'slpf'", "line 1"),
                  ("unknown", "'SLPF'", "line 1"),
                  ("'slll'", "row 2", "finite number"),
                  ("'slb'", "row 3", "duplicate", "row 2"),
                  ("'sbdm'", "row 3", "allowed range"),
                  ("'salb'", "row 3", "identical", "row 2"),
                  ("row 4", "slll < sdul < ssat")):
        assert any(all(word in p for word in words) for p in problems)


@pytest.mark.parametrize("duplicate", [False, True])
def test_declared_columns_match_csv(simulation, rows, tmp_path, duplicate):
    columns = list(rows[0])
    if duplicate:
        columns += ["slb"]
    else:
        rows = []
        columns.remove("slb")
        columns += ["SLB"]
    problems = check(simulation, FakeDataFrame(rows, columns))
    assert problems == check(simulation, write_csv(tmp_path / "soil.csv", rows, columns))
    if duplicate:
        assert len(problems) == 1 and "repeated in line 1" in problems[0]
    else:
        for word in ("missing", "unknown", "no layer rows"):
            assert any(word in p for p in problems)


@pytest.mark.parametrize("soil_id", [1234567890, "0012345678"])
def test_numeric_soil_id_matches_filex_as_text(simulation, rows, tmp_path, soil_id):
    simulation.filex.write_text(SAMPLE.replace("IBMZ910214", str(soil_id)), encoding="latin-1")
    for row in rows:
        row["soil_id"] = soil_id
    frame = FakeDataFrame(rows)
    assert check(simulation, frame) == check(
        simulation, write_csv(tmp_path / "soil.csv", rows)) == []
    simulation.filex.write_text(SAMPLE, encoding="latin-1")
    problems = check(simulation, frame)
    assert problems == check(simulation, tmp_path / "soil.csv")
    assert len(problems) == 1 and "ID_SOIL" in problems[0]
    assert repr(str(soil_id)) in problems[0]
    assert rows[0]["soil_id"] == soil_id


@pytest.mark.parametrize("empty", [None, "", "  ", float("nan")])
def test_optional_empty_cells_default_to_minus_99(simulation, rows, tmp_path, empty):
    # slnf is profile-level: equality with -99 proves the parsed default.
    for row in rows:
        row["slnf"] = -99
    rows[1]["slnf"] = empty
    rows[1]["ssks"] = empty
    csv_rows = deepcopy(rows)
    csv_rows[1].update(slnf="", ssks="")
    assert check(simulation, FakeDataFrame(rows)) == check(
        simulation, write_csv(tmp_path / "soil.csv", csv_rows)) == []
    assert rows[1]["slnf"] is empty


@pytest.mark.parametrize("column,value", [
    ("slll", None), ("slll", float("nan")), ("ssks", "nan"),
    ("ssks", float("inf")), ("soil_id", 123.5), ("soil_id", None),
    ("soil_id", float("nan")),
])
def test_invalid_cells_match_csv(simulation, rows, tmp_path, column, value):
    rows[1][column] = value
    csv_rows = deepcopy(rows)
    if isinstance(value, float) and math.isnan(value):
        csv_rows[1][column] = ""
    problems = check(simulation, FakeDataFrame(rows))
    assert problems == check(simulation, write_csv(tmp_path / "soil.csv", csv_rows))
    assert any(column in p and "row 3" in p for p in problems)


def test_failed_conversion_returns_one_problem(simulation, rows, monkeypatch):
    frame = FakeDataFrame(rows)

    def fail(orient):
        raise RuntimeError("cannot convert records")

    monkeypatch.setattr(frame, "to_dict", fail)
    problems = check(simulation, frame)
    assert len(problems) == 1
    assert all(word in problems[0] for word in
               ("Cannot read soil data DataFrame", "cannot convert records", "Supply"))


@pytest.mark.parametrize("source", [SimpleNamespace(columns=[]),
                                    SimpleNamespace(to_dict=lambda orient: []),
                                    SimpleNamespace(columns=[], to_dict=None)])
def test_detection_requires_columns_and_callable_to_dict(simulation, source):
    problems = check(simulation, source)
    assert len(problems) == 1 and "Cannot read soil data" in problems[0]


def test_real_dataframe_matches_csv(simulation, rows, tmp_path):
    pd = pytest.importorskip("pandas")
    for row in rows:
        row.update(soil_id=1234567890, slnf=-99)
    rows[1].update(slnf=None, ssks=None)
    simulation.filex.write_text(SAMPLE.replace("IBMZ910214", "1234567890"), encoding="latin-1")
    frame = pd.DataFrame(rows, index=[10, 20, 30])
    before = frame.copy(deep=True)
    path = tmp_path / "soil.csv"
    frame.to_csv(path, index=False)
    assert check(simulation, frame) == check(simulation, path) == []
    pd.testing.assert_frame_equal(frame, before)
    frame.loc[20, "sbdm"] = 10
    frame.loc[30, "slb"] = 15
    frame.to_csv(path, index=False)
    problems = check(simulation, frame)
    assert problems == check(simulation, path)
    assert any("row 3" in p and "sbdm" in p for p in problems)
    assert any("row 4" in p and "duplicate" in p for p in problems)
