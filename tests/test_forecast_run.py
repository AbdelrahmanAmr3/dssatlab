"""Checked forecast Simulations use the existing runner and weather writer."""

import subprocess

import pytest

from dssatlab import DSSATRunError, Simulation
from dssatlab.runner import RunResult
from test_filex_check import SAMPLE, filex
from test_forecast_check import METHODS, SIMDATES
from test_season_coverage import weather
from test_simulation_run import fake_dssat, snapshot


@pytest.fixture
def forecast(filex):
    text = SAMPLE.replace("GE              1", "GE              2") + METHODS + SIMDATES
    path = filex(text=text)
    path = path.rename(path.with_suffix(".FCX"))
    return Simulation(path, "02", weather("1980-02-25", "1982-02-25"))


@pytest.mark.parametrize("station,weather_name", [
    ("UFGA", "UFGA8201.WTH"), ("UFGA8307", "UFGA8307.WTH"),
])
@pytest.mark.parametrize("suffix", [".FCX", ".fcx"])
@pytest.mark.parametrize("warning", [None, b"An unrelated warning\xff\n"])
def test_forecast_batch_weather_and_result(
        forecast, fake_dssat, monkeypatch, station, weather_name, suffix, warning):
    forecast.filex = forecast.filex.rename(forecast.filex.with_suffix(suffix))
    forecast.filex.write_text(forecast.filex.read_text(encoding="latin-1").replace(
        "UFGA       -99", f"{station:<8}   -99"), encoding="latin-1")
    original = forecast.filex.read_bytes()
    before = snapshot(forecast.filex.parent)
    if warning is not None:
        fake_dssat.outputs["WARNING.OUT"] = warning
    expected_batch = (
        "$BATCH(FORECAST)\r\n\r\n"
        "@FILEX                                                                                        "
        "TRTNO     RP     SQ     OP     CO\r\n"
        f"{forecast.filex.name:<92}      2      1      0      0      0\r\n"
    ).encode("latin-1")
    execute = subprocess.run
    folders = []

    def inspect_run(command, *, cwd, stdin, capture_output, text):
        folders.append(cwd)
        assert command == [str(fake_dssat.executable), "Y", "DSSBatch.v48"]
        assert stdin == subprocess.DEVNULL and capture_output and text
        assert cwd.parent == forecast.filex.parent
        assert cwd.name.startswith("dssat_sim_")
        assert (cwd / forecast.filex.name).read_bytes() == original
        assert len(forecast.filex.name) == 12
        assert (cwd / "DSSBatch.v48").read_bytes() == expected_batch
        assert [path.name for path in cwd.glob("*.WTH")] == [weather_name]
        written = (cwd / weather_name).read_text(encoding="ascii").splitlines()
        assert written[0] == "*WEATHER DATA : UFGA (written by dssatlab)"
        assert written[4] == "@DATE  SRAD  TMAX  TMIN  RAIN"
        assert [line.split() for line in written[5:]] == [
            [f"{row['date'].year % 100:02d}{row['date'].timetuple().tm_yday:03d}",
             "20.0", "25.0", "10.0", "0.0"] for row in forecast.weather
        ]
        return execute(command, cwd=cwd, stdin=stdin, capture_output=capture_output, text=text)

    monkeypatch.setattr(subprocess, "run", inspect_run)
    assert forecast.check(False) == []
    result = forecast.run()

    assert len(folders) == 1
    assert isinstance(result, RunResult)
    assert result.returncode == 0 and result.stdout_tail == "DSSAT finished"
    assert result.run_dir.parent == folders[0]
    assert result.outputs == [result.run_dir / name for name in sorted(
        {"DSSBatch.v48", *fake_dssat.outputs})]
    assert (result.run_dir / "DSSBatch.v48").read_bytes() == expected_batch
    assert not (folders[0] / "DSSBatch.v48").exists()
    assert snapshot(forecast.filex.parent) == before


def test_forecast_missing_weather_still_raises_and_keeps_run(forecast, fake_dssat):
    warning = b"Weather record not found for YR DOY:  1982 058\n"
    fake_dssat.outputs["WARNING.OUT"] = warning
    before = snapshot(forecast.filex.parent)
    assert forecast.check(False) == []

    with pytest.raises(DSSATRunError) as error:
        forecast.run()

    assert len(fake_dssat.calls) == 1
    command, folder, kwargs = fake_dssat.calls[0]
    assert command == [str(fake_dssat.executable), "Y", "DSSBatch.v48"]
    assert kwargs["stdin"] == subprocess.DEVNULL
    run_dirs = list(folder.glob("dssat_run_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert str(error.value) == (
        "DSSAT reported no weather for year 1982, day of year 58 (1982-02-27). "
        "DSSAT exits 0 in this case and gives -99 for anything it could not reach.\n"
        f"Run directory (kept): {run_dir}\n"
        "Extend the weather data through that date and the days the crop needs, then run again."
    )
    assert (run_dir / "WARNING.OUT").read_bytes() == warning
    assert (run_dir / "Summary.OUT").read_bytes() == b"summary"
    assert (run_dir / "DSSBatch.v48").read_bytes().startswith(b"$BATCH(FORECAST)\r\n")
    assert (folder / forecast.filex.name).is_file()
    assert (folder / "UFGA8201.WTH").is_file()
    assert snapshot(forecast.filex.parent) == before
