"""Static course checks: read JSON and Markdown, never execute a lesson or DSSAT."""
import ast
import json
from pathlib import Path
import re


SETUP_CELL = '''# Connect to DSSAT and prepare a fresh copy of the lesson's data.
import os, shutil, subprocess, sys
from pathlib import Path
if "google.colab" in sys.modules:
    subprocess.run([sys.executable, "-m", "pip", "install", "dssatlab[course]>=0.23,<0.24"], check=True, capture_output=True)
    if Path.cwd().name != LESSON:
        if not Path("dssatlab").exists():
            subprocess.run(["git", "clone", "--depth", "1", "https://github.com/AbdelrahmanAmr3/dssatlab"], check=True)
        os.chdir(Path("dssatlab") / "course" / LESSON)
import dssatlab as dl
if "google.colab" in sys.modules:
    dl.install()
dssat = dl.connect()
HERE = Path.cwd()
RUNS = HERE / "runs"
if RUNS.exists():
    shutil.rmtree(RUNS)
_ = shutil.copytree(HERE / "data", RUNS)'''


def source(cell):
    return "".join(cell.get("source", []))


def text_values(value):
    """Read textual output fields, skipping embedded images and their base64 data."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from text_values(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not key.startswith("image/"):
                yield from text_values(item)


def check_paths(text):
    # Web links and HTML tags are not filesystem paths.
    text = re.sub(r"https?://[^\s\"'<>]+|<[^>]*>", "", text)
    pattern = r"\b[A-Za-z]:[\\/]|~[\\/]|\\\\[\w.-]+[\\/]|(?<![\w./])/[\w~.-]+"
    assert not re.search(pattern, text), "absolute path or user home in code/output"


def check_inventory(folder):
    inventory = folder / "data" / "SOURCE.md"
    assert inventory.is_file(), "missing data/SOURCE.md"
    names = []
    for line in inventory.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        first = line.strip().split("|")[1].strip().strip("`")
        if first.lower() == "file" or re.fullmatch(r"[: -]+", first):
            continue
        names.append(first)
    files = {path.relative_to(inventory.parent).as_posix()
             for path in inventory.parent.rglob("*")
             if path.is_file() and path != inventory}
    assert len(names) == len(set(names)) and set(names) == files, "SOURCE.md inventory mismatch"


def check_lesson(folder):
    cells = json.loads((folder / "lesson.ipynb").read_text(encoding="utf-8"))["cells"]
    setup_lesson = folder.name == "00_setup"
    if not setup_lesson:
        check_inventory(folder)
    for cell in cells:
        if cell["cell_type"] != "code":
            continue
        assert isinstance(cell.get("execution_count"), int), "missing execution count"
        assert not any(out.get("output_type") == "error" for out in cell.get("outputs", [])), "error output"
        if not setup_lesson:
            check_paths(source(cell))
            for text in text_values(cell.get("outputs", [])):
                check_paths(text)
    assert len(cells) >= 3, "missing template section"
    title = source(cells[0]).splitlines()
    assert cells[0]["cell_type"] == "markdown" and re.fullmatch(
        rf"# {folder.name[:2]} · .+", title[0] if title else ""), "missing title/goal"
    assert any(line.strip() and not line.startswith("#") for line in title[1:]), "missing goal"
    sections = []
    for heading in ("You will learn", "Your turn", "Recap"):
        matches = [i for i, cell in enumerate(cells) if cell["cell_type"] == "markdown"
                   and re.search(rf"(?m)^#+ {heading}\s*$", source(cell))]
        assert len(matches) == 1, f"missing template section: {heading}"
        sections.append(matches[0])
    assert 0 < sections[0] < sections[1] < sections[2], "template sections out of order"
    assert sections[0] == 1, "You will learn must follow the goal"
    assert len(re.findall(r"(?m)^\s*[-*] ", source(cells[1]))) == 3, "You will learn needs 3 bullets"
    assert cells[2]["cell_type"] == "code", "missing LESSON cell"
    tree = ast.parse(source(cells[2]))
    assert len(tree.body) == 1 and len(source(cells[2]).splitlines()) == 1, "LESSON needs its own cell"
    node = tree.body[0]
    assert isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(
        node.targets[0], ast.Name) and node.targets[0].id == "LESSON" and isinstance(
        node.value, ast.Constant) and node.value.value == folder.name, "wrong LESSON"
    if not setup_lesson:
        assert cells[3]["cell_type"] == "code" and source(cells[3]) == SETUP_CELL, "differing setup cell"
        assert sections[1] > 3, "template sections out of order"


def check_course(course):
    readme = (course / "README.md").read_text(encoding="utf-8")
    for notebook in sorted(course.glob("*/lesson.ipynb")):
        assert notebook.parent.name in readme, f"README missing lesson: {notebook.parent.name}"
        try:
            check_lesson(notebook.parent)
        except AssertionError as error:
            raise AssertionError(f"{notebook.parent.name}: {error}") from error


def test_course():
    check_course(Path(__file__).resolve().parent.parent / "course")


def fake_lesson(course, name="01_probe"):
    folder = course / name
    (folder / "data").mkdir(parents=True)
    (folder / "data" / "input.csv").write_text("value\n1\n", encoding="utf-8")
    (folder / "data" / "SOURCE.md").write_text(
        "| file | origin | what it is |\n|---|---|---|\n| `input.csv` | written here | values |\n", encoding="utf-8")
    (course / "README.md").write_text(name, encoding="utf-8")
    cells = []
    for kind, text in [
        ("markdown", f"# {name[:2]} · Probe\n\nRead a value."),
        ("markdown", "## You will learn\n- Read\n- Run\n- Compare"),
        ("code", f'LESSON = "{name}"'), ("code", SETUP_CELL),
        ("markdown", "## Your turn\nTry another value. Hint: edit the number."),
        ("code", "# Choose a value.\nvalue = 2"),
        ("markdown", "## Recap\n- Read\n- Run\n- Compare\n[Next](../02_probe/lesson.ipynb)"),
    ]:
        cell = {"cell_type": kind, "source": text}
        if kind == "code":
            cell.update(execution_count=1, outputs=[])
        cells.append(cell)
    save_lesson(folder, cells)
    return folder, cells


def save_lesson(folder, cells):
    (folder / "lesson.ipynb").write_text(json.dumps({"cells": cells}), encoding="utf-8")


def expect_failure(folder, message):
    try:
        check_course(folder.parent)
    except AssertionError as error:
        assert message in str(error)
    else:
        raise AssertionError(f"Expected failure: {message}")


def test_empty_and_valid_course(tmp_path):
    (tmp_path / "README.md").write_text("Course", encoding="utf-8")
    check_course(tmp_path)
    fake_lesson(tmp_path)
    check_course(tmp_path)


def test_absolute_paths_in_source_and_outputs(tmp_path):
    folder, cells = fake_lesson(tmp_path)
    for path in (r"C:\DSSAT48", "D:/DSSAT48", "/tmp/results", "/home/student", "~/data", r"\\server\data"):
        for output in (False, True):
            cells[5]["source"] = f"# Read data.\nfile = {path!r}" if not output else "# Read data.\nvalue = 2"
            cells[5]["outputs"] = [{"output_type": "stream", "text": [path]}] if output else []
            save_lesson(folder, cells)
            expect_failure(folder, "absolute path")


def test_web_links_relative_paths_and_images_allowed(tmp_path):
    folder, cells = fake_lesson(tmp_path)
    cells[5]["source"] = '# Read data.\nfile = "runs/input.csv"\nurl = "https://example.com/data"\nnewline = "\\n"'
    cells[5]["outputs"] = [{"output_type": "display_data", "data": {
        "image/png": "/abc/123", "text/html": "<table><tr><td>1</td></tr></table>"}}]
    save_lesson(folder, cells)
    check_course(tmp_path)


def test_inventory_mismatch_both_ways_and_duplicates(tmp_path):
    folder, _ = fake_lesson(tmp_path)
    inventory = folder / "data" / "SOURCE.md"
    original = inventory.read_text(encoding="utf-8")
    for text in (original.replace("input.csv", "other.csv"), original.split("| `")[0],
                 original + "| extra.csv | written here | extra |\n",
                 original + "| input.csv | written here | duplicate |\n"):
        inventory.write_text(text, encoding="utf-8")
        expect_failure(folder, "inventory mismatch")
    inventory.unlink()
    expect_failure(folder, "missing data/SOURCE.md")


def test_error_output(tmp_path):
    folder, cells = fake_lesson(tmp_path)
    cells[5]["outputs"] = [{"output_type": "error", "ename": "ValueError", "evalue": "bad"}]
    save_lesson(folder, cells)
    expect_failure(folder, "error output")


def test_missing_execution_count(tmp_path):
    folder, cells = fake_lesson(tmp_path)
    for value in (None, "1"):
        cells[5]["execution_count"] = value
        save_lesson(folder, cells)
        expect_failure(folder, "missing execution count")
    del cells[5]["execution_count"]
    save_lesson(folder, cells)
    expect_failure(folder, "missing execution count")


def test_wrong_lesson_and_separate_cell(tmp_path):
    folder, cells = fake_lesson(tmp_path)
    for text, message in [('LESSON = "02_wrong"', "wrong LESSON"),
                          ('LESSON = "01_probe"\nvalue = 1', "own cell")]:
        cells[2]["source"] = text
        save_lesson(folder, cells)
        expect_failure(folder, message)


def test_setup_cell_identical(tmp_path):
    folder, cells = fake_lesson(tmp_path)
    cells[3]["source"] += "\n"
    save_lesson(folder, cells)
    expect_failure(folder, "differing setup cell")


def test_missing_and_out_of_order_sections(tmp_path):
    folder, original = fake_lesson(tmp_path)
    for index in (1, 4, 6):
        cells = json.loads(json.dumps(original))
        cells[index]["source"] = "Other text"
        save_lesson(folder, cells)
        expect_failure(folder, "missing template section")
    cells = original.copy()
    cells[4], cells[6] = cells[6], cells[4]
    save_lesson(folder, cells)
    expect_failure(folder, "out of order")


def test_missing_goal_and_three_learning_bullets(tmp_path):
    folder, cells = fake_lesson(tmp_path)
    cells[0]["source"] = "# 01 · Probe"
    save_lesson(folder, cells)
    expect_failure(folder, "missing goal")
    cells[0]["source"] += "\n\nRead a value."
    cells[1]["source"] = "## You will learn\n- Read\n- Run"
    save_lesson(folder, cells)
    expect_failure(folder, "3 bullets")


def test_readme_missing_lesson(tmp_path):
    folder, _ = fake_lesson(tmp_path)
    (tmp_path / "README.md").write_text("Course", encoding="utf-8")
    expect_failure(folder, "README missing lesson")


def test_lesson_zero_exemptions(tmp_path):
    folder, cells = fake_lesson(tmp_path, "00_setup")
    (folder / "data" / "SOURCE.md").unlink()
    cells[3]["source"] = '# Find DSSAT.\npath = "C:/DSSAT48"'
    save_lesson(folder, cells)
    check_course(tmp_path)
    cells[3]["execution_count"] = None
    save_lesson(folder, cells)
    expect_failure(folder, "missing execution count")
