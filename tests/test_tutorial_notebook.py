"""The tutorial notebook's editable cells must match the committed data files."""
import json
from pathlib import Path

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
