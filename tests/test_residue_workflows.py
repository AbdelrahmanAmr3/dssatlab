"""Residues in FileX templates, experiment templates and whole-section sweeps."""

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from dssatlab import Simulation, run_sweep, write_experiment_template
from test_filex_template import data, rows
from test_simulation_template import installed
from test_simulation_run import fake_dssat, inputs
from test_planting_run import seen
from test_residues import EVENT, HEADER, FIELDS, sim


def test_l2_template_residue_level_written(data, rows, installed, tmp_path, capsys):
    event = dict(EVENT, date="2021-03-01", n=0.8, depth=15)
    edits = {"treatments": {1: {"residues": [event], "controls": {"residue": "R"}}}}
    original = deepcopy((data, rows, edits))
    simulation = Simulation(filex_template=data, weather=rows[0], soil=rows[1], management=edits)
    assert simulation.check() == []
    assert "residues: OK" in capsys.readouterr().out
    simulation.run()
    text = next(Path(installed.calls[-1][1]).glob("*.MZX")).read_text()
    assert "*RESIDUES AND ORGANIC FERTILIZER\n" + HEADER in text
    assert " 1 21060 RE001  1500   0.8   -99   -99   -99    15   -99    -99" in text
    treatment = next(line for line in text.splitlines() if "My treatment" in line and " 1  1 " in line)
    assert treatment[55:58] == "  1"
    assert (data, rows, edits) == original


def test_experiment_template_documents_and_checks_residue_example(sim, tmp_path, capsys):
    pytest.importorskip("yaml")
    # Enough inline FileX columns for the template's other experiment sections.
    text = sim.filex.read_text(encoding="latin-1")
    text += ("@N OPTIONS     WATER NITRO\n 1 OP              Y     Y\n"
             "@N OUTPUTS     FROPT\n 1 OU              1\n")
    text = text.replace("*FIELDS", "*CULTIVARS\n@C CR INGENO CNAME\n 1 MZ IB0035 Example\n\n*FIELDS")
    sim.filex.write_text(text, encoding="latin-1")
    (sim.filex.parent / "MZCER048.CUL").write_text("@VAR#  NAME\nIB0035 Example\n")
    start = date(1982, 2, 24)
    sim.weather = [dict(sim.weather[0], date=(start + timedelta(days=i)).isoformat()) for i in range(40)]
    path = tmp_path / "experiment.yaml"
    write_experiment_template(path, filex=sim.filex)
    sim.management = path
    assert sim.check(verbose=False) == []
    template = path.read_text(encoding="utf-8")
    assert "residues" in template and all(column in template for _, column, _, _ in FIELDS)
    assert "RENAME" in template and "same date" in template and "-99" in template
    template = template.replace("    # residues:", "    residues:").replace(
        '    #   - {date: "1982-02-25", material: "RE001", amount: 1500}',
        '      - {date: "1982-02-25", material: "RE001", amount: 1500}')
    path.write_text(template, encoding="utf-8")
    assert sim.check() == []
    assert "residues: OK\n" in capsys.readouterr().out


def test_sweep_replaces_whole_residue_sections_in_each_copy(sim, seen, fake_dssat):
    summary = Path(__file__).parent / "fixtures/output_files/summary/two_treatments/Summary.OUT"
    fake_dssat.outputs["Summary.OUT"] = summary.read_bytes()
    base = {"treatments": {2: {"residues": [dict(EVENT, n=1, depth=15)]}}}
    factors = {"residues": {"none": [], "reported": [dict(EVENT, amount=500)]}}
    original, source = deepcopy((base, factors)), sim.filex.read_bytes()
    result = run_sweep(sim.filex, sim.weather, treatments=[2], management=base, factors=factors)
    assert len(seen) == 3  # Unchanged base, then one FileX copy per value.
    assert b" 8 82056 RE001  1500     1   -99   -99   -99    15" in seen[0]
    row = next(line for line in seen[1].splitlines() if b"none" in line)
    assert row[55:58] == b"  0"
    assert b" 8 82056 RE001" not in seen[1]
    assert b" 8 82056 RE001   500   -99   -99   -99   -99   -99   -99    -99" in seen[2]
    assert {row["scenario"] for row in result} == {"base", "none", "reported"}
    assert {row["residues"] for row in result} == {None, "none", "reported"}
    assert len({row["run_dir"] for row in result}) == 3
    assert (base, factors) == original and sim.filex.read_bytes() == source
