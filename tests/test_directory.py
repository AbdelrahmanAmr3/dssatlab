"""Chosen directories with fake DSSAT; no installed DSSAT is used."""

from pathlib import Path

import pytest

import dssatlab as dl
from test_filex_template import data, rows
from test_scenarios import batch_inputs
from test_simulation_run import fake_dssat, inputs, snapshot
from test_simulation_template import installed


@pytest.mark.parametrize("relative", [False, True])
def test_run_directory_keeps_filex_cwd(inputs, fake_dssat, tmp_path, monkeypatch, relative):
    inputs.weather.rename(inputs.weather.with_name("measured.csv"))
    monkeypatch.chdir(tmp_path)
    parent = tmp_path / "chosen outputs with a long directory name beyond fifty one characters" / "nested"
    argument = str(parent.relative_to(tmp_path)) if relative else parent
    result = dl.run(inputs.filex, treatment=2, directory=argument)
    assert result.run_dir.parent == parent
    assert result.outputs == [result.run_dir / "Summary.OUT"]
    assert result.outputs[0].read_bytes() == b"summary"
    assert fake_dssat.calls[0][1] == inputs.filex.parent
    assert fake_dssat.calls[0][0][1:] == ["C", inputs.filex.name, "2"]
    assert not list(inputs.filex.parent.glob("dssat_run_*"))
    assert not (inputs.filex.parent / "Summary.OUT").exists()


def test_run_resolves_directory_before_discovery_changes_cwd(inputs, fake_dssat, tmp_path, monkeypatch):
    inputs.weather.rename(inputs.weather.with_name("measured.csv"))
    monkeypatch.chdir(tmp_path)
    fake_dssat.connect.side_effect = lambda **kwargs: (
        monkeypatch.chdir(inputs.filex.parent) or fake_dssat.executable)
    result = dl.run(inputs.filex, directory="outputs")
    assert result.run_dir.parent == tmp_path / "outputs"


def test_simulation_resolves_at_construction_without_creating_directory(
        inputs, fake_dssat, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = snapshot(inputs.filex.parent)
    sim = dl.Simulation(inputs.filex, 2, inputs.rows, directory="outputs/nested")
    parent = tmp_path / "outputs/nested"
    assert not parent.exists()
    assert sim.check() == []
    assert not parent.exists()
    monkeypatch.chdir(inputs.filex.parent)
    result = sim.run()
    assert result.run_dir.parent.parent == parent
    assert fake_dssat.calls[0][1] == result.run_dir.parent
    assert (result.run_dir.parent / inputs.filex.name).is_file()
    assert (result.run_dir.parent / "UFGA8201.WTH").is_file()
    assert snapshot(inputs.filex.parent) == before


@pytest.mark.parametrize("source_form", ["dict", "yaml"])
def test_template_directory(data, rows, installed, tmp_path, source_form):
    source = data
    if source_form == "yaml":
        yaml = pytest.importorskip("yaml")
        source = tmp_path / "inputs/filex.yaml"
        source.parent.mkdir()
        source.write_text(yaml.safe_dump(data), encoding="utf-8")
    parent = tmp_path / "outputs/nested"
    result = dl.Simulation(filex_template=source, weather=rows[0], soil=rows[1],
                           directory=parent).run()
    assert result.run_dir.parent.parent == parent
    assert installed.calls[0][1] == result.run_dir.parent
    assert (result.run_dir.parent / "TEST2101.MZX").is_file()
    assert (result.run_dir.parent / "SOIL.SOL").is_file()
    assert (result.run_dir.parent / "MZCER048.CUL").is_file()


@pytest.mark.parametrize("sweep", [False, True])
def test_batches_use_one_directory_for_every_simulation(
        batch_inputs, fake_dssat, tmp_path, monkeypatch, sweep):
    monkeypatch.chdir(tmp_path)
    parent = tmp_path / "outputs/nested"
    check = dl.Simulation._check_inputs

    def change_cwd(sim, *args, **kwargs):
        monkeypatch.chdir(batch_inputs.filex.parent)
        return check(sim, *args, **kwargs)

    monkeypatch.setattr(dl.Simulation, "_check_inputs", change_cwd)
    if sweep:
        summary = Path(__file__).parent / "fixtures/output_files/summary/two_treatments/Summary.OUT"
        fake_dssat.outputs["Summary.OUT"] = summary.read_bytes()
        result_rows = dl.run_sweep(batch_inputs.filex, batch_inputs.rows, treatments=[1, 3],
                                   factors={"fertilizer": {"none": []}}, directory="outputs/nested")
        directories = {row["run_dir"] for row in result_rows}
        assert {row["scenario"] for row in result_rows} == {"base", "none"}
    else:
        results = dl.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=[1, 3],
                                    scenarios={"same": {}}, directory="outputs/nested")
        directories = {result.run_dir for result in results.values()}
        assert list(results) == [("base", 1), ("base", 3), ("same", 1), ("same", 3)]
    assert len(directories) == 4
    assert all(path.parent.parent == parent for path in directories)
    assert {call[1] for call in fake_dssat.calls} == {path.parent for path in directories}
    assert not list(batch_inputs.filex.parent.glob("dssat_sim_*"))


@pytest.mark.parametrize("api", ["run", "simulation", "treatments", "sweep"])
@pytest.mark.parametrize("failure", ["file", "parent-file", "permission", "dated-folder"])
def test_unusable_directory_names_path_and_remedy(
        inputs, fake_dssat, tmp_path, monkeypatch, api, failure):
    parent = tmp_path / "chosen"
    if failure == "file":
        parent.write_text("keep me", encoding="utf-8")
    elif failure == "parent-file":
        parent.write_text("keep me", encoding="utf-8")
        parent = parent / "nested"
    else:
        mkdir = Path.mkdir

        def denied(path, *args, **kwargs):
            if failure == "permission" and path == parent:
                raise PermissionError("access denied")
            if failure == "dated-folder" and path.parent == parent:
                raise PermissionError("access denied")
            return mkdir(path, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", denied)
    before = snapshot(inputs.filex.parent)
    with pytest.raises(dl.DSSATError) as error:
        if api == "run":
            inputs.weather.rename(inputs.weather.with_name("measured.csv"))
            before = snapshot(inputs.filex.parent)
            dl.run(inputs.filex, directory=parent)
        elif api == "simulation":
            dl.Simulation(inputs.filex, 2, inputs.rows, directory=parent).run()
        elif api == "treatments":
            dl.run_treatments(inputs.filex, inputs.rows, treatments=[2], directory=parent)
        else:
            dl.run_sweep(inputs.filex, inputs.rows, treatments=[2],
                         factors={"fertilizer": {"none": []}}, directory=parent)
    assert str(parent) in str(error.value)
    assert "Pass directory=" in str(error.value)
    assert "writable folder" in str(error.value)
    assert fake_dssat.calls == []
    assert snapshot(inputs.filex.parent) == before
    if failure in ("file", "parent-file"):
        assert (tmp_path / "chosen").read_text(encoding="utf-8") == "keep me"


def test_run_directory_collision_and_launch_cleanup(inputs, fake_dssat, tmp_path):
    inputs.weather.rename(inputs.weather.with_name("measured.csv"))
    parent = tmp_path / "outputs"
    first = dl.run(inputs.filex, directory=parent)
    second = dl.run(inputs.filex, directory=parent)
    assert second.run_dir.name == first.run_dir.name + "-2"
    fake_dssat.start_error = OSError("cannot execute")
    with pytest.raises(dl.DSSATRunError, match="Could not start"):
        dl.run(inputs.filex, directory=parent)
    assert set(parent.iterdir()) == {first.run_dir, second.run_dir}


def test_failed_run_keeps_outputs_in_chosen_directory(inputs, fake_dssat, tmp_path):
    inputs.weather.rename(inputs.weather.with_name("measured.csv"))
    fake_dssat.returncode = 99
    parent = tmp_path / "outputs"
    with pytest.raises(dl.DSSATRunError) as error:
        dl.run(inputs.filex, directory=parent)
    kept, = parent.iterdir()
    assert str(kept) in str(error.value)
    assert (kept / "Summary.OUT").read_bytes() == b"summary"
