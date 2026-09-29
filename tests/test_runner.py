"""Run behavior through a fake DSSAT subprocess that writes real files."""
from dataclasses import FrozenInstanceError
from datetime import datetime
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dssatlab import DSSATRunError, run, runner


@pytest.fixture
def fake_dssat(tmp_path, monkeypatch):
    folder = tmp_path / "FileX folder"
    folder.mkdir()
    filex = folder / "uFgA8201.MzX"
    filex.write_text("FileX", encoding="utf-8")
    executable = tmp_path / "DSSAT install" / "dscsm048"
    connect = Mock(return_value=executable)
    monkeypatch.setattr(runner, "connect", connect)
    monkeypatch.setattr(runner, "datetime", SimpleNamespace(
        now=lambda: datetime(2026, 9, 29, 12, 34, 56)))
    state = SimpleNamespace(
        filex=filex, executable=executable, connect=connect,
        calls=[], outputs={"Summary.OUT": "summary"}, returncode=0,
        stdout="DSSAT finished\n", mtimes={},
    )

    def fake_run(command, *, cwd, **kwargs):
        state.calls.append((command, cwd, kwargs))
        assert any(path.is_dir() and path.name.startswith("dssat_run_")
                   for path in Path(cwd).iterdir())
        for name, content in state.outputs.items():
            output = Path(cwd) / name
            output.write_text(content, encoding="utf-8")
            if name in state.mtimes:
                os.utime(output, ns=(state.mtimes[name], state.mtimes[name]))
        return subprocess.CompletedProcess(command, state.returncode,
                                           stdout=state.stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return state


@pytest.mark.parametrize("relative", [False, True])
def test_all_treatments_command_and_result(tmp_path, monkeypatch, fake_dssat, relative):
    monkeypatch.chdir(tmp_path)
    filex = fake_dssat.filex
    argument = str(filex.relative_to(tmp_path)) if relative else filex

    result = run(argument)

    fake_dssat.connect.assert_called_once_with(interactive=False)
    assert fake_dssat.calls == [
        ([str(fake_dssat.executable), "A", filex.name], filex.parent,
         {"stdin": subprocess.DEVNULL, "capture_output": True, "text": True})
    ]
    assert isinstance(result, runner.RunResult)
    assert result.returncode == 0
    assert result.run_dir == filex.parent / "dssat_run_2026-09-29_123456"
    assert result.run_dir.is_dir()
    assert result.outputs == [result.run_dir / "Summary.OUT"]
    assert result.stdout_tail == "DSSAT finished"
    with pytest.raises(FrozenInstanceError):
        result.returncode = 1


def test_collects_created_and_modified_files_only(fake_dssat):
    folder = fake_dssat.filex.parent
    untouched = {fake_dssat.filex.name: "FileX", "LOCAL.WTH": "weather",
                 "LOCAL.SOL": "soil", "old.OUT": "old output"}
    for name, content in untouched.items():
        (folder / name).write_text(content, encoding="utf-8")
    before = {name: (folder / name).stat().st_mtime_ns for name in untouched}
    summary = folder / "Summary.OUT"
    summary.write_text("old summary", encoding="utf-8")
    os.utime(summary, ns=(2_000_000_000, 2_000_000_000))
    (folder / "existing directory").mkdir()
    (folder / "existing directory" / "nested.OUT").write_text("nested")
    fake_dssat.outputs = {"WARNING.OUT": "warning", "Summary.OUT": "new summary",
                          "LUN.LST": "list"}
    # Even a timestamp older than the original is a change, regardless of wall time.
    fake_dssat.mtimes = {name: 1_000_000_000 for name in fake_dssat.outputs}

    result = run(fake_dssat.filex)

    assert result.outputs == [result.run_dir / name
                              for name in ["LUN.LST", "Summary.OUT", "WARNING.OUT"]]
    for output in result.outputs:
        assert output.read_text(encoding="utf-8") == fake_dssat.outputs[output.name]
        assert not (folder / output.name).exists()
    for name, content in untouched.items():
        assert (folder / name).read_text(encoding="utf-8") == content
        assert (folder / name).stat().st_mtime_ns == before[name]
    assert (folder / "existing directory" / "nested.OUT").read_text() == "nested"


def test_same_second_runs_never_reuse_run_directory(fake_dssat):
    results = [run(fake_dssat.filex) for _ in range(3)]

    assert [result.run_dir.name for result in results] == [
        "dssat_run_2026-09-29_123456", "dssat_run_2026-09-29_123456-2",
        "dssat_run_2026-09-29_123456-3",
    ]
    for result in results:
        assert (result.run_dir / "Summary.OUT").read_text() == "summary"


@pytest.mark.parametrize("stdout", ["", "one\ntwo\n",
                                   "\n".join(str(i) for i in range(25)) + "\n"])
def test_stdout_tail_and_empty_outputs(fake_dssat, stdout):
    fake_dssat.stdout = stdout
    fake_dssat.outputs = {}

    result = run(fake_dssat.filex)

    assert result.stdout_tail == "\n".join(stdout.splitlines()[-20:])
    assert result.outputs == []


def test_nonzero_exit_reports_status_and_collects_outputs(fake_dssat):
    fake_dssat.returncode = 99
    fake_dssat.outputs = {"ERROR.OUT": "fatal input error"}

    result = run(fake_dssat.filex)

    assert result.returncode == 99
    assert result.outputs == [result.run_dir / "ERROR.OUT"]
    assert result.outputs[0].read_text() == "fatal input error"


def test_long_filename_rejected_before_discovery_or_run(fake_dssat):
    filex = fake_dssat.filex.with_name("UFGA82010.MZX")
    fake_dssat.filex.rename(filex)

    with pytest.raises(DSSATRunError) as error:
        run(filex)

    for text in (filex.name, "13", "12", "Rename", "8.3"):
        assert text in str(error.value)
    fake_dssat.connect.assert_not_called()
    assert fake_dssat.calls == []
    assert list(filex.parent.iterdir()) == [filex]
