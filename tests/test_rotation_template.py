"""Rotation FileX templates reuse crop checks and write one sequence."""

from copy import deepcopy
from datetime import date, timedelta
import hashlib
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, write_filex_template
from dssatlab.filex import _section_row, _treatment_rows
from dssatlab.filex_skeleton import write_filex
from dssatlab.filex_template import _check_filex_template, _load_filex_template
from test_filex_template import data, data_dir, rows


@pytest.fixture
def rotation(data):
    data.pop("treatment_name")
    data["planting"]["date"] = "1978-03-15"
    wheat = deepcopy(data)
    wheat.update(crop="wheat", cultivar={"code": "IB1500"})
    wheat["planting"]["date"] = "1978-11-15"
    return dict(treatment_name="Rotation", rotation=[
        data, dict(crop="fallow", end_date="1978-11-14"),
        wheat, dict(crop="fallow", end_date="1979-03-14")])


@pytest.fixture
def genotype(data_dir):
    (data_dir / "Genotype" / "WHCER048.CUL").write_text(
        "@VAR#  VAR-NAME\nIB1500 Wheat\n")
    return data_dir


@pytest.mark.parametrize("value", [None, {}, "maize", (), [], [None], [None] * 100])
def test_rotation_list_shape(rotation, genotype, value):
    rotation["rotation"] = value
    assert any("rotation:" in p and "list of 2 to 99" in p
               for p in _check_filex_template(rotation, genotype))


def _crop_components(crop, count):
    components = []
    for number in range(count):
        component = deepcopy(crop)
        planting = date(1978, 3, 15) + timedelta(days=2 * number)
        component["planting"]["date"] = planting.isoformat()
        component["harvest_date"] = (planting + timedelta(days=1)).isoformat()
        components.append(component)
    components[-1]["harvest_date"] = "1979-03-14"
    return components


@pytest.mark.parametrize("count", [10, 99])
def test_long_rotation_columns_and_levels(rotation, genotype, rows, tmp_path, count):
    rotation["rotation"] = _crop_components(rotation["rotation"][0], count)
    assert _check_filex_template(rotation, genotype) == []
    text = write_filex(rotation, *rows, tmp_path, data_dir=genotype).read_text()
    treatments = dict(_treatment_rows(text))
    assert list(treatments.values()) == [("1", str(n)) for n in range(1, count + 1)]
    for number, line in enumerate(treatments, 1):
        assert line[:2] == " 1"
        assert int(line[2:4]) == number
        assert line[4:8] == " 0 0"
        assert line[9:34] == "Rotation".ljust(25)
        # Level references retain their original three-character columns.
        for column in (34, 46, 67, 70):  # CU, MP, MH, SM
            assert line[column:column + 3] == f"{number:3d}"
        assert line[37:46] == "  1  0  0"
        assert line[49:67] == "  0" * 6
    assert list(treatments)[9][:8] == " 110 0 0"
    if count == 99:
        assert list(treatments)[98][:8] == " 199 0 0"


@pytest.mark.parametrize("count", [1, 100])
def test_rotation_component_count_rejected(rotation, genotype, rows, tmp_path, count):
    rotation["rotation"] = _crop_components(rotation["rotation"][0], count)
    expected = (f"FileX template, rotation: found {rotation['rotation']!r}. "
                "Supply a list of 2 to 99 rotation components.")
    with pytest.raises(DSSATCheckError) as error:
        write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert error.value.problems == [expected]
    assert not list(tmp_path.glob("*.SQX"))


def test_crop_first_rotation_bytes_unchanged(rotation, genotype, rows, tmp_path):
    path = write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    # Digest captured from the v0.16.1 renderer with this crop-first fixture.
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "fee4e3c86d84708639bdd0b190e3d908cb52552e22cb16ea4ee5c1b38ba152a7")


@pytest.mark.parametrize("key", ["crop", "cultivar", "planting", "harvest_date",
                                 "treatments", "treatment_fields"])
def test_mixed_forms(rotation, genotype, key):
    rotation[key] = None
    assert any("rotation" in p and key in p and "cannot" in p
               for p in _check_filex_template(rotation, genotype))


@pytest.mark.parametrize("component,expected", [
    (None, "expected a dict"), ([], "expected a dict"),
    ({}, "missing required field 'crop'"),
    ({"crop": "fallow"}, "missing required field 'end_date'"),
    ({"crop": "fallow", "end_date": "1978-02-30"}, "quoted YYYY-MM-DD"),
    ({"crop": "fallow", "end_date": date(1978, 11, 14)}, "quoted YYYY-MM-DD"),
    ({"crop": "fallow", "end_date": None}, "quoted YYYY-MM-DD"),
    ({"crop": "fallow", "end_date": "1978-11-14", "planting": {}}, "unknown key 'planting'"),
    ({"crop": "fallow", "end_date": "1978-11-14", "harvest_date": None}, "unknown key 'harvest_date'"),
    ({"crop": "fallow", "end_date": "1978-11-14", "cultivar": {}}, "unknown key 'cultivar'"),
])
def test_component_shape_prefix(rotation, genotype, component, expected):
    rotation["rotation"][2] = component
    assert any(p.startswith("FileX template, rotation[3]") and expected in p
               for p in _check_filex_template(rotation, genotype))


@pytest.mark.parametrize("change,expected", [
    ({"crop": "unknown"}, "not a template crop"),
    ({"cultivar": {"code": "IB1500"}}, "MZCER048.CUL"),
    ({"harvest_date": "1978-03-15"}, "not after"),
    ({"harvest_date": "bad"}, "quoted YYYY-MM-DD"),
    ({"planting": {"population": 1234567}}, "PPOP"),
    ({"planting": {"depth": -1}}, "depth"),
    ({"planting": {"date": "bad"}}, "date"),
])
def test_crop_checks_reused(rotation, genotype, change, expected):
    component = rotation["rotation"][0]
    for key, value in change.items():
        if key == "planting":
            component[key].update(value)
        else:
            component[key] = value
    assert any(p.startswith("FileX template, rotation[1]") and expected in p
               for p in _check_filex_template(rotation, genotype))


@pytest.mark.parametrize("missing", ["planting_material_weight", "sprout_length", "harvest_date"])
def test_potato_rules(rotation, genotype, rows, tmp_path, missing):
    component = rotation["rotation"][0]
    component.update(crop="potato", cultivar={"code": "IB0001"}, harvest_date="1978-08-01")
    component["planting"].update(planting_material_weight=1500, sprout_length=2)
    assert _check_filex_template(rotation, genotype) == []
    del (component if missing == "harvest_date" else component["planting"])[missing]
    with pytest.raises(DSSATCheckError) as error:
        write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert len(error.value.problems) == 1
    assert missing in error.value.problems[0] and "rotation[1]" in error.value.problems[0]
    assert not list(tmp_path.glob("*.SQX"))


def test_top_level_fallow_rejected(data, genotype):
    data["crop"] = "fallow"
    assert any("not a template crop" in p for p in _check_filex_template(data, genotype))


def test_all_problems_before_any_write(rotation, genotype, rows, tmp_path, monkeypatch):
    rotation.update(crop="maize", treatments=["Other"], treatment_name="")
    rotation["rotation"] = [None, dict(crop="fallow", end_date="bad", cultivar={}),
                            dict(crop="potato", cultivar={"code": "IB1500"}, planting={})]
    problems = _check_filex_template(rotation, genotype)
    for word in ("crop", "treatments", "treatment_name", "rotation[1]", "rotation[2]",
                 "rotation[3]", "end_date", "harvest_date", "sprout_length", "PTSUB048.CUL"):
        assert any(word in p for p in problems)
    def forbidden(*args, **kwargs):
        pytest.fail("invalid rotation must not write")
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    with pytest.raises(DSSATCheckError) as error:
        write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert error.value.problems == problems


def test_probe_a_fixture(rotation, genotype, rows, tmp_path):
    before = deepcopy(rotation)
    path = write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert path.name == "TEST7801.SQX"
    expected = Path(__file__).parent / "fixtures" / "rotation_probe_a.SQX"
    assert path.read_text() == expected.read_text()
    assert rotation == before


@pytest.mark.parametrize("end,years", [("1979-03-14", "1"), ("1980-03-13", "2")])
def test_cycle_years_and_dated_crop(rotation, genotype, rows, tmp_path, end, years):
    rotation["rotation"][-1]["end_date"] = end
    rotation["rotation"][0]["harvest_date"] = "1978-08-01"
    text = write_filex(rotation, *rows, tmp_path, data_dir=genotype).read_text()
    assert _section_row(text, "TREATMENTS", "N", 1, ("MH",))["MH"] == "1"
    assert _section_row(text, "HARVEST DETAILS", "H", 1, ("HDATE",))["HDATE"] == "78213"
    for level in range(1, 5):
        assert _section_row(text, "SIMULATION CONTROLS", "N", level, ("NYERS",))["NYERS"] == (
            years if level == 1 else "1")
    assert _section_row(text, "SIMULATION CONTROLS", "N", 1, ("HARVS",))["HARVS"] == "R"


def test_commented_example(tmp_path, data_dir):
    pytest.importorskip("yaml")
    path = tmp_path / "template.yaml"
    write_filex_template(path)
    example = path.read_text().split("# Rotation example", 1)[1].splitlines()[1:]
    path.write_text("\n".join(line[2:] for line in example if line.startswith("# ")))
    data, problems = _load_filex_template(path)
    assert problems == []
    assert len(data["rotation"]) == 2
    assert _check_filex_template(data, data_dir) == []


@pytest.mark.parametrize("name", [None, True, "", "  ", "x" * 26, "caf\u00e9", "a\nb"])
def test_rotation_name_rules(rotation, genotype, name):
    rotation["treatment_name"] = name
    assert _check_filex_template(rotation, genotype) == [
        f"FileX template, treatment_name: found {name!r}. "
        "Supply 1-25 printable ASCII characters, not just spaces."]


@pytest.mark.parametrize("key", ["treatment_name", "cultivar", "planting", "crop"])
def test_missing_required_fields(rotation, genotype, key):
    target = rotation if key == "treatment_name" else rotation["rotation"][0]
    del target[key]
    prefix = "FileX template" if key == "treatment_name" else "FileX template, rotation[1]"
    assert any(p.startswith(prefix) and f"missing required field '{key}'" in p
               for p in _check_filex_template(rotation, genotype))


def test_nine_components_and_crop_controls(rotation, genotype, rows, tmp_path):
    components = []
    for month in range(3, 11):
        c = deepcopy(rotation["rotation"][0])
        c.update(crop="soybean", cultivar={"code": "IB0011"})
        c["planting"]["date"] = f"1978-{month:02d}-15"
        c["harvest_date"] = f"1978-{month:02d}-25"
        components.append(c)
    rotation["rotation"] = components + [rotation["rotation"][-1]]
    text = write_filex(rotation, {1: rows[0]}, {1: rows[1]}, tmp_path,
                       data_dir=genotype).read_text()
    for level in range(1, 10):
        general = _section_row(text, "SIMULATION CONTROLS", "N", level, ("NYERS",))
        options = _section_row(text, "SIMULATION CONTROLS", "N", level, ("SYMBI",))
        assert options["SYMBI"] == ("Y" if level < 9 else "N")
        assert general["SDATE"] == "78074"
        row = next(line for line in text.splitlines() if line.startswith(f"{level:2d} GE"))
        assert row[71:] == ("CRGRO048" if level < 9 else "")
    assert " 9 FA IB0001 -99" in text
    assert " 1 9 0 0 Rotation                   9  1  0  0  0" in text
