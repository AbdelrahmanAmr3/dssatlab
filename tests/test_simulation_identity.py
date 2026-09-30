"""Scenario labels and supplied site data reach only the copied FileX."""

import pytest

from dssatlab import DSSATCheckError, Simulation, run_treatments
from test_scenarios import batch_inputs
from test_simulation_run import fake_dssat, inputs, snapshot, soil_rows


@pytest.mark.parametrize("station", ["UFGA", "UFGA8307"])
@pytest.mark.parametrize("soil_id", [None, "OWN0000001", "SHORT"])
@pytest.mark.parametrize("entry", [
    {"controls": {"start_date": "1982-02-25"}}, {"irrigation": []}, {"fertilizer": []},
])
def test_experiment_copy_uses_supplied_site_only_in_selected_field(
        batch_inputs, fake_dssat, soil_rows, station, soil_id, entry):
    filex = batch_inputs.filex
    text = filex.read_text().replace("UFGA       -99", f"{station:<8}   -99")
    filex.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    original = filex.read_bytes()
    weather = [dict(row, station="HOME") for row in batch_inputs.rows]
    soil = None if soil_id is None else [dict(row, soil_id=soil_id) for row in soil_rows]
    sim = Simulation(filex, "05", weather, soil=soil, name="own site",
                     management={"treatments": {5: entry}})

    assert sim.check(verbose=False) == []
    result = sim.run()
    copied = (result.run_dir.parent / filex.name).read_bytes()
    before, after = original.splitlines(), copied.splitlines()
    # Treatment 5 points at field 2; the other treatments and field stay intact.
    assert after[2:4] == before[2:4]
    assert after[4][8:34].strip() == b"own site"
    field = after.index(next(line for line in after if line.startswith(b" 2 UFGA0002")))
    assert after[field - 1] == before[field - 1]
    assert after[field][:11] == before[field][:11]
    assert after[field][11:20].strip() == b"HOME"
    assert after[field][20:67] == before[field][20:67]
    assert after[field][67:79].strip() == (soil_id or "IBMZ910014").encode()
    assert after[field][79:] == before[field][79:]
    assert len(after[field]) == len(before[field])
    assert copied.splitlines(keepends=True)[field].endswith(b"\r\n")
    assert filex.read_bytes() == original
    assert (result.run_dir.parent / "HOME8201.WTH").is_file()
    if soil_id:
        assert f"*{soil_id:<10}" in (result.run_dir.parent / "SOIL.SOL").read_text()


@pytest.mark.parametrize("header", ["TNAME....................", "TNAM....................."])
def test_scenarios_write_their_names_without_shifting_treatment_columns(
        batch_inputs, fake_dssat, header):
    filex = batch_inputs.filex
    filex.write_text(filex.read_text().replace("TNAME....................", header))
    original = filex.read_bytes()
    results = run_treatments(
        filex, batch_inputs.rows, treatments=[3],
        management={"treatments": {3: {"controls": {"start_date": "1982-02-25"}}}},
        scenarios={"own site": {}, "abcdefghijklmnopqrstuvwxyz": {}},
    )
    for (name, _), result in results.items():
        copied = (result.run_dir.parent / filex.name).read_text().splitlines()
        before = original.decode().splitlines()
        assert copied[3][8:34].strip() == name
        assert len(copied[3]) == len(before[3])
        assert copied[3][:8] == before[3][:8]
        assert copied[3][34:70] == before[3][34:70]  # SM changes for controls.
        assert copied[2] == before[2] and copied[4] == before[4]
    assert filex.read_bytes() == original


def test_overlong_scenario_name_is_rejected_before_any_copy(batch_inputs, fake_dssat):
    before = snapshot(batch_inputs.filex.parent)
    with pytest.raises(DSSATCheckError, match="26-character field"):
        run_treatments(
            batch_inputs.filex, batch_inputs.rows, treatments=[3],
            management={"treatments": {3: {"controls": {"start_date": "1982-02-25"}}}},
            scenarios={"abcdefghijklmnopqrstuvwxyz!": {}},
        )
    assert snapshot(batch_inputs.filex.parent) == before
    assert not list(batch_inputs.filex.parent.glob("dssat_sim_*"))


@pytest.mark.parametrize("management", [None, {"treatments": {}}, {"treatments": {3: {}}}])
def test_no_experiment_override_keeps_original_identity(batch_inputs, fake_dssat, management):
    result = Simulation(batch_inputs.filex, 3, batch_inputs.rows, management=management).run()
    assert (result.run_dir.parent / batch_inputs.filex.name).read_bytes() == batch_inputs.filex.read_bytes()

