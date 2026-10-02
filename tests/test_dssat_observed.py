"""FileA/FileT reading and direct Evaluation, without running DSSAT (#104)."""

from datetime import date
from pathlib import Path
import shutil

import pytest

import dssatlab as dl
from dssatlab.observed import _load_observed
from dssatlab.outputs import _SUMMARY_DATES
from dssatlab.runner import RunResult


FIXTURES = Path(__file__).parent / "fixtures" / "dssat_observed"


def observed_file(tmp_path, text, name="trial.MZT"):
    path = tmp_path / name
    path.write_text(text, encoding="ascii")
    return path


def filex(tmp_path, sdate="81279"):
    text = (FIXTURES / "KSAS8101.WHX").read_text().replace("81279", sdate)
    path = tmp_path / "TRIAL.mzx"
    path.write_text(text)
    return path


@pytest.mark.parametrize("header", [
    "*EXP. DATA ({kind}):", "*EXP.DATA ({kind}):", "*EXP.DATA({kind}):",
    "*EXPT.DATA  ({kind}):", "*EXPT.DATA ({kind}):", "*EXP.DATA ({kind})  NAME",
])
@pytest.mark.parametrize("kind", ["A", "T"])
def test_stock_header_spellings(tmp_path, header, kind):
    table_text = ("@TRNO HWAM\n1 5\n" if kind == "A"
                  else "@TRNO DATE LAID\n1 2024001 2\n")
    path = observed_file(tmp_path, "  " + header.format(kind=kind) + "\n" + table_text,
                         "trial.SBT" if kind == "A" else "trial.SBA")
    expected = (dict(date=None, HWAM=5.) if kind == "A"
                else dict(date="2024-01-01", LAID=2.))
    assert dl.read_dssat_observed(path) == [dict(scenario="base", treatment=1, **expected)]


@pytest.mark.parametrize("extension", ["SBA", "sba", "SBT", "sbt"])
def test_header_kind_from_extension(tmp_path, extension):
    kind = extension[-1].upper()
    table_text = ("@TRNO HWAM\n1 5\n" if kind == "A"
                  else "@TRNO DATE LAID\n1 2024001 2\n")
    rows = dl.read_dssat_observed(observed_file(tmp_path, "*EXP:\n" + table_text,
                                               "trial." + extension))
    expected = (dict(date=None, HWAM=5.) if kind == "A"
                else dict(date="2024-01-01", LAID=2.))
    assert rows == [dict(scenario="base", treatment=1, **expected)]


@pytest.mark.parametrize("text,name,lines", [
    ("*EXP:\n", "trial.txt", "line 1"),
    ("! no experiment header\n", "trial.SBA", "line 1"),
    ("*EXP.DATA(A):\n*EXP.DATA (T) NAME\n", "trial.SBA", "line 1, 2"),
    ("*EXP.DATA(A):\n*EXP:\n", "trial.SBT", "line 1, 2"),
    ("*EXP.DATA(A):\n*EXP:\n", "trial.txt", "line 1, 2"),
])
def test_invalid_header_kind_is_one_problem(tmp_path, text, name, lines):
    path = observed_file(tmp_path, text, name)
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.read_dssat_observed(path)
    assert len(caught.value.problems) == 1
    problem = caught.value.problems[0]
    assert all(part in problem for part in
               (str(path), lines, "FileA/FileT", "Checked", "(A)", "(T)", ".??A/.??T"))


@pytest.mark.parametrize("kind", ["A", "T"])
def test_repeated_headers_of_one_kind(tmp_path, kind):
    table_text = ("@TRNO HWAM\n1 5\n" if kind == "A"
                  else "@TRNO DATE LAID\n1 2024001 2\n")
    text = f"*EXP.DATA({kind}):\n" + table_text + "*EXP:\n" + table_text
    path = observed_file(tmp_path, text, "trial.SB" + kind)
    expected = (dict(date=None, HWAM=5.) if kind == "A"
                else dict(date="2024-01-01", LAID=2.))
    assert dl.read_dssat_observed(path) == [dict(scenario="base", treatment=1, **expected)]


@pytest.mark.parametrize("filename,yield_value,anthesis", [
    ("UFGA8201.MZA", 2929., "1982-05-12"),
    ("KSAS8101.WHA", 2317., "1982-05-21"),
])
def test_filea_samples(tmp_path, filename, yield_value, anthesis):
    for source in FIXTURES.glob(filename[:-1] + "*"):
        shutil.copyfile(source, tmp_path / source.name)
    rows = dl.read_dssat_observed(tmp_path / filename)
    assert len(rows) == 2
    assert rows[0]["HWAM"] == yield_value
    assert rows[0]["ADAT"] == anthesis
    assert rows[0]["date"] is None
    assert rows[0]["scenario"] == "base" and rows[0]["treatment"] == 1
    assert "GN%M" not in rows[0] and "SNAM" not in rows[0]
    assert _load_observed(rows)[1] == []


def test_filet_sample_two_tables(tmp_path):
    for suffix in ("MZT", "MZX"):
        shutil.copyfile(FIXTURES / f"UFGA8201.{suffix}", tmp_path / f"UFGA8201.{suffix}")
    rows = dl.read_dssat_observed(tmp_path / "UFGA8201.MZT")
    assert len(rows) == 2  # The second table has only unsupported soil measurements.
    assert rows[0] == dict(scenario="base", treatment=1, date="1982-02-26",
                           CWAD=0., LAID=0., GWAD=0.)
    assert rows[1]["LAID"] == .17
    assert "SW1D" not in rows[1] and "VN%D" not in rows[1]
    assert _load_observed(rows)[1] == []


@pytest.mark.parametrize("sdate,code,expected", [
    ("81279", "82150", "1982-05-30"),
    ("99335", "00010", "2000-01-10"),
    ("99335", "00366", "2000-12-31"),
    ("99335", "99334", "1999-11-30"),
    ("99335", "98365", "2098-12-31"),
    ("81279", "81279", "1981-10-06"),
    ("81279", "300", "1981-10-27"),
    ("81279", "010", "1982-01-10"),
    ("81279", "279", "1981-10-06"),
])
def test_short_dates_use_sdate_and_case_insensitive_filex(tmp_path, sdate, code, expected):
    filex(tmp_path, sdate)
    rows = dl.read_dssat_observed(observed_file(
        tmp_path, f"*EXP. DATA (T)\n@TRNO DATE LAID\n1 {code} 2\n"))
    assert rows[0]["date"] == expected
    assert _load_observed(rows)[1] == []


def test_bare_days_cross_year_and_use_each_treatments_start(tmp_path):
    path = filex(tmp_path, "99335")
    text = path.read_text()
    # Both sample treatments reference control level 1; give treatment 2 its own.
    lines = text.splitlines()
    second = next(i for i, line in enumerate(lines) if line.startswith(" 2 1"))
    lines[second] = lines[second][:-1] + "2"
    control = next(line for line in lines if line.startswith(" 1 GE"))
    lines.append(control.replace(" 1 GE", " 2 GE").replace("99335", "00001"))
    path.write_text("\n".join(lines) + "\n")
    rows = dl.read_dssat_observed(observed_file(tmp_path,
        "*EXP. DATA (T)\n@TRNO DATE LAID\n1 365 1\n1 1 2\n2 365 3\n"))
    assert [r["date"] for r in rows] == ["1999-12-31", "2000-01-01", "2000-12-30"]


def test_full_dates_kind_from_header_and_no_filex_read(tmp_path, monkeypatch):
    def forbidden(*args):
        pytest.fail("Seven-digit dates must not read a FileX")
    monkeypatch.setattr("dssatlab.dssat_observed._read_filex", forbidden)
    path = observed_file(tmp_path, "*EXP. DATA (A)\n@TRNO HWAM "
                         + " ".join(sorted(_SUMMARY_DATES)) + "\n1 5 "
                         + " ".join(["2024060"] * 6) + "\n", "any.crop")
    rows = dl.read_dssat_observed(str(path))
    assert all(rows[0][name] == "2024-02-29" for name in _SUMMARY_DATES)
    assert _load_observed(rows)[1] == []
    path.write_text("*EXP. DATA (T)\n@TRNO DATE LAID\n1 2024366 2\n")
    assert dl.read_dssat_observed(path)[0]["date"] == "2024-12-31"
    assert "read_dssat_observed" in dl.__all__


def test_tables_merge_and_missing_measurements_drop(tmp_path):
    path = observed_file(tmp_path,
        "*EXP. DATA (T)\n@TRNO DATE LAID YEAR DOY RUNNO SW1D\n"
        "1 2024001 2 2024 1 1 bad\n2 2024001 -99.00 2024 1 2 5\n"
        "! comment\n\n@TRNO DATE CWAD LAID\n1 2024001 100 -99\n"
        "2 2024002 -9.9e1 -99.0\n1 2024002 200 3\n")
    rows = dl.read_dssat_observed(path)
    assert rows == [dict(scenario="base", treatment=1, date="2024-01-01", LAID=2., CWAD=100.),
                    dict(scenario="base", treatment=1, date="2024-01-02", CWAD=200., LAID=3.)]
    assert _load_observed(rows)[1] == []
    path.write_text("*EXP. DATA (A)\n@TRNO HWAM ADAT\n1 -99.0 -99\n")
    assert dl.read_dssat_observed(path) == []
    path.write_text("*EXP. DATA (T)\n@TRNO DATE LAID\n1 -99 -99\n")
    assert dl.read_dssat_observed(path) == []
    path.write_text("*EXP. DATA (T)\n@TRNO DATE LAID\n1 -99 2\n")
    with pytest.raises(dl.DSSATCheckError, match="missing DATE"):
        dl.read_dssat_observed(path)


def test_all_problems_reported_with_path_and_line(tmp_path):
    path = observed_file(tmp_path,
        "*EXP. DATA (T)\n@TRNO DATE LAID CWAD\n"
        "1 2023366 bad nan\n2 82150 1 2\nwrong 2024001 inf 3\n")
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.read_dssat_observed(path)
    problems = caught.value.problems
    assert len(problems) == 6
    assert all(str(path) in p and "line " in p for p in problems)
    assert any("line 3" in p and "DATE" in p for p in problems)
    assert any("line 4" in p and "trial.MZX" in p for p in problems)
    assert any("line 5" in p and "TRNO" in p for p in problems)


def test_treatment_absent_from_filex_and_bad_anchor(tmp_path):
    anchor = filex(tmp_path)
    path = observed_file(tmp_path, "*EXP. DATA (A)\n@TRNO HWAM ADAT\n9 bad 82150\n")
    with pytest.raises(dl.DSSATCheckError, match="treatment number 9") as caught:
        dl.read_dssat_observed(path)
    assert len(caught.value.problems) == 2
    anchor.write_text(anchor.read_text().replace("81279", "81367"))
    path.write_text("*EXP. DATA (A)\n@TRNO ADAT\n1 82150\n")
    with pytest.raises(dl.DSSATCheckError, match="SDATE"):
        dl.read_dssat_observed(path)


@pytest.mark.parametrize("code", ["2024000", "2023366", "2024367", "0", "367", "82000", "82367", "2024-01-01"])
def test_invalid_dates(tmp_path, code):
    filex(tmp_path)
    path = observed_file(tmp_path, f"*EXP. DATA (T)\n@TRNO DATE LAID\n1 {code} 2\n")
    with pytest.raises(dl.DSSATCheckError, match="line 3.*bad date"):
        dl.read_dssat_observed(path)


def test_missing_file_unknown_kind_and_malformed_tables(tmp_path):
    path = tmp_path / "missing.MZA"
    with pytest.raises(dl.DSSATCheckError, match="line 1.*cannot read"):
        dl.read_dssat_observed(path)
    path.write_text("@TRNO HWAM\n1 bad\n")
    with pytest.raises(dl.DSSATCheckError, match="not a FileA/FileT") as caught:
        dl.read_dssat_observed(path)
    assert len(caught.value.problems) == 2
    path.write_text("*EXP. DATA (T)\n@TRNO LAID\n1 2\n@TRNO DATE LAID\n1 2024001\n")
    with pytest.raises(dl.DSSATCheckError) as caught:
        dl.read_dssat_observed(path)
    assert len(caught.value.problems) == 2


def test_conflicting_measurements_are_reported(tmp_path):
    path = observed_file(tmp_path, "*EXP. DATA (A)\n@TRNO HWAM\n1 2\n@TRNO HWAM\n1 3\n")
    with pytest.raises(dl.DSSATCheckError, match="line 5.*conflicting"):
        dl.read_dssat_observed(path)


def table(row):
    header = "".join(f"{name:>12}" for name in row)
    return "@" + header[1:] + "\n" + "".join(f"{value:>12}" for value in row.values()) + "\n"


@pytest.mark.parametrize("filename", ["UFGA8201.MZA", "UFGA8201.MZT", "KSAS8101.WHA"])
def test_sample_rows_pass_unchanged_to_evaluate(tmp_path, filename):
    rows = dl.read_dssat_observed(FIXTURES / filename)
    results = {}
    for row in rows:
        treatment = row["treatment"]
        run_dir = tmp_path / str(treatment)
        run_dir.mkdir(exist_ok=True)
        result = RunResult(returncode=0, run_dir=run_dir, outputs=[], stdout_tail="")
        results["base", treatment] = result
        measurements = {k: v for k, v in row.items() if k not in {"scenario", "treatment", "date"}}
        if row["date"] is None:
            measurements = {k: int(date.fromisoformat(v).strftime("%Y%j"))
                            if k in _SUMMARY_DATES else v for k, v in measurements.items()}
            (run_dir / "Summary.OUT").write_text(table(dict(RUNNO=1, TRNO=treatment, TNAM="test", **measurements)))
        else:
            day = date.fromisoformat(row["date"])
            path = run_dir / "PlantGro.OUT"
            content = table(dict(YEAR=day.year, DOY=day.timetuple().tm_yday, **measurements))
            with path.open("a") as stream:
                stream.write(f"*RUN 1 : test\n TREATMENT {treatment} : test\n" + content)
    evaluation = dl.evaluate(results, rows)
    assert evaluation.pairs and all(pair["error"] == 0 for pair in evaluation.pairs)


def test_rows_pass_unchanged_to_dataframe():
    pd = pytest.importorskip("pandas")
    rows = dl.read_dssat_observed(FIXTURES / "UFGA8201.MZA")
    pd.testing.assert_frame_equal(dl.to_dataframe(rows), pd.DataFrame(rows))
