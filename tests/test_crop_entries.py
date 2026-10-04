"""Mixed-crop template rules report problems before FileX rendering."""

from copy import deepcopy

import pytest

from dssatlab import Simulation
from test_filex_template import data, rows
from test_simulation_run import fake_dssat
from test_simulation_template import installed


@pytest.fixture
def mixed(data):
    maize = {key: data[key] for key in ("crop", "cultivar", "planting")}
    soybean, wheat = deepcopy(maize), deepcopy(maize)
    soybean.update(crop="soybean", cultivar={"code": "IB0011"})
    wheat.update(crop="wheat", cultivar={"code": "IB0488"}, harvest_date="2021-08-01")
    return dict(crops=[maize, soybean, wheat], treatments=["Maize A", "Soybean", "Wheat", "Maize B"],
                treatment_crops=[1, 2, 3, 1])


def problems(template, rows):
    return Simulation(filex_template=template, weather=rows[0], soil=rows[1]).check(verbose=False)


@pytest.mark.parametrize("form", ["crop", "rotation"])
def test_exactly_one_crop_form(mixed, rows, installed, form):
    mixed[form] = "maize" if form == "crop" else []
    assert any("supply exactly one of crop, rotation or crops" in p for p in problems(mixed, rows))


def test_crop_form_required(data, rows, installed):
    del data["crop"]
    assert any("supply exactly one of crop, rotation or crops" in p for p in problems(data, rows))


@pytest.mark.parametrize("key", ["cultivar", "planting", "harvest_date"])
def test_no_top_level_crop_values_beside_crops(mixed, rows, installed, key):
    mixed[key] = None
    assert any(f"crops: cannot be mixed with top-level {key}" in p for p in problems(mixed, rows))


def test_crops_cannot_combine_with_rotation(mixed, rows, installed):
    mixed["rotation"] = []
    assert any("rotations already take a crop per component" in p for p in problems(mixed, rows))


@pytest.mark.parametrize("change", [{"crops": None}, {"treatment_crops": None},
                                    {"treatment_crops": []}, {"treatment_crops": [4, 2, 3, 1]}])
def test_rotation_conflict_with_malformed_crop_entries_reports_problems(mixed, rows, installed, change):
    mixed.update(rotation=[], **change)
    assert any("rotations already take a crop per component" in p for p in problems(mixed, rows))


def test_rotation_conflict_with_missing_treatment_crops_reports_problems(mixed, rows, installed):
    mixed["rotation"] = []
    del mixed["treatment_crops"]
    found = problems(mixed, rows)
    assert any("rotations already take a crop per component" in p for p in found)
    assert any("crops: needs treatment_crops" in p for p in found)


@pytest.mark.parametrize("value", [None, {}, "maize", (), [], [{}] * 100])
def test_crops_requires_list_of_one_to_99_entries(mixed, rows, installed, value):
    mixed["crops"] = value
    assert any("crops: found" in p and "Supply a list of 1 to 99 crop entries" in p
               for p in problems(mixed, rows))


@pytest.mark.parametrize("entry", [None, [], "maize", 1])
def test_crop_entry_requires_dict(mixed, rows, installed, entry):
    mixed["crops"][1] = entry
    assert any("FileX template, crops[2]: expected a dict" in p for p in problems(mixed, rows))


@pytest.mark.parametrize("key", ["crop", "cultivar", "planting"])
def test_crop_entry_required_keys(mixed, rows, installed, key):
    del mixed["crops"][1][key]
    assert any(f"FileX template, crops[2]: missing required field '{key}'" in p
               for p in problems(mixed, rows))


def test_crop_entry_unknown_keys(mixed, rows, installed):
    mixed["crops"][1]["model"] = "CRGRO048"
    assert any("FileX template, crops[2]: unknown key 'model'" in p for p in problems(mixed, rows))


@pytest.mark.parametrize("change,expected", [
    ({"crop": "fallow"}, "not a template crop"),
    ({"cultivar": {"code": "bad"}}, "six printable ASCII characters"),
    ({"cultivar": {"code": "IB0035"}}, "SBGRO048.CUL"),
    ({"planting": {"depth": -1}}, "field 'depth': found -1"),
    ({"planting": {"population": 123456}}, "PPOP"),
    ({"planting": {"date": "bad"}}, "planting, field 'date'"),
    ({"harvest_date": "bad"}, "harvest_date"),
    ({"harvest_date": "2021-03-01"}, "not after the planting date"),
])
def test_single_crop_checks_located_at_entry(mixed, rows, installed, change, expected):
    entry = mixed["crops"][1]
    for key, value in change.items():
        if key == "planting":
            entry[key].update(value)
        else:
            entry[key] = value
    assert any(p.startswith("FileX template, crops[2]") and expected in p
               for p in problems(mixed, rows))


@pytest.mark.parametrize("missing", ["planting_material_weight", "sprout_length", "harvest_date"])
def test_potato_entry_requirements(mixed, rows, installed, missing):
    entry = mixed["crops"][1]
    entry.update(crop="potato", cultivar={"code": "IB0001"}, harvest_date="2021-08-01")
    entry["planting"].update(planting_material_weight=1500, sprout_length=2)
    del (entry if missing == "harvest_date" else entry["planting"])[missing]
    assert any(p.startswith("FileX template, crops[2]") and missing in p and "potato needs it" in p
               for p in problems(mixed, rows))


def test_crops_needs_treatments(mixed, rows, installed):
    del mixed["treatments"]
    mixed["treatment_name"] = "Only one"
    assert any("crops: needs treatments" in p for p in problems(mixed, rows))


def test_crops_needs_treatment_crops(mixed, rows, installed):
    del mixed["treatment_crops"]
    assert any("crops: needs treatment_crops" in p for p in problems(mixed, rows))


def test_treatment_crops_needs_crops(data, rows, installed):
    data["treatment_crops"] = [1]
    assert any("treatment_crops: needs crops" in p for p in problems(data, rows))


def test_treatment_crops_needs_treatments(data, rows, installed):
    data["treatment_crops"] = [1]
    assert any("treatment_crops: needs treatments" in p for p in problems(data, rows))


@pytest.mark.parametrize("value", [None, "1231", (1, 2, 3, 1), {}, [], [1, 2, 3], [1, 2, 3, 1, 1]])
def test_one_crop_entry_number_per_treatment(mixed, rows, installed, value):
    mixed["treatment_crops"] = value
    assert any("treatment_crops: supply one crop entry number per treatment" in p
               for p in problems(mixed, rows))


@pytest.mark.parametrize("value", [True, False, "1", 1.0, None, [], 0, -1, 4])
def test_treatment_crop_numbers_are_whole_and_in_range(mixed, rows, installed, value):
    mixed["treatment_crops"][3] = value
    assert any("treatment_crops[4]: found" in p and "Supply a whole number 1 to 3" in p
               for p in problems(mixed, rows))


def test_every_crop_entry_used(mixed, rows, installed):
    mixed["treatment_crops"] = [1, 1, 1, 1]
    found = problems(mixed, rows)
    for number in (2, 3):
        assert any(f"crop entry {number} is not used by any treatment" in p for p in found)


def test_independent_entry_and_mapping_problems_reported_together(mixed, rows, installed):
    mixed["crops"][0]["cultivar"]["code"] = "bad"
    mixed["crops"][1]["planting"]["depth"] = -1
    mixed["treatment_crops"] = [False, 4, 1]
    found = problems(mixed, rows)
    for expected in ("crops[1]", "crops[2]", "per treatment", "treatment_crops[1]", "treatment_crops[2]",
                     "crop entry 2 is not used", "crop entry 3 is not used"):
        assert any(expected in p for p in found)


@pytest.mark.parametrize("entries", [None, [], [{}] * 100])
def test_malformed_crops_does_not_hide_invalid_treatment_crop_numbers(mixed, rows, installed, entries):
    mixed.update(crops=entries, treatment_crops=[False, "2", 0, 100])
    found = problems(mixed, rows)
    assert any("Supply a list of 1 to 99 crop entries" in p for p in found)
    for number in range(1, 5):
        assert any(f"treatment_crops[{number}]: found" in p for p in found)


def test_valid_three_entries_four_treatments_without_mutation(mixed, installed):
    from dssatlab.crop_entries import _check_crop_entries
    before = deepcopy(mixed)
    assert _check_crop_entries(mixed, installed.executable.parent) == []
    assert mixed == before


def test_two_entries_can_name_the_same_crop(mixed, installed):
    from dssatlab.crop_entries import _check_crop_entries
    mixed["crops"][1] = deepcopy(mixed["crops"][0])
    mixed["crops"][1]["cultivar"]["code"] = "ZZ0001"
    assert _check_crop_entries(mixed, installed.executable.parent) == []


@pytest.mark.parametrize("count", [1, 99])
def test_crop_entry_count_boundaries(mixed, installed, count):
    from dssatlab.crop_entries import _check_crop_entries
    mixed["crops"] = [deepcopy(mixed["crops"][0]) for _ in range(count)]
    mixed["treatments"] = ["Maize"] * count
    mixed["treatment_crops"] = list(range(1, count + 1))
    assert _check_crop_entries(mixed, installed.executable.parent) == []


def test_treatment_crop_entry_selection(mixed):
    from dssatlab.filex_template import _template_crop_entry
    assert [_template_crop_entry(mixed, k)["crop"] for k in (1, 2, 3, 4)] == [
        "maize", "soybean", "wheat", "maize"]
    assert _template_crop_entry(mixed, "3")["cultivar"]["code"] == "IB0488"


def test_single_crop_entry_selection(data):
    from dssatlab.filex_template import _template_crop_entry
    assert _template_crop_entry(data, 1) == data


def test_single_crop_has_no_crop_entry_problems(data, installed):
    from dssatlab.crop_entries import _check_crop_entries
    assert _check_crop_entries(data, installed.executable.parent) == []


def test_rotation_has_no_crop_entry_problems(data, installed):
    from dssatlab.crop_entries import _check_crop_entries
    rotation = dict(treatment_name="Sequence", rotation=[data, {"crop": "fallow", "end_date": "2022-02-28"}])
    assert _check_crop_entries(rotation, installed.executable.parent) == []


def test_genotype_files_cover_each_entry_once(mixed, installed):
    from dssatlab.filex_template import _template_genotype_files
    mixed["crops"].append(deepcopy(mixed["crops"][0]))
    mixed["treatment_crops"][-1] = 4
    paths = _template_genotype_files(mixed, installed.executable.parent)
    assert [path.name for path in paths] == [
        "MZCER048.CUL", "MZCER048.ECO", "MZCER048.SPE",
        "SBGRO048.CUL", "SBGRO048.ECO", "SBGRO048.SPE",
        "WHCER048.CUL", "WHCER048.ECO", "WHCER048.SPE"]
