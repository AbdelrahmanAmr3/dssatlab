"""Stock $WEATHER anchors use the initial file and DSSAT's integer window."""

import pytest

from dssatlab import core
from test_harvest_required import simulation
from test_stock_weather import weather_file


@pytest.fixture(autouse=True)
def no_installed_weather(monkeypatch):
    monkeypatch.setattr(core, "detect", lambda: {"dssat_path": None})


def anchored_sim(tmp_path, sdate="88150", harvest="88151", *, planting=None,
                 station="AZMC8801", codes=("1988150", "1988151"), wide=True):
    sim = simulation(tmp_path, level=1, harvest=harvest)
    text = sim.filex.read_text().replace("82056", sdate)
    text = text.replace("UFGA       -99", f"{station:8s}   -99")
    if planting is not None:
        text = text.replace(f"     S {sdate}", f"     P {sdate}")
        text = text.replace("  1  1  0  0  0  0  0  0  0  0  0  1  1",
                            "  1  1  0  0  1  0  0  0  0  0  0  1  1")
        text += f"\n*PLANTING DETAILS\n@P PDATE EDATE\n 1 {planting} -99\n"
    sim.filex.write_text(text, encoding="ascii")
    sim.weather = weather_file(tmp_path, f"{station}.WTH", codes, wide=wide)
    return sim


def anchor_problems(sim):
    return [p for p in sim.check(False) if "anchors FileX years" in p]


def test_sdate_before_anchor_exact_message_and_coverage_problem(tmp_path):
    sim = anchored_sim(tmp_path, "88100")
    problems = sim.check(False)
    expected = (
        "FileX SDATE 88100 reads as 1988-04-09, before 1988-05-29, the first date "
        "of stock weather AZMC8801.WTH. A $WEATHER file anchors FileX years to "
        "its first date: DSSAT reads this date in another century or stops. "
        "Checked SDATE against AZMC8801.WTH. Supply weather starting on or "
        "before 1988-04-09, or move the date.")
    assert expected in problems
    assert sum("anchors FileX years" in p for p in problems) == 1
    assert any("not covered by weather data" in p for p in problems)


def test_sdate_on_anchor_has_no_problem(tmp_path):
    assert anchored_sim(tmp_path).check(False) == []


def test_start_p_before_anchor_names_pdate(tmp_path):
    sim = anchored_sim(tmp_path, planting="87150")
    problems = anchor_problems(sim)
    assert len(problems) == 1
    assert "FileX PDATE 87150 reads as 1987-05-30, before 1988-05-29" in problems[0]
    assert "Checked PDATE against AZMC8801.WTH" in problems[0]


def test_start_p_still_checks_positive_sdate(tmp_path):
    sim = anchored_sim(tmp_path, "88100", planting="88150")
    problems = anchor_problems(sim)
    assert len(problems) == 1
    assert problems[0].startswith("FileX SDATE 88100 reads as 1988-04-09, before")


@pytest.mark.parametrize("planting", [None, "88150"])
def test_controls_start_before_anchor_names_location(tmp_path, planting):
    sim = anchored_sim(tmp_path, planting=planting)
    sim.management = {"treatments": {7: {"controls": {"start_date": "1988-04-09"}}}}
    problems = anchor_problems(sim)
    assert len(problems) == 1
    assert problems[0].startswith(
        "treatments.7.controls.start_date 1988-04-09 reads as 1988-04-09, before")
    assert "Checked treatments.7.controls.start_date against AZMC8801.WTH" in problems[0]


@pytest.mark.parametrize("harvest,day", [("88100", "1988-04-09"),
                                        ("35061", "2035-03-02")])
def test_unshifted_reported_harvest_outside_anchor(tmp_path, harvest, day):
    early = harvest == "88100"
    sim = anchored_sim(tmp_path, "88150" if early else "35060", harvest,
                       codes=("1988150", "1988151") if early else
                       ("1936060", "2035060", "2035061"))
    problems = anchor_problems(sim)
    assert len(problems) == 1
    assert problems[0].startswith(f"FileX HDATE {harvest} reads as {day}, ")
    if not early:
        assert "more than 99 years after 1936-02-29" in problems[0]
        assert problems[0].endswith(
            "Supply weather starting within 99 years before 2035-03-02, or move the date.")


@pytest.mark.parametrize("sdate,expected", [("35060", False), ("35061", True)])
def test_leap_anchor_upper_bound_uses_yyyyddd_not_anniversary(tmp_path, sdate, expected):
    sim = anchored_sim(tmp_path, sdate, "35062",
                       codes=("1936060", "2035060", "2035061", "2035062"))
    problems = [p for p in anchor_problems(sim) if p.startswith("FileX SDATE")]
    assert bool(problems) is expected
    if expected:
        assert "more than 99 years after 1936-02-29" in problems[0]


def test_nyers_does_not_shift_hdate_for_anchor_check(tmp_path):
    sim = anchored_sim(tmp_path, "35060", "35060",
                       codes=("1936060", "2035060", "2036061"))
    sim.management = {"treatments": {7: {"controls": {"years": 2}}}}
    assert anchor_problems(sim) == []


def test_invalid_sdate_under_start_p_with_valid_planting(tmp_path):
    sim = anchored_sim(tmp_path, "88367", planting="88150")
    problems = sim.check(False)
    assert any("SDATE '88367' is invalid: day 367 does not exist in 1988" in p
               for p in problems)


@pytest.mark.parametrize("initial_wide", [True, False])
def test_anchor_comes_from_initial_not_effective_start_file(tmp_path, initial_wide):
    sim = anchored_sim(tmp_path, planting="89150", harvest="89151", station="AZMC")
    initial = weather_file(tmp_path, "AZMC8801.WTH",
                           ("1988300", "1988301") if initial_wide else ("88300", "88301"),
                           wide=initial_wide)
    effective = weather_file(tmp_path, "AZMC8901.WTH", ("1989150", "1989151"), wide=True)
    sim.weather = [effective, initial]
    problems = anchor_problems(sim)
    if initial_wide:
        assert len(problems) == 1
        assert "before 1988-10-26, the first date of stock weather AZMC8801.WTH" in problems[0]
    else:
        assert problems == []


def test_anchor_is_first_record_not_earliest_date(tmp_path):
    sim = anchored_sim(tmp_path, codes=("1988300", "1988150", "1988151"))
    problems = anchor_problems(sim)
    assert len(problems) == 2
    assert all("before 1988-10-26" in p for p in problems)


def test_initial_anchor_survives_failed_effective_lookup(tmp_path):
    sim = anchored_sim(tmp_path, planting="89150", harvest="89151", station="AZMC")
    sim.weather = weather_file(tmp_path, "AZMC8801.WTH", ("1988300",), wide=True)
    problems = sim.check(False)
    assert any("DSSAT requests AZMC8901.WTH" in p for p in problems)
    assert any("FileX SDATE 88150" in p and "anchors FileX years" in p for p in problems)


@pytest.mark.parametrize("source", ["classic", "rows"])
def test_classic_weather_and_weather_rows_add_no_anchor_problem(tmp_path, source):
    sim = anchored_sim(tmp_path, "88100", codes=("88150", "88151"), wide=False)
    if source == "rows":
        sim.weather = [{"station": "AZMC", "date": day, "latitude": 29.63,
                        "longitude": -82.37, "elevation": 10, "srad": 20,
                        "tmax": 25, "tmin": 15, "rain": 0}
                       for day in ("1988-05-29", "1988-05-30")]
    assert anchor_problems(sim) == []
