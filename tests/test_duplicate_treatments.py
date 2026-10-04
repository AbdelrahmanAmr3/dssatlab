"""Identical FileX treatment rows still select Q and retain duplicate-R checks."""

from datetime import date, timedelta
import subprocess

import pytest

from dssatlab import Simulation, run, runner


@pytest.fixture
def filex(tmp_path):
    row = f" 1 1 0 0 {'Duplicate':<25}  1  1  0  0  0  0  0  0  0  0  0  0  1\n"
    text = ("*TREATMENTS\n"
            "@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM\n"
            + row * 2 + "\n"
            "*CULTIVARS\n@C CR INGENO\n 1 MZ IB0001\n\n"
            "*FIELDS\n"
            "@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME\n"
            " 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910014 Field\n\n"
            "*SIMULATION CONTROLS\n"
            "@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL\n"
            " 1 GE              1     1     S 78074  2150 Duplicate rows\n")
    path = tmp_path / "UFGA7804.SQX"
    path.write_text(text, encoding="latin-1")
    return path


@pytest.mark.parametrize("treatment", [None, 1])
def test_identical_rows_run_in_q_with_both_batch_rows(filex, monkeypatch, treatment):
    executable = filex.parent / "dscsm048"
    monkeypatch.setattr(runner, "connect", lambda **kwargs: executable)
    batch_row = (filex.name.ljust(92) + "      1      1      1      0      0\r\n").encode("latin-1")
    batch = (b"$BATCH(SEQUENCE)\r\n\r\n"
             b"@FILEX                                                                                        "
             b"TRTNO     RP     SQ     OP     CO\r\n" + batch_row * 2)

    def execute(command, *, cwd, stdin, capture_output, text):
        assert command == [str(executable), "Q", "DSSBatch.v48"]
        assert cwd == filex.parent
        assert stdin == subprocess.DEVNULL and capture_output and text
        assert (cwd / "DSSBatch.v48").read_bytes() == batch
        return subprocess.CompletedProcess(command, 0, "done", "")

    monkeypatch.setattr(subprocess, "run", execute)
    result = run(filex, treatment=treatment)
    assert result.outputs == [result.run_dir / "DSSBatch.v48"]
    assert result.outputs[0].read_bytes() == batch


def test_identical_rows_report_existing_duplicate_r_problem(filex):
    first = date(1978, 3, 15)
    weather = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                    date=first + timedelta(days=i), srad=20, tmax=25, tmin=10, rain=0)
               for i in range(365)]
    before = filex.read_bytes()
    assert Simulation(filex, 1, weather).check() == [
        "Treatment 1 has rotation components R 1, 1: "
        "give each row of a sequence its own R number."]
    assert filex.read_bytes() == before
    assert list(filex.parent.iterdir()) == [filex]
