from datetime import date, timedelta
from pathlib import Path
import shutil

import pytest

import dssatlab
from dssatlab import DSSATOutputError


FIXTURES = Path(__file__).parent / "fixtures" / "output_files"
CASES = [
    ("soil_water", "SoilWat.OUT", date(1982, 2, 24), "SW1D", 0.020),
    ("plant_nitrogen", "PlantN.OUT", date(1982, 2, 26), "CNAD", 1.3),
    ("weather", "Weather.OUT", date(1982, 2, 25), "SRAD", 15.9),
]


@pytest.fixture(params=CASES, ids=[case[0] for case in CASES])
def daily(request):
    return request.param


def copy_output(tmp_path, kind, case="maize"):
    return shutil.copytree(FIXTURES / kind / case, tmp_path / kind)


def assert_error(run_dir, kind, filename, *details):
    with pytest.raises(DSSATOutputError) as caught:
        getattr(dssatlab, "read_" + kind)(run_dir)
    message = str(caught.value)
    for detail in (str(run_dir / filename), "Checked", "run directory",
                   "Check the run directory", "rerun DSSAT", *details):
        assert detail.lower() in message.lower()


@pytest.mark.parametrize("as_string", [False, True])
def test_real_daily_rows_preserve_columns_and_values(tmp_path, daily, as_string):
    kind, filename, start, column, last_value = daily
    run_dir = copy_output(tmp_path, kind)
    rows = getattr(dssatlab, "read_" + kind)(str(run_dir) if as_string else run_dir)
    assert len(rows) == 20
    assert [row["DATE"] for row in rows] == [start + timedelta(days=i) for i in range(20)]
    assert all(type(row["DATE"]) is date for row in rows)
    assert all((row["RUNNO"], row["TRNO"]) == (1, 1) for row in rows)
    assert rows[0]["YEAR"] == 1982
    assert rows[0]["DOY"] == start.timetuple().tm_yday
    assert rows[-1][column] == last_value
    assert type(rows[-1][column]) is float
    header = next(line for line in (run_dir / filename).read_text().splitlines()
                  if line.startswith("@"))
    assert set(rows[0]) == set(header[1:].split()) | {"DATE", "RUNNO", "TRNO"}
    if kind == "soil_water":
        assert [rows[-1][f"SW{i}D"] for i in range(1, 10)] == [
            0.020, 0.078, 0.087, 0.088, 0.088, 0.093, 0.092, 0.131, 0.259]
        assert rows[-1]["IR#C"] == 1
    elif kind == "plant_nitrogen":
        assert rows[-1]["VN%D"] == 3.29
    else:
        assert rows[0]["OZON7"] is None


@pytest.mark.parametrize("marker", ["-99", "-99.0", "-99.00"])
def test_daily_missing_values(tmp_path, daily, marker):
    kind, filename, _, column, _ = daily
    run_dir = copy_output(tmp_path, kind, "missing_value")
    path = run_dir / filename
    path.write_bytes(path.read_bytes().replace(b"-99.00", marker.rjust(6).encode()))
    rows = getattr(dssatlab, "read_" + kind)(run_dir)
    assert len(rows) == 20
    assert rows[-1][column] is None
    assert rows[0][column] is not None


@pytest.mark.parametrize("case,detail", [("no_header", "header"), ("truncated", "row")])
def test_broken_daily_files_never_return_partial_rows(tmp_path, daily, case, detail):
    kind, filename, *_ = daily
    assert_error(copy_output(tmp_path, kind, case), kind, filename, detail)


def test_missing_daily_file(tmp_path, daily):
    kind, filename, *_ = daily
    assert_error(tmp_path, kind, filename, "missing")


def test_daily_header_without_rows(tmp_path, daily):
    kind, filename, *_ = daily
    run_dir = copy_output(tmp_path, kind)
    path = run_dir / filename
    lines = path.read_bytes().splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(b"@"))
    path.write_bytes(b"\n".join(lines[:index + 1]) + b"\n")
    assert_error(run_dir, kind, filename, "no data rows")


def test_daily_two_runs_keep_their_own_identity(tmp_path, daily):
    kind, filename, *_ = daily
    run_dir = copy_output(tmp_path, kind)
    path = run_dir / filename
    second = path.read_bytes().split(b"*RUN", 1)[1]
    second = second.replace(b"   1 ", b"  12 ", 1).replace(b"TREATMENT  1", b"TREATMENT  7")
    path.write_bytes(path.read_bytes() + b"\n*RUN" + second)
    rows = getattr(dssatlab, "read_" + kind)(run_dir)
    assert len(rows) == 40
    assert rows[20:] == [dict(row, RUNNO=12, TRNO=7) for row in rows[:20]]


@pytest.mark.parametrize("kind,filename", [
    ("plant_growth", "PlantGro.OUT"), ("soil_water", "SoilWat.OUT"),
    ("plant_nitrogen", "PlantN.OUT"), ("weather", "Weather.OUT"),
])
def test_empty_second_run_never_returns_partial_rows(tmp_path, kind, filename):
    run_dir = copy_output(tmp_path, kind)
    path = run_dir / filename
    lines = path.read_bytes().splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(b"@"))
    second = b"\n".join(lines[:index + 1]).replace(b"*RUN   1", b"*RUN   2")
    path.write_bytes(path.read_bytes() + b"\n" + second + b"\n")
    assert_error(run_dir, kind, filename, "no data rows", "run block 2")


@pytest.mark.parametrize("suffix", [b" 123", b"broken"])
def test_daily_malformed_last_row(tmp_path, daily, suffix):
    kind, filename, *_ = daily
    run_dir = copy_output(tmp_path, kind)
    path = run_dir / filename
    path.write_bytes(path.read_bytes().rstrip() + suffix + b"\n")
    assert_error(run_dir, kind, filename, "row")


@pytest.mark.parametrize("encoded,expected", [
    (b"1982056", date(1982, 2, 25)), (b"1984366", date(1984, 12, 31)),
    (b"    -99", None), (b"1982366", "error"), (b"1982000", "error"),
    (b"1982bad", "error"),
])
def test_weather_date_column(tmp_path, encoded, expected):
    run_dir = copy_output(tmp_path, "weather")
    path = run_dir / "Weather.OUT"
    path.write_bytes(path.read_bytes().replace(b"1982056", encoded, 1))
    if expected == "error":
        assert_error(run_dir, "weather", "Weather.OUT", "WDATE", "row")
    else:
        row = dssatlab.read_weather(run_dir)[0]
        assert row["WDATE"] == expected
        assert row["DATE"] == date(1982, 2, 25)
