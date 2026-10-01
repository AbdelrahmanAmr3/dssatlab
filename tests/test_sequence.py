"""Sequence checks and runs through Simulation and a fake DSSAT executable."""

from pathlib import Path
import platform
import re
import subprocess

import pytest

from dssatlab import DSSATCheckError, DSSATRunError, Simulation
from test_simulation_run import fake_dssat  # noqa: F401; caches uname before mocking subprocess


FIXTURES = Path(__file__).parent / "fixtures"
REPORT = ("FileX: treatment 1 is a sequence of 6 rotation components "
          "(R 1-6: BN, FA, BN, FA, SB, FA); it runs in DSSAT's sequence mode.")


@pytest.fixture
def sequence(tmp_path):
    text = (FIXTURES / "UFGA7804.SQX").read_text(encoding="latin-1")
    text = text.replace(" 1 GE             10     5", " 1 GE              1     1")
    filex = tmp_path / "UFGA7804.SQX"
    filex.write_text(text, encoding="latin-1")
    weather = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                    date="1978-04-20", srad=20, tmax=25, tmin=10, rain=0)]
    return Simulation(filex, 1, weather)


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
    batch = folder / "DSSBatch.v48"
    assert batch.read_bytes() == (FIXTURES / "DSSBatch.v48").read_bytes()
    assert seen["DSSBatch.v48"] == batch.read_bytes()
    assert seen[sequence.filex.name] == sequence.filex.read_bytes()
    assert "UFGA7801.WTH" in seen
    for number, line in enumerate(batch.read_text().splitlines()[3:], 1):
        assert line[:92].rstrip() == sequence.filex.name
        assert [int(line[i:i+7]) for i in range(92, 127, 7)] == [1, 1, number, 0, 0]
    assert result.outputs == [result.run_dir / "Summary.OUT"]
    assert result.outputs[0].read_bytes() == b"summary"
    assert not (folder / "Summary.OUT").exists()
    assert (folder / "UFGA7801.WTH").is_file()


MESSAGES = {
    "filename": "A sequence runs in DSSAT's sequence mode, which needs a FileX filename of exactly 12 characters (8 plus the extension, like UFGA7804.SQX); 'SEQ1.SQX' has 8. Rename the FileX.",
    "R": "Treatment 1 has rotation components R 1, 1, 3, 4, 5, 6: give each row of a sequence its own R number.",
    "FL": "Treatment 1 is a sequence whose components use fields 1 and 2; dssatlab writes one weather file and one soil profile, so give every component the same field (FL).",
    "NREPS": "FileX NREPS 5 for sequence treatment 1: with measured weather every replicate repeats the same rows. Set NREPS to 1.",
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


@pytest.mark.parametrize("value", ["0", "-1", "x"])
def test_invalid_rotation_number(sequence, value):
    change_component(sequence, 1, "R", value)
    assert sequence.check() == [
        f"Treatment 1 has rotation components R 1, {value}, 3, 4, 5, 6: "
        "give each row of a sequence its own R number."]


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
    assert (folder / "DSSBatch.v48").is_file()
    if failure != "start":
        assert next(folder.glob("dssat_run_*/Summary.OUT")).is_file()
