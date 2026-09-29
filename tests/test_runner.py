"""Run behavior through a fake DSSAT subprocess that writes real files."""
from dataclasses import FrozenInstanceError
from datetime import datetime
import os
from pathlib import Path
import shlex
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dssatlab import DSSATNotFoundError, DSSATRunError, core, run, runner


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
        stdout="DSSAT finished\n", stderr="", mtimes={}, start_error=None,
    )

    def fake_run(command, *, cwd, **kwargs):
        state.calls.append((command, cwd, kwargs))
        assert any(path.is_dir() and path.name.startswith("dssat_run_")
                   for path in Path(cwd).iterdir())
        if state.start_error is not None:
            raise state.start_error
        for name, content in state.outputs.items():
            output = Path(cwd) / name
            output.write_bytes(content if isinstance(content, bytes)
                               else content.encode("utf-8"))
            if name in state.mtimes:
                os.utime(output, ns=(state.mtimes[name], state.mtimes[name]))
        return subprocess.CompletedProcess(command, state.returncode,
                                           stdout=state.stdout, stderr=state.stderr)

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


@pytest.mark.parametrize("stderr", ["", "stderr detail\n"])
def test_nonzero_exit_reports_status_and_collects_outputs(fake_dssat, stderr):
    fake_dssat.returncode = 99
    fake_dssat.stdout = "\n".join(f"console {i:02}" for i in range(25)) + "\n"
    fake_dssat.stderr = stderr
    fake_dssat.outputs = {"WARNING.OUT": "warning", "Summary.OUT": "partial"}

    with pytest.raises(DSSATRunError) as error:
        run(fake_dssat.filex, treatment=2)

    run_dir = fake_dssat.filex.parent / "dssat_run_2026-09-29_123456"
    message = str(error.value)
    command = [str(fake_dssat.executable), "C", fake_dssat.filex.name, "2"]
    tail = "\n".join((fake_dssat.stdout + stderr).splitlines()[-20:])
    for text in ("99", shlex.join(command), tail, str(run_dir),
                 "Open ERROR.OUT and WARNING.OUT"):
        assert text in message
    assert "console 04" not in message
    assert ("console 05" in message) == (not stderr)
    for name, content in fake_dssat.outputs.items():
        assert (run_dir / name).read_text() == content
        assert not (fake_dssat.filex.parent / name).exists()


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


@pytest.mark.parametrize("treatment", [3, 0, -1, "bad"])
def test_single_treatment_command_and_outputs(fake_dssat, treatment):
    result = run(fake_dssat.filex, treatment=treatment)

    assert fake_dssat.calls == [
        ([str(fake_dssat.executable), "C", fake_dssat.filex.name, str(treatment)],
         fake_dssat.filex.parent,
         {"stdin": subprocess.DEVNULL, "capture_output": True, "text": True})
    ]
    assert result.run_dir == fake_dssat.filex.parent / "dssat_run_2026-09-29_123456"
    assert result.outputs == [result.run_dir / "Summary.OUT"]
    assert result.outputs[0].read_text() == "summary"
    assert not (fake_dssat.filex.parent / "Summary.OUT").exists()


@pytest.mark.parametrize("kind", ["file", "directory", "missing", "wrong-name", "nested"])
def test_explicit_executable_validation_without_discovery_or_config(
        fake_dssat, tmp_path, monkeypatch, kind):
    executable = tmp_path / "chosen install" / "DSCSM048.EXE"
    executable.parent.mkdir()
    executable.write_text("fake DSSAT")
    executable.chmod(0o755)
    argument = executable if kind == "file" else executable.parent
    if kind == "missing":
        argument = tmp_path / "missing"
    elif kind == "wrong-name":
        argument = executable.rename(executable.with_name("other.exe"))
    elif kind == "nested":
        nested = executable.parent / "nested"
        nested.mkdir()
        executable.rename(nested / executable.name)
    save_config = Mock(side_effect=AssertionError("run must not save config"))
    monkeypatch.setattr(core.config, "save_config", save_config)
    fake_dssat.connect.side_effect = AssertionError("must not discover")

    if kind in ("file", "directory"):
        result = run(fake_dssat.filex, executable=str(argument))
        assert fake_dssat.calls[0][0] == [str(executable), "A", fake_dssat.filex.name]
        assert result.returncode == 0
    else:
        with pytest.raises(DSSATNotFoundError) as error:
            run(fake_dssat.filex, executable=argument)
        assert str(error.value) == str(core._invalid_path(argument))
        assert fake_dssat.calls == []
        assert list(fake_dssat.filex.parent.iterdir()) == [fake_dssat.filex]
    fake_dssat.connect.assert_not_called()
    save_config.assert_not_called()


@pytest.mark.parametrize("kind", ["missing", "directory", "missing-long-name"])
def test_invalid_filex_rejected_first(fake_dssat, kind):
    filex = fake_dssat.filex
    filex.unlink()
    if kind == "directory":
        filex.mkdir()
    elif kind == "missing-long-name":
        filex = filex.with_name("missing_long_name.MZX")

    with pytest.raises(DSSATRunError) as error:
        run(filex)

    for text in (str(filex), "does not exist or is not a file", "existing FileX"):
        assert text in str(error.value)
    fake_dssat.connect.assert_not_called()
    assert fake_dssat.calls == []
    assert not list(filex.parent.glob("dssat_run_*"))


@pytest.mark.parametrize("mkdir_error", [PermissionError("read-only"), OSError("denied")])
def test_unwritable_filex_folder(fake_dssat, monkeypatch, mkdir_error):
    mkdir = Path.mkdir

    def cannot_create_run_dir(path, *args, **kwargs):
        if path.name.startswith("dssat_run_"):
            raise mkdir_error
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", cannot_create_run_dir)
    with pytest.raises(DSSATRunError) as error:
        run(fake_dssat.filex)

    for text in (str(fake_dssat.filex.parent), "not writable", "Move the FileX",
                 "writable", str(mkdir_error)):
        assert text in str(error.value)
    assert fake_dssat.calls == []
    assert list(fake_dssat.filex.parent.iterdir()) == [fake_dssat.filex]


def test_executable_cannot_start_removes_only_new_empty_run_directory(fake_dssat):
    old_run_dir = fake_dssat.filex.parent / "dssat_run_2026-09-29_123456"
    old_run_dir.mkdir()
    fake_dssat.start_error = OSError("cannot execute")

    with pytest.raises(DSSATRunError) as error:
        run(fake_dssat.filex)

    command = [str(fake_dssat.executable), "A", fake_dssat.filex.name]
    for text in ("Could not start", shlex.join(command), "cannot execute",
                 "Check the DSSAT executable", "execute permission"):
        assert text in str(error.value)
    assert len(fake_dssat.calls) == 1
    assert list(fake_dssat.filex.parent.glob("dssat_run_*")) == [old_run_dir]


@pytest.mark.parametrize("returncode", [0, 99])
def test_error_out_raises_with_first_20_lines_and_keeps_outputs(fake_dssat, returncode):
    fake_dssat.returncode = returncode
    contents = b"invalid byte: \xff\n" + "\n".join(
        f"fatal line {i:02}" for i in range(1, 25)).encode("utf-8")
    fake_dssat.outputs = {"ERROR.OUT": contents, "WARNING.OUT": "warning"}
    # A modified ERROR.OUT counts too, even if one existed before this run.
    previous = fake_dssat.filex.parent / "ERROR.OUT"
    previous.write_text("old error")
    os.utime(previous, ns=(1_000_000_000, 1_000_000_000))

    with pytest.raises(DSSATRunError) as error:
        run(fake_dssat.filex)

    run_dir = fake_dssat.filex.parent / "dssat_run_2026-09-29_123456"
    message = str(error.value)
    for text in ("ERROR.OUT", "invalid byte: \ufffd", "fatal line 01", "fatal line 19",
                 str(run_dir), "Open ERROR.OUT and WARNING.OUT"):
        assert text in message
    assert "fatal line 20" not in message
    assert (run_dir / "ERROR.OUT").read_bytes() == contents
    assert (run_dir / "WARNING.OUT").read_text() == "warning"
    assert not previous.exists()


def test_untouched_error_out_does_not_fail_new_run(fake_dssat):
    previous = fake_dssat.filex.parent / "ERROR.OUT"
    previous.write_text("old error")

    result = run(fake_dssat.filex)

    assert result.returncode == 0
    assert result.outputs == [result.run_dir / "Summary.OUT"]
    assert previous.read_text() == "old error"
