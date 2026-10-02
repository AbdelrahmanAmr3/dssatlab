"""DSSAT treatment columns through public readers and templates."""
import re

import pytest
import dssatlab as lab
from dssatlab.filex import read_treatment_numbers
from test_simulation_run import fake_dssat, SAMPLE  # noqa: F401
from test_season_coverage import weather


@pytest.mark.parametrize("prefixes, expected", [
    ([f"  {n}1 0 0" for n in range(1, 7)], list(range(1, 7))),
    ([f" 1{r:2} 1 0" for r in range(1, 11)], [1] * 10),
    ([" 1 1 1 0", " 110 1 0"], [1, 1]),
    ([" 1 1 1 0", " 110 1 0", " 2 1 0 0"], [1, 1, 2]),
    ([" 1 1 0 0", "10 1 0 0"], [1, 10]),
    ([" 991 0 0", "1001 0 0", "1011 0 0", "1101 0 0"], [99, 100, 101, 110]),
    (["100 1 0 0", "101 1 0 0"], [100, 101]),
])
def test_numbers_and_templates(tmp_path, prefixes, expected):
    filex = tmp_path / "TEST0001.MZX"
    filex.write_text("*TREATMENTS\n@N R O C TNAME\n" + "\n".join(prefixes) + "\n")
    assert read_treatment_numbers(filex) == expected
    unique = list(dict.fromkeys(expected))
    for writer in (lab.write_experiment_template, lab.write_management_template):
        path = tmp_path / (writer.__name__ + ".yaml")
        writer(path, filex)
        assert re.findall(r"^  (\d+):$", path.read_text(), re.M) == list(map(str, unique))
    path = tmp_path / "scenarios.yaml"
    lab.write_scenario_template(path, filex)
    assert str(unique) in path.read_text()


@pytest.mark.parametrize("prefix", ["   1 0 0", " xx1 0 0"])
def test_unreadable_number_names_row_and_columns(tmp_path, prefix):
    filex = tmp_path / "BAD.MZX"
    prefix += " 1 1"
    filex.write_text("*TREATMENTS\n@N R O C FL SM\n" + prefix + "\n")
    with pytest.raises(ValueError) as error:
        read_treatment_numbers(filex)
    message = str(error.value)
    assert str(filex) in message and repr(prefix) in message
    assert "columns 1-3 (1-2 in a sequence FileX)" in message
    assert message.endswith("Correct the FileX row.")
    problems = lab.Simulation(filex, 1, weather("1982-02-25", "1982-02-26")).check()
    assert message in problems


def inline_filex(tmp_path, prefixes):
    lines = SAMPLE.splitlines()
    row = lines[2]
    lines[2:3] = [prefix + row[8:] for prefix in prefixes]
    path = tmp_path / "TEST0001.MZX"
    path.write_text("\n".join(lines) + "\n")
    return path


def test_check_selection_and_experiment_repoint(tmp_path, fake_dssat):
    filex = inline_filex(tmp_path, [f"  {n}1 0 0" for n in range(1, 7)])
    lines = filex.read_text().splitlines()
    ends = {m.group(): m.end() for m in re.finditer(r"\S+", lines[1])}
    for column in ("FL", "SM"):
        end = ends[column]
        lines[3] = lines[3][:end-3] + "  2" + lines[3][end:]
    field = next(i for i, row in enumerate(lines) if row.startswith(" 1 UFGA"))
    lines.insert(field + 1, " 2" + lines[field][2:])
    controls = next(row for row in lines if row.startswith(" 1 GE"))
    lines.append(" 2" + controls[2:].replace("82056", "82057"))
    filex.write_text("\n".join(lines) + "\n")
    # Only treatment 2 starts on the weather's first day, via field/controls level 2.
    days = weather("1982-02-26", "1982-02-26")
    sim = lab.Simulation(filex, 2, days, executable=fake_dssat.executable,
                         management={"treatments": {2: {"irrigation": []}}})
    assert sim.check() == []
    result = sim.run()
    rows = (result.run_dir.parent / filex.name).read_text().splitlines()[2:8]
    end = next(m.end() for m in re.finditer(r"\S+", SAMPLE.splitlines()[1]) if m.group() == "MI")
    assert [int(row[end-3:end]) for row in rows] == [1, 0, 1, 1, 1, 1]
    results = lab.run_treatments(filex, weather("1982-02-25", "1982-02-26"),
                                 executable=fake_dssat.executable)
    assert list(results) == [("base", n) for n in range(1, 7)]


@pytest.mark.parametrize("components, extra", [(list(range(1, 11)), False),
                                                 ([1, 10], False), ([1, 10], True)])
def test_sequence_batch_uses_fixed_component_numbers(tmp_path, fake_dssat, components, extra):
    prefixes = [f" 1{r:2} 0 0" for r in components]
    if extra:
        prefixes.append(" 2 1 0 0")
    filex = inline_filex(tmp_path, prefixes)
    days = weather("1982-02-25", "1983-02-24")
    sim = lab.Simulation(filex, 1, days, executable=fake_dssat.executable,
                         management={"treatments": {1: {"rotation": {10: {"irrigation": []}}}}})
    assert sim.check() == []
    result = sim.run()
    batch = (result.run_dir.parent / "DSSBatch.v48").read_text().splitlines()[3:]
    assert [int(row[106:113]) for row in batch] == components
    assert fake_dssat.calls[0][0][1] == "Q"
    copied = (result.run_dir.parent / filex.name).read_text().splitlines()[2:2+len(prefixes)]
    end = next(m.end() for m in re.finditer(r"\S+", SAMPLE.splitlines()[1]) if m.group() == "MI")
    assert [int(row[end-3:end]) for row in copied] == [0 if r == 10 else 1 for r in components] + ([1] if extra else [])
    if extra:
        assert lab.Simulation(filex, 2, days).check() == []
