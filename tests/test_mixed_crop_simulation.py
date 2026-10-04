"""Mixed-crop FileXs select levels, dates and fields per treatment."""

from copy import deepcopy
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, run_treatments
from dssatlab.filex import _section_row
from test_crop_entries import mixed
from test_filex_template import data, rows
from test_season_coverage import weather
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


@pytest.fixture
def inputs(mixed, rows):
    mixed["crops"][1]["planting"].update(date="2021-04-01", population=30, row_spacing=50)
    mixed["crops"][2]["planting"].update(date="2021-05-01", population=150, row_spacing=20, depth=3)
    mixed["treatment_fields"] = [1, 2, 1, 2]
    return dict(filex_template=mixed,
                weather={1: weather("2021-03-01", "2021-08-01", "TEST"),
                         2: weather("2021-03-01", "2021-08-01", "AMES")},
                soil={1: rows[1], 2: [dict(rows[1][0], soil_id="SECOND", slb=60)]})


def test_valid_mixed_template_check_is_read_only(inputs, installed, tmp_path):
    original, before = deepcopy(inputs), snapshot(tmp_path)
    assert Simulation(**inputs).check(verbose=False) == []
    assert inputs == original and snapshot(tmp_path) == before
    assert installed.calls == []


def test_exact_three_entry_four_treatment_filex(inputs, installed):
    folder = Simulation(**inputs).run().run_dir.parent
    expected = Path(__file__).with_name("fixtures") / "mixed_crops.MZX"
    assert (folder / "TEST2101.MZX").read_bytes() == expected.read_text(encoding="ascii").encode("ascii")


@pytest.mark.parametrize("treatment,entry,field", [(1, 1, 1), ("2", 2, 2), (3, 3, 1), (4, 1, 2)])
def test_simulation_runs_selected_crop_and_copies_all_genotypes(inputs, installed, treatment, entry, field):
    original = deepcopy(inputs)
    sim = Simulation(**inputs, treatment=treatment)
    assert sim.check(verbose=False) == []
    result = sim.run()
    folder = result.run_dir.parent
    text = (folder / "TEST2101.MZX").read_text()
    factors = _section_row(text, "TREATMENTS", "N", int(treatment), ("CU", "MP", "SM", "MH", "FL"))
    assert [factors[key] for key in ("CU", "MP", "SM", "FL")] == [str(entry)] * 3 + [str(field)]
    assert factors["MH"] == ("1" if entry == 3 else "0")
    genotype_names = {f"{prefix}.{suffix}" for prefix in ("MZCER048", "SBGRO048", "WHCER048")
                      for suffix in ("CUL", "ECO", "SPE")}
    assert {p.name for p in folder.iterdir() if p.suffix in (".CUL", ".ECO", ".SPE")} == genotype_names
    for name in genotype_names:
        assert (folder / name).read_bytes() == (installed.executable.parent / "Genotype" / name).read_bytes()
    assert {p.name for p in folder.glob("*.WTH")} == {"TEST2101.WTH", "AMES2101.WTH"}
    assert installed.calls[0][:2] == ([str(installed.executable), "C", "TEST2101.MZX", str(treatment)], folder)
    assert inputs == original


@pytest.mark.parametrize("scenarios", [None, {"changed": {}}])
def test_run_treatments_runs_every_crop(inputs, installed, scenarios):
    results = run_treatments(**inputs, scenarios=scenarios)
    names = ["base", "changed"] if scenarios else ["base"]
    assert list(results) == [(name, k) for name in names for k in (1, 2, 3, 4)]
    assert [call[0][-1] for call in installed.calls] == ["1", "2", "3", "4"] * len(names)
    assert len({r.run_dir.parent for r in results.values()}) == len(results)


def test_filename_uses_first_entry_even_when_first_treatment_uses_another(inputs, installed):
    template = inputs["filex_template"]
    template["treatment_crops"] = [2, 1, 3, 1]
    template["crops"][0]["planting"]["date"] = "2020-03-01"
    inputs["weather"] = {k: weather("2020-03-01", "2021-08-01", station)
                         for k, station in ((1, "TEST"), (2, "AMES"))}
    folder = Simulation(**inputs).run().run_dir.parent
    assert (folder / "TEST2001.MZX").is_file()
    assert {p.name for p in folder.glob("*.WTH")} == {"TEST2101.WTH", "AMES2101.WTH"}


def test_harvest_levels_are_numbered_only_for_entries_with_dates(inputs, installed):
    inputs["filex_template"]["crops"][0]["harvest_date"] = "2021-07-01"
    text = (Simulation(**inputs).run().run_dir.parent / "TEST2101.MZX").read_text()
    for treatment, harvest in enumerate((1, 0, 2, 1), 1):
        assert _section_row(text, "TREATMENTS", "N", treatment, ("MH",))["MH"] == str(harvest)
    for level, day in ((1, "21182"), (2, "21213")):
        assert _section_row(text, "HARVEST DETAILS", "H", level, ("HDATE",))["HDATE"] == day


def test_late_entry_start_requires_weather_but_early_entry_does_not(inputs, installed, tmp_path):
    inputs["weather"] = {k: weather("2021-03-01", "2021-03-31", station)
                         for k, station in ((1, "TEST"), (2, "AMES"))}
    assert Simulation(**inputs, treatment=1).check(verbose=False) == []
    sim = Simulation(**inputs, treatment=2)
    assert sim.check(verbose=False) == [
        "Simulation start date 2021-04-01 is not covered by weather data "
        "(2021-03-01 to 2021-03-31). Supply weather for that date."]
    before = snapshot(tmp_path)
    with pytest.raises(DSSATCheckError, match="Simulation start date 2021-04-01"):
        sim.run()
    assert snapshot(tmp_path) == before and installed.calls == []


def test_weather_can_start_on_selected_entry_planting(inputs, installed):
    inputs["weather"][2] = weather("2021-04-01", "2021-08-01", "AMES")
    assert Simulation(**inputs, treatment=2).check(verbose=False) == []
    assert any("Simulation start date 2021-03-01" in p
               for p in Simulation(**inputs, treatment=4).check(verbose=False))


def test_selected_entry_harvest_requires_weather(inputs, installed):
    inputs["weather"][1] = weather("2021-03-01", "2021-07-31", "TEST")
    assert Simulation(**inputs, treatment=1).check(verbose=False) == []
    assert Simulation(**inputs, treatment=3).check(verbose=False) == [
        "FileX template, crops[3], harvest_date: 2021-08-01 is not covered by "
        "weather data (2021-03-01 to 2021-07-31). Supply weather for that date."]


@pytest.mark.parametrize("end,valid", [("2022-03-31", False), ("2022-04-01", True)])
def test_years_override_uses_selected_entry_start(inputs, installed, end, valid):
    inputs["weather"][2] = weather("2021-03-01", end, "AMES")
    inputs["management"] = {"treatments": {2: {"controls": {"years": 2}}}}
    problems = Simulation(**inputs, treatment=2).check(verbose=False)
    assert problems == ([] if valid else [
        "Controls years 2: season 2 starts on 2022-04-01 (day 91 of 2022), "
        "after the weather data ends (2022-03-31). Supply weather for every season, or fewer years."])


def test_start_and_years_override_are_selected_per_treatment(inputs, installed):
    inputs["weather"][2] = weather("2020-12-30", "2021-12-31", "AMES")
    inputs["management"] = {"treatments": {"02": {"controls": {"years": 2, "start_date": "2020-12-30"}}}}
    sim = Simulation(**inputs, treatment=2)
    assert sim.check(verbose=False) == []
    folder = sim.run().run_dir.parent
    assert {p.name for p in folder.glob("*.WTH")} == {"TEST2001.WTH", "AMES2001.WTH"}
    text = (folder / "TEST2101.MZX").read_text()
    level = int(_section_row(text, "TREATMENTS", "N", 2, ("SM",))["SM"])
    general = _section_row(text, "SIMULATION CONTROLS", "N", level, ("NYERS", "SDATE"))
    assert [general[k] for k in ("NYERS", "SDATE")] == ["2", "20365"]
    assert next(line for line in text.splitlines() if line.startswith(f"{level:2d} GE"))[71:79] == "CRGRO048"
    assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("SYMBI",))["SYMBI"] == "Y"
    # The early start override belongs to treatment 2 alone.
    assert Simulation(**inputs, treatment=1).check(verbose=False) == []


@pytest.mark.parametrize("prefix,suffix", [("SBGRO048", "ECO"), ("WHCER048", "SPE")])
def test_missing_genotype_from_unselected_entry_prevents_writes(inputs, installed, tmp_path, prefix, suffix):
    path = installed.executable.parent / "Genotype" / f"{prefix}.{suffix}"
    path.unlink()
    sim = Simulation(**inputs, treatment=1)
    before = snapshot(tmp_path)
    assert sim.check(verbose=False) == [f"FileX template: missing genotype file {path}. "
                                       "Supply this file in the data directory's Genotype folder."]
    with pytest.raises(DSSATCheckError, match=f"{prefix}.{suffix}"):
        sim.run()
    assert snapshot(tmp_path) == before and installed.calls == []


@pytest.mark.parametrize("treatment", [True, 0, 5, "bad", None])
def test_invalid_selected_treatment_reports_problem(inputs, installed, treatment):
    assert Simulation(**inputs, treatment=treatment).check(verbose=False) == [
        "FileX template has treatments 1 to 4. Supply treatment=<k> with 1 <= k <= 4."]


def test_repeated_crop_entries_have_independent_levels(inputs, installed):
    template = inputs["filex_template"]
    template["crops"][1] = deepcopy(template["crops"][0])
    template["crops"][1]["cultivar"]["code"] = "ZZ0001"
    template["crops"][1]["planting"]["population"] = 8
    text = (Simulation(**inputs, treatment=2).run().run_dir.parent / "TEST2101.MZX").read_text()
    assert _section_row(text, "CULTIVARS", "C", 2, ("INGENO",))["INGENO"] == "ZZ0001"
    assert _section_row(text, "PLANTING DETAILS", "P", 2, ("PPOP",))["PPOP"] == "8"
    assert _section_row(text, "PLANTING DETAILS", "P", 1, ("PPOP",))["PPOP"] == "7.2"


@pytest.mark.parametrize("count", [1, 99])
def test_entry_level_boundaries_check_and_run(inputs, installed, count):
    entry = dict(inputs["filex_template"]["crops"][0], harvest_date="2021-07-01")
    inputs["filex_template"] = dict(crops=[deepcopy(entry) for _ in range(count)],
                                    treatments=[f"Maize {k}" for k in range(1, count + 1)],
                                    treatment_crops=list(range(1, count + 1)))
    inputs["weather"], inputs["soil"] = inputs["weather"][1], inputs["soil"][1]
    sim = Simulation(**inputs, treatment=count)
    assert sim.check(verbose=False) == []
    text = (sim.run().run_dir.parent / "TEST2101.MZX").read_text()
    row = _section_row(text, "TREATMENTS", "N", count, ("CU", "MP", "SM", "MH"))
    assert [row[key] for key in ("CU", "MP", "SM", "MH")] == [str(count)] * 4
    assert _section_row(text, "HARVEST DETAILS", "H", count, ("HDATE",))["HDATE"] == "21182"


def test_run_treatments_checks_late_entry_before_writing_any_simulation(inputs, installed, tmp_path):
    inputs["weather"][2] = weather("2021-03-01", "2021-03-31", "AMES")
    before = snapshot(tmp_path)
    with pytest.raises(DSSATCheckError, match="Scenario 'base', treatment 2: Simulation start date 2021-04-01"):
        run_treatments(**inputs)
    assert snapshot(tmp_path) == before and installed.calls == []


def test_unrelated_entry_error_does_not_hide_selected_start_and_season_problems(inputs, installed):
    inputs["filex_template"]["crops"][0]["planting"]["depth"] = -1
    inputs["weather"][2] = weather("2021-03-01", "2021-03-31", "AMES")
    inputs["management"] = {"treatments": {2: {"controls": {"years": 2}}}}
    problems = Simulation(**inputs, treatment=2).check(verbose=False)
    for expected in ("crops[1], planting, field 'depth'", "Simulation start date 2021-04-01",
                     "Controls years 2: season 2 starts on 2022-04-01"):
        assert any(expected in p for p in problems)


def test_unrelated_entry_error_does_not_hide_selected_harvest_problem(inputs, installed):
    inputs["filex_template"]["crops"][0]["planting"]["depth"] = -1
    inputs["weather"][1] = weather("2021-03-01", "2021-07-31", "TEST")
    problems = Simulation(**inputs, treatment=3).check(verbose=False)
    assert any("crops[1], planting, field 'depth'" in p for p in problems)
    assert any("crops[3], harvest_date: 2021-08-01 is not covered" in p for p in problems)


def test_malformed_mapping_does_not_hide_entry_genotype_problem(inputs, installed):
    inputs["filex_template"]["treatment_crops"] = None
    (installed.executable.parent / "Genotype" / "WHCER048.SPE").unlink()
    problems = Simulation(**inputs).check(verbose=False)
    assert any("treatment_crops: supply one crop entry number per treatment" in p for p in problems)
    assert any("missing genotype file" in p and "WHCER048.SPE" in p for p in problems)
