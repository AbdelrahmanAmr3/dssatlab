"""The FileX treatment-number reader."""

import pytest

from dssatlab.filex import read_treatment_numbers

HEADER = "@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM\n"
ROW = " {n} 1 0 0 TREATMENT {n}                    1  1  0  1  1  1  1  0  0  0  0  0  1\n"


def write(tmp_path, text):
    path = tmp_path / "TEST0001.MZX"
    path.write_text(text, encoding="latin-1")
    return path


def test_lists_treatments_in_file_order(tmp_path):
    text = "*TREATMENTS   -----FACTOR LEVELS-----\n" + HEADER + ROW.format(n=3) + ROW.format(n=1) + "\n*FIELDS\n"
    assert read_treatment_numbers(write(tmp_path, text)) == [3, 1]


def test_collects_rows_across_header_blocks(tmp_path):
    text = "*TREATMENTS\n" + HEADER + ROW.format(n=1) + "\n" + HEADER + ROW.format(n=2)
    assert read_treatment_numbers(write(tmp_path, text)) == [1, 2]


def test_missing_section_is_reported(tmp_path):
    with pytest.raises(ValueError, match="missing TREATMENTS section"):
        read_treatment_numbers(write(tmp_path, "*FIELDS\n"))


def test_section_without_rows_is_reported(tmp_path):
    with pytest.raises(ValueError, match="no treatment rows"):
        read_treatment_numbers(write(tmp_path, "*TREATMENTS\n" + HEADER))


def test_unreadable_path_is_reported(tmp_path):
    with pytest.raises(ValueError, match="Cannot read FileX"):
        read_treatment_numbers(tmp_path / "missing.MZX")


def test_comment_lines_are_skipped(tmp_path):
    text = "*TREATMENTS\n" + HEADER + "! a comment\n" + ROW.format(n=1)
    assert read_treatment_numbers(write(tmp_path, text)) == [1]
