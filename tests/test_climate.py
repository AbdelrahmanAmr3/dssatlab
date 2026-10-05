"""Narrow climate checks against excerpts of stock DSSAT climate files."""

import pytest

from dssatlab.climate import _read_climate_file


# Copied from C:/DSSAT48/Weather/Climate/{UFGA,DTCM}.CLI.
# Keep both tables; omit only unrelated range checks and flagged-data counts.
UFGA = """*CLIMATE:Gainesville,Florida,USA

@ INSI      LAT     LONG  ELEV   TAV   AMP  SRAY  TMXY  TMNY  RAIY
  UFGA   29.630  -82.370    10  20.9  13.0  16.5  27.4  14.4  1300
@START  DURN  ANGA  ANGB REFHT WNDHT SOURCE
  1958    49  0.25  0.50   2.0   3.0 Calculated_from_daily_data
@ GSST  GSDU
     1   365

*MONTHLY AVERAGES
@  MTH  SAMN  XAMN  NAMN  RTOT  RNUM  SHMN  AMTH  BMTH
     1  10.9  19.7   6.1  84.0   8.1   -99 0.250 0.500
     2  13.5  21.4   7.2 109.3   7.5   -99 0.250 0.500
     3  17.3  24.5  10.0  98.0   7.6   -99 0.250 0.500
     4  21.3  28.0  13.4  74.3   5.6   -99 0.250 0.500
     5  22.2  31.0  17.1  92.3   7.5   -99 0.250 0.500
     6  20.7  32.6  20.6 162.9  12.0   -99 0.250 0.500
     7  20.5  33.1  21.8 169.3  15.6   -99 0.250 0.500
     8  19.0  33.0  21.7 193.9  15.4   -99 0.250 0.500
     9  16.4  31.6  20.5 133.1  11.1   -99 0.250 0.500
    10  14.3  28.4  16.1  56.0   6.2   -99 0.250 0.500
    11  11.7  24.3  11.1  57.0   6.0   -99 0.250 0.500
    12   9.6  21.1   7.8  69.8   7.4   -99 0.250 0.500

*WGEN PARAMETERS
@  MTH  SDMN  SDSD  SWMN  SWSD  XDMN  XDSD  XWMN  XWSD  NAMN  NASD ALPHA  RTOT   PDW  RNUM
     1  11.8   0.9   8.2   1.2  19.6   4.8  19.9   4.4   6.1   5.6 0.440  84.0 0.222   8.1
     2  14.8   1.1   9.9   1.3  21.3   4.6  21.5   3.8   7.2   5.3 0.277 109.3 0.212   7.5
     3  18.7   1.4  12.8   1.7  24.8   4.0  23.7   3.8  10.0   5.3 0.341  98.0 0.199   7.6
     4  22.6   0.9  15.9   1.3  28.3   3.0  26.6   3.3  13.4   3.9 0.401  74.3 0.151   5.6
     5  23.3   0.8  18.9   0.8  31.3   2.2  30.3   2.3  17.1   3.1 0.685  92.3 0.177   7.5
     6  22.4   0.8  18.3   0.8  33.1   1.8  31.8   2.2  20.6   2.0 0.453 162.9 0.266  12.0
     7  22.2   0.8  18.8   1.0  33.8   1.6  32.5   1.9  21.8   1.3 0.310 169.3 0.396  15.6
     8  20.6   0.6  17.4   0.9  33.7   1.5  32.2   2.2  21.7   1.2 0.357 193.9 0.288  15.4
     9  17.6   0.7  14.5   0.8  32.0   2.0  31.0   2.2  20.5   2.3 0.449 133.1 0.258  11.1
    10  15.0   0.9  11.6   0.9  28.5   3.0  28.3   2.9  16.1   4.5 0.298  56.0 0.138   6.2
    11  12.4   1.5   8.9   1.7  24.5   3.5  23.6   3.6  11.1   5.0 0.368  57.0 0.157   6.0
    12  10.5   1.5   6.8   1.8  21.5   4.4  20.1   4.3   7.8   5.8 0.439  69.8 0.195   7.4
"""


DTCM = """*CLIMATE : Chiangmai
@ INSI      LAT     LONG  ELEV   TAV   AMP  SRAY  TMXY  TMNY  RAIY
  DTCM   19.000   99.000     0  25.6  11.8  17.3  31.5  19.7  1226
@START  DURN  ANGA  ANGB REFHT WNDHT SOURCE
  1963    16  0.25  0.50 -99.0 -99.0 Calculated_from_daily_data
@ GSST  GSDU
     1   365

*MONTHLY AVERAGES
@  MTH  SAMN  XAMN  NAMN  RTOT  RNUM  SHMN  AMTH  BMTH
     1  16.7  28.5  12.8  12.6   1.5 -99.0 0.250 0.500
     2  18.6  31.7  13.8   2.9   0.9 -99.0 0.250 0.500
     3  19.3  34.6  17.5  17.6   2.2 -99.0 0.250 0.500
     4  20.3  35.7  21.1  47.6   6.0 -99.0 0.250 0.500
     5  19.0  33.6  23.1 150.2  15.3 -99.0 0.250 0.500
     6  17.3  32.3  23.5 130.8  16.1 -99.0 0.250 0.500
     7  15.8  31.5  23.3 183.0  19.1 -99.0 0.250 0.500
     8  15.7  30.6  23.1 271.6  21.9 -99.0 0.250 0.500
     9  16.5  31.0  22.8 230.8  17.2 -99.0 0.250 0.500
    10  16.7  30.9  21.6 118.7  11.1 -99.0 0.250 0.500
    11  16.0  29.5  18.7  43.6   5.2 -99.0 0.250 0.500
    12  15.7  28.3  15.0  16.5   2.5 -99.0 0.250 0.500

*WGEN PARAMETERS
@  MTH  SDMN  SDSD  SWMN  SWSD  XDMN  XDSD  XWMN  XWSD  NAMN  NASD ALPHA  RTOT   PDW  RNUM
     1  16.9   1.6  12.0   3.0  28.7   2.0  24.7   3.9  12.8   3.2 0.783  12.6 0.029   1.5
     2  18.8   1.1  15.2   3.8  31.8   2.0  28.8   4.1  13.8   2.8 0.945   2.9 0.028   0.9
     3  19.5   1.5  16.6   2.7  34.8   2.2  31.9   3.2  17.5   2.3 0.562  17.6 0.056   2.2
     4  20.7   1.6  18.8   2.7  36.1   2.2  33.8   3.6  21.1   1.9 0.625  47.6 0.152   6.0
     5  20.3   2.3  17.7   3.2  34.6   2.4  32.7   2.8  23.1   1.3 0.647 150.2 0.371  15.3
     6  18.4   2.8  16.3   2.8  32.8   1.5  31.7   1.8  23.5   1.2 0.655 130.8 0.401  16.1
     7  17.4   2.9  14.8   3.0  32.5   1.3  30.9   2.1  23.3   0.9 0.589 183.0 0.522  19.1
     8  17.5   2.8  14.9   2.9  31.6   1.2  30.2   2.0  23.1   0.9 0.693 271.6 0.585  21.9
     9  18.0   2.4  15.3   2.7  31.8   1.3  30.5   2.0  22.8   1.1 0.711 230.8 0.406  17.2
    10  17.5   2.2  15.3   2.7  31.3   1.4  30.2   2.3  21.6   1.5 0.667 118.7 0.270  11.1
    11  16.5   2.2  13.9   2.8  29.6   2.0  29.2   2.2  18.7   2.9 0.651  43.6 0.115   5.2
    12  16.0   1.9  12.5   3.0  28.5   2.1  26.4   3.2  15.0   3.3 0.634  16.5 0.045   2.5
"""


@pytest.fixture(params=[("UFGA", "W"), ("DTCM", "S")])
def climate_file(tmp_path, request):
    station, method = request.param
    path = tmp_path / f"{station}.CLI"
    path.write_text(UFGA if station == "UFGA" else DTCM, encoding="ascii")
    return path, method


def replace_cell(path, section, month, column, value):
    lines = path.read_text().splitlines()
    start = lines.index("*" + section)
    header = lines[start + 1]
    names = header.split()[1:]
    field = names.index(column)
    # Stock columns end at their labels; preserve every other field's bytes.
    end = header.index(column) + len(column)
    begin = 0 if field == 0 else header.index(names[field - 1]) + len(names[field - 1]) + 1
    for index in range(start + 2, len(lines)):
        if lines[index].startswith("*"):
            break
        if lines[index].split() and lines[index].split()[0] == str(month):
            lines[index] = lines[index][:begin] + value.rjust(end - begin) + lines[index][end:]
            break
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def needed_table(method):
    return "WGEN PARAMETERS" if method == "W" else "MONTHLY AVERAGES"


def assert_problem(problems, *details):
    assert len(problems) == 1
    for detail in details:
        assert detail in problems[0]
    assert "Checked " in problems[0]
    assert "Supply " in problems[0] or "Correct " in problems[0]


def test_good_stock_climate_is_read_without_changes(climate_file):
    path, method = climate_file
    before = path.read_bytes()
    assert _read_climate_file(path, method) == []
    assert path.read_bytes() == before


def test_station_matches_first_four_filename_characters_case_insensitively(climate_file):
    path, method = climate_file
    renamed = path.with_name(path.stem.lower() + "1234.cli")
    path.rename(renamed)
    assert _read_climate_file(str(renamed), method) == []


@pytest.mark.parametrize("first_line", ["", "*WEATHER", " *CLIMATE", "!comment\n*CLIMATE"])
def test_first_line_must_start_with_climate(climate_file, first_line):
    path, method = climate_file
    text = path.read_text()
    path.write_text(first_line + "\n" + text.split("\n", 1)[1])
    assert_problem(_read_climate_file(path, method), str(path), "*CLIMATE", "first line")


def test_station_mismatch(climate_file):
    path, method = climate_file
    path.write_text(path.read_text().replace("  " + path.stem + " ", "  XXXX ", 1))
    assert_problem(_read_climate_file(path, method), "INSI", "XXXX", path.stem)


@pytest.mark.parametrize("column", ["LAT", "LONG", "ELEV", "TAV", "AMP"])
def test_station_value_must_be_numeric(climate_file, column):
    path, method = climate_file
    lines = path.read_text().splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("@ INSI"))
    header = lines[header_index]
    end = header.index(column) + len(column)
    lines[header_index + 1] = lines[header_index + 1][:end - 3] + "bad" + lines[header_index + 1][end:]
    path.write_text("\n".join(lines))
    assert_problem(_read_climate_file(path, method), column, "numeric", "bad")


def test_missing_month(climate_file):
    path, method = climate_file
    lines = path.read_text().splitlines()
    start = lines.index("*" + needed_table(method))
    del lines[start + 8]  # Month 7, following the table header and months 1-6.
    path.write_text("\n".join(lines))
    assert_problem(_read_climate_file(path, method), needed_table(method), "month 7")


@pytest.mark.parametrize("value", ["-99", "-99.0", "bad", "nan", "inf"])
def test_required_table_value_must_be_present_and_numeric(climate_file, value):
    path, method = climate_file
    column = "PDW" if method == "W" else "RTOT"
    replace_cell(path, needed_table(method), 7, column, value)
    assert_problem(_read_climate_file(path, method), needed_table(method), "month 7", column, value)


def test_last_required_value_is_checked(climate_file):
    path, method = climate_file
    replace_cell(path, needed_table(method), 12, "RNUM", "bad")
    assert_problem(_read_climate_file(path, method), "month 12", "RNUM", "bad")


def test_missing_required_table(climate_file):
    path, method = climate_file
    section = "*" + needed_table(method)
    before, after = path.read_text().split(section, 1)
    following = after.find("\n*")
    path.write_text(before + (after[following + 1:] if following >= 0 else ""))
    assert_problem(_read_climate_file(path, method), section, method)


def test_other_method_table_and_unrelated_fields_are_not_checked(climate_file):
    path, method = climate_file
    section = "*" + ("MONTHLY AVERAGES" if method == "W" else "WGEN PARAMETERS")
    before, after = path.read_text().split(section, 1)
    following = after.find("\n*")
    path.write_text(before + (after[following + 1:] if following >= 0 else "") + "\n*OTHER\nbad data\n")
    assert _read_climate_file(path, method) == []


def test_missing_station_header(climate_file):
    path, method = climate_file
    lines = path.read_text().splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("@ INSI"))
    del lines[index:index + 2]
    path.write_text("\n".join(lines))
    assert_problem(_read_climate_file(path, method), "@ INSI")


def test_reports_independent_problems_together(climate_file):
    path, method = climate_file
    path.write_text(path.read_text().replace("*CLIMATE", "*WRONG", 1).replace("  " + path.stem + " ", "  XXXX ", 1))
    replace_cell(path, needed_table(method), 2, "RNUM", "-99")
    problems = _read_climate_file(path, method)
    assert len(problems) == 3
    assert any("*CLIMATE" in problem for problem in problems)
    assert any("INSI" in problem for problem in problems)
    assert any("month 2" in problem and "RNUM" in problem for problem in problems)


def test_unreadable_climate_path_returns_problem(tmp_path):
    path = tmp_path / "NONE.CLI"
    assert_problem(_read_climate_file(path, "S"), str(path), "Cannot read")


def test_empty_climate_file_returns_problems(tmp_path):
    path = tmp_path / "UFGA.CLI"
    path.write_text("")
    problems = _read_climate_file(path, "W")
    assert len(problems) == 3
    assert any("*CLIMATE" in problem for problem in problems)
    assert any("@ INSI" in problem for problem in problems)
    assert any("*WGEN PARAMETERS" in problem for problem in problems)


@pytest.mark.parametrize("method,column", [
    ("S", column) for column in ("SAMN", "XAMN", "NAMN", "RTOT", "RNUM")
] + [
    ("W", column) for column in ("SDMN", "SDSD", "SWMN", "SWSD", "XDMN", "XDSD",
                                 "XWMN", "XWSD", "NAMN", "NASD", "ALPHA", "RTOT", "PDW", "RNUM")
])
def test_each_required_table_column_is_checked(tmp_path, method, column):
    path = tmp_path / "UFGA.CLI"
    path.write_text(UFGA)
    replace_cell(path, needed_table(method), 3, column, "bad")
    assert_problem(_read_climate_file(path, method), column, "month 3", "bad")


def test_station_missing_marker_is_numeric_by_spec(climate_file):
    path, method = climate_file
    path.write_text(path.read_text().replace("  20.9", " -99.0").replace("  25.6", " -99.0"))
    assert _read_climate_file(path, method) == []


def test_missing_station_values(climate_file):
    path, method = climate_file
    lines = path.read_text().splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("@ INSI"))
    del lines[index + 1]
    path.write_text("\n".join(lines))
    assert_problem(_read_climate_file(path, method), "station values", "@ INSI")


def test_missing_table_column(climate_file):
    path, method = climate_file
    lines = path.read_text().splitlines()
    index = lines.index("*" + needed_table(method)) + 1
    lines[index] = lines[index].replace("RNUM", "NOPE")
    path.write_text("\n".join(lines))
    assert_problem(_read_climate_file(path, method), "required columns", "RNUM")
