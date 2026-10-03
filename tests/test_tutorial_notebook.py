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
    for cell in cells[start:]:
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
