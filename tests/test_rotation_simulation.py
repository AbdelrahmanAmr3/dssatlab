"""Rotation templates check and run as one sequence using a fake DSSAT."""

from copy import deepcopy
from datetime import date, timedelta

import pytest

from dssatlab import DSSATCheckError, DSSATRunError, Simulation, run_treatments
from dssatlab.filex import _section_row
from test_filex_template import data, rows
from test_rotation_template import rotation
from test_season_coverage import weather
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


@pytest.fixture
def sim(rotation, rows, installed):
    rotation["rotation"][2]["cultivar"]["code"] = "IB0488"
    return Simulation(filex_template=rotation, weather=weather("1978-03-15", "1979-03-14"),
                      soil=rows[1])


def test_report_and_read_only_check(sim, installed, tmp_path, capsys):
    before = snapshot(tmp_path)
    assert sim.check(True) == []
    assert ("FileX: treatment 1 is a sequence of 4 rotation components "
            "(R 1-4: MZ, FA, WH, FA); it runs in DSSAT's sequence mode.") in capsys.readouterr().out
    assert snapshot(tmp_path) == before
    assert installed.calls == []


@pytest.mark.parametrize("name", [None, "a scenario name too long for a treatment row" * 2])
@pytest.mark.parametrize("controls", [{}, {"years": 3}, {"years": 3, "start_date": "1978-03-16"}])
def test_run_sequence_inputs(sim, installed, name, controls):
    sim.name = name
    sim.management = {"treatments": {1: {"controls": controls}}} if controls else None
    sim.weather = weather("1978-03-15", "1981-03-15")
    original = deepcopy(sim.filex_template)
    if "start_date" in controls:
        with pytest.raises(DSSATCheckError, match="rotation component 1.*before simulation start"):
            sim.run()
        assert installed.calls == []
        assert sim.filex_template == original
        return
    result = sim.run()
    folder = result.run_dir.parent
    command, cwd, _ = installed.calls[0]
    assert command == [str(installed.executable), "Q", "DSSBatch.v48"]
    assert cwd == folder
    lines = (folder / "DSSBatch.v48").read_text().splitlines()[3:]
    assert len(lines) == 4
    for number, line in enumerate(lines, 1):
        assert line[:92].rstrip() == "UFGA7801.SQX"
        assert [int(line[i:i+7]) for i in range(92, 127, 7)] == [1, 1, number, 0, 0]
    assert {p.name for p in folder.glob("*.*") if p.suffix in (".CUL", ".ECO", ".SPE")} == {
        f"{crop}CER048.{suffix}" for crop in ("MZ", "WH") for suffix in ("CUL", "ECO", "SPE")}
    assert (folder / "SOIL.SOL").is_file()
    assert (folder / "UFGA7801.WTH").is_file()
    text = (folder / "UFGA7801.SQX").read_text()
    general = _section_row(text, "SIMULATION CONTROLS", "N", 1, ("NYERS",))
    assert int(general["NYERS"]) == controls.get("years", 1)
    assert general["SDATE"] == "78074"
    for level in range(2, 5):
        assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("NYERS",))["NYERS"] == "1"
    assert name is None or name not in text
    assert text.count(" 0 0 Rotation") == 4
    assert sim.filex_template == original


@pytest.mark.parametrize("years,override,last", [(1, False, "1979-03-14"),
                                                   (2, False, "1980-03-13"),
                                                   (3, True, "1981-03-14")])
@pytest.mark.parametrize("short", [False, True])
def test_sequence_coverage(sim, years, override, last, short):
    if override:
        sim.management = {"treatments": {1: {"controls": {"years": years}}}}
    elif years == 2:
        sim.filex_template["rotation"][-1]["end_date"] = "1980-03-13"
    end = date.fromisoformat(last) - timedelta(days=int(short))
    sim.weather = weather("1978-03-15", end.isoformat())
    prefix = "Controls years" if override else "FileX NYERS"
    assert sim.check(False) == ([
        f"{prefix} {years}: the sequence runs from 1978-03-15 through {last}, "
        f"after the weather data ends ({end}). Supply weather through {last}, or fewer years."
    ] if short else [])


@pytest.mark.parametrize("entry", [{"planting": {}}, {"controls": {"water": "N"}}])
def test_experiment_data_limit(sim, installed, entry):
    sim.management = {"treatments": {1: entry}}
    expected = ("Treatment 1 is a sequence of 4 rotation components; experiment data for a "
                "sequence takes only controls years, start_date and rotation. Edit the components "
                "in the FileX for other changes.")
    assert sim.check(False) == [expected]
    with pytest.raises(DSSATCheckError):
        sim.run()
    assert installed.calls == []


@pytest.mark.parametrize("treatment", [2, "2", True, "bad"])
def test_treatment_one_only(sim, treatment):
    sim.treatment = treatment
    assert sim.check(False) == ["FileX template has only treatment 1. Supply treatment=1."]


@pytest.mark.parametrize("kind", ["weather", "soil"])
def test_per_field_sources_rejected(sim, kind):
    setattr(sim, kind, {1: getattr(sim, kind)})
    assert any("needs treatment_fields" in p for p in sim.check(False))


@pytest.mark.parametrize("prefix,suffix", [("MZCER048", "ECO"), ("WHCER048", "SPE")])
def test_missing_genotype(sim, installed, prefix, suffix):
    path = installed.executable.parent / "Genotype" / f"{prefix}.{suffix}"
    path.unlink()
    assert sim.check(False) == [f"FileX template: missing genotype file {path}. "
                                "Supply this file in the data directory's Genotype folder."]


@pytest.mark.parametrize("scenarios", [False, True])
def test_run_treatments_once_per_scenario(sim, installed, scenarios):
    overrides = {"another": {"weather": weather("1978-03-15", "1979-03-14", station="TEST"),
                              "soil": [dict(sim.soil[0], soil_id="ANOTHER")]}} if scenarios else None
    results = run_treatments(filex_template=sim.filex_template, weather=sim.weather,
                             soil=sim.soil, scenarios=overrides)
    assert list(results) == ([("base", 1), ("another", 1)] if scenarios else [("base", 1)])
    assert len(installed.calls) == len(results)
    if scenarios:
        folder = results["another", 1].run_dir.parent
        text = (folder / "TEST7801.SQX").read_text()
        assert "ANOTHER" in text and "another" not in text
        assert (folder / "TEST7801.WTH").is_file()


def test_missing_weather_warning(sim, installed):
    installed.outputs["WARNING.OUT"] = b"Weather record not found for YR DOY: 1978 111"
    with pytest.raises(DSSATRunError, match="1978-04-21"):
        sim.run()


@pytest.mark.parametrize('last', ['1979-03-14', '1980-03-12', '1980-03-13'])
def test_final_fallow_harvest_updates_cycle_weather(sim, last):
    sim.management = {'treatments': {'01': {'rotation': {'04': {
        'harvest': [{'date': '1980-03-13'}],
    }}}}}
    sim.weather = weather('1978-03-15', last)
    problems = sim.check(False)
    if last == '1980-03-13':
        assert problems == []
    else:
        assert (f'FileX NYERS 2: the sequence runs from 1978-03-15 through 1980-03-13, '
                f'after the weather data ends ({last}). Supply weather through 1980-03-13, '
                'or fewer years.') in problems
        assert any('rotation component 4' in p and 'outside weather range' in p for p in problems)


def test_final_harvest_rechecks_cycle_closure(sim):
    sim.weather = weather('1978-03-15', '1981-03-15')
    sim.management = {'treatments': {1: {'rotation': {4: {
        'harvest': [{'date': '1979-03-20'}],
    }}}}}
    problems = sim.check(False)
    assert len(problems) == 1
    assert ('rotation component 4, harvest: the last component ends on 1979-03-20 '
            '(day 79 of the year), not before the first planting') in problems[0]
