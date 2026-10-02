from dataclasses import FrozenInstanceError, fields
from datetime import date
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import dssatlab
from dssatlab import (DSSATError, DSSATOutputError, read_dssat_evaluation,
                      read_plant_growth, read_summary, to_dataframe)
from dssatlab.runner import RunResult


@pytest.fixture
def result(tmp_path):
    fixtures = Path(__file__).parent / "fixtures" / "output_files"
    run_dir = tmp_path / "run directory"
    for kind in ("summary", "plant_growth", "soil_water", "plant_nitrogen", "weather", "evaluate"):
        shutil.copytree(fixtures / kind / "maize", run_dir, dirs_exist_ok=True)
    return RunResult(0, run_dir, sorted(run_dir.glob("*.OUT")), "DSSAT finished")


def test_result_readers_use_its_run_directory(result):
    assert result.summary() == read_summary(result.run_dir)
    assert result.plant_growth() == read_plant_growth(result.run_dir)
    assert result.dssat_evaluation() == read_dssat_evaluation(result.run_dir)


@pytest.mark.parametrize("kind,filename,column,expected", [
    ("soil_water", "SoilWat.OUT", "SW1D", 0.086),
    ("plant_nitrogen", "PlantN.OUT", "CNAD", 0.0),
    ("weather", "Weather.OUT", "SRAD", 14.8),
])
def test_result_daily_readers_and_missing_files(result, kind, filename, column, expected):
    rows = getattr(result, kind)()
    assert len(rows) == 20
    assert rows[0][column] == expected
    assert rows == getattr(dssatlab, "read_" + kind)(result.run_dir)
    (result.run_dir / filename).unlink()
    with pytest.raises(DSSATOutputError, match=filename):
        getattr(result, kind)()


@pytest.mark.parametrize("name", ["returncode", "run_dir", "outputs", "stdout_tail"])
def test_result_still_frozen_with_original_fields(result, name):
    assert [field.name for field in fields(result)] == [
        "returncode", "run_dir", "outputs", "stdout_tail"]
    with pytest.raises(FrozenInstanceError):
        setattr(result, name, None)


def test_result_plot_delegates_lazily(result, monkeypatch):
    calls = []
    axes = object()

    def fake_plot(run_dir, variable):
        calls.append((run_dir, variable))
        return axes

    monkeypatch.setitem(sys.modules, "dssatlab.plot",
                        SimpleNamespace(plot_plant_growth=fake_plot))
    assert result.plot("LAID") is axes
    assert calls == [(result.run_dir, "LAID")]


@pytest.mark.parametrize("reader", [read_summary, read_plant_growth])
def test_dataframe_preserves_reader_columns_and_values(result, reader):
    pd = pytest.importorskip("pandas")
    rows = reader(result.run_dir)
    frame = to_dataframe(rows)
    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == list(rows[0])
    assert len(frame) == len(rows)
    for index, row in enumerate(rows):
        for name, expected in row.items():
            actual = frame.at[index, name]
            if expected is None:
                assert pd.isna(actual)
            else:
                assert actual == expected
                if type(expected) is date:
                    assert type(actual) is date


def test_dataframe_missing_values_and_column_order():
    pd = pytest.importorskip("pandas")
    rows = [{"DATE": date(1982, 5, 13), "HWAM": 2295, "TNAM": "Rainfed"},
            {"DATE": None, "HWAM": None, "TNAM": None}]
    frame = to_dataframe(rows)
    assert list(frame.columns) == ["DATE", "HWAM", "TNAM"]
    assert type(frame.at[0, "DATE"]) is date
    assert frame.at[0, "DATE"] == rows[0]["DATE"]
    assert frame.at[0, "HWAM"] == 2295 and frame.at[0, "TNAM"] == "Rainfed"
    assert all(pd.isna(frame.at[1, name]) for name in frame.columns)


def test_dataframe_empty_rows():
    pd = pytest.importorskip("pandas")
    frame = to_dataframe([])
    assert isinstance(frame, pd.DataFrame)
    assert frame.empty and list(frame.columns) == []


def test_dataframe_without_pandas(monkeypatch):
    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(DSSATError, match="pip install pandas") as caught:
        to_dataframe([])
    assert "DataFrame" in str(caught.value)
    assert "import" in str(caught.value)


def test_import_does_not_import_pandas():
    code = """
import builtins
import sys
original_import = builtins.__import__
def check_import(name, *args, **kwargs):
    if name == 'pandas' or name.startswith('pandas.'):
        raise AssertionError('Importing dssatlab attempted to import pandas')
    return original_import(name, *args, **kwargs)
builtins.__import__ = check_import
import dssatlab
assert 'pandas' not in sys.modules
"""
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_repr_is_short_and_hides_console_tail(tmp_path):
    run_dir = tmp_path / "dssat_run_1"
    run_dir.mkdir()
    (run_dir / "Summary.OUT").write_text("x")
    text = repr(RunResult(0, run_dir, [run_dir / "Summary.OUT"], "DSSAT finished\n" * 50))
    assert "1 output files" in text and "DSSAT finished" not in text and "\n" not in text
