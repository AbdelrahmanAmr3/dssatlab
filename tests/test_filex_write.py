"""FileX cells preserve the blank skipped by DSSAT's fixed formats."""

import pytest

from dssatlab.controls import _controls_text
from dssatlab.filex_write import _cell, _event_row, _planting_row, _repoint


@pytest.mark.parametrize("value", [123456, "ABCDEF", 1234.5, 123456.0])
def test_full_width_cell_requires_leading_blank(value):
    with pytest.raises(ValueError) as error:
        _cell(value, 6, "INITIAL CONDITIONS", "ICRES")
    message = str(error.value)
    assert f"INITIAL CONDITIONS column ICRES: value {str(value)!r} does not fit" in message
    assert "6-character field" in message
    assert "needs one leading blank" in message
    assert "Supply a shorter value" in message


@pytest.mark.parametrize("value,expected", [
    (1000.0, "  1000"), (-100.0, "  -100"), (10000.0, " 10000"),
    (100.0, " 100.0"), (12.5, "  12.5"), (0.0, "   0.0"),
    (-99, "   -99"), ("82056", " 82056"), ("IR001", " IR001"),
])
def test_cell_compacts_only_integral_floats_that_do_not_fit(value, expected):
    assert _cell(value, 6, "INITIAL CONDITIONS", "ICRES") == expected


@pytest.mark.parametrize("column", ["P", "C", "I", "F"])
def test_row_writers_accept_full_width_first_column(column):
    columns = {column: (0, 2), "PPOP": (2, 8)}
    if column == "P":
        row = _planting_row(columns, 99, {"population": 7.2})
    else:
        row = _event_row(columns, {column: 99, "PPOP": 7.2}, "DETAILS")
    assert row == "99   7.2"


@pytest.mark.parametrize("writer", ["planting", "event"])
def test_row_writers_reject_full_width_non_first_column(writer):
    columns = {"P": (0, 2), "PPOP": (2, 8)}
    with pytest.raises(ValueError, match="needs one leading blank"):
        if writer == "planting":
            _planting_row(columns, 1, {"population": 123456})
        else:
            _event_row(columns, {"P": 1, "PPOP": 123456}, "DETAILS")


FILEX = """*TREATMENTS
@N SM
 1  1
*SIMULATION CONTROLS
@N GENERAL START SDATE FROPT
 1 GE          S 82056     1
@N OUTPUTS FROPT
 1 OU          1
@N METHODS
98 ME
"""


def test_controls_accept_full_width_level_number():
    written = _controls_text(FILEX, 1, {"output_interval": 2})
    assert "\n 1 99\n" in written
    assert "\n 1 GE" in written
    assert "\n99 GE          S 82056     1\n" in written
    assert "\n99 OU          2\n" in written


@pytest.mark.parametrize("value", [100, "ABC"])
def test_treatment_level_cell_requires_leading_blank(value):
    lines = FILEX.splitlines(keepends=True)
    with pytest.raises(ValueError, match="TREATMENTS column SM.*needs one leading blank"):
        _repoint(lines, 1, "SM", value)


def test_controls_reject_full_width_changed_cell():
    with pytest.raises(ValueError, match="column FROPT.*needs one leading blank"):
        _controls_text(FILEX.replace("98 ME", " 1 ME"), 1, {"output_interval": 123456})
