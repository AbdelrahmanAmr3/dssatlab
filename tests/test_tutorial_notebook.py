"""The tutorial notebook's editable cells must match the committed data files."""
import ast
from datetime import date, timedelta
import json
from pathlib import Path

from dssatlab import Simulation
from test_experiment_template import sim_inputs
from test_management_file import sim_inputs as management_inputs

NOTEBOOK = Path(__file__).resolve().parent.parent / "notebook" / "dssatlab_tutorial.ipynb"
DATA = NOTEBOOK.parent / "tutorial_data"


def _writefile_cells():
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    for cell in cells:
        source = "".join(cell["source"])
        if cell["cell_type"] == "code" and source.startswith("%%writefile "):
            header, _, body = source.partition("\n")
            yield Path(header.split()[1]).name, body


def test_editable_cells_match_data_files():
    cells = dict(_writefile_cells())
    for name in ("my_soil.csv", "my_experiment.yaml", "my_observed.csv"):
        expected = (DATA / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert cells[name].rstrip("\n") == expected.rstrip("\n")


def test_weather_file_is_committed():
    assert (DATA / "my_weather.csv").is_file()


def test_case17_is_an_unexecuted_stock_sequence_run():
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    start = next(i for i, cell in enumerate(cells)
                 if "".join(cell["source"]).startswith("## Case 17:"))
    calls = []
    end = next(i for i, cell in enumerate(cells[start + 1:], start + 1)
               if "".join(cell["source"]).startswith("## Case 18:"))
    for cell in cells[start:end]:
        if cell["cell_type"] != "code":
            continue
        assert cell["execution_count"] is None and cell["outputs"] == []
        tree = ast.parse("".join(cell["source"]))
        calls.extend(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == "run")
    assert len(calls) == 1
    call = calls[0]
    assert isinstance(call.func.value, ast.Name) and call.func.value.id == "dl"
    assert ast.literal_eval(call.args[0]) == "case17_sequence/MSKB8902.SQX"
    assert call.keywords == []  # run() selects sequence mode from the FileX.


def test_case18_is_an_unexecuted_stock_weather_simulation(tmp_path, sim_inputs):
    from test_simulation_stock_weather import stock_file

    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    start = next(i for i, cell in enumerate(cells)
                 if "".join(cell["source"]).startswith("## Case 18:"))
    end = next(i for i, cell in enumerate(cells[start + 1:], start + 1)
               if "".join(cell["source"]).startswith("## Case 19:"))
    calls = []
    for cell in cells[start:end]:
        if cell["cell_type"] != "code":
            continue
        assert cell["execution_count"] is None and cell["outputs"] == []
        calls.extend(node for node in ast.walk(ast.parse("".join(cell["source"])))
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute))
    call, = [node for node in calls if node.func.attr == "Simulation"]
    assert call.func.value.id == "dl" and call.args == []
    kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}
    assert kwargs == {"filex": "case1_gainesville/UFGA8201.MZX", "treatment": 1,
                      "weather": "case1_gainesville/UFGA8201.WTH"}
    assert any(node.func.attr == "check" and node.func.value.id == "sim18" for node in calls)
    assert any(node.func.attr == "run" and node.func.value.id == "sim18" for node in calls)
    # Use a small stock fixture to check the documented input shape, without DSSAT.
    filex, _ = sim_inputs
    assert Simulation(filex=filex, treatment=kwargs["treatment"],
                      weather=stock_file(tmp_path)).check(False) == []


def test_case19_environment_and_soil_analysis_pass_checks(sim_inputs):
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    start = next(i for i, cell in enumerate(cells)
                 if "".join(cell["source"]).startswith("## Case 19:"))
    calls, values = [], {}
    for cell in cells[start:]:
        if cell["cell_type"] != "code":
            continue
        assert cell["execution_count"] is None and cell["outputs"] == []
        tree = ast.parse("".join(cell["source"]))
        for node in tree.body:
            if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "experiment19"):
                values["experiment19"] = ast.literal_eval(node.value)
        calls.extend(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute))
    call, = [node for node in calls if node.func.attr == "Simulation"]
    assert call.func.value.id == "dl" and call.args == []
    kwargs = {kw.arg: kw.value for kw in call.keywords}
    assert ast.literal_eval(kwargs["filex"]) == "case1_gainesville/UFGA8201.MZX"
    assert ast.literal_eval(kwargs["treatment"]) == 1
    assert kwargs["weather"].id == "weather12"
    assert kwargs["management"].id == "experiment19"
    assert any(node.func.attr == "check" and node.func.value.id == "sim19" for node in calls)
    assert any(node.func.attr == "run" and node.func.value.id == "sim19" for node in calls)
    entry = values["experiment19"]["treatments"][1]
    assert entry["environment"][0]["srad"] == {"multiply": 0.5}
    assert entry["soil_analysis"]["layers"][0]["extractable_p"] == 12
    filex, weather = sim_inputs
    assert Simulation(filex, weather=weather,
                      management=values["experiment19"]).check(False) == []


def test_case16_residue_passes_checks(sim_inputs):
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    values = {}
    for cell in cells:
        source = "".join(cell["source"])
        if cell["cell_type"] != "code" or not source.startswith("experiment16 ="):
            continue
        # Read literal data only; never execute notebook cells or run DSSAT.
        assignment = ast.parse(source).body[0]
        values[assignment.targets[0].id] = ast.literal_eval(assignment.value)
        assert cell["execution_count"] is None and cell["outputs"] == []
    filex, weather = sim_inputs
    weather = [dict(weather[0], date=(date(1982, 2, 25) + timedelta(days=i)).isoformat())
               for i in range(140)]
    assert Simulation(
        filex, weather=weather, management=values["experiment16"],
    ).check(False) == []
