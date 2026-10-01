"""Named template treatments share base levels and preserve the original FileX."""

from copy import deepcopy

import pytest

from dssatlab import Simulation, write_filex_template
from dssatlab.filex import _section_row, read_treatment_numbers
from dssatlab.filex_skeleton import _render_filex, write_filex
from dssatlab.filex_template import _check_filex_template, _load_filex_template
from test_filex_template import data, data_dir, rows
from test_simulation_run import fake_dssat
from test_simulation_template import installed


@pytest.mark.parametrize("names", [
    {}, {"treatment_name": "Control", "treatments": ["Variant"]},
    {"treatment_name": None, "treatments": []},
    {"treatment_name": "", "treatments": ["", None]},
])
def test_exactly_one_name_key(data, data_dir, names):
    del data["treatment_name"]
    data.update(names)
    assert _check_filex_template(data, data_dir) == [
        "Supply exactly one of treatment_name or treatments."]


@pytest.mark.parametrize("names", [None, "Control", ("Control",), {}, 1, [], ["T"] * 100])
def test_treatments_requires_list_of_one_to_99_names(data, data_dir, names):
    del data["treatment_name"]
    data["treatments"] = names
    problems = _check_filex_template(data, data_dir)
    assert len(problems) == 1
    assert "treatments" in problems[0]
    assert "Supply a list of 1 to 99 treatment names." in problems[0]


@pytest.mark.parametrize("bad", ["", " " * 25, "x" * 26, "a\nb", "caf\u00e9",
                                     "\x1f", "\x7f", None, True, 12, []])
def test_bad_name_reports_one_based_position(data, data_dir, bad):
    del data["treatment_name"]
    data["treatments"] = ["Control", bad, "Variant"]
    problems = _check_filex_template(data, data_dir)
    assert len(problems) == 1
    assert "treatments[2]" in problems[0]
    assert "Supply 1-25 printable ASCII characters, not just spaces." in problems[0]


def test_all_bad_names_and_independent_problems_are_reported(data, data_dir):
    del data["treatment_name"]
    data["treatments"] = ["Control", "", None, "   ", "Good"]
    data["planting"]["depth"] = -1
    problems = _check_filex_template(data, data_dir)
    assert len(problems) == 4
    for position in (2, 3, 4):
        assert any(f"treatments[{position}]" in p for p in problems)
    assert any("depth" in p for p in problems)


@pytest.mark.parametrize("names", [["A"], ["~" * 25], [" padded "], ["Same", "Same"],
                                 ["T"] * 99])
def test_valid_names_and_duplicates_are_accepted_without_mutation(data, data_dir, names):
    del data["treatment_name"]
    data["treatments"] = names
    before = deepcopy(data)
    assert _check_filex_template(data, data_dir) == []
    assert data == before


@pytest.mark.parametrize("crop,code", [("maize", "IB0035"), ("wheat", "IB0488")])
@pytest.mark.parametrize("harvest", [False, True])
@pytest.mark.parametrize("count", [1, 3, 10, 99])
def test_rendered_treatments_share_base_levels(
        data, data_dir, rows, tmp_path, crop, code, harvest, count):
    del data["treatment_name"]
    names = [f"Treatment {i}" for i in range(1, count + 1)]
    data.update(crop=crop, cultivar={"code": code}, treatments=names)
    if harvest:
        data["harvest_date"] = "2021-08-01"
    path = write_filex(data, *rows, tmp_path, data_dir=data_dir)
    text = path.read_text(encoding="ascii")
    assert read_treatment_numbers(path) == list(range(1, count + 1))
    treatment_lines = text.split("@N R O C TNAME", 1)[1].splitlines()[1:count + 1]
    factors = dict(CU="1", FL="1", SA="0", IC="0", MP="1", MI="0", MF="0",
                   MR="0", MC="0", MT="0", ME="0", MH=str(int(harvest)), SM="1")
    for number, (name, line) in enumerate(zip(names, treatment_lines), 1):
        assert line[:9] == f"{number:2d} 1 0 0 "
        assert line[9:34] == f"{name:<25}"
        assert line[34:].split() == list(factors.values())
        row = _section_row(text, "TREATMENTS", "N", number, tuple(factors))
        assert row["TNAME"] == name
        assert {key: row[key] for key in factors} == factors
    assert text.splitlines()[0] == f"*EXP.DETAILS: TEST2101{path.suffix[1:3]} {names[0]}"
    general = next(line for line in text.splitlines() if line.startswith(" 1 GE"))
    assert general[45:70] == f"{names[0]:<25}"


@pytest.mark.parametrize("harvest", [False, True])
def test_one_element_list_is_byte_identical(data, rows, harvest):
    if harvest:
        data["harvest_date"] = "2021-08-01"
    original = _render_filex(data, *rows)
    data["treatments"] = [data.pop("treatment_name")]
    assert _render_filex(data, *rows) == original


@pytest.mark.parametrize("alternative", [False, True])
def test_written_template_documents_loadable_alternative(tmp_path, data_dir, alternative):
    pytest.importorskip("yaml")
    path = tmp_path / "filex.yaml"
    write_filex_template(path)
    text = path.read_text()
    assert '# treatments: [' in text
    if alternative:
        text = "\n".join("# " + line if line.startswith("treatment_name:") else
                         line[2:] if line.startswith("# treatments:") else line
                         for line in text.splitlines())
        path.write_text(text)
    loaded, problems = _load_filex_template(path)
    assert problems == []
    assert _check_filex_template(loaded, data_dir) == []


def test_template_simulation_still_runs_treatment_one(data, rows, installed):
    data["treatments"] = [data.pop("treatment_name"), "Second", "Third"]
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1], treatment=1)
    assert sim.check(verbose=False) == []
    result = sim.run()
    filex = result.run_dir.parent / "TEST2101.MZX"
    assert read_treatment_numbers(filex) == [1, 2, 3]
    assert installed.calls[0][0] == [str(installed.executable), "C", filex.name, "1"]
