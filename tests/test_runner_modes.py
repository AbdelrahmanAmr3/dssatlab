"""FileX run modes and batch lifecycle through a fake DSSAT subprocess."""

import subprocess

import pytest

from dssatlab import DSSATRunError, run, runner


SEQUENCE = "*TREATMENTS\n@N R O C TNAME\n 1 3 0 0 First\n 110 0 0 Second\n"
ORDINARY = "*TREATMENTS\n@N R O C TNAME\n  2 1 0 0 First\n  5 1 0 0 Second\n"
HEADER = (b"@FILEX                                                                                        "
          b"TRTNO     RP     SQ     OP     CO\r\n")


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    filex = tmp_path / "UFGA7804.SQX"
    filex.write_text(SEQUENCE, encoding="latin-1")
    executable = tmp_path / "dscsm048"
    monkeypatch.setattr(runner, "connect", lambda **kwargs: executable)
    return filex, executable


@pytest.mark.parametrize("name,text,treatment,mode,rows", [
    ("UFGA7804.SQX", SEQUENCE, 1, "Q", [(1, 3), (1, 10)]),
    ("UFGA7804.SQX", SEQUENCE, None, "Q", [(1, 3), (1, 10)]),
    ("UFGA7804.MZX", SEQUENCE, 1, "Q", [(1, 3), (1, 10)]),
    ("UFGA7804.SQX", SEQUENCE + " 2 4 0 0 Third\n 2 7 0 0 Fourth\n",
     2, "Q", [(2, 4), (2, 7)]),
    ("UFAC2301.FCX", ORDINARY, 5, "Y", [(5, 0)]),
    ("UFAC2301.fcx", ORDINARY, None, "Y", [(2, 0), (5, 0)]),
    ("UFAC2301.FCX", SEQUENCE + " 2 4 0 0 Third\n 2 7 0 0 Fourth\n",
     None, "Y", [(1, 0), (2, 0)]),
])
def test_batch_command_text_and_collection(inputs, monkeypatch, name, text, treatment, mode, rows):
    original, executable = inputs
    filex = original.rename(original.with_name(name))
    filex.write_text(text, encoding="latin-1")
    batch = ((b"$BATCH(SEQUENCE)\r\n\r\n" if mode == "Q" else b"$BATCH(FORECAST)\r\n\r\n")
             + HEADER + b"".join(
                 (name.ljust(92) + f"{n:7d}      1{r:7d}      0      0\r\n").encode("latin-1")
                 for n, r in rows))

    def execute(command, *, cwd, stdin, capture_output, text):
        assert command == [str(executable), mode, "DSSBatch.v48"]
        assert cwd == filex.parent
        assert stdin == subprocess.DEVNULL and capture_output and text
        assert (cwd / "DSSBatch.v48").read_bytes() == batch
        (cwd / "Summary.OUT").write_text("summary")
        return subprocess.CompletedProcess(command, 0, "done", "")

    monkeypatch.setattr(subprocess, "run", execute)
    result = run(filex, treatment=treatment)
    assert result.outputs == [result.run_dir / "DSSBatch.v48", result.run_dir / "Summary.OUT"]
    assert (result.run_dir / "DSSBatch.v48").read_bytes() == batch
    assert not (filex.parent / "DSSBatch.v48").exists()
    assert filex.read_text(encoding="latin-1") == text


@pytest.mark.parametrize("text,treatment", [(ORDINARY, None), (ORDINARY, 5),
                                           (SEQUENCE + "  2 1 0 0 Third\n", 2)])
@pytest.mark.parametrize("existing", [False, True])
def test_normal_run_has_no_batch_side_effect(inputs, monkeypatch, text, treatment, existing):
    filex, executable = inputs
    filex.write_text(text, encoding="latin-1")
    batch = filex.parent / "DSSBatch.v48"
    if existing:
        batch.write_bytes(b"user batch")

    def execute(command, *, cwd, **kwargs):
        expected = ["A", filex.name] if treatment is None else ["C", filex.name, str(treatment)]
        assert command == [str(executable), *expected]
        assert batch.exists() == existing
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", execute)
    result = run(filex, treatment=treatment)
    assert result.outputs == []
    assert batch.exists() == existing
    if existing:
        assert batch.read_bytes() == b"user batch"


@pytest.mark.parametrize("name,mode,label", [("UFGA7804.SQX", "Q", "sequence"),
                                           ("UFAC2301.FCX", "Y", "forecast")])
@pytest.mark.parametrize("guard", ["existing", "short-name"])
def test_batch_guards_write_nothing(inputs, monkeypatch, name, mode, label, guard):
    original, _ = inputs
    if guard == "short-name":
        name = name[1:]
    filex = original.rename(original.with_name(name))
    batch = filex.parent / "DSSBatch.v48"
    if guard == "existing":
        batch.write_bytes(b"user batch\xff")
        message = (f"Cannot run FileX {name} in {label} mode ({mode}): {filex.parent} "
                   "already holds DSSBatch.v48, which run() writes. Nothing was run. "
                   "Move or rename it" + (", or use Simulation, which runs in its own folder."
                   if mode == "Q" else
                   ", or copy the forecast FileX and its inputs to their own folder."))
    else:
        message = (f"Cannot run FileX {name!r}: its filename has 11 characters; "
                   f"DSSAT's {label} mode ({mode}) accepts exactly 12. Rename the FileX "
                   "to exactly 12 characters, including the extension, using DSSAT's 8.3 style.")
    before = {p: p.read_bytes() for p in filex.parent.iterdir()}

    def forbidden(*args, **kwargs):
        pytest.fail("guard must run before discovery or launch")

    monkeypatch.setattr(runner, "connect", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(DSSATRunError) as error:
        run(filex)
    assert str(error.value) == message
    assert {p: p.read_bytes() for p in filex.parent.iterdir()} == before


def test_multiple_sequence_treatments_require_selection(inputs, monkeypatch):
    filex, _ = inputs
    filex.write_text(SEQUENCE + " 2 4 0 0 Third\n 3 7 0 0 Fourth\n", encoding="latin-1")

    def forbidden(*args, **kwargs):
        pytest.fail("multi-treatment guard must run before discovery or launch")

    monkeypatch.setattr(runner, "connect", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(DSSATRunError) as error:
        run(filex)
    assert str(error.value) == (
        f"Cannot run FileX {filex.name} in sequence mode (Q) without a treatment: "
        "it has treatments 1, 2, 3, and DSSAT runs one continuous batch, carrying each "
        "treatment into the next. Nothing was run. Pass run(filex, treatment=n) for each treatment.")
    assert list(filex.parent.iterdir()) == [filex]


@pytest.mark.parametrize("mode", ["Q", "Y"])
@pytest.mark.parametrize("failure", ["nonzero", "error-out", "start"])
def test_batch_lifecycle_on_failure(inputs, monkeypatch, mode, failure):
    filex, _ = inputs
    if mode == "Y":
        filex = filex.rename(filex.with_suffix(".FCX"))
    seen = []

    def execute(command, *, cwd, **kwargs):
        seen.append((cwd / "DSSBatch.v48").read_bytes())
        if failure == "start":
            raise OSError("cannot execute")
        (cwd / "Summary.OUT").write_text("partial")
        if failure == "error-out":
            (cwd / "ERROR.OUT").write_text("failure")
        return subprocess.CompletedProcess(command, 99 if failure == "nonzero" else 0, "", "")

    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(DSSATRunError, match="Could not start|DSSAT run failed"):
        run(filex)
    assert len(seen) == 1
    assert not (filex.parent / "DSSBatch.v48").exists()
    run_dirs = list(filex.parent.glob("dssat_run_*"))
    if failure == "start":
        assert run_dirs == []
    else:
        assert len(run_dirs) == 1
        assert (run_dirs[0] / "DSSBatch.v48").read_bytes() == seen[0]
        assert (run_dirs[0] / "Summary.OUT").read_text() == "partial"
