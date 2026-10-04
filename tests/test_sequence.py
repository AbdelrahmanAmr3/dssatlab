"""Sequence checks and runs through Simulation and a fake DSSAT executable."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import platform
import re
import subprocess

import pytest

from dssatlab import DSSATCheckError, DSSATRunError, Simulation
from test_season_coverage import weather
from test_simulation_run import fake_dssat  # noqa: F401; caches uname before mocking subprocess


FIXTURES = Path(__file__).parent / "fixtures"
REPORT = ("FileX: treatment 1 is a sequence of 6 rotation components "
          "(R 1-6: BN, FA, BN, FA, SB, FA); it runs in DSSAT's sequence mode.")


@pytest.fixture
def sequence(tmp_path):
    text = (FIXTURES / "UFGA7804.SQX").read_text(encoding="latin-1")
    text = text.replace(" 1 GE             10     5", " 1 GE              1     1")
    text = re.sub(r"(?m)^( *\d+ ME {14})W", r"\1M", text)
    text = re.sub(r"(?m)^( *\d+ OU {14})Y", r"\1N", text)
    filex = tmp_path / "UFGA7804.SQX"
    filex.write_text(text, encoding="latin-1")
    return Simulation(filex, 1, weather("1978-04-20", "1979-04-19"))


def change_component(sim, index, column, value):
    """Edit one fixed-width treatment cell in the test FileX."""
    text = sim.filex.read_text(encoding="latin-1")
    lines = text.splitlines(keepends=True)
    header_index = next(i for i, line in enumerate(lines) if line.startswith("@N R O C"))
    header = lines[header_index]
    ends = {m.group().rstrip("."): m.end() for m in re.finditer(r"\S+", header)}
    right = ends[column]
    left = max((end for end in ends.values() if end < right), default=0)
    row_index = header_index + index + 1
    line = lines[row_index]
    lines[row_index] = line[:left] + f"{value:>{right-left}}" + line[right:]
    sim.filex.write_text("".join(lines), encoding="latin-1")


def test_sequence_run_batch_outputs_and_report(sequence, fake_dssat, capsys, monkeypatch):
    seen = {}
    fake_run = subprocess.run

    def record_inputs(command, *, cwd, **kwargs):
        seen.update({path.name: path.read_bytes() for path in cwd.iterdir() if path.is_file()})
        return fake_run(command, cwd=cwd, **kwargs)

    platform.uname()
    monkeypatch.setattr(subprocess, "run", record_inputs)
    assert sequence.check(verbose=True) == []
    assert REPORT in capsys.readouterr().out
    result = sequence.run()
    folder = result.run_dir.parent
    assert fake_dssat.calls == [
        ([str(fake_dssat.executable), "Q", "DSSBatch.v48"], folder,
         {"stdin": subprocess.DEVNULL, "capture_output": True, "text": True})]
    batch = result.run_dir / "DSSBatch.v48"
    assert batch.read_bytes() == (FIXTURES / "DSSBatch.v48").read_bytes()
    assert seen["DSSBatch.v48"] == batch.read_bytes()
    assert seen[sequence.filex.name] == sequence.filex.read_bytes()
    assert "UFGA7801.WTH" in seen
    for number, line in enumerate(batch.read_text().splitlines()[3:], 1):
        assert line[:92].rstrip() == sequence.filex.name
        assert [int(line[i:i+7]) for i in range(92, 127, 7)] == [1, 1, number, 0, 0]
    assert result.outputs == [batch, result.run_dir / "Summary.OUT"]
    assert (result.run_dir / "Summary.OUT").read_bytes() == b"summary"
    assert not (folder / "DSSBatch.v48").exists()
    assert not (folder / "Summary.OUT").exists()
    assert (folder / "UFGA7801.WTH").is_file()


MESSAGES = {
    "filename": "A sequence runs in DSSAT's sequence mode, which needs a FileX filename of exactly 12 characters (8 plus the extension, like UFGA7804.SQX); 'SEQ1.SQX' has 8. Rename the FileX.",
    "R": "Treatment 1 has rotation components R 1, 1, 3, 4, 5, 6: give each row of a sequence its own R number.",
    "FL": "Treatment 1 is a sequence whose components use fields 1 and 2; dssatlab writes one weather file and one soil profile, so give every component the same field (FL).",
    "NREPS": "FileX NREPS 5 for sequence treatment 1: with measured weather every replicate repeats the same rows. Checked the first component's GENERAL NREPS and sequence WTHER. Set NREPS to 1.",
}


@pytest.mark.parametrize("failures", [(key,) for key in MESSAGES] + [tuple(MESSAGES)])
def test_sequence_checks_collect_before_writing(sequence, fake_dssat, failures, capsys):
    for failure in failures:
        if failure == "filename":
            new_path = sequence.filex.with_name("SEQ1.SQX")
            sequence.filex.rename(new_path)
            sequence.filex = new_path
        elif failure in ("R", "FL"):
            change_component(sequence, 1, failure, "1" if failure == "R" else "2")
        else:
            text = sequence.filex.read_text().replace(" 1 GE              1     1", " 1 GE              1     5")
            sequence.filex.write_text(text)
    before = set(sequence.filex.parent.iterdir())
    problems = sequence.check(verbose=True)
    assert problems == [MESSAGES[key] for key in failures]
    report = capsys.readouterr().out
    assert all(message in report for message in problems)
    with pytest.raises(DSSATCheckError) as error:
        sequence.run()
    assert error.value.problems == problems
    assert set(sequence.filex.parent.iterdir()) == before
    assert fake_dssat.calls == []


def test_three_fields_are_listed(sequence):
    change_component(sequence, 1, "FL", "2")
    change_component(sequence, 2, "FL", "3")
    assert sequence.check() == [MESSAGES["FL"].replace("fields 1 and 2", "fields 1, 2 and 3")]


@pytest.mark.parametrize("nreps", ["01", "-99"])
def test_nreps_one_or_default_passes(sequence, nreps):
    text = sequence.filex.read_text().replace(" 1 GE              1     1", f" 1 GE              1 {nreps:>5}")
    sequence.filex.write_text(text)
    assert sequence.check() == []


@pytest.mark.parametrize("value", ["0", "x"])
def test_invalid_rotation_number(sequence, value):
    change_component(sequence, 1, "R", value)
    assert sequence.check() == [
        f"Treatment 1 has rotation components R 1, {value}, 3, 4, 5, 6: "
        "give each row of a sequence its own R number."]


def test_negative_component_selects_normal_columns(sequence):
    from dssatlab.filex import read_treatment_numbers

    change_component(sequence, 1, "R", "-1")
    # R=-1 is not Fortran I2's positive component format, so N is " 1-".
    with pytest.raises(ValueError, match="columns 1-3"):
        read_treatment_numbers(sequence.filex)


@pytest.mark.parametrize("name", ["another scenario", "too long to fit a treatment name column " * 3])
def test_scenario_preserves_rotation_component_names(sequence, fake_dssat, name):
    sequence.name = name
    original = sequence.filex.read_bytes()
    assert sequence.check() == []
    result = sequence.run()
    assert (result.run_dir.parent / sequence.filex.name).read_bytes() == original
    assert sequence.filex.read_bytes() == original


def test_missing_weather_still_raises(sequence, fake_dssat):
    fake_dssat.outputs["WARNING.OUT"] = b"Weather record not found for YR DOY: 1978 111"
    with pytest.raises(DSSATRunError, match="1978-04-21"):
        sequence.run()
    assert fake_dssat.calls[0][0][1:] == ["Q", "DSSBatch.v48"]
    folder = fake_dssat.calls[0][1]
    assert next(folder.glob("dssat_run_*/WARNING.OUT")).read_bytes() == fake_dssat.outputs["WARNING.OUT"]


def test_single_row_keeps_mode_c_and_report(sequence, fake_dssat, capsys):
    for index in range(1, 6):
        change_component(sequence, index, "@N", "2")
    sequence.filex.write_text(sequence.filex.read_text().replace("NREPS", "OTHER"))
    assert sequence.check(verbose=True) == []
    assert "sequence" not in capsys.readouterr().out
    result = sequence.run()
    assert fake_dssat.calls[0][0] == [str(fake_dssat.executable), "C", sequence.filex.name, "1"]
    assert not (result.run_dir.parent / "DSSBatch.v48").exists()


def test_missing_nreps_and_unreadable_crop(sequence, fake_dssat, capsys):
    sequence.filex.write_text(sequence.filex.read_text().replace("NREPS", "OTHER"))
    change_component(sequence, 1, "CU", "99")
    assert sequence.check(verbose=True) == []
    assert "R 1-6: BN, ?, BN, FA, SB, FA" in capsys.readouterr().out
    sequence.run()


@pytest.mark.parametrize("failure", ["exit", "error-out", "start"])
def test_sequence_runner_errors(sequence, fake_dssat, failure):
    if failure == "exit":
        fake_dssat.returncode = 99
    elif failure == "error-out":
        fake_dssat.outputs["ERROR.OUT"] = b"DSSAT failure"
    else:
        fake_dssat.start_error = OSError("cannot execute")
    with pytest.raises(DSSATRunError, match="Could not start|DSSAT run failed"):
        sequence.run()
    folder = fake_dssat.calls[0][1]
    assert not (folder / "DSSBatch.v48").exists()
    if failure != "start":
        assert next(folder.glob("dssat_run_*/DSSBatch.v48")).is_file()
        assert next(folder.glob("dssat_run_*/Summary.OUT")).is_file()
    else:
        assert not list(folder.glob("dssat_run_*"))


@pytest.mark.parametrize("entry", [
    {"planting": {}}, {"controls": {"unknown": 1}},
    {"controls": {"water": "N"}}, {"irrigation": [], "fertilizer": []},
])
def test_sequence_rejects_component_experiment_data(sequence, fake_dssat, entry, capsys):
    sequence.weather = weather("1978-04-20", "1980-04-28")
    sequence.management = {"treatments": {"01": entry}}
    original = deepcopy(sequence.management)
    expected = ("Treatment 1 is a sequence of 6 rotation components; experiment data for a "
                "sequence takes only controls years, start_date, weather_source, replicates, random_seed "
                "and rotation. Edit the components "
                "in the FileX for other changes.")
    assert sequence.check(True) == [expected]
    assert "FileX: REJECTED" in capsys.readouterr().out
    before = set(sequence.filex.parent.iterdir())
    with pytest.raises(DSSATCheckError) as error:
        sequence.run()
    assert error.value.problems == [expected]
    assert set(sequence.filex.parent.iterdir()) == before
    assert fake_dssat.calls == []
    assert sequence.management == original


@pytest.mark.parametrize("controls", [
    {"years": 2}, {"start_date": "1978-04-21"},
    {"years": 2, "start_date": "1978-04-21"},
])
def test_sequence_controls_copy_only_first_component(sequence, fake_dssat, monkeypatch, controls):
    sequence.weather = weather("1978-04-20", "1980-04-28", station="TEST")
    sequence.management = {"treatments": {1: {"controls": controls}}}
    original = sequence.filex.read_bytes()
    seen = {}
    fake_run = subprocess.run

    def record(command, *, cwd, **kwargs):
        seen["filex"] = (cwd / sequence.filex.name).read_bytes()
        return fake_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", record)
    assert sequence.check(False) == []
    sequence.run()
    written = seen["filex"]
    original_rows = original.split(b"*TREATMENTS")[1].split(b"*CULTIVARS")[0].splitlines(keepends=True)
    written_rows = written.split(b"*TREATMENTS")[1].split(b"*CULTIVARS")[0].splitlines(keepends=True)
    first = next(i for i, row in enumerate(original_rows) if row.startswith(b" 1 1"))
    assert written_rows[first] == original_rows[first][:70] + b"  5" + original_rows[first][73:]
    assert written_rows[:first] + written_rows[first+1:] == original_rows[:first] + original_rows[first+1:]
    old_controls = original.split(b"*SIMULATION CONTROLS")[1]
    new_controls = written.split(b"*SIMULATION CONTROLS")[1]
    old_rows = [row for row in old_controls.splitlines() if row.startswith(b" 1 ")]
    new_rows = [row for row in new_controls.splitlines() if row.startswith(b" 5 ")]
    expected = [b" 5" + row[2:] for row in old_rows]
    if "years" in controls:
        expected[0] = expected[0].replace(b"GE              1", b"GE              2")
    if "start_date" in controls:
        expected[0] = expected[0].replace(b"78110", b"78111")
    assert new_rows == expected
    assert [row for row in new_controls.splitlines(keepends=True) if row[:3] in
            (b" 1 ", b" 2 ", b" 3 ", b" 4 ")] == [
                row for row in old_controls.splitlines(keepends=True) if row[:3] in
                (b" 1 ", b" 2 ", b" 3 ", b" 4 ")]
    field = written.split(b"*FIELDS")[1].splitlines()[2]
    assert field[12:20] == b"TEST    "  # DSSAT's mode Q reads WSTA as (I3,9X,A8): no leading blank
    assert sequence.filex.read_bytes() == original


@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("start,years,last", [
    ("1978-04-20", 10, "1988-04-18"),
    ("1980-02-29", 1, "1981-02-28"),
    ("1978-04-20", 1, "1979-04-19"),
])
@pytest.mark.parametrize("short", [False, True, "year-end"])
def test_sequence_weather_end(sequence, fake_dssat, capsys, override, start, years, last, short):
    first, last_day = date.fromisoformat(start), date.fromisoformat(last)
    end = (date(last_day.year - 1, 12, 31) if short == "year-end" else
           last_day - timedelta(days=int(short)))
    text = sequence.filex.read_text().replace("78110", first.strftime("%y%j"))
    text = text.replace(" 1 GE              1", f" 1 GE          {years:5d}")
    sequence.filex.write_text(text)
    if override:
        sequence.management = {"treatments": {1: {"controls": {"years": years, "start_date": start}}}}
        sequence.filex.write_text(text.replace(f" 1 GE          {years:5d}", " 1 GE             99")
                                 .replace(first.strftime("%y%j"), "78110"))
    sequence.weather = weather(start, end.isoformat())
    prefix = "Controls years" if override else "FileX NYERS"
    expected = ([f"{prefix} {years}: the sequence runs from {start} through {last}, "
                 f"after the weather data ends ({end}). Supply weather through {last}, "
                 "or fewer years."] if short else [])
    if start == '1980-02-29':
        expected.append(f"{'Controls start_date' if override else 'Simulation start date'} "
                        "'1980-02-29' is after the FileX's first irrigation date 1978-05-11; "
                        "DSSAT stops with error IPIRR. Start on or before that date, or give irrigation in the management data.")
    before = set(sequence.filex.parent.iterdir())
    problems = sequence.check(True)
    inherited = [p for p in problems if 'outside weather range' in p
                 or 'before simulation start date' in p]
    expected_count = (6 if start == '1980-02-29' else 2) if override and years == 1 else 0
    assert len(inherited) == expected_count
    if override and start == '1980-02-29':
        before_start = [p for p in inherited if 'before simulation start date' in p]
        assert len(before_start) == 1
        assert '1978-04-30 is before simulation start date (1980-02-29)' in before_start[0]
    assert [p for p in problems if p not in inherited] == expected
    report = capsys.readouterr().out
    if short:
        assert "FileX: REJECTED" in report and expected[0] in report
        with pytest.raises(DSSATCheckError) as error:
            sequence.run()
        assert error.value.problems == expected + inherited
    assert set(sequence.filex.parent.iterdir()) == before
    assert fake_dssat.calls == []


@pytest.mark.parametrize("replacement", ["P 78110", "S XXXXX", "S 79110"])
def test_sequence_coverage_uses_start_p_and_skips_unresolved_s(sequence, replacement):
    sequence.filex.write_text(sequence.filex.read_text().replace("S 78110", replacement))
    sequence.weather = weather("1978-04-20", "1978-04-21")
    problems = sequence.check(False)
    assert any("sequence runs from" in p for p in problems) == (replacement != "S XXXXX")
    assert not any("season 1" in p for p in problems)


@pytest.mark.parametrize("override", [False, True])
def test_sequence_start_still_needs_weather(sequence, override):
    sequence.weather = weather("1978-04-21", "1979-04-19")
    if override:
        sequence.management = {"treatments": {1: {"controls": {"start_date": "1978-04-20"}}}}
    problems = sequence.check(False)
    inherited = [p for p in problems if 'outside weather range' in p]
    assert len(inherited) == (2 if override else 0)
    expected = (
        "Controls start_date '1978-04-20' is not covered by weather data "
        "(1978-04-21 to 1979-04-19). Supply weather for the simulation's start date."
        if override else
        "FileX SDATE '78110' is 1978-04-20 (DSSAT reads two-digit years 00-35 as "
        "2000-2035 and 36-99 as 1936-1999), not covered by weather data "
        "(1978-04-21 to 1979-04-19). Supply weather for 1978-04-20, or set controls.start_date.")
    assert [p for p in problems if p not in inherited] == [expected]


def test_sequence_missing_nyers_defaults_to_one(sequence):
    sequence.filex.write_text(sequence.filex.read_text().replace("NYERS", "OTHER"))
    assert sequence.check(False) == []
    sequence.weather.pop()
    assert sequence.check(False)[0].startswith("FileX NYERS 1: the sequence runs")
