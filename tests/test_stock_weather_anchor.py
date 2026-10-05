"""Stock $WEATHER anchors use the initial file and DSSAT's integer window."""

import pytest

from dssatlab import core
from test_harvest_required import simulation
from test_stock_weather import weather_file


@pytest.fixture(autouse=True)
def no_installed_weather(monkeypatch):
    monkeypatch.setattr(core, "detect", lambda: {"dssat_path": None})


def anchored_sim(tmp_path, sdate="88150", harvest="88151", *, planting=None,
                 station="AZMC8801", codes=("1988150", "1988151"), wide=True,
                 sequence=False, code="R"):
    sim = simulation(tmp_path, level=1, harvest=harvest, sequence=sequence, code=code)
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


@pytest.mark.parametrize("start", ["S", "P", "E"])
def test_positive_sdate_is_checked_under_any_start_setting(tmp_path, start):
    sim = anchored_sim(tmp_path, "88100")
    sim.filex.write_text(sim.filex.read_text().replace("     S 88100", f"     {start} 88100"))
    problems = sim.check(False)
    anchors = [p for p in problems if "anchors FileX years" in p]
    assert len(anchors) == 1
    assert anchors[0].startswith(
        "FileX SDATE 88100 reads as 1988-04-09, before 1988-05-29")
    if start != "S":
        reason = " (START E needs an emergence date)" if start == "E" else ""
        assert problems == [
            f"Stock weather {sim.weather}: cannot check weather dates because "
            f"the simulation start is unknown{reason}. Checked START and "
            "SDATE/PDATE for treatment 7. "
            "Use START S or P with a valid date, or pass the weather as rows.",
            anchors[0],
        ]


@pytest.mark.parametrize("source", ["experiment", "filex"])
@pytest.mark.parametrize("second,expected_count", [("1988-05-30", 1), ("1988-04-10", 2)])
def test_each_reported_harvest_date_is_checked(tmp_path, source, second, expected_count):
    sim = anchored_sim(tmp_path, harvest="88100")
    if source == "experiment":
        sim.management = {"treatments": {7: {"harvest": [
            {"date": "1988-04-09"}, {"date": second},
        ]}}}
    else:
        code = "88151" if second == "1988-05-30" else "88101"
        text = sim.filex.read_text().replace(
            " 1 88100 GS000   -99   -99   100     0 -99",
            " 1 88100 GS000   -99   -99   100     0 -99\n"
            f" 1 {code} GS000   -99   -99   100     0 -99")
        sim.filex.write_text(text)
    problems = anchor_problems(sim)
    assert len(problems) == expected_count
    field = "treatments.7.harvest.0.date 1988-04-09" if source == "experiment" else "FileX HDATE 88100"
    assert problems[0].startswith(f"{field} reads as 1988-04-09, before 1988-05-29")
    if expected_count == 2:
        field = "treatments.7.harvest.1.date 1988-04-10" if source == "experiment" else "FileX HDATE 88101"
        assert problems[1].startswith(f"{field} reads as 1988-04-10, before 1988-05-29")


@pytest.mark.parametrize("source", ["experiment", "filex"])
def test_unknown_start_checks_sdate_and_reported_harvest(tmp_path, source):
    sim = anchored_sim(tmp_path, "88100", "88101")
    sim.filex.write_text(sim.filex.read_text().replace("     S 88100", "     E 88100"))
    if source == "experiment":
        sim.management = {"treatments": {7: {"harvest": [{"date": "1988-04-10"}]}}}
    problems = sim.check(False)
    assert len(problems) == 3
    assert "simulation start is unknown (START E needs an emergence date)" in problems[0]
    assert problems[1].startswith("FileX SDATE 88100 reads as 1988-04-09, before")
    field = "treatments.7.harvest.0.date 1988-04-10" if source == "experiment" else "FileX HDATE 88101"
    assert problems[2].startswith(f"{field} reads as 1988-04-10, before 1988-05-29")


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


@pytest.mark.parametrize("source", ["filex", "experiment"])
@pytest.mark.parametrize("harvest,day,relation", [
    ("36059", "1936-02-28", "before"),
    ("36060", "1936-02-29", None),
    ("35060", "2035-03-01", None),
    ("35061", "2035-03-02", "more than 99 years after"),
])
def test_later_rotation_harvest_anchor_boundaries(tmp_path, source, harvest, day, relation):
    sim = anchored_sim(tmp_path, "36060", harvest if source == "filex" else "35061",
                       codes=("1936060", "2035060", "2035061"), sequence=True)
    if source == "experiment":
        sim.management = {"treatments": {"07": {"rotation": {"02": {
            "harvest": [{"date": day}],
        }}}}}
    problems = anchor_problems(sim)
    if relation is None:
        assert problems == []
        return
    field = ("FileX HDATE (rotation component 2)" if source == "filex" else
             "treatments.7.rotation.2.harvest.0.date")
    value = harvest if source == "filex" else day
    advice = "on or before" if relation == "before" else "within 99 years before"
    assert problems == [
        f"{field} {value} reads as {day}, {relation} 1936-02-29, the first date "
        "of stock weather AZMC8801.WTH. A $WEATHER file anchors FileX years to "
        "its first date: DSSAT reads this date in another century or stops. "
        f"Checked {field.removeprefix('FileX ')} against AZMC8801.WTH. "
        f"Supply weather starting {advice} {day}, or move the date."]


@pytest.mark.parametrize("source", ["filex", "experiment"])
@pytest.mark.parametrize("first_reported", [False, True])
def test_rotation_checks_each_harvest_in_each_reported_component(tmp_path, source, first_reported):
    sim = anchored_sim(tmp_path, harvest="88100", sequence=True)
    text = sim.filex.read_text()
    if first_reported:
        text = text.replace(" 1 MA              R     R     R     N     M",
                            " 1 MA              R     R     R     N     R")
    if source == "filex":
        text = text.replace(
            " 1 88100 GS000   -99   -99   100     0 -99",
            " 1 88100 GS000   -99   -99   100     0 -99\n"
            " 1 88101 GS000   -99   -99   100     0 -99\n"
            " 1 88151 GS000   -99   -99   100     0 -99")
    else:
        events = [{"date": "1988-04-09"}, {"date": "1988-04-10"}, {"date": "1988-05-30"}]
        sim.management = {"treatments": {7: {"rotation": {
            1: {"harvest": events}, 2: {"harvest": events},
        }}}}
    sim.filex.write_text(text)
    problems = anchor_problems(sim)
    components = [1, 2] if first_reported else [2]
    fields = [(f"FileX HDATE (rotation component {component})" if source == "filex" else
               f"treatments.7.rotation.{component}.harvest.{event}.date")
              for component in components for event in range(2)]
    values = ["88100", "88101"] if source == "filex" else ["1988-04-09", "1988-04-10"]
    assert len(problems) == len(fields)
    for i, (field, problem) in enumerate(zip(fields, problems)):
        assert problem.startswith(f"{field} {values[i % 2]} reads as ")
        assert "before 1988-05-29" in problem


@pytest.mark.parametrize("source", ["filex", "experiment"])
@pytest.mark.parametrize("code", ["M", "A", "D"])
def test_rotation_non_reported_harvest_has_no_anchor_problem(tmp_path, source, code):
    sim = anchored_sim(tmp_path, harvest="88100", sequence=True, code=code)
    if source == "experiment":
        sim.management = {"treatments": {7: {"rotation": {2: {
            "harvest": [{"date": "1988-04-09"}],
        }}}}}
    assert anchor_problems(sim) == []
