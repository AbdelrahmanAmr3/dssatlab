"""Tests for reading DSSAT evaluation (Evaluate.OUT) (#105)."""

from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATOutputError, read_dssat_evaluation
from dssatlab.runner import RunResult


FIXTURES = Path(__file__).parent / "fixtures" / "output_files" / "evaluate" / "maize"

@pytest.mark.parametrize("as_string", [False, True])
def test_read_dssat_evaluation_maize_fixture(as_string):
    run_dir = FIXTURES
    rows = read_dssat_evaluation(str(run_dir) if as_string else run_dir)
    assert len(rows) == 6

    # Treatment 1 check
    t1 = rows[0]
    assert t1["RUN"] == 1 and type(t1["RUN"]) is int
    assert t1["EXCODE"] == "UFGA8201MZ" and type(t1["EXCODE"]) is str
    assert t1["TN"] == 1 and type(t1["TN"]) is int
    assert t1["RN"] == 1 and type(t1["RN"]) is int
    assert t1["CR"] == "MZ" and type(t1["CR"]) is str
    assert t1["ADAPS"] == 76 and type(t1["ADAPS"]) is int
    assert t1["ADAPM"] == 75 and type(t1["ADAPM"]) is int
    assert t1["PD1PS"] is None
    assert t1["PD1PM"] is None
    assert t1["MDAPS"] == 128 and type(t1["MDAPS"]) is int
    assert t1["MDAPM"] == 128 and type(t1["MDAPM"]) is int
    assert t1["HWAMS"] == 2293 and type(t1["HWAMS"]) is int
    # Specific requirement: HWAMM of treatment 1 == 2929.0 and type is float
    assert t1["HWAMM"] == 2929.0 and type(t1["HWAMM"]) is float
    assert t1["H#AMS"] == 742 and type(t1["H#AMS"]) is int
    assert t1["H#AMM"] == 917.0 and type(t1["H#AMM"]) is float
    assert t1["HWUMS"] == 0.3090 and type(t1["HWUMS"]) is float
    assert t1["HWUMM"] == 0.218 and type(t1["HWUMM"]) is float
    assert t1["H#UMS"] == 110.9 and type(t1["H#UMS"]) is float
    assert t1["H#UMM"] == 229.0 and type(t1["H#UMM"]) is float
    assert t1["CWAMS"] == 6556 and type(t1["CWAMS"]) is int
    assert t1["CWAMM"] == 5532.0 and type(t1["CWAMM"]) is float
    assert t1["BWAMS"] == 4307 and type(t1["BWAMS"]) is int
    assert t1["BWAMM"] == 3530.0 and type(t1["BWAMM"]) is float
    assert t1["LAIXS"] == 1.99 and type(t1["LAIXS"]) is float
    assert t1["LAIXM"] == 2.26 and type(t1["LAIXM"]) is float
    assert t1["HIAMS"] == 0.350 and type(t1["HIAMS"]) is float
    assert t1["HIAMM"] is None
    assert t1["GNAMS"] == 40 and type(t1["GNAMS"]) is int
    assert t1["GNAMM"] == 31.7 and type(t1["GNAMM"]) is float
    assert t1["CNAMS"] == 80 and type(t1["CNAMS"]) is int
    assert t1["CNAMM"] == 69.5 and type(t1["CNAMM"]) is float
    assert t1["SNAMS"] == 37 and type(t1["SNAMS"]) is int
    assert t1["SNAMM"] == 37.8 and type(t1["SNAMM"]) is float
    assert t1["GN%MS"] == 1.7 and type(t1["GN%MS"]) is float
    assert t1["GN%MM"] == 1.80 and type(t1["GN%MM"]) is float
    assert t1["CWAAS"] == 3933 and type(t1["CWAAS"]) is int
    assert t1["CWAAM"] is None
    assert t1["L#SMS"] == 20.41 and type(t1["L#SMS"]) is float
    assert t1["EDAPS"] == 11 and type(t1["EDAPS"]) is int
    assert t1["EDAPM"] is None

    # Treatment 4 check (integers and floats in other rows)
    t4 = rows[3]
    assert t4["RUN"] == 4
    assert t4["TN"] == 4
    assert t4["HWAMS"] == 11854 and type(t4["HWAMS"]) is int
    assert t4["HWAMM"] == 11881 and type(t4["HWAMM"]) is int
    assert t4["H#AMM"] == 3847.0 and type(t4["H#AMM"]) is float
    assert t4["CWAMS"] == 22454 and type(t4["CWAMS"]) is int
    assert t4["CWAMM"] == 22001 and type(t4["CWAMM"]) is int


def test_missing_evaluate_file_raises_dssat_output_error(tmp_path):
    run_dir = tmp_path / "empty_run_dir"
    run_dir.mkdir()
    with pytest.raises(DSSATOutputError) as exc_info:
        read_dssat_evaluation(run_dir)
    message = str(exc_info.value)
    assert str(run_dir / "Evaluate.OUT") in message
    assert "Run the FileX with run() and its FileA beside it" in message


def test_broken_evaluate_file_errors(tmp_path):
    run_dir = tmp_path / "broken"
    run_dir.mkdir()
    eval_file = run_dir / "Evaluate.OUT"

    # Missing @ header
    eval_file.write_text("*EVALUATION : test\n* another comment\n")
    with pytest.raises(DSSATOutputError, match="header.*not found"):
        read_dssat_evaluation(run_dir)

    # Data before header
    eval_file.write_text("1 UFGA8201MZ 1 1 MZ\n@RUN EXCODE TN RN CR\n")
    with pytest.raises(DSSATOutputError, match="data before header"):
        read_dssat_evaluation(run_dir)

    # No data rows
    eval_file.write_text("@RUN EXCODE TN RN CR\n")
    with pytest.raises(DSSATOutputError, match="no data rows"):
        read_dssat_evaluation(run_dir)

    # Duplicate columns
    eval_file.write_text("@RUN EXCODE RUN\n 1 UFGA8201MZ 1\n")
    with pytest.raises(DSSATOutputError, match="unique"):
        read_dssat_evaluation(run_dir)

    # Malformed data row (wrong column count)
    eval_file.write_text("@RUN EXCODE TN RN CR\n 1 UFGA8201MZ 1\n")
    with pytest.raises(DSSATOutputError, match="Malformed Evaluate.OUT data row"):
        read_dssat_evaluation(run_dir)


def test_multiple_evaluation_blocks_and_headers(tmp_path):
    run_dir = tmp_path / "multi_block"
    run_dir.mkdir()
    eval_file = run_dir / "Evaluate.OUT"
    content = """*EVALUATION : BLOCK 1
@RUN EXCODE TN RN CR HWAMS HWAMM
   1 UFGA8201MZ 1 1 MZ 2293 2929.
   2 UFGA8201MZ 2 1 MZ 2293 3130.

*EVALUATION : BLOCK 2
@RUN EXCODE TN RN CR HWAMS HWAMM LAIXS
   3 UFGA8201MZ 3 1 MZ 8207 6850. 2.51
"""
    eval_file.write_text(content)
    rows = read_dssat_evaluation(run_dir)
    assert len(rows) == 3
    assert rows[0]["RUN"] == 1 and rows[0]["HWAMM"] == 2929.0 and "LAIXS" not in rows[0]
    assert rows[1]["RUN"] == 2 and rows[1]["HWAMM"] == 3130.0 and "LAIXS" not in rows[1]
    assert rows[2]["RUN"] == 3 and rows[2]["HWAMM"] == 6850.0 and rows[2]["LAIXS"] == 2.51


def test_run_result_dssat_evaluation(tmp_path):
    run_dir = tmp_path / "run_dir"
    shutil.copytree(FIXTURES, run_dir)
    result = RunResult(0, run_dir, [run_dir / "Evaluate.OUT"], "DSSAT finished")
    rows = result.dssat_evaluation()
    assert len(rows) == 6
    assert rows == read_dssat_evaluation(run_dir)
    assert rows[0]["HWAMM"] == 2929.0


def test_cropsim_title_line_and_trno_column(tmp_path):
    # CROPSIM (wheat CSCER048) starts Evaluate.OUT with a $ title and names the treatment TRNO.
    (tmp_path / "Evaluate.OUT").write_text(
        "$PLANT EVALUATION\n  \n*EVALUATION : KSAS8101WH  N RESPONSE,KANSAS STATE    CSCER048\n\n"
        "@RUN EXCODE      TRNO RN CR EDAPS EDAPM HWAMS HWAMM HWUMS HWUMM\n"
        "   1 KSAS8101WH     2  0 WH     5   -99  3485   -99 0.019 -99.0\n")
    assert read_dssat_evaluation(tmp_path) == [dict(
        RUN=1, EXCODE="KSAS8101WH", TRNO=2, RN=0, CR="WH", EDAPS=5, EDAPM=None,
        HWAMS=3485, HWAMM=None, HWUMS=0.019, HWUMM=None)]
