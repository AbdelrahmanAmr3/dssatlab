"""Stock weather uses the usual checks and reaches DSSAT without rewriting."""

from datetime import date
from pathlib import Path

import pytest

import dssatlab as lab
from test_filex_template import data, rows
from test_scenarios import batch_inputs
from test_sequence import sequence
from test_simulation_run import fake_dssat, inputs, snapshot
from test_simulation_template import installed
from test_stock_weather import weather_file
from test_season_coverage import weather


def stock_file(folder, name="ufga8201.wth", days=None, *, wide=False):
    days = days or [date(1982, 2, 24), date(1982, 2, 25), date(1982, 2, 26)]
    codes = [f"{day.year if wide else day.year % 100:0{4 if wide else 2}d}"
             f"{day.timetuple().tm_yday:03d}" for day in days]
    path = weather_file(folder, name, codes, wide=wide)
    # Retain CRLF, a non-ASCII comment, PAR flags and an ignored extra column.
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                     + b"! caf\xe9\r\n")
    return path


def assert_copied(result, paths):
    folder = result.run_dir.parent
    assert sorted(p.name for p in folder.glob("*.WTH")) == sorted(p.name.upper() for p in paths)
    for path in paths:
        assert (folder / path.name.upper()).read_bytes() == path.read_bytes()


@pytest.mark.parametrize("ending", [b"\r\n\x1a", b"\x1a", b"\x1a\r\n"])
def test_stock_weather_accepts_final_dos_eof(inputs, fake_dssat, tmp_path, ending):
    path = weather_file(tmp_path, "UFGA8201.WTH", ("82055", "82056", "82057"))
    path.write_bytes(path.read_bytes().rstrip(b"\r\n") + ending)
    sim = lab.Simulation(inputs.filex, 2, path)
    assert sim.check(verbose=False) == []
    assert_copied(sim.run(), [path])


@pytest.mark.parametrize("marker", [b"\x1a\n", b"\x1a"])
def test_stock_weather_rejects_dos_eof_in_middle(inputs, tmp_path, marker):
    path = weather_file(tmp_path, "UFGA8201.WTH", ("82055", "82056", "82057"))
    path.write_bytes(path.read_bytes().replace(b"82056", marker + b"82056"))
    problems = lab.Simulation(inputs.filex, 2, path).check(verbose=False)
    assert any("invalid date" in problem and "\\x1a" in problem for problem in problems)


@pytest.mark.parametrize("problem", ["station", "gap", "duplicate", "srad"])
def test_stock_weather_has_one_usual_weather_problem(inputs, tmp_path, problem):
    source = stock_file(tmp_path, name="xyzz8201.wth" if problem == "station" else "ufga8201.wth")
    if problem == "gap":
        source = stock_file(tmp_path, days=[date(1982, 2, 25), date(1982, 2, 27)])
        expected = ("Weather data: missing date 1982-02-26. "
                    "Supply one row for each missing calendar day.")
    elif problem == "duplicate":
        first = stock_file(tmp_path, days=[date(1982, 2, 24), date(1982, 2, 25)])
        second = stock_file(tmp_path, "UFGA.WTH", days=[date(1982, 2, 25), date(1982, 2, 26)])
        source = [str(first), second]
        expected = ("Weather data duplicate date 1982-02-25 in rows 3 and 4. "
                    "Keep one row per day.")
    elif problem == "srad":
        source.write_bytes(source.read_bytes().replace(b"  20.0N", b"  -99.0", 1))
        expected = ("Weather data row 2, column 'srad': found -99.0; "
                    "allowed range is 0 to 45 MJ/m2 per day. Correct the value using DSSAT's units.")
    else:
        expected = ("FileX WSTA 'UFGA' expects station 'UFGA', but the weather template has "
                    "station 'XYZZ'. Make the station codes exactly equal; "
                    "filenames are case-sensitive on Linux.")
    before = snapshot(tmp_path)
    sim = lab.Simulation(inputs.filex, 2, source)
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(lab.DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("form", ["path", "str", "list"])
@pytest.mark.parametrize("wide", [False, True])
def test_stock_run_copies_only_supplied_weather(inputs, fake_dssat, tmp_path, form, wide):
    path = stock_file(tmp_path, wide=wide)
    source = {"path": path, "str": str(path), "list": [str(path)]}[form]
    before = snapshot(inputs.filex.parent)
    source_before = (path.read_bytes(), path.stat().st_mtime_ns)
    sim = lab.Simulation(inputs.filex, 2, source)
    assert sim.check(verbose=False) == []
    assert_copied(sim.run(), [path])
    assert snapshot(inputs.filex.parent) == before
    assert (path.read_bytes(), path.stat().st_mtime_ns) == source_before


@pytest.mark.parametrize("other", ["dict", "dataframe"])
@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_list_is_one_problem(inputs, tmp_path, other, reverse):
    row = inputs.rows[0]
    if other == "dataframe":
        row = pytest.importorskip("pandas").DataFrame(inputs.rows)
    source = [stock_file(tmp_path), row]
    if reverse:
        source.reverse()
    problems = lab.Simulation(inputs.filex, 2, source).check(verbose=False)
    assert len(problems) == 1
    assert "mix" in problems[0].lower() and "weather" in problems[0].lower()
    assert "Supply" in problems[0]


@pytest.mark.parametrize("form", ["path", "list", "field"])
def test_stock_weather_refused_for_template(data, rows, installed, tmp_path, form):
    path = stock_file(tmp_path)
    source = {"path": path, "list": [path], "field": {1: path}}[form]
    sim = lab.Simulation(filex_template=data, weather=source, soil=rows[1])
    expected = ("A stock weather file needs a copied FileX. "
                "Supply weather data rows for a FileX template.")
    assert sim.check(verbose=False) == [expected]
    with pytest.raises(lab.DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == [expected]
    assert installed.calls == []


def test_stock_weather_through_run_treatments(batch_inputs, fake_dssat, tmp_path):
    path = stock_file(tmp_path)
    results = lab.run_treatments(batch_inputs.filex, str(path))
    assert list(results) == [("base", 1), ("base", 3), ("base", 5)]
    for result in results.values():
        assert_copied(result, [path])


def test_stock_weather_as_named_scenario(batch_inputs, fake_dssat, tmp_path):
    path = stock_file(tmp_path)
    results = lab.run_treatments(batch_inputs.filex, batch_inputs.rows, treatments=[1],
                                 scenarios={"stock": {"weather": [path]}})
    assert list(results) == [("base", 1), ("stock", 1)]
    assert_copied(results["stock", 1], [path])


def test_stock_weather_through_sweep(batch_inputs, fake_dssat, tmp_path):
    path = stock_file(tmp_path)
    summary = Path(__file__).parent / "fixtures/output_files/summary/two_treatments/Summary.OUT"
    fake_dssat.outputs["Summary.OUT"] = summary.read_bytes()
    result = lab.run_sweep(batch_inputs.filex, path, treatments=[1],
                           factors={"fertilizer": {"zero": []}})
    assert {row["scenario"] for row in result} == {"base", "zero"}
    for folder in {row["run_dir"].parent for row in result}:
        assert list(folder.glob("*.WTH")) == [folder / path.name.upper()]
        assert (folder / path.name.upper()).read_bytes() == path.read_bytes()


def test_stock_yearly_files_through_seasonal_run(inputs, fake_dssat, tmp_path):
    inputs.filex.write_text(inputs.filex.read_text().replace("GE              1", "GE              2"))
    days = [row["date"] for row in weather("1982-02-24", "1983-02-26")]
    first = stock_file(tmp_path, days=[day for day in days if day.year == 1982])
    second = stock_file(tmp_path, "UFGA8301.WTH", days=[day for day in days if day.year == 1983])
    sim = lab.Simulation(inputs.filex, 2, [str(first), second])
    assert sim.check(verbose=False) == []
    assert_copied(sim.run(), [first, second])


def test_stock_weather_through_sequence_run(sequence, fake_dssat, tmp_path):
    path = stock_file(tmp_path, "ufga.wth", days=[row["date"] for row in sequence.weather])
    sequence.weather = path
    assert sequence.check(verbose=False) == []
    result = sequence.run()
    assert (result.run_dir / "DSSBatch.v48").is_file()
    assert_copied(result, [path])
