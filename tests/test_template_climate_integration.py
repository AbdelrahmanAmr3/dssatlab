"""Climate station identity, shared sources and unchanged template weather copies."""

from copy import deepcopy
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError, Simulation, run_treatments
from dssatlab.filex import _section_row
from test_climate import DTCM
from test_rotation_template import rotation
from test_simulation_run import fake_dssat
from test_simulation_template import data, installed, rows
from test_template_climate import climate, controls


@pytest.fixture(params=[False, True], ids=["single-crop", "crop-entries"])
def template(data, request):
    if not request.param:
        return data
    maize = {key: value for key, value in data.items() if key != "treatment_name"}
    soybean = deepcopy(maize)
    soybean.update(crop="soybean", cultivar={"code": "IB0011"})
    return dict(crops=[maize, soybean], treatments=["Maize", "Soybean"],
                treatment_crops=[1, 2])


@pytest.mark.parametrize("method", ["W", "S"])
@pytest.mark.parametrize("form", ["str", "path", "list"])
def test_climate_run_uses_header_and_copies_bytes(
        template, rows, installed, climate, method, form):
    lower = climate.with_name("ufga.cli")
    climate.rename(lower)
    before = lower.read_bytes()
    source = {"str": str(lower), "path": lower, "list": [lower]}[form]
    selected = 2 if "crops" in template else 1
    sim = Simulation(filex_template=template, weather=source, soil=rows[1],
                     treatment=selected, management=controls(method, selected), name="own climate")
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    text = (folder / "UFGA2101.MZX").read_text()
    assert _section_row(text, "FIELDS", "L", 1, ("WSTA",))["WSTA"] == "UFGA"
    coordinates = text.split("@L ...........XCRD", 1)[1].splitlines()[1]
    assert [float(coordinates[left:right]) for left, right in
            ((2, 18), (18, 34), (34, 44))] == [-82.37, 29.63, 10]
    factors = _section_row(text, "TREATMENTS", "N", selected, ("SM",))
    assert factors["TNAME"] == "own climate"
    assert _section_row(text, "SIMULATION CONTROLS", "N", int(factors["SM"]),
                        ("WTHER",))["WTHER"] == method
    assert (folder / "UFGA.CLI").read_bytes() == before == lower.read_bytes()
    assert not list(folder.glob("*.WTH"))


@pytest.mark.parametrize("selected", [1, 2])
@pytest.mark.parametrize("keys", [int, str])
def test_mixed_fields_write_only_daily_station_weather(
        data, rows, installed, climate, selected, keys):
    data.pop("treatment_name")
    data.update(treatments=["Measured", "Generated"], treatment_fields=[1, 2])
    if selected == 1:
        # Copy other fields unchanged even when only their headers were checked.
        climate.write_text(climate.read_text().split("*MONTHLY AVERAGES", 1)[0])
    before = climate.read_bytes()
    sim = Simulation(filex_template=data, treatment=selected,
                     weather={keys(1): rows[0], keys(2): [climate]},
                     soil={keys(1): rows[1], keys(2): rows[1]},
                     management={"treatments": {2: {"controls": {"weather_source": "S"}}}})
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    assert {p.name for p in folder.glob("*.WTH")} == {"TEST2101.WTH"}
    assert {p.name for p in folder.glob("*.CLI")} == {"UFGA.CLI"}
    assert (folder / "UFGA.CLI").read_bytes() == before
    text = (folder / "TEST2101.MZX").read_text()
    assert _section_row(text, "FIELDS", "L", 1, ("WSTA",))["WSTA"] == "TEST"
    assert _section_row(text, "FIELDS", "L", 2, ("WSTA",))["WSTA"] == "UFGA"


def test_all_climate_fields_are_copied(data, rows, installed, climate, tmp_path):
    other = tmp_path / "dtcm.cli"
    other.write_text(DTCM)
    data.pop("treatment_name")
    data.update(treatments=["First", "Second"], treatment_fields=[1, 2])
    sim = Simulation(filex_template=data, weather={1: climate, 2: other},
                     soil={1: rows[1], 2: rows[1]}, management=controls("W"))
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    assert {p.name for p in folder.glob("*.CLI")} == {"UFGA.CLI", "DTCM.CLI"}
    assert (folder / "UFGA.CLI").read_bytes() == climate.read_bytes()
    assert (folder / "DTCM.CLI").read_bytes() == other.read_bytes()
    assert not list(folder.glob("*.WTH"))


def test_rotation_writer_copies_climate_unchanged(rotation, rows, installed, climate):
    rotation["rotation"][2]["cultivar"]["code"] = "IB0488"
    before = climate.read_bytes()
    sim = Simulation(filex_template=rotation, weather=climate, soil=rows[1],
                     management=controls("W"))
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    text = (folder / "UFGA7801.SQX").read_text()
    assert _section_row(text, "FIELDS", "L", 1, ("WSTA",))["WSTA"] == "UFGA"
    assert (folder / "UFGA.CLI").read_bytes() == before == climate.read_bytes()
    assert not list(folder.glob("*.WTH"))
    assert installed.calls[0][0][-2:] == ["Q", "DSSBatch.v48"]


@pytest.mark.parametrize("selected", [1, 2])
@pytest.mark.parametrize("collision", ["other-cli", "rows"])
def test_shared_station_requires_same_source(
        data, rows, installed, climate, tmp_path, selected, collision):
    data.pop("treatment_name")
    data.update(treatments=["First", "Second"], treatment_fields=[1, 2])
    other = tmp_path / "other" / "UFGA.CLI"
    other.parent.mkdir()
    other.write_bytes(climate.read_bytes())  # Identical headers still mean different paths.
    second = other if collision == "other-cli" else [dict(rows[0][0], station="UFGA",
        latitude=29.63, longitude=-82.37, elevation=10)]
    method = "M" if selected == 2 and collision == "rows" else "W"
    inputs = dict(filex_template=data, weather={1: climate, 2: second},
                  soil={1: rows[1], 2: rows[1]}, management=controls(method, selected))
    message = ("Fields 1 and 2 share station UFGA but different weather sources. "
               "Supply the same source for both.")
    sim = Simulation(**inputs, treatment=selected, name="climate scenario")
    assert sim.check(False) == [message]
    with pytest.raises(DSSATCheckError) as error:
        run_treatments(**inputs, treatments=[selected], scenarios={"climate scenario": {}})
    assert error.value.problems == [f"Scenario {name!r}, treatment {selected}: {message}"
                                    for name in ("base", "climate scenario")]
    assert installed.calls == []


@pytest.mark.parametrize("selected", [1, 2])
def test_shared_station_accepts_same_resolved_climate_path(
        data, rows, installed, climate, selected):
    data.pop("treatment_name")
    data.update(treatments=["First", "Second"], treatment_fields=[1, 2])
    sim = Simulation(filex_template=data, weather={"1": str(climate), "2": [Path("UFGA.CLI")]},
                     soil={1: rows[1], 2: rows[1]}, treatment=selected,
                     management=controls("W", selected), name="same climate")
    assert sim.check(False) == []
    folder = sim.run().run_dir.parent
    assert {p.name for p in folder.glob("*.CLI")} == {"UFGA.CLI"}
    assert not list(folder.glob("*.WTH"))
