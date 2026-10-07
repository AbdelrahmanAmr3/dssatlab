"""Experiment data reading and round trips without running DSSAT in CI."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

import dssatlab as dl
from dssatlab.filex_write import _columns, _repoint, _section_bounds
from test_simulation_run import fake_dssat, inputs


STOCK = Path(__file__).parent / "fixtures" / "filex_template" / "UFGA8201.MZX"


@pytest.fixture
def filex(tmp_path):
    path = tmp_path / "UFGA8201.MZX"
    path.write_text(STOCK.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _change(path, section, column, value, *, level=1):
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _section_bounds(lines, section)
    columns = {}
    for index in range(start + 1, end):
        line = lines[index]
        if line.startswith("@"):
            columns = _columns(line)
        elif column in columns and line[:3].strip() == str(level):
            left, right = columns[column]
            lines[index] = line[:left] + str(value).rjust(right - left) + line[right:]
            break
    else:
        raise AssertionError(f"missing {section} {column} level {level}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _factor(path, column, value, treatment=1):
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    _repoint(lines, treatment, column, value)
    path.write_text("".join(lines), encoding="utf-8")


def test_public_reader_maps_units_dates_and_shared_levels(filex):
    before = filex.read_bytes()
    entry = dl.read_experiment(filex)
    assert "read_experiment" in dl.__all__
    assert entry["planting"] == dict(
        date="1982-02-26", population=7.2, emergence_population=7.2,
        method="S", distribution="R", row_spacing=61, row_direction=0,
        depth=7, sprout_length=0)
    assert entry["fertilizer"][0] == dict(
        date="1982-04-07", material="FE001", application="AP001", depth=10,
        n=27, p=0, k=0)
    assert entry["irrigation"] == dict(
        efficiency=1, events=[dict(date="1982-03-04", method="IR001", amount=13)])
    assert dl.read_experiment(str(filex), "01") == entry
    other = dl.read_experiment(filex, 4)
    assert other["planting"] == entry["planting"]
    assert len(other["fertilizer"]) == 6
    assert len(other["irrigation"]["events"]) == 16
    assert filex.read_bytes() == before


@pytest.mark.parametrize("treatment", range(1, 7))
def test_simulation_round_trip(filex, treatment, inputs, fake_dssat):
    inputs.filex.write_bytes(filex.read_bytes())
    entry = dl.read_experiment(inputs.filex, treatment)
    original, data = inputs.filex.read_bytes(), deepcopy(entry)
    start = date(1982, 2, 25)
    weather = [dict(inputs.rows[0], date=(start + timedelta(days=i)).isoformat())
               for i in range(120)]
    sim = dl.Simulation(inputs.filex, treatment, weather,
                        management={"treatments": {treatment: entry}})
    assert sim.check(False) == []
    result = sim.run()
    assert dl.read_experiment(result.run_dir.parent / inputs.filex.name, treatment) == entry
    assert inputs.filex.read_bytes() == original
    assert entry == data
    assert len(fake_dssat.calls) == 1


def test_zero_levels_omit_sections_even_when_sections_are_absent(filex):
    for column in ("MP", "MF", "MI"):
        _factor(filex, column, 0)
    text = filex.read_text(encoding="utf-8")
    filex.write_text(text[:text.index("*PLANTING DETAILS")], encoding="utf-8")
    assert dl.read_experiment(filex) == {}


def test_names_are_ignored(filex):
    entry = dl.read_experiment(filex)
    for section, column in (("PLANTING DETAILS", "PLNAME"),
                            ("FERTILIZERS", "FERNAME"),
                            ("IRRIGATION AND WATER MANAGEMENT", "IRNAME")):
        _change(filex, section, column, "name")
        assert dl.read_experiment(filex) == entry


@pytest.mark.parametrize("treatment,event_level,event_number", [
    (1, 1, 9), (1, 2, 1), (3, 2, 1),
])
def test_irrigation_events_follow_control_block(filex, treatment, event_level, event_number):
    entry = dl.read_experiment(filex, treatment)
    text = filex.read_text(encoding="utf-8")
    event = f" {event_level} 82063 IR001    13"
    assert event in text
    filex.write_text(text.replace(event, f" {event_number} 82063 IR001    13"),
                     encoding="utf-8")
    assert dl.read_experiment(filex, treatment) == entry


@pytest.mark.parametrize("section,column,value", [
    *[("IRRIGATION AND WATER MANAGEMENT", column, value)
      for column, value in (("IDEP", 10), ("ITHR", 50), ("IEPT", 100),
                            ("IOFF", "GS000"), ("IAME", "IR001"), ("IAMT", 20))],
    *[("FERTILIZERS", column, value)
      for column, value in (("FAMC", 1), ("FAMO", 1), ("FOCD", "FE001"))],
])
def test_unrepresentable_columns_name_source_level_and_column(filex, section, column, value):
    _change(filex, section, column, value)
    before = filex.read_bytes()
    with pytest.raises(dl.DSSATCheckError) as error:
        dl.read_experiment(filex)
    message = str(error.value)
    assert all(part in message for part in (str(filex), "level 1", column,
                                            "Checked", "representable"))
    assert filex.read_bytes() == before


def test_writer_constants_and_numeric_missing_markers_are_allowed(filex):
    _change(filex, "FERTILIZERS", "FAMC", -99)
    _change(filex, "FERTILIZERS", "FAMO", "0.0")
    _change(filex, "IRRIGATION AND WATER MANAGEMENT", "IDEP", "-99.0")
    assert dl.read_experiment(filex)["fertilizer"][0]["n"] == 27


def test_unknown_column_with_value_is_rejected(filex):
    text = filex.read_text(encoding="utf-8").replace("FERNAME", "EXTRA  ")
    filex.write_text(text, encoding="utf-8")
    _change(filex, "FERTILIZERS", "EXTRA", 12)
    with pytest.raises(dl.DSSATCheckError, match="EXTRA"):
        dl.read_experiment(filex)


@pytest.mark.parametrize("column,date_code,expected", [
    ("PDATE", "35001", "2035-01-01"), ("PDATE", "36001", "1936-01-01"),
    ("EDATE", "00060", "2000-02-29"),
])
def test_filex_century_rule_and_emergence_date(filex, column, date_code, expected):
    _change(filex, "PLANTING DETAILS", column, date_code)
    field = "date" if column == "PDATE" else "emergence_date"
    assert dl.read_experiment(filex)["planting"][field] == expected


@pytest.mark.parametrize("column,value,fragment", [
    ("PDATE", "82366", "PDATE"), ("PPOP", "NaN", "PPOP"),
    ("PPOP", 0, "population"), ("PLME", "99", "method"),
])
def test_invalid_planting_is_not_repaired(filex, column, value, fragment):
    _change(filex, "PLANTING DETAILS", column, value)
    with pytest.raises(dl.DSSATCheckError, match=fragment):
        dl.read_experiment(filex)


@pytest.mark.parametrize("section,needle", [("fertilizer", " 1 82097 FE001"),
                                            ("irrigation", " 1 82063 IR001")])
def test_repeated_event_dates_are_rejected(filex, section, needle):
    text = filex.read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if line.startswith(needle))
    filex.write_text(text.replace(line, line + "\n" + line), encoding="utf-8")
    with pytest.raises(dl.DSSATCheckError) as error:
        dl.read_experiment(filex)
    assert section in str(error.value) and "duplicate date" in str(error.value)
    assert "level 1" in str(error.value) and str(filex) in str(error.value)


def test_day_timing_reads_selected_sm_and_efficiency(filex):
    _change(filex, "IRRIGATION AND WATER MANAGEMENT", "EFIR", ".75")
    _change(filex, "IRRIGATION AND WATER MANAGEMENT", "IDATE", 0)
    text = filex.read_text(encoding="utf-8")
    header = "@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS"
    text += "\n" + header + "\n 2 MA              R     D     R     N     M\n"
    filex.write_text(text, encoding="utf-8")
    _factor(filex, "SM", 2)
    assert dl.read_experiment(filex)["irrigation"] == dict(
        efficiency=.75, events=[dict(days_after_planting=0, method="IR001", amount=13)])


@pytest.mark.parametrize("code", list("AFNX"))
def test_irrigation_timing_that_cannot_be_expressed_is_rejected(filex, code):
    lines = filex.read_text(encoding="utf-8").splitlines(keepends=True)
    _repoint(lines, 1, "IRRIG", code, "SIMULATION CONTROLS", "N")
    filex.write_text("".join(lines), encoding="utf-8")
    with pytest.raises(dl.DSSATCheckError) as error:
        dl.read_experiment(filex)
    assert "IDATE" in str(error.value) and f"IRRIG '{code}'" in str(error.value)


def test_empty_irrigation_schedule_keeps_efficiency(filex):
    text = filex.read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if line.startswith(" 1 82063 IR001"))
    filex.write_text(text.replace(line, ""), encoding="utf-8")
    assert dl.read_experiment(filex)["irrigation"] == dict(efficiency=1, events=[])


@pytest.mark.parametrize("treatment", [True, False, None, 0, -1, 1.5, "x", "١"])
def test_invalid_treatment_number(filex, treatment):
    with pytest.raises(dl.DSSATCheckError, match="invalid treatment number"):
        dl.read_experiment(filex, treatment)


def test_missing_treatment_and_unreadable_path(filex, tmp_path):
    with pytest.raises(dl.DSSATCheckError, match="treatment number 99"):
        dl.read_experiment(filex, 99)
    with pytest.raises(dl.DSSATCheckError, match="Cannot read experiment data"):
        dl.read_experiment(tmp_path / "missing.MZX")
    with pytest.raises(dl.DSSATCheckError, match="Supply a readable FileX"):
        dl.read_experiment(None)


@pytest.mark.parametrize("number", [" 1", "01"])
def test_sequence_is_rejected(filex, number):
    text = filex.read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if line.startswith(" 1 1 0 0"))
    first = number + line[2:]
    second = number + " 2" + line[4:]
    filex.write_text(text.replace(line, first + "\n" + second),
                     encoding="utf-8")
    with pytest.raises(dl.DSSATCheckError, match="sequences"):
        dl.read_experiment(filex)


@pytest.mark.parametrize("suffix", [".FCX", ".fcx"])
def test_forecast_is_rejected(filex, suffix):
    forecast = filex.with_suffix(suffix)
    filex.rename(forecast)
    with pytest.raises(dl.DSSATCheckError, match="forecasts"):
        dl.read_experiment(forecast)


@pytest.mark.parametrize("failure", ["missing section", "missing level", "missing column"])
def test_bad_referenced_planting_reports_what_to_supply(filex, failure):
    text = filex.read_text(encoding="utf-8")
    if failure == "missing section":
        text = text.replace("*PLANTING DETAILS", "*UNUSED DETAILS")
    elif failure == "missing level":
        text = text.replace(" 1 82057", " 9 82057")
    else:
        text = text.replace("PLRS", "XXXX")
    filex.write_text(text, encoding="utf-8")
    with pytest.raises(dl.DSSATCheckError) as error:
        dl.read_experiment(filex)
    assert "PLANTING DETAILS level 1" in str(error.value)
    assert "Supply" in str(error.value)
