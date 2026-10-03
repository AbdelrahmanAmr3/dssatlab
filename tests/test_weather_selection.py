"""e2e22 sections 2-6: selected files, rather than their union, cover a run."""

from datetime import date, timedelta

import pytest

from dssatlab import core
from dssatlab.weather_files import _walk_weather_files, _weather_directory
from test_harvest_required import simulation
from test_simulation_stock_weather import stock_file


@pytest.fixture(autouse=True)
def no_installed_weather(monkeypatch):
    monkeypatch.setattr(core, "detect", lambda: {"dssat_path": None})


def days(first, last):
    first, last = date.fromisoformat(first), date.fromisoformat(last)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def period(tmp_path, start="82364", harvest="83002", station="UFGA"):
    sim = simulation(tmp_path, level=1, harvest=harvest)
    text = sim.filex.read_text().replace("82056", start)
    sim.filex.write_text(text.replace("UFGA       -99", f"{station:8s}   -99"))
    return sim


def assert_file_problem(sim, name):
    problems = sim.check(False)
    assert any(name in p and "Checked" in p and "Supply" in p for p in problems), problems


def test_223_yearly_rollover_never_uses_fallback(tmp_path):
    sim = period(tmp_path)
    sim.weather = [stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-12-30", "1982-12-31")),
                   stock_file(tmp_path, "UFGA.WTH", days=days("1983-01-01", "1983-01-02"))]
    assert_file_problem(sim, "UFGA8301.WTH")


def test_224_next_year_only_does_not_meet_first_lookup(tmp_path):
    sim = period(tmp_path, "82056", "83002")
    sim.weather = stock_file(tmp_path, "UFGA8301.WTH", days=days("1982-02-25", "1983-01-02"))
    assert_file_problem(sim, "UFGA8201.WTH")


@pytest.mark.parametrize("start,year,code", [("S", 1982, "82056"),
                                           ("P", 1983, "83057"),
                                           ("E", 1984, "84060")])
@pytest.mark.parametrize("missing", [None, "initial", "effective"])
def test_initial_lookup_then_effective_start_year(tmp_path, start, year, code, missing):
    # e2e22 initial_S/P/E: every candidate contains all three years.
    sim = period(tmp_path, "82056", "83058" if start == "S"
                 else f"{year % 100:02d}{int(code[-3:]) + 1:03d}")
    text = sim.filex.read_text().replace("     S 82056", f"     {start} 82056")
    text = text.replace("  1  1  0  0  0  0  0  0  0  0  0  1  1",
                        "  1  1  0  0  1  0  0  0  0  0  0  1  1")
    text += ("\n*PLANTING DETAILS\n@P PDATE EDATE\n 1 83057 84060\n")
    sim.filex.write_text(text)
    supplied = []
    for candidate in (1982, 1983, 1984):
        if missing == "initial" and candidate == 1982 or missing == "effective" and candidate == year:
            continue
        path = stock_file(tmp_path, f"UFGA{candidate % 100:02d}01.WTH",
                          days=days("1982-01-01", "1984-12-31"), wide=True)
        # Different valid rainfall identifies the selected candidate in the returned rows.
        path.write_bytes(path.read_bytes().replace(b"    0.0", f"    {candidate - 1980}.0".encode()))
        supplied.append(path)
    sim.weather = supplied
    if missing:
        assert_file_problem(sim, "UFGA8201.WTH" if missing == "initial" else f"UFGA{year % 100:02d}01.WTH")
    else:
        assert sim.check(False) == []
        from dssatlab.filex import _read_filex
        from dssatlab.sequence import _rotation_components
        from dssatlab.stock import _simulation_weather
        rows, problems = _simulation_weather(sim, _read_filex(sim.filex, 7)[0], {},
                                             _rotation_components(sim.filex, 7))
        assert problems == []
        assert {row["rain"] for row in rows} == {float(year - 1980)}


def test_eight_character_wsta_uses_literal_not_sdate_name(tmp_path):
    sim = period(tmp_path, station="UFGA8301")
    sim.weather = [stock_file(tmp_path, "UFGA8301.WTH", days=days("1982-12-30", "1983-01-02")),
                   stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-01-01", "1982-12-31"))]
    assert sim.check(False) == []


@pytest.mark.parametrize("station", ["UFGA", "UFGA9901"])
def test_mode_c_rejects_four_character_fallback(tmp_path, station):
    sim = period(tmp_path, station=station)
    sim.weather = stock_file(tmp_path, "UFGA.WTH", days=days("1982-01-01", "1984-12-31"))
    assert_file_problem(sim, f"{station if len(station) == 8 else 'UFGA8201'}.WTH")
    assert any("mode C" in p for p in sim.check(False))


@pytest.mark.parametrize("competitor", [False, True])
def test_yearly_named_multi_year_file_continues(tmp_path, competitor):
    sim = period(tmp_path)
    first = stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-12-30", "1983-01-02"))
    sim.weather = [first]
    if competitor:
        sim.weather.append(stock_file(tmp_path, "UFGA8301.WTH", days=days("1983-01-01", "1983-01-02")))
    assert sim.check(False) == []


def test_yearly_rollover_uses_next_year_file(tmp_path):
    sim = period(tmp_path)
    sim.weather = [stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-12-30", "1982-12-31")),
                   stock_file(tmp_path, "UFGA8301.WTH", days=days("1983-01-01", "1983-01-02"))]
    assert sim.check(False) == []


def test_exhausted_multi_year_file_does_not_borrow_next_year(tmp_path):
    sim = period(tmp_path, "82364", "84002")
    sim.weather = [stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-12-30", "1983-12-31")),
                   stock_file(tmp_path, "UFGA8401.WTH", days=days("1984-01-01", "1984-01-02"))]
    assert_file_problem(sim, "UFGA8201.WTH")
    assert any("1984-01-01" in p for p in sim.check(False))


@pytest.mark.parametrize("start,harvest", [("82001", "83330"), ("09120", "09170")])
def test_long_file_reads_past_one_year_and_record_10000(tmp_path, start, harvest):
    sim = period(tmp_path, start, harvest, "UFGA8201")
    sim.weather = stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-01-01", "2012-12-31"), wide=True)
    assert sim.check(False) == []


def wed_install(tmp_path, sim):
    folder = tmp_path / "installed"
    folder.mkdir()
    executable = folder / "DSCSM048.EXE"
    executable.write_text("fake DSSAT")
    executable.chmod(0o755)
    wed = folder / "custom weather"
    wed.mkdir()
    # Profile path differs from the conventional Weather directory.
    (folder / "DSSATPRO.v48").write_text(f"WED {wed.drive or '-99'} {str(wed)[len(wed.drive):]}\n")
    sim.executable = executable
    return wed


def test_same_name_local_beats_wed(tmp_path):
    sim = period(tmp_path)
    wed = wed_install(tmp_path, sim)
    installed = stock_file(wed, "UFGA8201.WTH", days=days("1982-12-30", "1983-01-02"))
    installed.write_bytes(installed.read_bytes().replace(b"  20.0N", b"  -99.0"))
    sim.weather = stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-12-30", "1983-01-02"))
    before = installed.read_bytes()
    assert sim.check(False) == []
    assert installed.read_bytes() == before


def test_installed_only_cannot_satisfy_supplied_initial_lookup(tmp_path):
    sim = period(tmp_path)
    wed = wed_install(tmp_path, sim)
    stock_file(wed, "UFGA8201.WTH", days=days("1982-12-30", "1983-01-02"))
    sim.weather = stock_file(tmp_path, "UFGA8301.WTH", days=days("1982-12-30", "1983-01-02"))
    assert_file_problem(sim, "UFGA8201.WTH")


def test_wed_yearly_shadows_local_fallback(tmp_path):
    sim = period(tmp_path)
    wed = wed_install(tmp_path, sim)
    stock_file(wed, "UFGA8201.WTH", days=days("1982-12-30", "1983-01-02"))
    sim.weather = stock_file(tmp_path, "UFGA.WTH", days=days("1982-12-30", "1983-01-02"))
    assert_file_problem(sim, "UFGA8201.WTH")
    assert any("shadows" in p and str(wed) in p for p in sim.check(False))


def test_local_rollover_retains_directory_even_with_installed_next(tmp_path):
    sim = period(tmp_path)
    wed = wed_install(tmp_path, sim)
    stock_file(wed, "UFGA8301.WTH", days=days("1983-01-01", "1983-01-02"))
    sim.weather = stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-12-30", "1982-12-31"))
    assert_file_problem(sim, "UFGA8301.WTH")


@pytest.mark.parametrize("station,competitor", [("UFGA", None), ("UFGA", "local"),
                                               ("UFGA0001", "installed")])
def test_report_mode_a_continuous_fallback_keeps_selected_file(tmp_path, station, competitor):
    # continuous_only/local_next and path_continuous_installed_next, sections 5-6.
    first = stock_file(tmp_path, "UFGA.WTH", days=days("1982-01-01", "1984-12-31"))
    paths, wed = [first], None
    if competitor == "local":
        paths.append(stock_file(tmp_path, "UFGA8301.WTH", days=days("1983-01-01", "1983-01-30")))
    elif competitor == "installed":
        wed = tmp_path / "wed"
        wed.mkdir()
        stock_file(wed, "UFGA8301.WTH", days=days("1983-01-01", "1983-01-30"))
    rows, problems = _walk_weather_files(paths, station, "82350", date(1982, 12, 16),
                                         date(1983, 1, 30), wed=wed, mode="A")
    assert problems == []
    assert len(rows) == 1096  # Only the continuous file, with no competitor appended.


@pytest.mark.parametrize("start", [date(1982, 2, 25), date(1983, 2, 26), date(1984, 2, 29)])
def test_report_mode_a_fallback_satisfies_both_lookup_stages(tmp_path, start):
    first = stock_file(tmp_path, "UFGA.WTH", days=days("1982-01-01", "1984-12-31"))
    rows, problems = _walk_weather_files([first], "UFGA", "82056", start, start, mode="A")
    assert problems == []
    assert start in {row["date"] for row in rows}


@pytest.mark.parametrize("last,missing,next_name", [("1982-12-31", "1983-01-01", "UFGA8301.WTH"),
                                                   ("1983-12-31", "1984-01-01", "UFGA8401.WTH")])
def test_report_mode_a_exhausted_fallback_stays_selected(tmp_path, last, missing, next_name):
    first = stock_file(tmp_path, "UFGA.WTH", days=days("1982-01-01", last))
    second = stock_file(tmp_path, next_name, days=days(missing, missing))
    _, problems = _walk_weather_files([first, second], "UFGA", "82350", date(1982, 12, 16),
                                      date.fromisoformat(missing), mode="A")
    assert len(problems) == 1
    assert all(part in problems[0] for part in ("UFGA.WTH", missing, "Checked", "Supply"))


@pytest.mark.parametrize("station,start,end", [("UFGA", date(1982, 1, 1), date(1983, 11, 26)),
                                              ("UFGA", date(2009, 4, 30), date(2009, 6, 19)),
                                              ("UFGA9901", date(1982, 12, 16), date(1983, 1, 30))])
def test_report_mode_a_long_and_explicit_missing_literal_fallback(tmp_path, station, start, end):
    first = stock_file(tmp_path, "UFGA.WTH", days=days("1982-01-01", "2012-12-31"), wide=True)
    rows, problems = _walk_weather_files([first], station, "82001", start, end, mode="A")
    assert problems == []
    assert len(rows) == 11323
    assert {start, end}.issubset({row["date"] for row in rows})


def test_installed_yearly_with_local_next_still_needs_supplied_initial_file(tmp_path):
    # path_installed_yearly_local_next: installed weather is not supplied coverage.
    sim = period(tmp_path)
    wed = wed_install(tmp_path, sim)
    for year in (1982, 1983):
        stock_file(wed, f"UFGA{year % 100:02d}01.WTH", days=days(f"{year}-01-01", f"{year}-12-31"))
    sim.weather = stock_file(tmp_path, "UFGA8301.WTH", days=days("1983-01-01", "1983-01-02"))
    assert_file_problem(sim, "UFGA8201.WTH")


@pytest.mark.parametrize("profile,line", [("DSSATPRO.v48", "WED -99 {path}"),
                                         ("DSSATPRO.L48", "WED {path}")])
def test_wed_path_is_read_from_profile_not_conventional_folder(tmp_path, profile, line):
    sim = period(tmp_path)
    wed = wed_install(tmp_path, sim)
    original = sim.executable.parent / "DSSATPRO.v48"
    original.unlink()
    (sim.executable.parent / profile).write_text(line.format(path=wed) + "\n")
    assert _weather_directory(sim.executable) == wed


def test_rollover_file_with_old_year_records_fails_in_that_file(tmp_path, monkeypatch):
    from dssatlab import weather_files

    first = stock_file(tmp_path, "UFGA8201.WTH", days=days("1982-12-30", "1982-12-31"))
    second = stock_file(tmp_path, "UFGA8301.WTH", days=days("1982-01-01", "1982-12-31"))
    read = weather_files._read_stock_weather
    opened = set()

    def read_once(path, *args):
        # Bound the regression: a broken walk reopens the same exhausted file forever.
        if path in opened:
            raise AssertionError("Weather selection reopened an exhausted file")
        opened.add(path)
        return read(path, *args)

    monkeypatch.setattr(weather_files, "_read_stock_weather", read_once)
    _, problems = _walk_weather_files([first, second], "UFGA", "82364", date(1982, 12, 30),
                                      date(1983, 1, 2))
    assert len(problems) == 1
    assert all(part in problems[0] for part in ("UFGA8301.WTH", "1983-01-01", "Checked", "Supply"))
