"""IC surface details and initial conditions off through checks and FileX copies."""

from copy import deepcopy
from datetime import date, timedelta

import pytest

from dssatlab import Simulation, write_experiment_template
from dssatlab.filex import _section_row
from dssatlab.filex_skeleton import _write_template_simulation
from dssatlab.filex_write import _write_management
from test_filex_template import data, data_dir, rows


HEADER = "@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME"
FILEX = """*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 First                     1  1  0  1  1  0  0  0  0  0  0  0  1
 2 1 0 0 Second                    1  1  0  1  1  0  0  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0001 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910014 Field

*INITIAL CONDITIONS
@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME
 1    MZ 82056    10    20   0.5   0.8   -99   100     1     2    50    10    -99
@C  ICBL  SH2O  SNH4  SNO3
 1    15   0.2     1     2

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 82056  2150 Example                   MZCER048
@N METHODS     WTHER
 1 ME              M
@N OPTIONS     WATER NITRO
 1 OP              Y     Y
@N OUTPUTS     FNAME OVVEW SUMRY FROPT
 1 OU              N     Y     Y     1
"""
DETAILS = [
    ("root_mass", "ICRT", 120, -1, "0 or greater"),
    ("nodule_mass", "ICND", 15, -1, "0 or greater"),
    ("rhizobia_number", "ICRN", 0.4, 1.1, "0 to 1"),
    ("rhizobia_effectiveness", "ICRE", 0.8, -0.1, "0 to 1"),
    ("residue_n", "ICREN", 1.5, 101, "0 to 100"),
    ("residue_p", "ICREP", 0.2, -1, "0 to 100"),
    ("residue_incorporation", "ICRIP", 80, 101, "0 to 100"),
    ("residue_depth", "ICRID", 20, -1, "0 or greater"),
]


@pytest.fixture
def sim(tmp_path):
    path = tmp_path / "UFGA8201.MZX"
    path.write_text(FILEX, encoding="latin-1")
    weather = [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                    date="1982-02-25", srad=20, tmax=25, tmin=10, rain=0)]
    ic = dict(date="1982-02-25", layers=[dict(depth=15, water=0.2, nh4=1, no3=2)])
    return Simulation(path, 1, weather,
                      management={"treatments": {1: {"initial_conditions": ic}}})


def conditions(sim):
    return sim.management["treatments"][1]["initial_conditions"]


def copy_text(sim, tmp_path):
    path = tmp_path / "copy.MZX"
    path.write_bytes(sim.filex.read_bytes())
    _write_management(path, sim.treatment, sim.management)
    return path.read_text(encoding="latin-1")


@pytest.mark.parametrize("value,expected", [(1000.0, "  1000"), (100.0, " 100.0"),
                                           (1250, "  1250")])
def test_residue_mass_keeps_icres_leading_blank(sim, tmp_path, value, expected):
    conditions(sim)["residue_mass"] = value
    assert sim.check(verbose=False) == []
    text = copy_text(sim, tmp_path)
    row = text.rsplit(HEADER, 1)[1].splitlines()[1]
    assert row[38:44] == "   -99"  # ICWD stays separate from ICRES.
    assert row[44:50] == expected
    assert sim.filex.read_text(encoding="latin-1") == FILEX


@pytest.mark.parametrize("value", [123456, 1234.5])
def test_full_width_residue_mass_rejected_before_folder_creation(sim, value):
    from dssatlab import DSSATCheckError

    conditions(sim)["residue_mass"] = value
    before = sorted(sim.filex.parent.iterdir())
    problems = sim.check(verbose=False)
    assert any("column ICRES" in p and "needs one leading blank" in p for p in problems)
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems
    assert sorted(sim.filex.parent.iterdir()) == before
    assert sim.filex.read_text(encoding="latin-1") == FILEX


@pytest.mark.parametrize("field,column,value,bad,span", DETAILS)
def test_detail_written_in_new_level(sim, tmp_path, field, column, value, bad, span):
    conditions(sim)[field] = value
    original = sim.filex.read_bytes()
    inputs = deepcopy(sim.management)
    assert sim.check(verbose=False) == []
    text = copy_text(sim, tmp_path)
    assert _section_row(text, "TREATMENTS", "N", 1, ("IC",))["IC"] == "2"
    assert _section_row(text, "TREATMENTS", "N", 2, ("IC",))["IC"] == "1"
    row = _section_row(text, "INITIAL CONDITIONS", "C", 2, (column,))
    assert row[column] == str(value)
    assert all(row[c] == "-99" for f, c, *_ in DETAILS if f != field)
    assert sim.filex.read_bytes() == original and sim.management == inputs


@pytest.mark.parametrize("field,column,value,bad,span", DETAILS)
@pytest.mark.parametrize("kind", ["range", "bool", "non-number", "non-finite"])
def test_detail_rejected_with_value_and_range(sim, field, column, value, bad, span, kind):
    invalid = {"range": bad, "bool": True, "non-number": "bad", "non-finite": float("inf")}[kind]
    conditions(sim)[field] = invalid
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert f"field '{field}'" in problems[0] and repr(invalid) in problems[0]
    assert span in problems[0] and "Supply" in problems[0]


@pytest.mark.parametrize("endpoint", [0, 1])
def test_detail_range_endpoints_accepted(sim, endpoint):
    for field, _, _, _, span in DETAILS:
        conditions(sim)[field] = endpoint * (100 if span == "0 to 100" else 1)
    assert sim.check(verbose=False) == []


@pytest.mark.parametrize("field,column,value,bad,span", DETAILS)
def test_missing_detail_column_required_only_when_given(sim, tmp_path, field, column, value, bad, span):
    # Rename without shifting fixed-width cells: this header lacks the requested column.
    sim.filex.write_text(FILEX.replace(f" {column} ", f" {'X' * len(column)} "), encoding="latin-1")
    assert sim.check(verbose=False) == []
    text = copy_text(sim, tmp_path)
    assert _section_row(text, "TREATMENTS", "N", 1, ("IC",))["IC"] == "2"
    conditions(sim)[field] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert f"header is missing columns {column}. Supply the needed columns." in problems[0]


@pytest.mark.parametrize("has_section", [True, False])
def test_off_repoints_only_ic_and_adds_no_level(sim, tmp_path, has_section):
    if not has_section:
        start, end = FILEX.index("*INITIAL CONDITIONS"), FILEX.index("*SIMULATION CONTROLS")
        sim.filex.write_text(FILEX[:start] + FILEX[end:], encoding="latin-1")
    sim.management["treatments"][1]["initial_conditions"] = "off"
    original = sim.filex.read_text(encoding="latin-1")
    assert sim.check(verbose=False) == []
    text = copy_text(sim, tmp_path)
    old = next(line for line in original.splitlines() if line.startswith(" 1 1 0 0"))
    new = old[:43] + "  0" + old[46:]
    assert text == original.replace(old, new, 1)
    assert sim.filex.read_text(encoding="latin-1") == original


def test_off_keeps_weather_coverage_problem(sim):
    sim.management["treatments"][1]["initial_conditions"] = "off"
    sim.weather[0]["date"] = "1982-02-26"
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert "Simulation start date '1982-02-25' is not covered by weather data" in problems[0]


@pytest.mark.parametrize("value", [False, None, 0, "OFF", "other", [], True])
def test_invalid_section_names_quoted_off(sim, value):
    sim.management["treatments"][1]["initial_conditions"] = value
    problems = sim.check(verbose=False)
    assert len(problems) == 1
    assert 'expected a dict or the quoted string "off"' in problems[0]
    assert "omit the section to keep the FileX level" in problems[0]


@pytest.mark.parametrize("yaml_value", ["off", "null", "42", '"other"', '"off"'])
def test_yaml_requires_quoted_off(sim, tmp_path, yaml_value):
    pytest.importorskip("yaml")
    path = tmp_path / "experiment.yaml"
    path.write_text(f"treatments:\n  1:\n    initial_conditions: {yaml_value}\n")
    sim.management = path
    problems = sim.check(verbose=False)
    if yaml_value == '"off"':
        assert problems == []
    else:
        assert len(problems) == 1 and 'or the quoted string "off"' in problems[0]


def test_written_experiment_template_documents_details_and_loads(sim, tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "experiment.yaml"
    write_experiment_template(path)
    text = path.read_text(encoding="utf-8")
    for field, column, *_ in DETAILS:
        assert any(field in line and column in line for line in text.splitlines())
    assert 'initial_conditions: "off"' in text
    (tmp_path / "MZCER048.CUL").write_text("@VAR#  VAR-NAME\nIB0035 Example\n")
    sim.weather = [dict(sim.weather[0], date=(date(1982, 2, 25) + timedelta(days=i)).isoformat())
                   for i in range(35)]
    sim.management = path
    assert sim.check(verbose=False) == []
    for field, *_ in DETAILS:
        text = text.replace(f"# {field}:", f"{field}:")
    path.write_text(text, encoding="utf-8")
    assert sim.check(verbose=False) == []


@pytest.mark.parametrize("off", [False, True])
def test_l2_accepts_details_and_off(tmp_path, monkeypatch, data, data_dir, rows, off):
    executable = data_dir / "DSCSM048.EXE"
    executable.write_text("unit-test executable")
    executable.chmod(0o755)
    for suffix in ("ECO", "SPE"):
        (data_dir / "Genotype" / f"MZCER048.{suffix}").write_text("unit-test genotype")
    monkeypatch.chdir(tmp_path)
    ic = "off" if off else dict(date="2021-03-01", layers=[dict(depth=30, water=0.2, nh4=1, no3=2)],
                               **{field: value for field, _, value, *_ in DETAILS})
    management = {"treatments": {1: {"initial_conditions": ic}}}
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     executable=executable, management=management)
    assert sim.check(verbose=False) == []
    path = _write_template_simulation(sim, management)
    text = path.read_text(encoding="latin-1")
    assert _section_row(text, "TREATMENTS", "N", 1, ("IC",))["IC"] == ("0" if off else "1")
    if off:
        block = text.split("*INITIAL CONDITIONS", 1)[1].split("\n*", 1)[0]
        assert not any(line.strip() and not line.startswith("@") for line in block.splitlines())
    else:
        surface = _section_row(text, "INITIAL CONDITIONS", "C", 1, ("ICRT",))
        for _, column, value, *_ in DETAILS:
            assert surface[column] == str(value)
