"""Soil codes retain DSSAT's five-character, fixed-column layout."""

from copy import deepcopy

import pytest

from dssatlab.soil import _parse_soil, write_soil_file
from test_soil_check import rows, simulation, write_csv


COLUMNS = ("slmh", "smhb", "smpx", "smke", "scom")


def source_for(form, rows, tmp_path):
    if form == "dataframe":
        return pytest.importorskip("pandas").DataFrame(rows)
    if form == "csv":
        return write_csv(tmp_path / "soil.csv", rows)
    return rows


@pytest.mark.parametrize("form", ["csv", "dataframe"])
@pytest.mark.parametrize("code", ["AP", "BT", "IB001", "BN", "a_+.1", 1, 1.0, 0.6])
def test_codes_checked_and_written_in_six_character_columns(
        simulation, rows, tmp_path, form, code):
    for row in rows:
        row.update(dict.fromkeys(COLUMNS, code))
    source = source_for(form, rows, tmp_path)
    simulation.soil = source
    assert simulation.check() == []
    parsed, problems = _parse_soil(source)
    assert problems == []
    text = write_soil_file(parsed, tmp_path / "SOIL.SOL").read_text("ascii")
    expected = f"{code:g}" if isinstance(code, (int, float)) else code
    lines = text.splitlines()
    for index in (0, 7, 8, 9):
        assert lines[5][index * 6:(index + 1) * 6] == f"{expected:>6}"
    for line in lines[7:]:
        assert line[6:12] == f"{expected:>6}"
        assert len(line) == 102
    assert len(lines[5]) == 60
    csv_parsed, problems = _parse_soil(write_csv(tmp_path / "equivalent.csv", rows))
    assert problems == []
    assert write_soil_file(csv_parsed, tmp_path / "equivalent.SOL").read_bytes() == text.encode("ascii")


@pytest.mark.parametrize("form", ["rows", "csv", "dataframe"])
@pytest.mark.parametrize("column", COLUMNS)
@pytest.mark.parametrize("value", ["١", "IB0001", "2*BN", "A B", "A,B", "A/B", 'A"B',
                                 "A'B", "é", 123456, "oops!!", float("inf")])
def test_invalid_codes_name_row_column_value_and_rule(
        simulation, rows, tmp_path, form, column, value):
    for row in rows:
        row[column] = -99
    rows[1][column] = value
    simulation.soil = source_for(form, rows, tmp_path)
    problems = simulation.check()
    assert any(all(word in problem for word in
                   ("row 3", repr(column), str(value), "1-5 ASCII", "_ . + -",
                    "5-character code")) for problem in problems)


@pytest.mark.parametrize("form", ["rows", "csv", "dataframe"])
@pytest.mark.parametrize("missing", [None, "", "  ", float("nan"), "nan", -99, -99.0])
def test_missing_codes_write_minus_99(simulation, rows, tmp_path, form, missing):
    for row in rows:
        row.update(dict.fromkeys(COLUMNS, -99))
    rows[1].update(dict.fromkeys(COLUMNS, missing))
    simulation.soil = source_for(form, rows, tmp_path)
    assert simulation.check() == []
    parsed, problems = _parse_soil(simulation.soil)
    assert problems == []
    lines = write_soil_file(parsed, tmp_path / "SOIL.SOL").read_text("ascii").splitlines()
    assert lines[5][:6] == "   -99"
    assert lines[5][42:] == "   -99" * 3
    assert lines[8][6:12] == "   -99"


@pytest.mark.parametrize("form", ["rows", "csv", "dataframe"])
@pytest.mark.parametrize("code", ["1E2", "2e1", "1_0"])
def test_number_shaped_text_codes_stay_text(simulation, rows, tmp_path, form, code):
    for row in rows:
        row["slmh"] = code
    simulation.soil = source_for(form, rows, tmp_path)
    assert simulation.check() == []
    parsed, problems = _parse_soil(simulation.soil)
    assert problems == []
    lines = write_soil_file(parsed, tmp_path / "SOIL.SOL").read_text("ascii").splitlines()
    assert lines[8][6:12] == f"{code:>6}"


@pytest.mark.parametrize("form", ["csv", "dataframe"])
def test_scom_must_match_every_profile_row(simulation, rows, tmp_path, form):
    for row in rows:
        row["scom"] = "BN"
    rows[1]["scom"] = "AP"
    before = deepcopy(rows)
    simulation.soil = source_for(form, rows, tmp_path)
    assert any(all(word in problem for word in ("row 3", "scom", "AP", "BN", "identical"))
               for problem in simulation.check())
    assert rows == before
