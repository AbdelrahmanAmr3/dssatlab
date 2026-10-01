"""FileX templates check before writing and remain editable by v0.6 writers."""

from copy import deepcopy
from pathlib import Path
import sys

import pytest

import dssatlab
from dssatlab import DSSATCheckError, DSSATError


# Expected template crops: name, cultivar, CR, SMODEL, genotype prefix, extensions, SYMBI.
CROPS = [
    ("maize", "IB0035", "MZ", "MZCER048", "MZCER048", ("CUL", "ECO", "SPE"), "N"),
    ("wheat", "IB0488", "WH", "CSCER048", "WHCER048", ("CUL", "ECO", "SPE"), "N"),
    ("rice", "IB0012", "RI", "RICER048", "RICER048", ("CUL", "SPE"), "N"),
    ("soybean", "IB0011", "SB", "CRGRO048", "SBGRO048", ("CUL", "ECO", "SPE"), "Y"),
    ("potato", "IB0001", "PT", "PTSUB048", "PTSUB048", ("CUL", "ECO", "SPE"), "N"),
    ("sorghum", "IB0040", "SG", "SGCER048", "SGCER048", ("CUL", "ECO", "SPE"), "N"),
    ("pearl millet", "IB0033", "ML", "MLCER048", "MLCER048", ("CUL", "ECO", "SPE"), "N"),
    ("barley", "IB0101", "BA", "CSCER048", "BACER048", ("CUL", "ECO", "SPE"), "N"),
    ("peanut", "GH0001", "PN", "CRGRO048", "PNGRO048", ("CUL", "ECO", "SPE"), "Y"),
    ("dry bean", "IB0001", "BN", "CRGRO048", "BNGRO048", ("CUL", "ECO", "SPE"), "Y"),
]


@pytest.fixture
def data():
    return dict(crop="maize", treatment_name="My treatment", cultivar={"code": "IB0035"},
                planting=dict(date="2021-03-01", method="S", distribution="R",
                              population=7.2, row_spacing=75, depth=5))


@pytest.fixture
def data_dir(tmp_path):
    folder = tmp_path / "data" / "Genotype"
    folder.mkdir(parents=True)
    for _, code, _, _, prefix, _, _ in CROPS:
        (folder / f"{prefix}.CUL").write_text(
            f"*CULTIVARS\n!XX9999 is only a comment\n@VAR#  VAR-NAME\n{code} Example\n")
    # A second model must not affect the fixed model's cultivar lookup.
    (folder / "MZIXM048.CUL").write_text("@VAR#  VAR-NAME\nXX9999 Other\n")
    return folder.parent


@pytest.fixture
def rows():
    from dssatlab.weather import _parse_weather
    from dssatlab.soil import _parse_soil
    weather, problems = _parse_weather([dict(station="TEST", latitude=45.125,
        longitude=-100.25, elevation=234, date="2021-03-01", srad=20, tmax=25,
        tmin=10, rain=0)])
    assert problems == []
    soil, problems = _parse_soil([dict(soil_id="SOIL123456", salb=0.13, slro=60,
        sldr=0.5, slpf=1, slb=30, slll=0.1, sdul=0.24, ssat=0.45, srgf=1)])
    assert problems == []
    return weather, soil


def test_written_template_loads_and_passes_checks(tmp_path, data_dir):
    pytest.importorskip("yaml")
    from dssatlab.filex_template import _load_filex_template, _check_filex_template
    path = tmp_path / "filex.yaml"
    assert dssatlab.write_filex_template(path) is None
    data, problems = _load_filex_template(path)
    assert problems == []
    assert _check_filex_template(data, data_dir) == []
    assert set(data) == {"crop", "treatment_name", "planting", "cultivar"}
    assert "write_filex_template" in dssatlab.__all__
    assert all(row[0] in path.read_text() for row in CROPS)


def test_existing_template_is_preserved(tmp_path):
    path = tmp_path / "filex.yaml"
    path.write_bytes(b"keep me")
    with pytest.raises(DSSATError, match="already exists"):
        dssatlab.write_filex_template(path)
    assert path.read_bytes() == b"keep me"


def test_dict_needs_no_yaml(data, data_dir, monkeypatch):
    from dssatlab.filex_template import _load_filex_template, _check_filex_template
    monkeypatch.setitem(sys.modules, "yaml", None)
    before = deepcopy(data)
    loaded, problems = _load_filex_template(data)
    assert problems == []
    assert _check_filex_template(loaded, data_dir) == []
    assert data == before
    _, problems = _load_filex_template("missing.yaml")
    assert any("PyYAML" in p for p in problems)


@pytest.mark.parametrize("crop", ["cotton", "Rice", "pearl_millet", "dry-bean", "MZ", [], None])
def test_unsupported_crop_lists_supported_crops(data, data_dir, crop):
    from dssatlab.filex_template import _check_filex_template
    data["crop"] = crop
    problems = _check_filex_template(data, data_dir)
    assert any("is not a template crop" in p and all(row[0] in p for row in CROPS)
               for p in problems)


@pytest.mark.parametrize("crop,filename,near", [
    (crop, f"{prefix}.CUL", code) for crop, code, _, _, prefix, _, _ in CROPS])
def test_unknown_cultivar_has_closest_codes(data, data_dir, crop, filename, near):
    from dssatlab.filex_template import _check_filex_template
    data.update(crop=crop, cultivar={"code": "XX9999"})
    problems = _check_filex_template(data, data_dir)
    assert any(filename in p and "XX9999" in p and "Closest codes:" in p
               and near in p for p in problems)


@pytest.mark.parametrize("field", ["crop", "planting", "cultivar"])
def test_missing_required_field(data, data_dir, field):
    from dssatlab.filex_template import _check_filex_template
    del data[field]
    assert any(field in p and "missing" in p for p in _check_filex_template(data, data_dir))


@pytest.mark.parametrize("field,value,word", [
    ("treatment_name", "", "treatment_name"),
    ("treatment_name", "x" * 26, "treatment_name"),
    ("treatment_name", "line\nbreak", "treatment_name"),
    ("treatment_name", "caf\u00e9", "treatment_name"),
    ("cultivar", {"code": True}, "code"),
    ("cultivar", {}, "code"),
    ("planting", {}, "planting"),
    ("station", "ABCD", "unknown"),
])
def test_invalid_values_are_check_problems(data, data_dir, field, value, word):
    from dssatlab.filex_template import _check_filex_template
    data[field] = value
    assert any(word in p for p in _check_filex_template(data, data_dir))


def test_all_problems_before_any_write(tmp_path, data, data_dir, rows):
    from dssatlab.filex_skeleton import write_filex
    data.update(treatment_name="", cultivar={"code": "XX9999"})
    data["planting"].update(date="bad", population=-1, row_spacing=False)
    del data["planting"]["depth"]
    destination = tmp_path / "not-created"
    with pytest.raises(DSSATCheckError) as error:
        write_filex(data, *rows, destination, data_dir=data_dir)
    for word in ("treatment_name", "XX9999", "date", "population", "row_spacing", "depth"):
        assert any(word in p for p in error.value.problems)
    assert not destination.exists()


def test_planting_overflow_checked_before_writing(data, data_dir):
    from dssatlab.filex_template import _check_filex_template
    data["planting"]["population"] = 1234567
    assert any("PPOP" in p and "does not fit" in p
               for p in _check_filex_template(data, data_dir))


def test_missing_cultivar_file_and_independent_planting_problem(data, data_dir):
    from dssatlab.filex_template import _check_filex_template
    (data_dir / "Genotype" / "MZCER048.CUL").unlink()
    data["planting"]["depth"] = -1
    problems = _check_filex_template(data, data_dir)
    assert any("MZCER048.CUL" in p and "cannot check" in p for p in problems)
    assert any("depth" in p and "nonnegative" in p for p in problems)


def test_extra_planting_fields_belong_in_experiment_data(data, data_dir):
    from dssatlab.filex_template import _check_filex_template
    data["planting"]["emergence_date"] = "2021-03-03"
    assert any("emergence_date" in p and "unknown key" in p
               for p in _check_filex_template(data, data_dir))


def test_check_does_not_round_multiple_oversized_planting_fields(data, data_dir):
    from dssatlab.filex_template import _check_filex_template
    data["planting"].update(population=1234567, row_spacing=1234567, depth=1234567)
    problems = _check_filex_template(data, data_dir)
    for column in ("PPOP", "PLRS", "PLDP"):
        assert any(column in p and "does not fit" in p for p in problems)


@pytest.mark.parametrize("contents,word", [("", "header"), ("@VAR# NAME\n", "codes")])
def test_malformed_cultivar_table(data, data_dir, contents, word):
    from dssatlab.filex_template import _check_filex_template
    (data_dir / "Genotype" / "MZCER048.CUL").write_text(contents)
    assert any(word in p for p in _check_filex_template(data, data_dir))


@pytest.mark.parametrize("crop,code,model,extension", [
    ("maize", "IB0035", "MZCER048", ".MZX"),
    ("wheat", "IB0488", "CSCER048", ".WHX")])
def test_skeleton_fixed_width_and_existing_writers(tmp_path, data, data_dir, rows,
                                                 crop, code, model, extension):
    from dssatlab.filex_skeleton import write_filex
    from dssatlab.filex import _read_filex, read_treatment_numbers, _section_row
    from dssatlab.filex_write import _write_management
    crop_code = {"maize": "MZ", "wheat": "WH"}[crop]
    data.update(crop=crop, cultivar={"code": code})
    before = deepcopy((data, rows))
    path = write_filex(data, *rows, tmp_path, data_dir=data_dir)
    assert isinstance(path, Path) and path.parent == tmp_path
    assert len(path.name) <= 12 and len(path.stem) <= 8 and path.suffix == extension
    assert (data, rows) == before
    assert read_treatment_numbers(path) == [1]
    values, problems = _read_filex(path, 1)
    assert problems == []
    assert values == dict(WSTA="TEST", ID_SOIL="SOIL123456", START="S", SDATE="21060", NYERS="1")
    text = path.read_text(encoding="ascii")
    for section in ("EXP.DETAILS", "GENERAL", "TREATMENTS", "CULTIVARS", "FIELDS",
                    "INITIAL CONDITIONS", "PLANTING DETAILS", "SIMULATION CONTROLS"):
        assert "*" + section in text
    cultivar = next(line for line in text.splitlines() if line[3:5] == crop_code)
    assert cultivar[6:12] == code
    general = next(line for line in text.splitlines() if line.startswith(" 1 GE"))
    assert general[71:79] == model
    coordinates = text.split("FHDUR\n", 1)[1].splitlines()[0]
    assert float(coordinates[2:18]) == -100.25
    assert float(coordinates[18:34]) == 45.125
    assert float(coordinates[34:44]) == 234
    treatment = _section_row(text, "TREATMENTS", "N", 1, ("MI", "MF"))
    assert treatment["MI"] == treatment["MF"] == "0"
    _write_management(path, 1, {"treatments": {1: {
        "planting": dict(data["planting"], population=8),
        "cultivar": {"crop": crop_code, "code": code},
        "irrigation": [dict(date="2021-03-01", amount=20, method="IR001")],
        "fertilizer": [dict(date="2021-03-01", material="FE001", application="AP001", depth=5, n=20)],
        "initial_conditions": dict(date="2021-03-01", layers=[dict(depth=30, water=0.2, nh4=1, no3=2)]),
        "controls": dict(start_date="2021-03-01", water="Y", nitrogen="Y", output_interval=2),
    }}})
    edited = path.read_text(encoding="ascii")
    assert _read_filex(path, 1)[1] == []
    assert "IR001" in edited and "FE001" in edited
    controls = _section_row(edited, "TREATMENTS", "N", 1, ("SM",))
    assert _section_row(edited, "SIMULATION CONTROLS", "N", int(controls["SM"]),
                        ("FROPT",))["FROPT"] == "2"


def test_duplicate_yaml_key_rejected(tmp_path):
    pytest.importorskip("yaml")
    from dssatlab.filex_template import _load_filex_template
    path = tmp_path / "filex.yaml"
    path.write_text("crop: maize\ncrop: wheat\n")
    assert any("duplicate key" in p for p in _load_filex_template(path)[1])


@pytest.mark.parametrize("crop,code,digest", [
    ("maize", "IB0035", "e8f4919dc7a358db393ffeadfcee6a49b39e062ab0ca30998d874266a60c83e4"),
    ("wheat", "IB0488", "53e8d83b06fe0e7c62c8b63a2b882ec2b4f91751e073ac389d8c58356b0689c2"),
])
def test_original_skeleton_bytes_unchanged(data, rows, crop, code, digest):
    import hashlib
    from dssatlab.filex_skeleton import _render_filex
    data.update(crop=crop, cultivar={"code": code})
    # Digests captured from the pre-v0.10 renderer with these same inputs.
    assert hashlib.sha256(_render_filex(data, *rows)[1].encode("ascii")).hexdigest() == digest
