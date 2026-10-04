"""Potato requirements and dated harvests are checked before any write."""

from datetime import date

import pytest

from dssatlab import DSSATCheckError, Simulation
from dssatlab.filex import _section_row
from dssatlab.filex_skeleton import write_filex
from dssatlab.filex_template import _check_filex_template
from test_filex_template import data, data_dir, rows
from test_simulation_run import fake_dssat, snapshot
from test_simulation_template import installed


@pytest.mark.parametrize("crop", ["maize", "potato"])
def test_dated_harvest_with_management_renders_in_section_order(data, rows, installed, crop):
    data.update(crop=crop, harvest_date="2021-03-02")
    if crop == "potato":
        data["cultivar"]["code"] = "IB0001"
    data["planting"].update(planting_material_weight=1500, sprout_length=2)
    rows[0].append(dict(rows[0][0], date=date(2021, 3, 2)))
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], management={
        "treatments": {1: {
            "irrigation": [dict(date="2021-03-01", amount=20, method="IR001")],
            "fertilizer": [dict(date="2021-03-01", material="FE001",
                                application="AP001", depth=5, n=20)],
        }}})
    assert sim.check(verbose=False) == []
    result = sim.run()
    extension = "PTX" if crop == "potato" else "MZX"
    text = (result.run_dir.parent / f"TEST2101.{extension}").read_text()
    assert _section_row(text, "TREATMENTS", "N", 1, ("MH",))["MH"] == "1"
    planting = _section_row(text, "PLANTING DETAILS", "P", 1, ("PLWT", "SPRL"))
    assert planting["PLWT"] == "1500" and planting["SPRL"] == "2"
    assert text.count("*HARVEST DETAILS") == 1
    assert "@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME\n" in text
    harvest = _section_row(text, "HARVEST DETAILS", "H", 1, ("HDATE", "HSTG"))
    assert harvest["HDATE"] == "21061" and harvest["HSTG"] == "GS000"
    assert all(harvest[key] == "-99" for key in ("HCOM", "HSIZE", "HPC", "HBPC", "HNAME"))
    assert _section_row(text, "SIMULATION CONTROLS", "N", 1, ("HARVS",))["HARVS"] == "R"
    sections = ["PLANTING DETAILS", "IRRIGATION AND WATER MANAGEMENT",
                "FERTILIZERS (INORGANIC)", "HARVEST DETAILS", "SIMULATION CONTROLS"]
    positions = [text.index("*" + section) for section in sections]
    assert positions == sorted(positions)


@pytest.mark.parametrize("missing", [
    ("planting_material_weight", "sprout_length", "harvest_date"),
    ("planting_material_weight",), ("sprout_length",), ("harvest_date",),
])
def test_missing_potato_fields_reported_without_writes(data, rows, installed, tmp_path, missing):
    data.update(crop="potato", cultivar={"code": "IB0001"})
    data["planting"].update(planting_material_weight=1500, sprout_length=2)
    data["harvest_date"] = "2021-03-02"
    rows[0].append(dict(rows[0][0], date=date(2021, 3, 2)))
    for field in missing:
        del (data if field == "harvest_date" else data["planting"])[field]
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1])
    before = snapshot(tmp_path)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert len(error.value.problems) == len(missing)
    for field in missing:
        assert any(field in p and "potato needs" in p for p in error.value.problems)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("harvest", ["2021-02-28", "2021-03-01"])
def test_harvest_must_be_after_planting(data, data_dir, harvest):
    data["harvest_date"] = harvest
    assert any("harvest_date" in p and "after" in p
               for p in _check_filex_template(data, data_dir))


@pytest.mark.parametrize("harvest", [None, True, date(2021, 3, 2), "2021-02-30", "20210302"])
def test_harvest_requires_quoted_iso_date(data, data_dir, harvest):
    data["harvest_date"] = harvest
    assert any("harvest_date" in p and "quoted" in p
               for p in _check_filex_template(data, data_dir))


def test_harvest_outside_weather_collected_with_other_problems(data, rows, installed, tmp_path):
    data.update(harvest_date="2021-03-02", treatment_name="")
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1])
    before = snapshot(tmp_path)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert any("harvest_date" in p and "weather" in p for p in error.value.problems)
    assert any("treatment_name" in p for p in error.value.problems)
    assert snapshot(tmp_path) == before


def test_material_and_sprout_overflow_rejected_before_write(data, data_dir, rows, tmp_path):
    data["planting"].update(planting_material_weight=1234567, sprout_length=1234567)
    before = snapshot(tmp_path)
    with pytest.raises(DSSATCheckError) as error:
        write_filex(data, *rows, tmp_path, data_dir=data_dir)
    for column in ("PLWT", "SPRL"):
        assert any(column in p and "does not fit" in p for p in error.value.problems)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("field", ["planting_material_weight", "sprout_length"])
@pytest.mark.parametrize("value", [True, "2", float("inf"), float("nan")])
def test_material_and_sprout_use_experiment_number_checks(data, data_dir, field, value):
    data["planting"][field] = value
    assert any(field in p and "finite number" in p
               for p in _check_filex_template(data, data_dir))
