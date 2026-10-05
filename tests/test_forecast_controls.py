"""Forecast-date checks and the fixed-column SIMDATES copy edit (T2)."""

from datetime import date
from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATCheckError, Simulation, write_experiment_template, write_management_template
from dssatlab.filex_write import _write_management
from dssatlab.management import _check_management
from dssatlab.management_file import _load_management
from test_management_file import sim_inputs


FIXTURE = Path(__file__).parent / "fixtures" / "controls" / "UFGA8201.MZX"
# Deliberately place the FODAT header token elsewhere: DSSAT uses fixed columns.
HEADER = b"@N SIMDATES   HDATE XDATE YDATE FODAT OTHER\r\n"
ROW = b" 1 SD    -99     -99     -99 2023137 tail\xff\r\n"


@pytest.fixture
def forecast(sim_inputs):
    filex, weather = sim_inputs
    path = filex.with_suffix(".FCX")
    path.write_bytes(FIXTURE.read_bytes() + b"\r\n" + HEADER + ROW)
    return Simulation(path, 3, weather, management={"treatments": {3: {
        "controls": {"forecast_date": "2040-01-01"}}}})


@pytest.mark.parametrize("value", ["2023-02-30", "23-05-17", "20230517", "2023-5-17",
                                 date(2023, 5, 17), None, True, 2023137, []])
def test_invalid_forecast_date_has_the_start_date_message(forecast, value):
    forecast.management["treatments"][3]["controls"]["forecast_date"] = value
    expected = (f"Management data treatment 3, controls, field 'forecast_date': found {value!r}. "
                "Supply a valid ISO calendar date as a quoted YYYY-MM-DD string "
                '(for example "2024-05-10"); quote the date, even in a dict.')
    assert expected in forecast.check(verbose=False)


@pytest.mark.parametrize("suffix", [".SNX", ".MZX"])
def test_forecast_date_needs_a_forecast_filex(forecast, suffix):
    forecast.filex = forecast.filex.with_suffix(suffix)
    forecast.filex.write_bytes(FIXTURE.read_bytes() + HEADER + ROW)
    expected = (f"Controls forecast_date needs a forecast FileX (.FCX); FileX {forecast.filex} "
                "is not one. Remove forecast_date or use a .FCX.")
    assert expected in forecast.check(verbose=False)
    with pytest.raises(DSSATCheckError) as error:
        forecast.run()
    assert expected in error.value.problems


@pytest.mark.parametrize("value", ["0001-01-01", "1900-01-01", "2040-01-01", "9999-12-31"])
def test_forecast_date_accepts_four_digit_years(forecast, value):
    forecast.management["treatments"][3]["controls"]["forecast_date"] = value
    problems, _ = _check_management(forecast.management, forecast.filex, 3)
    assert problems == []


def test_forecast_check_accepts_a_year_beyond_2035_without_a_date_problem(forecast):
    assert not any("has no forecast date" in text for text in forecast.check(verbose=False))


def test_forecast_check_needs_weather_and_a_12_character_name(forecast, tmp_path):
    forecast.weather = None
    short = tmp_path / "A.FCX"
    shutil.copy2(forecast.filex, short)
    forecast.filex = short
    problems = forecast.check(verbose=False)
    assert any("forecast needs measured weather" in text for text in problems)
    assert any("exactly 12" in text for text in problems)


@pytest.mark.parametrize("row", [ROW, b" 1 SD", b" 1 SD    -99     -99     -99",
                                 b" 1 SD    -99     -99     -99     -99 tail\r\n"])
def test_copy_writes_fodat_and_preserves_other_bytes(forecast, tmp_path, row):
    original = FIXTURE.read_bytes() + b"\r\n" + HEADER + row
    forecast.filex.write_bytes(original)
    copy = tmp_path / "copy.FCX"
    shutil.copy2(forecast.filex, copy)
    _write_management(copy, 3, forecast.management)
    written = copy.read_bytes()
    base = row.rstrip(b"\r\n").ljust(28)
    expected = b" 2" + base[2:28] + b" 2040001" + base[36:]
    assert expected in written.splitlines()
    treatment = next(line for line in original.splitlines() if line.startswith(b" 3 1 0 0"))
    expected_prefix = original.replace(treatment, treatment[:70] + b"  2" + treatment[73:])
    assert written.startswith(expected_prefix)
    assert forecast.filex.read_bytes() == original
    # The other treatments keep the original SM level.
    for number in (1, 5):
        original_treatment = next(line for line in original.splitlines()
                                  if line.startswith(f" {number} 1 0 0".encode()))
        assert original_treatment in written.splitlines()


def test_missing_selected_simdates_is_a_check_problem(forecast):
    forecast.filex.write_bytes(FIXTURE.read_bytes() + HEADER + ROW.replace(b" 1 SD", b" 7 SD"))
    problems = forecast.check(verbose=False)
    assert any("SIMDATES/FODAT" in p and "level 1 has no row" in p for p in problems)
    assert forecast.filex.read_bytes().endswith(ROW.replace(b" 1 SD", b" 7 SD"))


def test_absent_simdates_is_not_inserted(forecast):
    original = FIXTURE.read_bytes()
    forecast.filex.write_bytes(original)
    assert any("SIMDATES/FODAT" in p for p in forecast.check(verbose=False))
    assert forecast.filex.read_bytes() == original


@pytest.mark.parametrize("row,expected", [
    (ROW, date(2023, 5, 17)),
    (ROW.replace(b" 1 SD", b"01 SD"), date(2023, 5, 17)),
    (b" 1 SD    -99     -99     -99 2040001", date(2040, 1, 1)),
    (b" 1 SD    -99     -99     -99 2024366", date(2024, 12, 31)),
    (b" 1 SD", None), (ROW[:35], None),
    (b" 1 SD    -99     -99     -99     -99", None),
    (b" 1 SD    -99     -99     -99 XXXXXXX", None),
    (b" 1 SD    -99     -99     -99 2023366", None),
    (b" 1 SD    -99     -99     -99 2023000", None),
    (b" 1 SD    -99     -99     -99 0000137", None),
    (b"", None),
])
def test_read_fodat_uses_fixed_columns_and_real_calendar_days(row, expected):
    from dssatlab.controls import _filex_forecast_date

    text = (FIXTURE.read_bytes() + HEADER + row).decode("latin-1")
    assert _filex_forecast_date(text, 3) == expected


def test_reader_returns_missing_when_simdates_is_absent():
    from dssatlab.controls import _filex_forecast_date

    assert _filex_forecast_date(FIXTURE.read_bytes().decode("latin-1"), 3) is None


def test_reader_and_writer_use_the_selected_treatments_sm_level(forecast, tmp_path):
    from dssatlab.controls import _filex_forecast_date

    original = forecast.filex.read_bytes()
    treatment = next(line for line in original.splitlines() if line.startswith(b" 3 1 0 0"))
    original = original.replace(treatment, treatment[:70] + b"  7" + treatment[73:])
    controls = FIXTURE.read_bytes().split(b"*SIMULATION CONTROLS")[1]
    original += controls.replace(b" 1 ", b" 7 ") + HEADER + ROW.replace(
        b" 1 SD", b" 7 SD").replace(b"2023137", b"2023138")
    forecast.filex.write_bytes(original)
    assert _filex_forecast_date(original.decode("latin-1"), 3) == date(2023, 5, 18)
    copy = tmp_path / "copy.FCX"
    shutil.copy2(forecast.filex, copy)
    _write_management(copy, 3, forecast.management)
    written = copy.read_bytes()
    assert b" 8 SD    -99     -99     -99 2040001 tail\xff" in written.splitlines()
    assert _filex_forecast_date(written.decode("latin-1"), 3) == date(2040, 1, 1)
    assert _filex_forecast_date(written.decode("latin-1"), 1) == date(2023, 5, 17)
    assert forecast.filex.read_bytes() == original


@pytest.mark.parametrize("writer", [write_management_template, write_experiment_template])
def test_template_forecast_example_loads_and_passes_checks(forecast, tmp_path, writer):
    pytest.importorskip("yaml")
    path = tmp_path / "experiment.yaml"
    writer(path)
    text = path.read_text(encoding="utf-8")
    assert '# forecast_date: "2023-05-17"' in text
    data, problems = _load_management(path)
    assert problems == []
    # Uncomment the documented value in the generated example and check it too.
    text = text.replace('    # controls:', '    controls:')
    text = text.replace('# forecast_date: "2023-05-17"', 'forecast_date: "2023-05-17"')
    path.write_text(text, encoding="utf-8")
    data, problems = _load_management(path)
    assert problems == []
    assert data["treatments"][1]["controls"]["forecast_date"] == "2023-05-17"
    cul = Path(__file__).parent / "fixtures" / "cultivar" / "MZCER048.CUL"
    (tmp_path / cul.name).write_bytes(cul.read_bytes())
    problems, _ = _check_management(data, forecast.filex, 1)
    assert problems == []
