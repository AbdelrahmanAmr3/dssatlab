"""Narrow FileX checks through Simulation, with real sample column alignment."""

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from dssatlab import Simulation
from dssatlab.filex import _weather_filename


SAMPLE = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 RAINFED LOW NITROGEN       1  1  0  1  1  1  1  0  0  0  0  0  1
 2 1 0 0 RAINFED HIGH NITROGEN      1  1  0  1  1  1  2  0  0  0  0  0  1
 3 1 0 0 IRRIGATED LOW NITROGEN     1  1  0  1  1  2  1  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910014 Field section
@L ...........XCRD ...........YCRD .....ELEV .............AREA .SLEN .FLWR .SLAS FLHST FHDUR
 1             -99             -99       -99               -99   -99   -99   -99   -99

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 N X IRRIGATION, GAINESVILLE
@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2
 1 OP              Y     Y     Y     N     N     N     N     Y     M
"""


@pytest.fixture
def filex(tmp_path):
    def write(station="UFGA", start="S", sdate="82056", text=SAMPLE):
        text = text.replace("UFGA       -99", f"{station:<8}   -99")
        text = text.replace("S 82056", f"{start} {sdate:>5}")
        path = tmp_path / "UFGA8201.MZX"
        path.write_text(text, encoding="latin-1")
        return path
    return write


@pytest.fixture
def weather(tmp_path):
    def write(station="UFGA", days=None, **changes):
        days = days if days is not None else ["1982-02-24", "1982-02-25", "1982-02-26"]
        rows = [dict(station=station, latitude=45, longitude=-100, elevation=200,
                     date=day, srad=20, tmax=25, tmin=10, rain=0) for day in days]
        for row in rows:
            row.update(changes)
        path = tmp_path / "weather.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path
    return write


@pytest.mark.parametrize("station", ["UFGA", "UFGA8201"])
@pytest.mark.parametrize("treatment", [1, 2, 3, "2", "03"])
def test_valid_treatment_and_fields_with_other_header_blocks(filex, weather, station, treatment):
    assert Simulation(filex(station=station), treatment, weather()).check() == []


@pytest.mark.parametrize("station,sdate,expected", [
    ("UFGA", "82056", "UFGA8201.WTH"), ("uFgA", "00001", "uFgA0001.WTH"),
    ("UFGA8201", "83056", "UFGA8201.WTH"), ("uFgA8207", "99365", "uFgA8207.WTH"),
])
def test_weather_filename(station, sdate, expected):
    assert _weather_filename(station, sdate) == expected


@pytest.mark.parametrize("treatment", [4, "99", 0, -1])
def test_unknown_treatment(filex, weather, treatment):
    problems = Simulation(filex(), treatment, weather()).check()
    assert len(problems) == 1
    assert f"treatment number {treatment}" in problems[0]
    assert "does not exist" in problems[0]


@pytest.mark.parametrize("treatment", [None, True, 1.0, "1.0", " 1", "one", "", object()])
def test_invalid_treatment(filex, weather, treatment):
    problems = Simulation(filex(), treatment, weather()).check()
    assert len(problems) == 1
    assert "treatment number is invalid" in problems[0]


@pytest.mark.parametrize("section", ["TREATMENTS", "FIELDS", "SIMULATION CONTROLS"])
def test_missing_section(filex, weather, section):
    text = SAMPLE.replace(f"*{section}", "*UNUSED")
    problems = Simulation(filex(text=text), 1, weather()).check()
    assert any(f"missing {section} section" in p for p in problems)


@pytest.mark.parametrize("delimiter", ["\n", "@L OTHER\n", "*UNUSED\n"])
def test_does_not_read_field_rows_outside_a_matching_block(filex, weather, delimiter):
    text = SAMPLE.replace(" 1 UFGA0002", delimiter + " 1 UFGA0002")
    problems = Simulation(filex(text=text), 1, weather()).check()
    assert any("FIELDS: row L= 1 does not exist" in p for p in problems)


@pytest.mark.parametrize("section,expected", [("FIELDS", "year 82 day 056"),
                                            ("SIMULATION CONTROLS", "expects station")])
def test_available_filex_comparisons_survive_other_section_problems(filex, weather, section, expected):
    text = SAMPLE.replace(f"*{section}", "*UNUSED")
    problems = Simulation(filex(text=text), 1,
                          weather(station="ABCD", days=["1982-02-26"])).check()
    assert any(f"missing {section} section" in p for p in problems)
    assert any(expected in p for p in problems)


@pytest.mark.parametrize("old,new,expected", [
    ("@L ID_FIELD", "!L ID_FIELD", "FIELDS has no header block containing"),
    (" WSTA....", " OTHER...", "WSTA"),
    (" START", " OTHER", "START"),
    (" 1 UFGA0002", " 2 UFGA0002", "FIELDS: row L= 1 does not exist"),
    (" 1 GE", " 2 GE", "SIMULATION CONTROLS: row N= 1 does not exist"),
    (" 1  1  0  1", " 1  x  0  1", "invalid FL"),
    (" 0  0  0  1\n", " 0  0  0  x\n", "invalid SM"),
])
def test_missing_columns_rows_and_bad_levels(filex, weather, old, new, expected):
    problems = Simulation(filex(text=SAMPLE.replace(old, new)), 1, weather()).check()
    assert any(expected in p for p in problems)


def test_treatment_references_select_other_field_and_controls(filex, weather):
    lines = SAMPLE.splitlines()
    lines[3] = lines[3].replace(" 1  1  0  1", " 1  2  0  1")[:-1] + "2"
    field = lines[8].replace(" 1 UFGA0002 UFGA", " 2 UFGA0002 ABCD")
    control = lines[14].replace(" 1 GE", " 2 GE").replace("82056", "83001")
    lines.insert(15, control)
    lines.insert(9, field)
    path = filex(text="\n".join(lines))
    assert Simulation(path, 2, weather(station="ABCD", days=["1983-01-01"])).check() == []
    assert Simulation(path, 1, weather()).check() == []


@pytest.fixture
def multilevel_filex(filex):
    treatments = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 JAN   46 CM ROWSPACE       1  1  0  1  1  0  0  0  0  0  0  1  1
 4 1 0 0 FEB   46 CM ROWSPACE       1  1  0  1  4  0  0  0  0  0  0  2  2

"""
    controls = """*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 86014  2150 JAN CG NO-STRESS
@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2
 1 OP              N     N     N     N     N     N     N     N     M
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              M     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMO
 1 OU              N     Y     Y     5     Y     N     Y     Y     N     N     Y     N     N

@  AUTOMATIC MANAGEMENT
@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          98155 98200    40   100    30    40    10

@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 2 GE              1     1     S 86044  2150 FEB CG NO-STRESS
@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2
 2 OP              N     N     N     N     N     N     N     N     M
"""
    fields = "*FIELDS" + SAMPLE.split("*FIELDS")[1].split("*SIMULATION CONTROLS")[0]
    return filex(text=treatments + fields + controls)


@pytest.mark.parametrize("treatment,day,other_day,start", [
    (1, "1986-01-14", "1986-02-13", "year 86 day 014"),
    (4, "1986-02-13", "1986-01-14", "year 86 day 044"),
])
def test_repeated_controls_groups(multilevel_filex, weather, treatment, day, other_day, start):
    assert Simulation(multilevel_filex, treatment, weather(days=[day])).check() == []
    problems = Simulation(multilevel_filex, treatment, weather(days=[other_day])).check()
    assert len(problems) == 1 and start in problems[0]


def test_controls_level_absent_from_all_matching_blocks(multilevel_filex, weather):
    text = multilevel_filex.read_text(encoding="latin-1").replace(" 2 GE", " 3 GE")
    multilevel_filex.write_text(text, encoding="latin-1")
    problems = Simulation(multilevel_filex, 4, weather()).check()
    assert len(problems) == 1
    assert "SIMULATION CONTROLS: row N= 2 does not exist" in problems[0]


def test_later_matching_fields_header_is_used(filex, weather):
    text = SAMPLE.replace("@L ID_FIELD", "@  FIELD DETAILS\n\n@L ID_FIELD")
    assert Simulation(filex(text=text), 1, weather()).check() == []


def test_field_level_only_in_first_header_block(filex, weather):
    text = SAMPLE.replace(" 1             -99", " 2             -99")
    assert Simulation(filex(text=text), 1, weather()).check() == []


def test_column_positions_come_from_headers_and_latin1_is_accepted(filex, weather):
    lines = SAMPLE.splitlines()
    lines[1] = lines[1][:33] + "...." + lines[1][33:]
    for i in (2, 3, 4):
        lines[i] = lines[i][:33] + "    " + lines[i][33:]
    text = "\n".join(lines).replace("Field section", "Champ cultivé")
    assert Simulation(filex(text=text), 1, weather()).check() == []


@pytest.mark.parametrize("start", ["P", "E", "I", "A", "s", " "])
def test_other_start_options_allow_weather_after_sdate(filex, weather, start):
    # Verified on real DSSAT: the weather file name uses the year of SDATE for every START option.
    assert Simulation(filex(start=start, sdate="81014"), 1, weather()).check() == []


def test_weather_filename_uses_the_sdate_year():
    assert _weather_filename("UFGA", "81014") == "UFGA8101.WTH"


@pytest.mark.parametrize("start", ["S", "P", "E"])
@pytest.mark.parametrize("sdate", ["82x56", "8205", "", "-9956"])
def test_bad_sdate(filex, weather, sdate, start):
    problems = Simulation(filex(sdate=sdate, start=start), 1, weather()).check()
    assert len(problems) == 1
    assert "SDATE" in problems[0] and "five digits" in problems[0]


@pytest.mark.parametrize("station", ["", "UFG", "UFGA82"])
def test_bad_station_length(filex, weather, station):
    problems = Simulation(filex(station=station), 1, weather()).check()
    assert len(problems) == 1
    assert "WSTA" in problems[0] and "invalid length" in problems[0]


@pytest.mark.parametrize("station,template", [("UFGA", "ABCD"), ("UFGA8201", "ABCD"),
                                              ("UFGA", "ufga"), ("ufga8201", "UFGA")])
def test_station_mismatch_names_both(filex, weather, station, template):
    problems = Simulation(filex(station=station), 1, weather(station=template)).check()
    assert len(problems) == 1
    assert station in problems[0] and template in problems[0]
    assert "filenames are case-sensitive on Linux" in problems[0]


@pytest.mark.parametrize("days", [["1982-02-24"], ["1982-02-26"],
                                  ["1982-02-24", "1982-02-26"]])
def test_start_missing_names_start_and_weather_dates(filex, weather, days):
    problems = Simulation(filex(), 1, weather(days=days)).check()
    assert any("year 82 day 056" in p and days[0] in p and days[-1] in p
               for p in problems)


@pytest.mark.parametrize("year", [1982, 2082])
def test_start_compares_without_century_rule(filex, weather, year):
    assert Simulation(filex(), 1, weather(days=[f"{year}-02-25"])).check() == []


def test_start_covered_in_multi_year_weather(filex, weather):
    days = [(date(1981, 12, 31) + timedelta(days=i)).isoformat() for i in range(58)]
    assert Simulation(filex(), 1, weather(days=days)).check() == []


def test_filex_and_weather_problems_collected_together(filex, weather):
    problems = Simulation(filex(station="UFG", start="P", sdate="bad"), 1,
                          weather(rain=-1)).check()
    for message in ("rain", "WSTA", "SDATE"):
        assert any(message in p for p in problems)


@pytest.mark.parametrize("changes,expected", [({"station": "bad"}, "year 82 day 056"),
                                            ({"date": "bad"}, "expects station")])
def test_only_unavailable_weather_comparisons_skipped(filex, weather, changes, expected):
    options = dict(station="ABCD", days=["1982-02-26"])
    options.update(changes)
    problems = Simulation(filex(), 1, weather(**options)).check()
    assert any(expected in p for p in problems)


@pytest.mark.parametrize("data", [None, [], [{"station": "bad", "date": "bad"}]])
def test_filex_problems_without_usable_weather(filex, data):
    problems = Simulation(filex(sdate="bad"), 1, data).check()
    assert any("SDATE" in p for p in problems)
    assert any("weather" in p.lower() for p in problems)
    assert not any("expects station" in p or "not covered" in p for p in problems)


@pytest.mark.parametrize("kind", ["missing", "directory", "denied", "invalid"])
def test_unreadable_filex_is_a_problem(tmp_path, weather, monkeypatch, kind):
    weather_path = weather(rain=-1)
    source = {"missing": tmp_path / "absent.MZX", "directory": tmp_path,
              "denied": tmp_path / "denied.MZX", "invalid": object()}[kind]
    if kind == "denied":
        def denied(*args, **kwargs):
            raise PermissionError("read denied")
        monkeypatch.setattr(Path, "read_text", denied)
    problems = Simulation(source, 1, weather_path).check()
    assert sum("Cannot read FileX" in p for p in problems) == 1
    assert any("rain" in p for p in problems)


def test_checks_write_nothing_and_reread_inputs(filex, weather, tmp_path):
    path = filex()
    simulation = Simulation(path, 1, weather())
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    assert simulation.check() == []
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before
    filex(sdate="bad")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    assert any("SDATE" in p for p in simulation.check())
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before


@pytest.mark.parametrize("wther,fname,expected_problems", [
    ("W", "N", [
        "FileX WTHER 'W' in controls level 1 (treatment 1): DSSAT would generate weather "
        "and ignore the weather data supplied. Set WTHER to M."
    ]),
    ("M", "Y", [
        "FileX FNAME 'Y' in controls level 1 (treatment 1): DSSAT would name its output "
        "files after the experiment (UFGA8201.OSU) instead of Summary.OUT, which dssatlab "
        "reads. Set FNAME to N."
    ]),
    ("W", "Y", [
        "FileX WTHER 'W' in controls level 1 (treatment 1): DSSAT would generate weather "
        "and ignore the weather data supplied. Set WTHER to M.",
        "FileX FNAME 'Y' in controls level 1 (treatment 1): DSSAT would name its output "
        "files after the experiment (UFGA8201.OSU) instead of Summary.OUT, which dssatlab "
        "reads. Set FNAME to N.",
    ]),
    ("S", "N", [
        "FileX WTHER 'S' in controls level 1 (treatment 1): DSSAT would generate weather "
        "and ignore the weather data supplied. Set WTHER to M."
    ]),
    ("G", "N", [
        "FileX WTHER 'G' in controls level 1 (treatment 1): DSSAT would generate weather "
        "and ignore the weather data supplied. Set WTHER to M."
    ]),
])
def test_wther_and_fname_reported_for_one_row_treatment(filex, weather, wther, fname, expected_problems):
    controls = f"""
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              {wther}     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              {fname}     N     Y     1     N     N     N     N     N     N     Y     N     N     A
"""
    path = filex(text=SAMPLE + controls)
    assert Simulation(path, 1, weather()).check() == expected_problems


def test_two_row_treatment_level_two_w_reported_once(filex, weather):
    treatments = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 COMPONENT 1                1  1  0  1  1  1  1  0  0  0  0  0  1
 1 2 0 0 COMPONENT 2                1  1  0  1  1  1  1  0  0  0  0  0  2
"""
    fields = "*FIELDS" + SAMPLE.split("*FIELDS")[1].split("*SIMULATION CONTROLS")[0]
    controls = """*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 COMPONENT 1
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              M     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              N     N     Y     1     N     N     N     N     N     N     Y     N     N     A
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 2 GE              1     1     S 82056  2150 COMPONENT 2
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 2 ME              W     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 2 OU              N     N     Y     1     N     N     N     N     N     N     Y     N     N     A
"""
    path = filex(text=treatments + fields + controls)
    problems = Simulation(path, 1, weather()).check()
    assert [p for p in problems if "WTHER" in p or "FNAME" in p] == [
        "FileX WTHER 'W' in controls level 2 (treatment 1): DSSAT would generate weather "
        "and ignore the weather data supplied. Set WTHER to M."
    ]


def test_two_rows_both_using_level_one_with_w_reported_once(filex, weather):
    treatments = """*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 COMPONENT 1                1  1  0  1  1  1  1  0  0  0  0  0  1
 1 2 0 0 COMPONENT 2                1  1  0  1  1  1  1  0  0  0  0  0  1
"""
    fields = "*FIELDS" + SAMPLE.split("*FIELDS")[1].split("*SIMULATION CONTROLS")[0]
    controls = """*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 COMPONENT 1
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              W     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              N     N     Y     1     N     N     N     N     N     N     Y     N     N     A
"""
    path = filex(text=treatments + fields + controls)
    problems = Simulation(path, 1, weather()).check()
    assert [p for p in problems if "WTHER" in p or "FNAME" in p] == [
        "FileX WTHER 'W' in controls level 1 (treatment 1): DSSAT would generate weather "
        "and ignore the weather data supplied. Set WTHER to M."
    ]


@pytest.mark.parametrize("controls", [
    # M/N passes
    """
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              M     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              N     N     Y     1     N     N     N     N     N     N     Y     N     N     A
""",
    # Missing METHODS block entirely
    """
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              N     N     Y     1     N     N     N     N     N     N     Y     N     N     A
""",
    # Missing OUTPUTS block entirely
    """
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              M     M     E     R     S     L     R     1     G     R     2
""",
    # Missing both METHODS and OUTPUTS blocks (SAMPLE already has neither)
    "",
    # Level row missing in METHODS / OUTPUTS
    """
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 2 ME              W     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 2 OU              Y     N     Y     1     N     N     N     N     N     N     Y     N     N     A
""",
    # WTHER column missing from METHODS header
    """
@N METHODS     INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              M     E     R     S     L     R     1     G     R     2
""",
    # FNAME column missing from OUTPUTS header
    """
@N OUTPUTS     OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              N     Y     1     N     N     N     N     N     N     Y     N     N     A
""",
    # Blank or -99 WTHER / FNAME
    """
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME                    M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU            -99     N     Y     1     N     N     N     N     N     N     Y     N     N     A
""",
])
def test_valid_controls_and_missing_rows_or_columns_pass(filex, weather, controls):
    path = filex(text=SAMPLE + controls)
    assert Simulation(path, 1, weather()).check() == []


def test_filex_template_controls_pass_wther_and_fname_checks():
    template_data = dict(crop="maize", treatment_name="My treatment", cultivar={"code": "IB0035"},
                         planting=dict(date="2021-03-01", method="S", distribution="R",
                                       population=7.2, row_spacing=75, depth=5))
    weather_rows = [dict(station="TEST", latitude=45.125, longitude=-100.25, elevation=234,
                         date="2021-03-01", srad=20, tmax=25, tmin=10, rain=0)]
    soil_rows = [dict(soil_id="SOIL123456", salb=0.13, slro=60, sldr=0.5, slpf=1,
                      slb=30, slll=0.1, sdul=0.24, ssat=0.45, srgf=1)]
    sim = Simulation(filex_template=template_data, weather=weather_rows, soil=soil_rows, treatment=1)
    assert [p for p in sim.check() if "WTHER" in p or "FNAME" in p] == []


def test_run_treatments_labels_controls_problem(filex, weather):
    from dssatlab import DSSATCheckError, run_treatments
    controls = """
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              W     M     E     R     S     L     R     1     G     R     2
@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT
 1 OU              Y     N     Y     1     N     N     N     N     N     N     Y     N     N     A
"""
    path = filex(text=SAMPLE + controls)
    with pytest.raises(DSSATCheckError) as exc_info:
        run_treatments(filex=path, weather=weather(), treatments=[1])
    problems = exc_info.value.problems
    assert len(problems) == 2
    assert problems[0] == (
        "Scenario 'base', treatment 1: FileX WTHER 'W' in controls level 1 (treatment 1): "
        "DSSAT would generate weather and ignore the weather data supplied. Set WTHER to M."
    )
    assert problems[1] == (
        "Scenario 'base', treatment 1: FileX FNAME 'Y' in controls level 1 (treatment 1): "
        "DSSAT would name its output files after the experiment (UFGA8201.OSU) instead of "
        "Summary.OUT, which dssatlab reads. Set FNAME to N."
    )


def test_simulation_run_raises_check_error_on_controls_problem(filex, weather):
    from dssatlab import DSSATCheckError
    controls = """
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              W     M     E     R     S     L     R     1     G     R     2
"""
    path = filex(text=SAMPLE + controls)
    sim = Simulation(path, 1, weather())
    with pytest.raises(DSSATCheckError) as exc_info:
        sim.run()
    assert any("WTHER 'W'" in p for p in exc_info.value.problems)


def test_treatment_selection_only_checks_its_own_controls_levels(filex, weather):
    controls = """
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 2 GE              1     1     S 82056  2150 SECOND
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              M     M     E     R     S     L     R     1     G     R     2
 2 ME              W     M     E     R     S     L     R     1     G     R     2
"""
    text = SAMPLE.replace(" 2 1 0 0 RAINFED HIGH NITROGEN      1  1  0  1  1  1  2  0  0  0  0  0  1",
                          " 2 1 0 0 RAINFED HIGH NITROGEN      1  1  0  1  1  1  2  0  0  0  0  0  2")
    path = filex(text=text + controls)
    assert Simulation(path, 1, weather()).check() == []
    problems = Simulation(path, 2, weather()).check()
    assert problems == [
        "FileX WTHER 'W' in controls level 2 (treatment 2): DSSAT would generate weather "
        "and ignore the weather data supplied. Set WTHER to M."
    ]


def test_verbose_check_reports_in_filex_section(filex, weather, capsys):
    controls = """
@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL
 1 ME              W     M     E     R     S     L     R     1     G     R     2
"""
    path = filex(text=SAMPLE + controls)
    Simulation(path, 1, weather()).check(verbose=True)
    captured = capsys.readouterr().out
    assert "FileX:" in captured
    assert "FileX WTHER 'W' in controls level 1 (treatment 1)" in captured


