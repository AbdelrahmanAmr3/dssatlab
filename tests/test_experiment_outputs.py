"""Experiment-named output lookup through readers and RunResult (B4)."""
from datetime import date

import pytest

import dssatlab
from dssatlab.runner import RunResult


SUMMARY = "@RUNNO TRNO TNAM.... HWAM\n     1    1     BASE   42\n"
DAILY = "*RUN 1\n TREATMENT 1 : BASE\n@YEAR DOY VALUE\n 1982 056    42\n"
EVALUATE = "@RUNNO TRNO HWAMS\n1 1 42\n"
CASES = [
    ("summary", "Summary.OUT", "SU", SUMMARY, {"RUNNO": 1, "TRNO": 1, "TNAM": "BASE", "HWAM": 42}),
    ("plant_growth", "PlantGro.OUT", "PG", DAILY, None),
    ("soil_water", "SoilWat.OUT", "SW", DAILY, None),
    ("plant_nitrogen", "PlantN.OUT", "PN", DAILY, None),
    ("weather", "Weather.OUT", "WE", DAILY, None),
    ("dssat_evaluation", "Evaluate.OUT", "EV", EVALUATE, {"RUNNO": 1, "TRNO": 1, "HWAMS": 42}),
]


@pytest.mark.parametrize("method,filename,code,text,expected", CASES)
@pytest.mark.parametrize("suffix_case", ["upper", "lower", "mixed"])
def test_experiment_named_readers_and_result(tmp_path, method, filename, code, text, expected, suffix_case):
    suffix = {"upper": "O" + code, "lower": ("O" + code).lower(),
              "mixed": "o" + code[0] + code[1].lower()}[suffix_case]
    path = tmp_path / ("X." + suffix)
    path.write_text(text)
    # A directory with a matching suffix is not an output file.
    (tmp_path / ("Y.O" + code)).mkdir()
    result = RunResult(0, tmp_path, [path], "finished")
    expected = expected or dict(YEAR=1982, DOY=56, VALUE=42, DATE=date(1982, 2, 25), RUNNO=1, TRNO=1)
    assert getattr(dssatlab, "read_" + method)(str(tmp_path)) == [expected]
    assert getattr(result, method)() == [expected]


@pytest.mark.parametrize("method,filename,code,text,expected", CASES)
def test_standard_name_wins(tmp_path, method, filename, code, text, expected):
    (tmp_path / filename).write_text(text)
    (tmp_path / ("X.O" + code)).write_text("malformed")
    (tmp_path / ("Y.O" + code)).write_text("malformed")
    assert getattr(dssatlab, "read_" + method)(tmp_path)


@pytest.mark.parametrize("method,filename,code,text,expected", CASES)
def test_ambiguous_experiment_names(tmp_path, method, filename, code, text, expected):
    for name in ("X.O" + code, "Y.o" + code.lower()):
        (tmp_path / name).write_text(text)
    with pytest.raises(dssatlab.DSSATOutputError) as caught:
        getattr(dssatlab, "read_" + method)(tmp_path)
    message = str(caught.value)
    assert "X.O" + code in message and "Y.o" + code.lower() in message
    assert "Checked" in message and "Keep one experiment" in message


@pytest.mark.parametrize("method,filename,code,text,expected", CASES)
def test_missing_names_both_forms(tmp_path, method, filename, code, text, expected):
    with pytest.raises(dssatlab.DSSATOutputError) as caught:
        getattr(dssatlab, "read_" + method)(tmp_path)
    assert filename + " or <experiment>.O" + code in str(caught.value)
