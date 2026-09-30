from datetime import date
from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATOutputError, read_summary


FIXTURES = Path(__file__).parent / "fixtures" / "output_files" / "summary"


def copy_summary(tmp_path, case="maize"):
    return shutil.copytree(FIXTURES / case, tmp_path / case)


def assert_output_error(run_dir, *details):
    with pytest.raises(DSSATOutputError) as caught:
        read_summary(run_dir)
    message = str(caught.value)
    assert str(run_dir / "Summary.OUT") in message
    assert "Checked" in message
    assert "Check the run directory" in message
    assert "rerun DSSAT" in message
    for detail in details:
        assert detail.lower() in message.lower()


@pytest.mark.parametrize("as_string", [False, True])
def test_maize_summary_preserves_columns_and_types(tmp_path, as_string):
    run_dir = copy_summary(tmp_path)
    rows = read_summary(str(run_dir) if as_string else run_dir)
    assert len(rows) == 1
    row = rows[0]
    assert (row["RUNNO"], row["TRNO"], row["TNAM"]) == (
        1, 1, "RAINFED LOW NITROGEN")
    assert row["CR"] == "MZ"
    assert row["MODEL"] == "MZCER048"
    assert row["EXNAME"] == "UFGA8201"
    assert row["FNAM"] == "UFGA0002"
    assert row["WSTA"] == "UFGA8201"
    assert row["WYEAR"] == 1982
    assert row["SOIL_ID"] == "IBMZ910014"
    assert row["HWAM"] == 2295
    assert type(row["HWAM"]) is int
    assert row["HWUM"] == 0.3090
    assert type(row["HWUM"]) is float
    assert row["H#UM"] == 111.0
    assert type(row["H#UM"]) is float
    assert row["XLAT"] == -82.3689
    assert row["LONG"] == 29.638
    assert row["CRST"] == 1
    assert row["DWAP"] is None
    assert row["EYLDH"] is None
    assert {key: row[key] for key in ("SDAT", "PDAT", "EDAT", "ADAT", "MDAT", "HDAT")} == {
        "SDAT": date(1982, 2, 25), "PDAT": date(1982, 2, 26),
        "EDAT": date(1982, 3, 9), "ADAT": date(1982, 5, 13),
        "MDAT": date(1982, 7, 4), "HDAT": date(1982, 7, 4),
    }
    header = next(line for line in (run_dir / "Summary.OUT").read_text().splitlines()
                  if line.startswith("@"))
    assert set(row) == {name.rstrip(".") for name in header[1:].split()}


def test_wheat_summary(tmp_path):
    row, = read_summary(copy_summary(tmp_path, "wheat"))
    assert (row["RUNNO"], row["TRNO"], row["TNAM"]) == (
        1, 1, "DRYLAND  - 0 KG N/HA")
    assert row["CR"] == "WH"
    assert row["HWAM"] == 2195
    assert row["ADAT"] == date(1982, 5, 21)
    assert row["SDAT"] == date(1981, 10, 6)


def test_two_treatments_yield_two_complete_rows(tmp_path):
    first, second = read_summary(copy_summary(tmp_path, "two_treatments"))
    assert (first["RUNNO"], first["TRNO"], first["TNAM"]) == (
        1, 1, "RAINFED LOW NITROGEN")
    assert second == dict(first, RUNNO=2, TRNO=2, TNAM="IRRIGATED HIGH NITROGEN")


def test_missing_values_in_yield_and_date(tmp_path):
    row, = read_summary(copy_summary(tmp_path, "missing_value"))
    assert row["HWAM"] is None
    assert row["ADAT"] is None
    assert row["PDAT"] == date(1982, 2, 26)


@pytest.mark.parametrize("marker", ["-99", "-99.0", "-99.000"])
def test_all_missing_value_spellings(tmp_path, marker):
    run_dir = copy_summary(tmp_path, "missing_value")
    path = run_dir / "Summary.OUT"
    path.write_bytes(path.read_bytes().replace(b"     -99", marker.rjust(8).encode()))
    row, = read_summary(run_dir)
    assert row["HWAM"] is None
    assert row["ADAT"] is None


def test_missing_summary(tmp_path):
    assert_output_error(tmp_path, "missing", "run directory")


@pytest.mark.parametrize("case,detail", [("no_header", "header"), ("wrong_columns", "row")])
def test_broken_summary(tmp_path, case, detail):
    assert_output_error(copy_summary(tmp_path, case), detail)


def test_no_data_rows(tmp_path):
    run_dir = copy_summary(tmp_path)
    path = run_dir / "Summary.OUT"
    lines = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(b"".join(lines[:4]))
    assert_output_error(run_dir, "no data rows")


def test_invalid_second_row_never_returns_partial_data(tmp_path):
    run_dir = copy_summary(tmp_path, "two_treatments")
    path = run_dir / "Summary.OUT"
    lines = path.read_bytes().splitlines(keepends=True)
    lines[5] = lines[5][:-20] + b"\r\n"
    path.write_bytes(b"".join(lines))
    assert_output_error(run_dir, "row", "6")


def test_extra_data_column_is_rejected(tmp_path):
    run_dir = copy_summary(tmp_path)
    path = run_dir / "Summary.OUT"
    path.write_bytes(path.read_bytes().rstrip() + b"   123\r\n")
    assert_output_error(run_dir, "row")


def test_latin1_text_and_numeric_text_identifiers(tmp_path):
    run_dir = copy_summary(tmp_path)
    path = run_dir / "Summary.OUT"
    path.write_bytes(path.read_bytes().replace(b"RAINFED LOW NITROGEN", b"CAF\xe9 LOW NITROGEN   ")
                     .replace(b"IBMZ910014", b"0012345678"))
    row, = read_summary(run_dir)
    assert row["TNAM"] == "CAF\xe9 LOW NITROGEN"
    assert row["SOIL_ID"] == "0012345678"


@pytest.mark.parametrize("encoded,expected", [("1982365", date(1982, 12, 31)),
                                               ("1984366", date(1984, 12, 31))])
def test_date_year_boundaries(tmp_path, encoded, expected):
    run_dir = copy_summary(tmp_path)
    path = run_dir / "Summary.OUT"
    path.write_bytes(path.read_bytes().replace(b"1982133", encoded.encode()))
    assert read_summary(run_dir)[0]["ADAT"] == expected


@pytest.mark.parametrize("encoded", [b"1982000", b"1982366", b"1982999", b"1982bad"])
def test_invalid_dates_are_output_errors(tmp_path, encoded):
    run_dir = copy_summary(tmp_path)
    path = run_dir / "Summary.OUT"
    path.write_bytes(path.read_bytes().replace(b"1982133", encoded))
    assert_output_error(run_dir, "ADAT", "row")


def test_column_boundaries_follow_header_widths(tmp_path):
    run_dir = copy_summary(tmp_path)
    expected = read_summary(run_dir)
    path = run_dir / "Summary.OUT"
    lines = path.read_bytes().splitlines(keepends=True)
    lines[3] = b"@   " + lines[3][1:]
    lines[4] = b"   " + lines[4]
    path.write_bytes(b"".join(lines))
    assert read_summary(run_dir) == expected


@pytest.mark.parametrize("replacement", [b"        ", b" 12   34"])
def test_missing_or_multiple_numbers_in_one_column(tmp_path, replacement):
    run_dir = copy_summary(tmp_path)
    path = run_dir / "Summary.OUT"
    path.write_bytes(path.read_bytes().replace(b"    2295", replacement, 1))
    assert_output_error(run_dir, "HWAM", "row")


def test_header_without_treatment_identity(tmp_path):
    run_dir = copy_summary(tmp_path)
    path = run_dir / "Summary.OUT"
    path.write_bytes(path.read_bytes().replace(b"TRNO", b"XXXX"))
    assert_output_error(run_dir, "header", "TRNO")
