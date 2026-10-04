"""Tests for rotation date checks: simulation start, last known end, order, and closure."""

from copy import deepcopy
from pathlib import Path

import pytest

from dssatlab import DSSATCheckError
from dssatlab.filex_skeleton import write_filex
from dssatlab.filex_template import _check_filex_template
from test_filex_template import data, data_dir, rows
from test_rotation_template import genotype, rotation


def _mutated_rotation(base, case):
    """Return a deep copy of base rotation mutated to trigger a specific date check problem."""
    rot = deepcopy(base)
    if case == "fallow_first":
        rot["rotation"] = [
            dict(crop="fallow", end_date="1978-11-14"),
            deepcopy(rot["rotation"][2]),
            deepcopy(rot["rotation"][3]),
        ]
    elif case == "last_no_end":
        wheat = deepcopy(rot["rotation"][2])
        wheat.pop("harvest_date", None)
        wheat["planting"]["date"] = "1978-11-20"
        rot["rotation"][-1] = wheat
    elif case == "order_planting":
        rot["rotation"][2]["planting"]["date"] = "1978-05-30"
    elif case == "order_fallow":
        rot["rotation"][1]["end_date"] = "1978-03-10"
    elif case == "cycle_closure":
        rot["rotation"][-1]["end_date"] = "1979-03-20"
    return rot


_EXACT_CASES = [
    ("fallow_first",
     "FileX template, rotation[1]: a leading fallow needs start_date. "
     "Supply start_date before end_date."),
    ("last_no_end",
     "FileX template, rotation[4]: the last component needs a known end so the next cycle can start on time. "
     "Make it a fallow with end_date, or give it a harvest_date."),
    ("order_planting",
     "FileX template, rotation[3], planting date: 1978-05-30 is not after rotation[2]'s end (1978-11-14). "
     "DSSAT would move it a year later. Supply rotation dates in order."),
    ("order_fallow",
     "FileX template, rotation[2], end_date: 1978-03-10 is not after rotation[1]'s end (1978-03-15). "
     "DSSAT would move it a year later. Supply rotation dates in order."),
    ("cycle_closure",
     "FileX template, rotation: the last component ends on 1979-03-20 (day 79 of the year), not before "
     "the first planting's day of the year (day 74, 1978-03-15); DSSAT would start the next cycle a year late. "
     "End the last component before day 74, for example on 1979-03-14."),
]


@pytest.mark.parametrize("case,expected_message", _EXACT_CASES)
def test_exact_date_check_messages(rotation, genotype, rows, tmp_path, case, expected_message):
    rot = _mutated_rotation(rotation, case)
    problems = _check_filex_template(rot, genotype)
    assert problems == [expected_message]

    with pytest.raises(DSSATCheckError) as error:
        write_filex(rot, *rows, tmp_path, data_dir=genotype)
    assert error.value.problems == [expected_message]


def test_leap_year_cycle_closure(rotation, genotype, rows, tmp_path):
    rotation["rotation"][-1]["end_date"] = "1980-03-14"
    expected = (
        "FileX template, rotation: the last component ends on 1980-03-14 (day 74 of the year), not before "
        "the first planting's day of the year (day 74, 1978-03-15); DSSAT would start the next cycle a year late. "
        "End the last component before day 74, for example on 1980-03-13."
    )
    assert _check_filex_template(rotation, genotype) == [expected]

    with pytest.raises(DSSATCheckError) as error:
        write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert error.value.problems == [expected]


def test_unknown_cultivar_does_not_hide_cycle_closure(rotation, genotype):
    rotation["rotation"][0]["cultivar"]["code"] = "ZZ9999"
    rotation["rotation"][-1]["end_date"] = "1979-03-20"
    problems = _check_filex_template(rotation, genotype)
    assert len(problems) == 2
    assert any("rotation[1]" in p and "ZZ9999" in p for p in problems)
    assert any("last component ends on 1979-03-20" in p for p in problems)


def test_bad_population_does_not_hide_date_order(rotation, genotype):
    rotation["rotation"][2]["planting"]["population"] = -1
    rotation["rotation"][2]["planting"]["date"] = "1978-05-30"
    problems = _check_filex_template(rotation, genotype)
    assert len(problems) == 2
    assert any("rotation[3]" in p and "population" in p for p in problems)
    assert any("1978-05-30 is not after rotation[2]'s end" in p for p in problems)


@pytest.mark.parametrize("year,end", [("1978", "1979-01-02"), ("1936", "1936-12-31")])
def test_first_planting_day_one_cycle_closure(rotation, genotype, rows, tmp_path, year, end):
    rotation["rotation"][0]["planting"]["date"] = f"{year}-01-01"
    rotation["rotation"][1]["end_date"] = f"{year}-06-01"
    rotation["rotation"][2]["planting"]["date"] = f"{year}-06-02"
    rotation["rotation"][3]["end_date"] = end
    expected = (
        "FileX template, rotation: the first planting is on day 1 of the year "
        f"({year}-01-01), so the last component cannot end before it in the year; "
        "DSSAT would start the next cycle a year late. Plant the first crop after January 1."
    )
    assert _check_filex_template(rotation, genotype) == [expected]

    with pytest.raises(DSSATCheckError) as error:
        write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert error.value.problems == [expected]


def test_harvest_date_followed_by_next_day_planting_ok(rotation, genotype, rows, tmp_path):
    wheat = deepcopy(rotation["rotation"][2])
    wheat["planting"]["date"] = "1978-08-02"
    wheat["harvest_date"] = "1979-03-14"
    maize = deepcopy(rotation["rotation"][0])
    maize["harvest_date"] = "1978-08-01"
    rot = dict(treatment_name="TwoCrop", rotation=[maize, wheat])
    assert _check_filex_template(rot, genotype) == []
    path = write_filex(rot, *rows, tmp_path, data_dir=genotype)
    assert path.is_file()


def test_malformed_component_plus_date_problem_both_reported(rotation, genotype, rows, tmp_path):
    rotation["rotation"][2]["planting"]["date"] = "1978-05-30"
    rotation["rotation"][3] = dict(crop="fallow", end_date="bad")
    problems = _check_filex_template(rotation, genotype)
    assert len(problems) == 2
    assert any("1978-05-30 is not after rotation[2]'s end" in p for p in problems)
    assert any("rotation[4], end_date:" in p and "quoted YYYY-MM-DD" in p for p in problems)

    with pytest.raises(DSSATCheckError) as error:
        write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert error.value.problems == problems


def test_probe_a_fixture_has_no_problems(rotation, genotype, rows, tmp_path):
    assert _check_filex_template(rotation, genotype) == []
    path = write_filex(rotation, *rows, tmp_path, data_dir=genotype)
    assert path.name == "TEST7801.SQX"
    assert path.is_file()


def test_skip_malformed_components_never_crash(rotation, genotype):
    rot = dict(treatment_name="Invalid", rotation=[
        None,
        dict(crop="fallow", end_date="bad"),
        dict(crop="wheat", planting={}),
        dict(crop="fallow", end_date="1979-03-20"),
    ])
    problems = _check_filex_template(rot, genotype)
    # The malformed components are reported with shape problems, and date checks don't crash
    assert any("rotation[1]: expected a dict" in p for p in problems)
    assert any("rotation[2], end_date:" in p and "bad" in p for p in problems)
    assert any("rotation[3], planting:" in p and "non-empty dict" in p for p in problems)
    assert any("rotation[3]: missing required field 'cultivar'" in p for p in problems)
    # Date checks requiring valid components 1 and 3 are skipped
    assert not any("first component must be a crop" in p for p in problems)
    assert not any("DSSAT would start the next cycle a year late" in p for p in problems)
