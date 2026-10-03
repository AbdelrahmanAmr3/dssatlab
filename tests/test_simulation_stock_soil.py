"""Stock soil checks read only IDs and runs preserve the supplied file."""

import pytest

import dssatlab as lab
from test_filex_template import data, rows
from test_simulation_run import fake_dssat, inputs, snapshot
from test_simulation_template import installed


def stock_soil(folder, name="IB.SOL", ids=("IBOTHER001", "IBMZ910014")):
    path = folder / name
    # Extra columns, CRLF and non-ASCII comments must reach DSSAT unchanged.
    content = b"*SOILS: stock profiles\r\n! caf\xe9\r\n"
    for soil_id in ids:
        content += f"*{soil_id}  stock profile\r\n".encode("ascii")
        content += b"@ SLB EXTRA\r\n   60 preserved\r\n"
    path.write_bytes(content)
    return path


@pytest.mark.parametrize("kind", ["id", "name", "missing", "empty", "case"])
def test_stock_soil_reports_one_problem(inputs, fake_dssat, tmp_path, kind):
    name = {"name": "OTHER.SOL", "case": "IB.sol"}.get(kind, "IB.SOL")
    ids = ("IBOTHER001", "IBOTHER002") if kind == "id" else ("IBMZ910014",)
    path = tmp_path / name if kind == "missing" else stock_soil(tmp_path, name, ids)
    if kind == "empty":
        path.write_bytes(b"*SOILS: title only\r\n*\r\n! no profiles\r\n")
    before = snapshot(tmp_path)
    sim = lab.Simulation(inputs.filex, 2, inputs.weather, soil=path)
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    message = problems[0]
    assert str(path) in message and "stock soil file" in message.lower()
    assert "Supply" in message or "Rename" in message
    if kind in ("id", "empty"):
        assert "IBMZ910014" in message and "IDs found" in message
        assert "SOILS" not in message
        for soil_id in ids if kind == "id" else ("none",):
            assert soil_id in message
    elif kind in ("name", "case"):
        assert "IB.SOL" in message and "SOIL.SOL" in message
    else:
        assert "Cannot read" in message
    with pytest.raises(lab.DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("name", ["IB.SOL", "SOIL.SOL"])
@pytest.mark.parametrize("form", ["str", "path"])
@pytest.mark.parametrize("sibling", [False, True])
def test_run_copies_only_stock_soil(inputs, fake_dssat, tmp_path, name, form, sibling):
    path = stock_soil(inputs.filex.parent if sibling else tmp_path, name)
    before = snapshot(inputs.filex.parent)
    source_before = (path.read_bytes(), path.stat().st_mtime_ns)
    source = str(path) if form == "str" else path
    sim = lab.Simulation(inputs.filex, 2, inputs.weather, soil=source)
    assert sim.check(verbose=False) == []
    folder = sim.run().run_dir.parent
    assert [p.name for p in folder.iterdir() if p.suffix.upper() == ".SOL"] == [name]
    assert (folder / name).read_bytes() == path.read_bytes()
    for sibling_name in inputs.siblings:
        if not sibling_name.upper().endswith(".SOL"):
            assert (folder / sibling_name).read_bytes() == (inputs.filex.parent / sibling_name).read_bytes()
    assert snapshot(inputs.filex.parent) == before
    assert (path.read_bytes(), path.stat().st_mtime_ns) == source_before


def test_stock_soil_keeps_selected_id_with_experiment_overrides(inputs, fake_dssat, tmp_path):
    path = stock_soil(tmp_path)
    sim = lab.Simulation(inputs.filex, 2, inputs.weather, soil=path,
                         management={"treatments": {2: {"controls": {"start_date": "1982-02-25"}}}})
    assert sim.check(verbose=False) == []
    folder = sim.run().run_dir.parent
    assert b"IBMZ910014" in (folder / inputs.filex.name).read_bytes()
    assert b"IBOTHER001" not in (folder / inputs.filex.name).read_bytes()
    assert (folder / path.name).read_bytes() == path.read_bytes()


def test_stock_soil_id_is_checked_with_experiment_overrides(inputs, tmp_path):
    path = stock_soil(tmp_path, ids=("IBOTHER001",))
    sim = lab.Simulation(inputs.filex, 2, inputs.weather, soil=path,
                         management={"treatments": {2: {"controls": {"start_date": "1982-02-25"}}}})
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("IBMZ910014", "IBOTHER001", "IDs found"))


@pytest.mark.parametrize("form", ["str", "path", "field"])
def test_stock_soil_refused_for_template(data, rows, installed, tmp_path, form):
    path = tmp_path / "missing.SoL"  # Refuse before trying to read or parse CSV.
    source = {"str": str(path), "path": path, "field": {1: path}}[form]
    sim = lab.Simulation(filex_template=data, weather=rows[0], soil=source)
    expected = ("A stock soil file needs a copied FileX. "
                "Supply soil data rows for a FileX template.")
    before = snapshot(tmp_path)
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(lab.DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert snapshot(tmp_path) == before
