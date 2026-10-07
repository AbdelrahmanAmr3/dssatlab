"""Execute course notebooks against real DSSAT, saving their outputs in place."""
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient


def execute(lesson):
    """Run one lesson in a fresh kernel; report a zero-based failing cell index."""
    path = lesson / "lesson.ipynb"
    notebook = None
    index = "unavailable"
    ok = False

    def track_cell(cell, cell_index, **kwargs):
        nonlocal index
        index = cell_index

    try:
        notebook = nbformat.read(path, as_version=4)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                cell.execution_count = None
                cell.outputs = []
        client = NotebookClient(notebook, timeout=1800, kernel_name="python3",
                                resources={"metadata": {"path": str(lesson)}},
                                on_cell_start=track_cell)
        client.execute()
        ok = True
        message = f"{lesson.name}: ok"
    except Exception as error:
        if notebook is not None and isinstance(index, int):
            cell = notebook.cells[index]
            errors = [out for out in cell.get("outputs", []) if out.output_type == "error"]
            if errors:
                error = f"{errors[0].ename}: {errors[0].evalue}"
        detail = " ".join(str(error).split())
        message = f"{lesson.name}: failed (cell {index}): {detail}"
    if notebook is not None:
        try:
            nbformat.write(notebook, path)
        except Exception as error:
            ok = False
            message = f"{lesson.name}: failed (save): {' '.join(str(error).split())}"
    print(message)
    return ok


def main(names):
    course = Path(__file__).resolve().parent
    if any(Path(name).name != name or name in (".", "..") for name in names):
        print("Use lesson folder names, such as 01_first_simulation.")
        return 1
    lessons = [course / name for name in names] if names else sorted(
        path.parent for path in course.glob("*/lesson.ipynb"))
    results = [execute(lesson) for lesson in lessons]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
