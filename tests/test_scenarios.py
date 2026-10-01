"""Batch behavior through Simulation and a fake DSSAT subprocess."""

from copy import deepcopy
from datetime import date
from pathlib import Path
import subprocess

import pytest

import dssatlab as lab
from test_season_coverage import weather as continuous_weather
from test_simulation_run import fake_dssat, inputs, snapshot, soil_rows


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def batch_inputs(inputs):
    inputs.filex.write_bytes((FIXTURES / "scenarios" / "UFGA8201.MZX").read_bytes())
    return inputs


def test_all_treatments_have_separate_simulation_folders_and_run_directories(
        batch_inputs, fake_dssat):
    before = snapshot(batch_inputs.filex.parent)
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.weather,
                                 executable=fake_dssat.executable)
    assert list(results) == [("base", 1), ("base", 3), ("base", 5)]
    assert len({result.run_dir for result in results.values()}) == 3
    assert len({result.run_dir.parent for result in results.values()}) == 3
    for (_, treatment), result in results.items():
        assert result.returncode == 0
        assert result.run_dir.is_dir()
        assert (result.run_dir / "Summary.OUT").read_bytes() == b"summary"
        assert (result.run_dir.parent / batch_inputs.filex.name).exists()
        command, cwd, kwargs = fake_dssat.calls[[1, 3, 5].index(treatment)]
        assert command == [str(fake_dssat.executable), "C", batch_inputs.filex.name, str(treatment)]
        assert cwd == result.run_dir.parent
        assert kwargs["stdin"] == subprocess.DEVNULL
    assert snapshot(batch_inputs.filex.parent) == before


@pytest.mark.parametrize("numbers", [(1, 1, 2), (2, 2, 1)])
def test_all_treatments_selects_repeated_numbers_once_in_file_order(
        batch_inputs, fake_dssat, numbers):
    lines = batch_inputs.filex.read_text().splitlines()
    for index, (number, component) in enumerate(zip(numbers, (1, 2, 1)), 2):
        lines[index] = f"{number:2} {component}" + lines[index][4:]
    batch_inputs.filex.write_text("\n".join(lines) + "\n")
    weather = continuous_weather("1982-02-25", "1983-02-24")
    results = lab.run_treatments(batch_inputs.filex, weather,
                                 treatments=None, executable=fake_dssat.executable)
    assert list(results) == [("base", numbers[0]), ("base", numbers[2])]
    assert len(fake_dssat.calls) == 2
    assert len({result.run_dir for result in results.values()}) == 2


@pytest.mark.parametrize("treatments", [[1, 1], [1, "01"]])
def test_explicit_duplicate_treatments_remain_a_check_problem(
        batch_inputs, fake_dssat, treatments):
    with pytest.raises(lab.DSSATCheckError, match="Duplicate treatment number"):
        lab.run_treatments(batch_inputs.filex, batch_inputs.weather, treatments=treatments)
    assert fake_dssat.calls == []


def test_subset_scenarios_replace_whole_inputs_without_mutating_them(
        batch_inputs, fake_dssat, soil_rows):
    weather = [dict(row, rain=9) for row in batch_inputs.rows]
    planting = dict(date="1982-02-26", method="S", distribution="R",
                    population=8, row_spacing=75, depth=4)
    management = {"treatments": {3: {"planting": planting}}}
    scenarios = {"changed": {"weather": weather, "soil": None,
                              "management": {"treatments": {}}}}
    before = deepcopy((scenarios, management, soil_rows))
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=[3, 1],
                                 soil=soil_rows, management=management, scenarios=scenarios)
    assert list(results) == [("base", 3), ("base", 1), ("changed", 3), ("changed", 1)]
    base = results["base", 3].run_dir.parent
    changed = results["changed", 3].run_dir.parent
    assert (base / "SOIL.SOL").read_text().startswith("*SOILS")
    assert (changed / "SOIL.SOL").read_text() == "original SOIL.SOL"
    assert (base / batch_inputs.filex.name).read_bytes() != batch_inputs.filex.read_bytes()
    expected = batch_inputs.filex.read_bytes().splitlines(keepends=True)
    expected[3] = expected[3][:8] + b"                   changed" + expected[3][34:]
    assert (changed / batch_inputs.filex.name).read_bytes() == b"".join(expected)
    assert (base / "UFGA8201.WTH").read_bytes() != (changed / "UFGA8201.WTH").read_bytes()
    assert (scenarios, management, soil_rows) == before


def test_checks_every_pair_and_collects_all_problems_before_any_run(batch_inputs, fake_dssat):
    scenarios = {
        "typo": {"weahter": batch_inputs.rows, "weather": [dict(batch_inputs.rows[0], rain=-1)]},
        "wrong_station": {"weather": [dict(row, station="XXXX") for row in batch_inputs.rows]},
    }
    before = sorted(batch_inputs.filex.parent.iterdir())
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=[1, 5, 99],
                           scenarios=scenarios)
    problems = exc.value.problems
    for scenario in ("typo", "wrong_station"):
        for treatment in (1, 5, 99):
            assert any(f"scenario '{scenario}'" in p.lower() and f"treatment {treatment}:" in p
                       for p in problems)
    assert any("scenario 'base'" in p.lower() and "treatment 99:" in p for p in problems)
    assert any("rain" in p for p in problems)
    assert any("WSTA" in p for p in problems)
    assert any("weahter" in p and "weather, soil, management" in p for p in problems)
    assert fake_dssat.calls == []
    assert sorted(batch_inputs.filex.parent.iterdir()) == before


def test_base_and_scenario_weather_must_match_every_selected_station(batch_inputs, fake_dssat):
    text = batch_inputs.filex.read_text().replace("2 UFGA0002 UFGA", "2 UFGA0002 XXXX")
    batch_inputs.filex.write_text(text)
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios={"same": {}})
    assert len(exc.value.problems) == 2
    for scenario, problem in zip(("base", "same"), exc.value.problems):
        assert f"scenario '{scenario}'" in problem.lower()
        assert "treatment 5:" in problem and "WSTA" in problem and "XXXX" in problem
    assert fake_dssat.calls == []
    assert list(lab.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=[1])) == [("base", 1)]


@pytest.mark.parametrize("failure", ["exit", "error_out", "missing_weather"])
def test_first_failure_stops_and_names_all_kept_run_directories(
        batch_inputs, fake_dssat, monkeypatch, failure):
    original_run = subprocess.run

    def fail_third(command, *, cwd, **kwargs):
        if len(fake_dssat.calls) == 2:
            if failure == "exit":
                fake_dssat.returncode = 7
            elif failure == "error_out":
                fake_dssat.outputs["ERROR.OUT"] = b"bad crop data"
            else:
                fake_dssat.outputs["WARNING.OUT"] = b"Weather record not found for YR DOY: 1982 057"
        return original_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fail_third)
    with pytest.raises(lab.DSSATRunError) as exc:
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios={"extra": {}})
    assert len(fake_dssat.calls) == 3
    assert "scenario 'base'" in str(exc.value).lower() and "treatment 5" in str(exc.value)
    assert "kept" in str(exc.value).lower()
    assert isinstance(exc.value.__cause__, lab.DSSATRunError)
    kept = list(batch_inputs.filex.parent.glob("dssat_sim_*/dssat_run_*"))
    assert len(kept) == 3
    for directory in kept:
        assert str(directory) in str(exc.value)
        assert (directory / "Summary.OUT").exists()


@pytest.mark.parametrize("scenarios,fragment", [
    ({"base": {"soil": None}}, "reserved"),
    ({"mistyped": {"Weather": []}}, "weather, soil, management"),
    ({"invalid": []}, "dict"),
    ({False: {}}, "name"),
    ({" ": {}}, "name"),
    ([], "mapping"),
])
def test_invalid_scenarios_are_check_problems(batch_inputs, fake_dssat, scenarios, fragment):
    with pytest.raises(lab.DSSATCheckError, match=fragment):
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows, scenarios=scenarios)
    assert fake_dssat.calls == []


@pytest.mark.parametrize("treatments", [[], [1, "01"], [True], ["oops"], 1])
def test_invalid_selection_never_runs(batch_inputs, fake_dssat, treatments):
    with pytest.raises(lab.DSSATCheckError, match="treatment"):
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=treatments)
    assert fake_dssat.calls == []


def test_missing_filex_is_a_check_problem_with_context(batch_inputs, fake_dssat):
    batch_inputs.filex.unlink()
    with pytest.raises(lab.DSSATCheckError, match="FileX") as exc:
        lab.run_treatments(batch_inputs.filex, batch_inputs.rows)
    assert all("scenario" in p.lower() and "treatment" in p for p in exc.value.problems)
    assert fake_dssat.calls == []


def test_combine_summaries_keeps_every_row_and_adds_result_keys(batch_inputs, fake_dssat):
    fake_dssat.outputs["Summary.OUT"] = (
        FIXTURES / "output_files" / "summary" / "two_treatments" / "Summary.OUT").read_bytes()
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=[3],
                                 scenarios={"repeat": {}})
    rows = lab.combine_summaries(results)
    assert [(r["scenario"], r["treatment"], r["TRNO"]) for r in rows] == [
        ("base", 3, 1), ("base", 3, 2), ("repeat", 3, 1), ("repeat", 3, 2)]
    assert all(r["HWAM"] == 2295 and r["SDAT"] == date(1982, 2, 25) and r["DWAP"] is None
               for r in rows)
    assert "scenario" not in results["base", 3].summary()[0]
    assert lab.combine_summaries({}) == []


def test_combined_summaries_work_with_dataframe(batch_inputs, request):
    pd = pytest.importorskip("pandas")
    # pandas may query the platform via subprocess during import on Windows.
    fake_dssat = request.getfixturevalue("fake_dssat")
    fake_dssat.outputs["Summary.OUT"] = (
        FIXTURES / "output_files" / "summary" / "two_treatments" / "Summary.OUT").read_bytes()
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=[1])
    frame = lab.to_dataframe(lab.combine_summaries(results))
    assert isinstance(frame, pd.DataFrame)
    assert frame["scenario"].tolist() == ["base", "base"]
    assert frame["treatment"].tolist() == [1, 1]
    assert frame["HWAM"].tolist() == [2295, 2295]


def test_scenario_management_override_can_use_cultivar_initial_conditions_and_controls(
        inputs, fake_dssat):
    inputs.filex.write_bytes((FIXTURES / "initial_conditions" / "UFGA8201.MZX").read_bytes())
    # The shared fixture adds an odd-cased MZCER048.cUl; two .CUL files for one crop are rejected.
    for old in inputs.filex.parent.iterdir():
        if old.suffix.lower() == ".cul":
            old.unlink()
    cul = FIXTURES / "cultivar" / "MZCER048.CUL"
    (inputs.filex.parent / cul.name).write_bytes(cul.read_bytes())
    experiment = {
        "cultivar": {"crop": "MZ", "code": "IB0035"},
        "initial_conditions": {"date": "1982-02-25",
                               "layers": [dict(depth=15, water=0.25, nh4=1, no3=2)]},
        "controls": {"water": "N"},
    }
    scenarios = {"what_if": {"management": {"treatments": {2: experiment}}}}
    results = lab.run_treatments(inputs.filex, inputs.rows, treatments=[2], scenarios=scenarios)
    assert list(results) == [("base", 2), ("what_if", 2)]
    base = (results["base", 2].run_dir.parent / inputs.filex.name).read_bytes()
    changed = (results["what_if", 2].run_dir.parent / inputs.filex.name).read_bytes()
    assert base == inputs.filex.read_bytes()
    assert b" 2 MZ IB0035" in changed
    assert b" 2    15  0.25     1     2" in changed
    assert b" 2 OP              N     Y" in changed
