"""DataFrame and calendar-date weather inputs through Simulation.check()."""

import csv
from datetime import date, datetime
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


@pytest.fixture
def rows():
    return [dict(station="AB12", latitude=45, longitude=-100, elevation=200,
                 date=day, srad=20, tmax=25, tmin=10, rain=0)
            for day in ("2021-03-01", "2021-03-02", "2021-03-03")]


def check(weather):
    problems = dssatlab.Simulation("missing.MZX", 1, weather).check()
    # These tests isolate weather checks; ticket #14 also reports the absent FileX.
    filex_problems = [p for p in problems if p.startswith("Cannot read FileX ")]
    assert len(filex_problems) == 1
    return [p for p in problems if p not in filex_problems]


def write_csv(path, rows, columns=None):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_plain_rows_and_fake_dataframe_do_not_import_pandas(tmp_path, rows):
    pandas_was_imported = "pandas" in sys.modules
    assert check(rows) == []
    assert check(FakeDataFrame(rows)) == check(
        write_csv(tmp_path / "weather.csv", rows)) == []
    if not pandas_was_imported:
        assert "pandas" not in sys.modules


def test_dataframe_columns_and_row_numbers_match_csv(tmp_path, rows):
    for row in rows:
        row["Rain"] = row.pop("rain")
    rows[0]["srad"] = "oops"
    rows[1]["date"] = "bad-date"
    problems = check(FakeDataFrame(rows))
    assert problems == check(write_csv(tmp_path / "weather.csv", rows))
    assert any("missing" in p and "'rain'" in p and "line 1" in p for p in problems)
    assert any("unknown" in p and "'Rain'" in p and "line 1" in p for p in problems)
    assert any("'srad'" in p and "row 2" in p and "finite number" in p for p in problems)
    assert any("'date'" in p and "row 3" in p and "YYYY-MM-DD" in p for p in problems)


def test_empty_dataframe_uses_declared_columns(tmp_path, rows):
    columns = [name for name in rows[0] if name != "rain"] + ["Rain"]
    problems = check(FakeDataFrame([], columns))
    assert problems == check(write_csv(tmp_path / "weather.csv", [], columns))
    assert any("missing" in p and "'rain'" in p for p in problems)
    assert any("unknown" in p and "'Rain'" in p for p in problems)
    assert any("no daily rows" in p for p in problems)


def test_duplicate_dataframe_columns_match_csv(tmp_path, rows):
    columns = list(rows[0]) + ["rain"]
    problems = check(FakeDataFrame(rows, columns))
    assert problems == check(write_csv(tmp_path / "weather.csv", rows, columns))
    assert len(problems) == 1
    assert "'rain'" in problems[0] and "repeated" in problems[0]
    assert "line 1" in problems[0]


def test_failed_dataframe_conversion_returns_one_source_problem(rows, monkeypatch):
    frame = FakeDataFrame(rows)

    def fail(orient):
        raise RuntimeError("cannot convert records")

    monkeypatch.setattr(frame, "to_dict", fail)
    problems = check(frame)
    assert len(problems) == 1
    assert "Cannot read weather data" in problems[0]
    assert "cannot convert records" in problems[0]
    assert "Supply" in problems[0]


@pytest.mark.parametrize("source", [SimpleNamespace(columns=[]),
                                    SimpleNamespace(to_dict=lambda orient: [])])
def test_dataframe_detection_requires_both_attributes(source):
    problems = check(source)
    assert len(problems) == 1
    assert "Cannot read weather data" in problems[0]


@pytest.mark.parametrize("day", [date(2021, 3, 2), datetime(2021, 3, 2)])
def test_plain_rows_accept_calendar_dates_and_midnight(rows, day):
    rows[1]["date"] = day
    assert check(rows) == []
    assert rows[1]["date"] is day


@pytest.mark.parametrize("day", [datetime(2021, 3, 2, 1),
                                  datetime(2021, 3, 2, 0, 1),
                                  datetime(2021, 3, 2, 0, 0, 1),
                                  datetime(2021, 3, 2, microsecond=1)])
def test_plain_rows_reject_time_parts(rows, day):
    rows[1]["date"] = day
    assert any("row 3" in p and "'date'" in p and
               "date has a time part; use a whole date" in p for p in check(rows))


@pytest.mark.parametrize("bad_cell", [False, True])
def test_real_dataframe_matches_csv_with_datetime64_and_numpy(tmp_path, rows, bad_cell):
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    frame = pd.DataFrame(rows, index=[10, 20, 30])
    frame["date"] = pd.to_datetime(frame["date"])
    frame["srad"] = np.array([20, 20, 20], dtype=np.float64)
    frame["tmax"] = np.array([25, 25, 25], dtype=np.int64)
    if bad_cell:
        frame.loc[20, "srad"] = np.nan
        rows[1]["srad"] = float("nan")
    problems = check(frame)
    assert problems == check(write_csv(tmp_path / "weather.csv", rows))
    if bad_cell:
        assert len(problems) == 1
        assert "row 3" in problems[0] and "'srad'" in problems[0]
        assert "finite number" in problems[0]
    else:
        assert problems == []


def test_real_dataframe_rejects_submicrosecond_time_part(rows):
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"]).astype("datetime64[ns]")
    frame.loc[1, "date"] += pd.Timedelta(nanoseconds=1)
    assert any("row 3" in p and "date has a time part; use a whole date" in p
               for p in check(frame))
