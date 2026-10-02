"""Simulation runs through a fake DSSAT subprocess writing real output files."""

import csv
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
import platform
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dssatlab import DSSATCheckError, DSSATRunError, Simulation, runner
from dssatlab import simulation as simulation_module
from dssatlab.soil import write_soil_file
from dssatlab.weather import write_weather_file


SAMPLE = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 2 1 0 0 RAINFED HIGH NITROGEN      1  1  0  1  1  1  2  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910014 Field section

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 N X IRRIGATION, GAINESVILLE
"""
STAMP = "2026-09-29_123456"


@pytest.fixture
def inputs(tmp_path):
    folder = tmp_path / "FileX folder"
    folder.mkdir()
    filex = folder / "UFGA8201.MZX"
    filex.write_text(SAMPLE, encoding="latin-1")
    siblings = ["SOIL.SOL", "XX.SOL", "LOCAL.SOL", "other.sol",
                "MZCER048.cUl", "MZCER048.ECO", "MZCER048.spe"]
    for name in siblings + ["UFGA8201.WTH", "notes.txt"]:
        (folder / name).write_text(f"original {name}")
    (folder / "nested.SOL").mkdir()
    (folder / "nested.SOL" / "deep.SOL").write_text("nested soil")
    rows = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                 date=day, srad=20, tmax=25, tmin=10, rain=0)
            for day in ["1982-02-24", "1982-02-25", "1982-02-26"]]
    weather = folder / "weather.csv"
    with weather.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return SimpleNamespace(filex=filex, weather=weather, rows=rows, siblings=siblings)


@pytest.fixture
def soil_rows():
    return [dict(soil_id="IBMZ910014", salb=0.13, slro=60, sldr=0.5,
                 slpf=1, slb=depth, slll=0.1, sdul=0.24, ssat=0.45,
                 srgf=1, sbdm=1.3) for depth in (5, 15, 30)]


@pytest.fixture
def fake_dssat(tmp_path, monkeypatch):
    executable = tmp_path / "DSSAT install" / "DSCSM048.EXE"
    executable.parent.mkdir()
    executable.write_text("fake DSSAT")
    executable.chmod(0o755)
    connect = Mock(return_value=executable)
    monkeypatch.setattr(runner, "connect", connect)
    monkeypatch.setattr(runner, "datetime", SimpleNamespace(
        now=lambda: datetime(2026, 9, 29, 12, 34, 56)))
    state = SimpleNamespace(executable=executable, connect=connect, calls=[],
                            outputs={"Summary.OUT": b"summary"}, returncode=0,
                            start_error=None)

    def fake_run(command, *, cwd, **kwargs):
        state.calls.append((command, cwd, kwargs))
        if state.start_error is not None:
            raise state.start_error
        for name, content in state.outputs.items():
            (Path(cwd) / name).write_bytes(content)
        return subprocess.CompletedProcess(command, state.returncode,
                                           stdout="DSSAT finished\n", stderr="")

    platform.uname()  # Windows Python 3.10 runs `ver` once; cache it before faking run
    monkeypatch.setattr(subprocess, "run", fake_run)
    return state


def snapshot(folder):
    """Original entries, contents and file timestamps, excluding new simulations."""
    return {path.relative_to(folder): (path.read_bytes(), path.stat().st_mtime_ns)
            if path.is_file() else None
            for path in folder.rglob("*")
            if not path.relative_to(folder).parts[0].startswith("dssat_sim_")}


def test_filex_name_over_twelve_characters_is_a_check_problem_and_creates_nothing(
        inputs, fake_dssat):
    long_name = inputs.filex.with_name("UFGA82010.MZX")  # 13 characters
    inputs.filex.rename(long_name)
    before = sorted(inputs.filex.parent.iterdir())
    sim = Simulation(long_name, 2, inputs.weather)

    problems = sim.check()
    assert any("13 characters" in p and "12" in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()

    assert any("13 characters" in p for p in error.value.problems)
    assert fake_dssat.calls == []
    assert sorted(inputs.filex.parent.iterdir()) == before  # no simulation folder left behind


def test_constructor_stores_all_inputs_without_work(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("construction must only store inputs"))
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    filex, treatment, weather, executable = (object() for _ in range(4))
    sim = Simulation(filex, treatment, weather, executable)
    assert sim.filex is filex and sim.treatment is treatment
    assert sim.weather is weather and sim.executable is executable
    assert Simulation(filex, treatment, weather).executable is None
    forbidden.assert_not_called()


@pytest.mark.parametrize("station,weather_name", [
    ("UFGA", "UFGA8201.WTH"), ("UFGA8307", "UFGA8307.WTH")])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("soil_form", [None, "rows", "path", "str"])
def test_run_command_inputs_weather_and_result(
        inputs, fake_dssat, tmp_path, monkeypatch, soil_rows,
        station, weather_name, explicit, soil_form):
    inputs.filex.write_text(SAMPLE.replace("UFGA       -99", f"{station:<8}   -99"))
    soil = None
    if soil_form is not None:
        soil = [dict(row, slb=str(row["slb"])) for row in soil_rows]
        if soil_form in ("path", "str"):
            path = inputs.filex.parent / "soil.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(soil[0]))
                writer.writeheader()
                writer.writerows(soil)
            soil = path if soil_form == "path" else str(path)
    original_soil = deepcopy(soil)
    before = snapshot(inputs.filex.parent)
    listing = set(inputs.filex.parent.iterdir())
    monkeypatch.chdir(tmp_path)
    filex = str(inputs.filex.relative_to(tmp_path))
    executable = fake_dssat.executable if explicit else None
    returned = []

    def record_run(*args, **kwargs):
        assert kwargs == {"treatment": 2, "executable": executable}
        assert type(kwargs["treatment"]) is int
        result = runner.run(*args, **kwargs)
        returned.append(result)
        return result

    monkeypatch.setattr(simulation_module, "run", record_run)
    result = Simulation(filex, "02", inputs.weather, executable, soil=soil).run()

    sim_folder = inputs.filex.parent / f"dssat_sim_{STAMP}"
    assert result is returned[0]
    assert isinstance(result, runner.RunResult)
    assert result.returncode == 0 and result.stdout_tail == "DSSAT finished"
    assert result.run_dir == sim_folder / f"dssat_run_{STAMP}"
    assert result.outputs == [result.run_dir / "Summary.OUT"]
    assert result.outputs[0].read_bytes() == b"summary"
    assert fake_dssat.calls == [
        ([str(fake_dssat.executable), "C", inputs.filex.name, "2"], sim_folder,
         {"stdin": subprocess.DEVNULL, "capture_output": True, "text": True})]
    if explicit:
        fake_dssat.connect.assert_not_called()
    else:
        fake_dssat.connect.assert_called_once_with(interactive=False)
    siblings = inputs.siblings if soil is None else [
        name for name in inputs.siblings if Path(name).suffix.upper() != ".SOL"]
    expected_names = {inputs.filex.name, *siblings, weather_name, result.run_dir.name}
    if soil is not None:
        expected_names.add("SOIL.SOL")
        expected_soil = write_soil_file(soil_rows, tmp_path / "expected.SOL")
        assert (sim_folder / "SOIL.SOL").read_bytes() == expected_soil.read_bytes()
    assert {p.name for p in sim_folder.iterdir()} == expected_names
    for name in [inputs.filex.name, *siblings]:
        assert (sim_folder / name).read_bytes() == (inputs.filex.parent / name).read_bytes()
        assert (sim_folder / name).stat().st_mtime_ns == (inputs.filex.parent / name).stat().st_mtime_ns
    parsed = [dict(row, date=date.fromisoformat(row["date"]),
                   tav=-99, amp=-99, refht=-99, wndht=-99) for row in inputs.rows]
    expected = write_weather_file(parsed, tmp_path / "expected.WTH")
    assert (sim_folder / weather_name).read_bytes() == expected.read_bytes()
    assert snapshot(inputs.filex.parent) == before
    assert set(inputs.filex.parent.iterdir()) == listing | {sim_folder}
    assert soil == original_soil


@pytest.mark.parametrize("with_soil", [False, True])
def test_all_problems_stop_before_writing_or_running(
        inputs, fake_dssat, monkeypatch, soil_rows, with_soil):
    rows = [dict(inputs.rows[0], rain=-1, tmax=0, station="ABCD")]
    soil_rows[0]["sbdm"] = 10
    sim = Simulation(inputs.filex, 2, rows, soil=soil_rows if with_soil else None)
    problems = sim.check()
    assert len(problems) == (5 if with_soil else 4)
    for word in ("rain", "tmax", "WSTA", "start") + (("sbdm",) if with_soil else ()):
        assert any(word in problem for problem in problems)
    before = snapshot(inputs.filex.parent)
    listing = set(inputs.filex.parent.iterdir())
    forbidden = Mock(side_effect=AssertionError("checks must finish before writing"))
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(simulation_module, "write_weather_file", forbidden)

    with pytest.raises(DSSATCheckError) as error:
        sim.run()

    assert error.value.problems == problems
    assert all(problem in str(error.value) for problem in problems)
    forbidden.assert_not_called()
    fake_dssat.connect.assert_not_called()
    assert fake_dssat.calls == []
    assert snapshot(inputs.filex.parent) == before
    assert set(inputs.filex.parent.iterdir()) == listing


@pytest.mark.parametrize("with_soil", [False, True])
def test_same_second_simulations_never_reuse_folders(inputs, fake_dssat, soil_rows, with_soil):
    soil = soil_rows if with_soil else None
    results = [Simulation(inputs.filex, 2, inputs.weather, soil=soil).run() for _ in range(3)]
    assert [result.run_dir.parent.name for result in results] == [
        f"dssat_sim_{STAMP}", f"dssat_sim_{STAMP}-2", f"dssat_sim_{STAMP}-3"]
    assert all((result.run_dir / "Summary.OUT").read_bytes() == b"summary"
               for result in results)
    if with_soil:
        assert all((result.run_dir.parent / "SOIL.SOL").read_bytes() ==
                   (results[0].run_dir.parent / "SOIL.SOL").read_bytes() for result in results)


def test_unusable_soil_raises_existing_run_error_and_keeps_run(inputs, fake_dssat, soil_rows):
    fake_dssat.returncode = 99
    fake_dssat.outputs["ERROR.OUT"] = b"End of soil file... soil profile not found"
    before = snapshot(inputs.filex.parent)
    with pytest.raises(DSSATRunError) as error:
        Simulation(inputs.filex, 2, inputs.weather, soil=soil_rows).run()
    run_dir = inputs.filex.parent / f"dssat_sim_{STAMP}" / f"dssat_run_{STAMP}"
    for text in ("return code 99", "ERROR.OUT", "End of soil file...", str(run_dir)):
        assert text in str(error.value)
    assert (run_dir / "ERROR.OUT").read_bytes() == fake_dssat.outputs["ERROR.OUT"]
    assert (run_dir / "Summary.OUT").read_bytes() == b"summary"
    assert (run_dir.parent / "SOIL.SOL").is_file()
    assert snapshot(inputs.filex.parent) == before


@pytest.mark.parametrize("warning", [None, b"An unrelated warning\xff\n"])
def test_missing_or_unrelated_warning_returns_run_result(inputs, fake_dssat, warning):
    if warning is not None:
        fake_dssat.outputs["WARNING.OUT"] = warning
    result = Simulation(inputs.filex, 2, inputs.weather).run()
    assert isinstance(result, runner.RunResult) and result.returncode == 0


@pytest.mark.parametrize("year,day,calendar", [(1982, "58", "1982-02-27"),
                                               (2024, "060", "2024-02-29")])
def test_missing_weather_names_first_date_and_keeps_run(inputs, fake_dssat, year, day, calendar):
    warning = (f"unrelated\nWeather record not found for YR DOY:  {year}\t{day}\n"
               "Weather record not found for YR DOY: 1981 001\n").encode() + b"\xff"
    fake_dssat.outputs["WARNING.OUT"] = warning
    before = snapshot(inputs.filex.parent)
    with pytest.raises(DSSATRunError) as error:
        Simulation(inputs.filex, 2, inputs.weather).run()
    run_dir = inputs.filex.parent / f"dssat_sim_{STAMP}" / f"dssat_run_{STAMP}"
    message = str(error.value)
    for text in (str(year), f"day of year {int(day)}", calendar, "exits 0", "-99",
                 str(run_dir), "kept", "Extend the weather data", "crop needs", "run again"):
        assert text in message
    assert "1981-01-01" not in message
    assert (run_dir / "WARNING.OUT").read_bytes() == warning
    assert (run_dir.parent / inputs.filex.name).is_file()
    assert snapshot(inputs.filex.parent) == before


@pytest.mark.parametrize("failure", ["exit", "error-out", "start"])
def test_existing_run_failures_propagate_and_keep_simulation(inputs, fake_dssat, failure):
    if failure == "exit":
        fake_dssat.returncode = 99
    elif failure == "error-out":
        fake_dssat.outputs["ERROR.OUT"] = b"DSSAT failure"
    else:
        fake_dssat.start_error = OSError("cannot execute")
    with pytest.raises(DSSATRunError, match="Could not start|DSSAT run failed"):
        Simulation(inputs.filex, 2, inputs.weather).run()
    sim_folder = inputs.filex.parent / f"dssat_sim_{STAMP}"
    assert (sim_folder / inputs.filex.name).is_file()
    assert (sim_folder / "UFGA8201.WTH").is_file()
    if failure != "start":
        assert (sim_folder / f"dssat_run_{STAMP}" / "Summary.OUT").is_file()


def test_runner_exception_is_not_replaced(inputs, fake_dssat):
    failure = DSSATRunError("existing run error")
    fake_dssat.connect.side_effect = failure
    with pytest.raises(DSSATRunError) as error:
        Simulation(inputs.filex, 2, inputs.weather).run()
    assert error.value is failure
    assert (inputs.filex.parent / f"dssat_sim_{STAMP}" / inputs.filex.name).is_file()


@pytest.mark.parametrize("failure", [PermissionError("read-only"), OSError("denied")])
def test_unwritable_simulation_folder(inputs, fake_dssat, monkeypatch, failure):
    mkdir = Path.mkdir

    def cannot_create(path, *args, **kwargs):
        if path.name.startswith("dssat_sim_"):
            raise failure
        return mkdir(path, *args, **kwargs)

    before = set(inputs.filex.parent.iterdir())
    monkeypatch.setattr(Path, "mkdir", cannot_create)
    with pytest.raises(DSSATRunError) as error:
        Simulation(inputs.filex, 2, inputs.weather).run()
    for text in ("Cannot create simulation folder", str(inputs.filex.parent),
                 "not writable", str(failure), "Move the FileX somewhere writable"):
        assert text in str(error.value)
    assert error.value.__cause__ is failure
    assert fake_dssat.calls == []
    fake_dssat.connect.assert_not_called()
    assert set(inputs.filex.parent.iterdir()) == before
