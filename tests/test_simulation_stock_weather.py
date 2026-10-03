"""Stock weather uses the usual checks and reaches DSSAT without rewriting."""

from datetime import date
from pathlib import Path

import pytest

import dssatlab as lab
from dssatlab.filex import _read_filex
from dssatlab.sequence import _rotation_components
from dssatlab.stock import _simulation_weather
from test_filex_template import data, rows
from test_scenarios import batch_inputs
from test_sequence import sequence
from test_simulation_run import fake_dssat, inputs, snapshot
from test_simulation_run import SAMPLE
from test_simulation_template import installed
from test_stock_weather import weather_file
from test_season_coverage import weather
from test_harvest_required import simulation as harvest_simulation


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


@pytest.mark.parametrize("overrides", [False, True])
@pytest.mark.parametrize("missing", [False, True])
def test_invalid_calendar_sdate_is_reported_without_raising(inputs, tmp_path, overrides, missing):
    inputs.filex.write_text(inputs.filex.read_text().replace("82056", "82367"))
    path = tmp_path / "UFGA8201.WTH" if missing else stock_file(tmp_path)
    management = {"treatments": {2: {"fertilizer": []}}} if overrides else None
    problems = lab.Simulation(inputs.filex, 2, path, management=management).check(False)
    assert any("SDATE '82367' is invalid" in problem for problem in problems)


@pytest.mark.parametrize("years,last", [(1, "1982-12-31"), (2, "1983-12-31")])
def test_stock_weather_covers_inherited_fixed_harvest(tmp_path, years, last):
    sim = harvest_simulation(tmp_path, level=1, harvest="82365")
    sim.filex.write_text(sim.filex.read_text().replace("GE              1", f"GE          {years:5d}"))
    end = "1982-02-25" if years == 1 else "1983-02-25"
    days = [row["date"] for row in weather("1982-02-25", end)]
    sim.weather = stock_file(tmp_path, "UFGA.WTH", days=days)
    assert sim.check(False) == [
        f"FileX NYERS {years}: the fixed harvest is on {last}, "
        f"after the weather data ends ({end}). Supply weather through {last}, or fewer years."]


@pytest.mark.parametrize("fixed_harvest", [False, True])
def test_single_season_accepts_next_year_stock_filename(tmp_path, fixed_harvest):
    sim = harvest_simulation(tmp_path, code="R" if fixed_harvest else "M",
                             level=1, harvest="83002")
    sim.filex.write_text(sim.filex.read_text().replace("82056", "82364"))
    first = stock_file(tmp_path, "UFGA8201.WTH", days=[date(1982, 12, 30), date(1982, 12, 31)])
    second = stock_file(tmp_path, "UFGA8301.WTH", days=[date(1983, 1, 1), date(1983, 1, 2)])
    sim.weather = [first, second]
    assert sim.check(False) == []


def test_stock_weather_preserves_eight_character_wsta_with_overrides(inputs, fake_dssat, tmp_path):
    inputs.filex.write_text(inputs.filex.read_text().replace("UFGA       -99", "UFGA8209   -99"))
    path = stock_file(tmp_path, "UFGA8209.WTH")
    sim = lab.Simulation(inputs.filex, 2, path, management={"treatments": {2: {"fertilizer": []}}})
    assert sim.check(False) == []
    result = sim.run()
    copied = result.run_dir.parent / inputs.filex.name
    assert _read_filex(copied, 2)[0]["WSTA"] == "UFGA8209"
    assert_copied(result, [path])


@pytest.mark.parametrize("par", ["missing", "blank", "mixed_files"])
def test_stock_par_is_ignored_by_checks_and_copied(inputs, fake_dssat, tmp_path, par):
    first = stock_file(tmp_path, days=[date(1982, 2, 24), date(1982, 2, 25)])
    before = first.read_bytes()
    if par == "mixed_files":
        second = weather_file(tmp_path, "UFGA.WTH", ("82057",), par=False)
        paths = [first, second]
    else:
        first.write_bytes(before.replace(b"  50.0N", b"  -99.0" if par == "missing" else b"       "))
        paths = [first]
    sim = lab.Simulation(inputs.filex, 2, paths)
    assert sim.check(False) == []
    assert_copied(sim.run(), paths)


@pytest.mark.parametrize("column", ["srad", "tmax", "tmin", "rain"])
@pytest.mark.parametrize("missing", [-99, "", None])
@pytest.mark.parametrize("stock", [False, True])
def test_required_weather_missing_value_reports_date(inputs, tmp_path, column, missing, stock):
    if stock:
        source = stock_file(tmp_path)
        spans = {"srad": b"  20.0N", "tmax": b"   25.0", "tmin": b"   15.0", "rain": b"    0.0"}
        source.write_bytes(source.read_bytes().replace(spans[column],
            b"       " if missing in ("", None) else b"  -99.0", 1))
    else:
        source = [dict(row) for row in inputs.rows]
        source[0][column] = missing
    problems = lab.Simulation(inputs.filex, 2, source).check(False)
    message = next(problem for problem in problems if f"column {column!r}" in problem)
    assert "1982-02-24" in message


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
        expected = ("Weather data row 2, column 'srad' (1982-02-24): found -99.0; "
                    "allowed range is 0 to 45 MJ/m2 per day. Correct the value using DSSAT's units.")
    else:
        expected = ("FileX WSTA 'UFGA' expects station 'UFGA', but stock weather file xyzz8201.wth has "
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
    sim = lab.Simulation(filex_template=data, weather=source, soil=rows[1],
                         executable=installed.executable)
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


@pytest.mark.parametrize('wsta,name', [
    ('UFGA', 'UFGA.WTH'),
    ('UFGA', 'UFGA8301.WTH'),
    ('UFGA8209', 'UFGA.WTH'),
])
def test_supplied_weather_names_are_copied(inputs, fake_dssat, tmp_path, wsta, name):
    inputs.filex.write_text(inputs.filex.read_text().replace('UFGA       -99', f'{wsta:8s}   -99'))
    path = stock_file(tmp_path, name)
    sim = lab.Simulation(inputs.filex, 2, path, executable=fake_dssat.executable.parent)
    assert sim.check(False) == []
    assert_copied(sim.run(), [path])


def test_stock_century_boundary_covers_simulation_start(inputs, tmp_path):
    inputs.filex.write_text(inputs.filex.read_text().replace('82056', '00001'))
    path = weather_file(tmp_path, 'UFGA.WTH', ('99365', '00001', '00002'))
    assert lab.Simulation(inputs.filex, 2, path).check(False) == []


@pytest.mark.parametrize('start,override', [
    ('P', False), ('P', True), ('S', False),
])
def test_stock_weather_uses_effective_start_date(tmp_path, start, override):
    sim = harvest_simulation(tmp_path, level=1, harvest='84057')
    text = sim.filex.read_text().replace('UFGA       -99', 'UFGA8401   -99')
    text = text.replace('     S 82056', f'     {start} {"84056" if start == "S" else "82056"}')
    text = text.replace('  1  1  0  0  0  0  0  0  0  0  0  1  1',
                        '  1  1  0  0  1  0  0  0  0  0  0  1  1')
    text += ('\n*PLANTING DETAILS\n'
             '@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE'
             '  PENV  PLPH  SPRL\n'
             f' 1 {"82056" if override else "84056"}   -99    10    10     S     R'
             '    75     0     5   -99   -99   -99   -99   -99\n')
    sim.filex.write_text(text, encoding='ascii')
    if override:
        sim.management = {'treatments': {'07': {'planting': {
            'date': '1984-02-25', 'method': 'S', 'distribution': 'R',
            'population': 10, 'depth': 5, 'row_spacing': 75}}}}
    sim.weather = stock_file(tmp_path, 'UFGA8401.WTH',
                             days=[date(1984, 2, 25), date(1984, 2, 26)])
    assert sim.check(False) == []
    if start == 'P' and not override:
        # This override changes SDATE only; IPEXP still uses planting/emergence.
        values, problems = _read_filex(sim.filex, sim.treatment)
        assert problems == []
        rows, problems = _simulation_weather(sim, values, {'treatments': {
            7: {'controls': {'start_date': '1982-02-25'}}}},
            _rotation_components(sim.filex, sim.treatment))
        assert problems == []
        assert [row['date'] for row in rows] == [date(1984, 2, 25), date(1984, 2, 26)]


@pytest.mark.parametrize('start', ['E', 'P'])
@pytest.mark.parametrize('override', [False, True])
def test_stock_weather_unknown_start_is_one_problem(tmp_path, start, override):
    filex = tmp_path / 'UFGA8201.MZX'
    filex.write_text(SAMPLE.replace('     S 82056', f'     {start} 82056'), encoding='ascii')
    management = {'treatments': {2: {'fertilizer': []}}} if override else None
    sim = lab.Simulation(filex, 2, 'missing.WTH', management=management)
    problems = sim.check(False)
    assert len(problems) == 1
    assert all(part in problems[0] for part in (
        'Stock weather missing.WTH', 'simulation start is unknown',
        'START and SDATE/PDATE/EDATE', 'treatment 2', 'Supply a valid simulation start date', 'weather as rows'))
    with pytest.raises(lab.DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems


def test_stock_weather_missing_station_needs_a_reported_filex_problem(inputs):
    sim = lab.Simulation(inputs.filex, 2, 'missing.WTH')
    values, problems = _read_filex(sim.filex, sim.treatment)
    assert problems == []
    del values['WSTA']
    rows, problems = _simulation_weather(sim, values, {}, [])
    assert rows == [] and len(problems) == 1
    assert 'WSTA' in problems[0] and 'Supply' in problems[0]
    inputs.filex.write_text(inputs.filex.read_text().replace('WSTA....', 'STATION.'))
    _, filex_problems = _read_filex(sim.filex, sim.treatment)
    assert filex_problems
    assert sim.check(False) == filex_problems


def test_identity_check_skips_station_edit_without_weather_rows(inputs, monkeypatch):
    monkeypatch.setattr(lab.simulation, '_simulation_weather', lambda *args: ([], []))
    sim = lab.Simulation(inputs.filex, 2, 'missing.WTH',
                         management={'treatments': {2: {'fertilizer': []}}})
    assert sim.check(False) == []
