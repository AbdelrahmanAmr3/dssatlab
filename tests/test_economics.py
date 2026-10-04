"""Net returns at expected prices, tested through the public API."""

from copy import deepcopy
import os
from pathlib import Path

import pytest

import dssatlab as lab


COLUMNS = "GRAN BYPR BASE NFER NCOS IRRI IRCO SCOS RESM PCOS PFER KCOS KFER".split()


def price_section(crop="MZ", treatment=1, components=None, columns=None, spaced=True):
    """Build a complete Price file section; unspecified components are ignored."""
    columns = COLUMNS if columns is None else columns
    components = components or {}
    values = {name: components.get(name, (-1, 0, 0, 0)) for name in columns}
    heading = f"* TREATMENT{' ' if spaced else ''}{treatment}\n"
    text = f"* {crop}\n" + heading + "@PRAM " + " ".join(columns) + "\n"
    for index, parameter in enumerate(("IDIS", "PAR1", "PAR2", "PAR3")):
        text += parameter + " " + " ".join(str(values[name][index]) for name in columns) + "\n"
    return text


def write_price(tmp_path, text):
    path = tmp_path / "case.PRI"
    path.write_text("* PRICE-COST_FILE : test\n\n! prices and costs\n" + text, encoding="utf-8")
    return path


def test_all_formula_terms_and_input_copies(tmp_path):
    components = {
        "GRAN": (0, 200, 0, 0), "BYPR": (0, 50, 0, 0), "BASE": (0, 100, 0, 0),
        "NFER": (0, 2, 0, 0), "NCOS": (0, 3, 0, 0), "IRRI": (0, 4, 0, 0),
        "IRCO": (0, 5, 0, 0), "SCOS": (0, 6, 0, 0), "RESM": (0, 7, 0, 0),
        "PCOS": (0, 8, 0, 0), "PFER": (0, 9, 0, 0), "KCOS": (0, 10, 0, 0),
        "KFER": (0, 11, 0, 0),
    }
    path = write_price(tmp_path, price_section(components=components))
    rows = [{"CR": "MZ", "TRNO": 1, "scenario": "wet", "treatment": 99, "R#": 2,
             "HWAH": 5000, "BWAH": 2000, "NICM": 10, "NI#M": 2, "IRCM": 30,
             "IR#M": 3, "DWAP": 4, "RECM": 2000, "PICM": 5, "PI#M": 2,
             "KICM": 6, "KI#M": 3, "net_return": -123}]
    original = deepcopy(rows)
    out = lab.net_returns(rows, path)
    # 1000 + 100 - 100 - 20 - 6 - 120 - 15 - 24 - 14 - 40 - 18 - 60 - 33.
    assert out == [dict(rows[0], net_return=650.0)]
    assert isinstance(out[0]["net_return"], float)
    assert out is not rows and out[0] is not rows[0]
    assert rows == original


@pytest.mark.parametrize("idis,par1,par2,par3,expected", [
    (-1, 999, 0, 0, 0.0), (0, 200, 0, 0, 400.0),
    (1, 100, 300, 0, 400.0), (2, 100, 200, 600, 600.0), (3, 200, 25, 0, 400.0),
])
def test_each_distribution_expected_value(tmp_path, idis, par1, par2, par3, expected):
    path = write_price(tmp_path, price_section(components={"GRAN": (idis, par1, par2, par3)}))
    assert lab.net_returns([{"CR": "MZ", "TRNO": 1, "HWAH": 2000}], path)[0]["net_return"] == expected


def test_spaced_unspaced_treatments_and_crop_matching(tmp_path):
    text = price_section("BN", 10, {"GRAN": (3, 200, 20, 0)}, spaced=False)
    text += price_section("MZ", 10, {"GRAN": (0, 100, 0, 0)})
    text += price_section("FA", 10, {"BASE": (0, 25, 0, 0)})
    rows = [{"CR": crop, "TRNO": 10, "R#": number, "HWAH": 1000}
            for number, crop in enumerate(("BN", "MZ", "FA"), 1)]
    assert [row["net_return"] for row in lab.net_returns(rows, write_price(tmp_path, text))] == [200, 100, -25]


def test_one_crop_heading_over_nine_treatments(tmp_path):
    text = "* SB\n" + "".join(price_section("SB", n, {"BASE": (0, n, 0, 0)}).removeprefix("* SB\n")
                              for n in range(1, 10))
    rows = [{"CR": "SB", "TRNO": n} for n in range(1, 10)]
    assert [r["net_return"] for r in lab.net_returns(rows, write_price(tmp_path, text))] == [-n for n in range(1, 10)]


def test_columns_read_by_name(tmp_path):
    path = write_price(tmp_path, price_section(components={"GRAN": (0, 200, 0, 0), "BASE": (0, 50, 0, 0)},
                                               columns=list(reversed(COLUMNS))))
    assert lab.net_returns([{"CR": "MZ", "TRNO": 1, "HWAH": 1000}], str(path))[0]["net_return"] == 150


@pytest.mark.parametrize("idis,expected", [(0, None), (-1, 0.0)])
def test_none_quantity_for_used_or_ignored_component(tmp_path, idis, expected):
    path = write_price(tmp_path, price_section(components={"GRAN": (idis, 0, 0, 0)}))
    assert lab.net_returns([{"CR": "MZ", "TRNO": 1, "HWAH": None}], path)[0]["net_return"] == expected


def test_ignored_quantities_need_not_exist_or_be_numeric(tmp_path):
    path = write_price(tmp_path, price_section(components={"BASE": (0, 10, 0, 0)}))
    assert lab.net_returns([{"CR": "MZ", "TRNO": 1, "HWAH": "ignored"}], path)[0]["net_return"] == -10


def test_season_statistics_accept_net_returns(tmp_path):
    path = write_price(tmp_path, price_section(components={"GRAN": (0, 200, 0, 0)}))
    rows = [{"CR": "MZ", "TRNO": 1, "HWAH": value} for value in (1000, None, 3000)]
    stats = lab.summarize_seasons(lab.net_returns(rows, path), variables=["net_return"])
    assert len(stats) == 1
    assert stats[0]["variable"] == "net_return"
    assert stats[0]["mean"] == 400
    assert stats[0]["missing"] == 1
    assert stats[0]["seasons"] == 3


def test_to_dataframe_accepts_net_returns(tmp_path):
    pd = pytest.importorskip("pandas")
    path = write_price(tmp_path, price_section(components={"BASE": (0, 10, 0, 0)}))
    frame = lab.to_dataframe(lab.net_returns([{"CR": "MZ", "TRNO": 1}], path))
    assert isinstance(frame, pd.DataFrame)
    assert frame.to_dict("records") == [{"CR": "MZ", "TRNO": 1, "net_return": -10.0}]


def test_empty_rows_still_validate_price_file(tmp_path):
    path = write_price(tmp_path, price_section())
    assert lab.net_returns([], path) == []
    path.write_text("", encoding="utf-8")
    with pytest.raises(lab.DSSATCheckError, match="no crop/treatment sections"):
        lab.net_returns([], path)


@pytest.mark.parametrize("kind", ["absent", "directory", "invalid_encoding"])
def test_missing_or_unreadable_file_is_one_problem(tmp_path, kind):
    path = tmp_path / "bad.PRI"
    if kind == "directory":
        path.mkdir()
    elif kind == "invalid_encoding":
        path.write_bytes(b"\xff")
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([{"CR": "MZ", "TRNO": 1}], path)
    assert len(exc.value.problems) == 1
    message = exc.value.problems[0]
    assert str(path) in message and "read" in message and "Supply" in message


@pytest.mark.parametrize("crop,treatment", [("SB", 1), ("MZ", 2), ("FA", 1)])
def test_no_matching_section_lists_available_sections(tmp_path, crop, treatment):
    path = write_price(tmp_path, price_section())
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([{"CR": crop, "TRNO": treatment}], path)
    message = exc.value.problems[0]
    for part in ("Summary row 1", repr(crop), str(treatment), "available", "MZ", "Add"):
        assert part in message


def test_duplicate_section(tmp_path):
    path = write_price(tmp_path, price_section() + price_section())
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([], path)
    assert any("duplicate" in p and "MZ" in p and "treatment 1" in p and "Remove" in p
               for p in exc.value.problems)


@pytest.mark.parametrize("columns,problem", [(COLUMNS[:-1], "missing columns: KFER"),
                                            (COLUMNS + ["OTHER"], "extra columns: OTHER")])
def test_missing_or_extra_price_column(tmp_path, columns, problem):
    path = write_price(tmp_path, price_section(columns=columns))
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([], path)
    assert any(problem in p and "MZ" in p and "treatment 1" in p and "Use" in p
               for p in exc.value.problems)


@pytest.mark.parametrize("parameter", ["IDIS", "PAR1", "PAR2", "PAR3"])
def test_missing_parameter_row(tmp_path, parameter):
    text = "\n".join(line for line in price_section().splitlines() if not line.startswith(parameter))
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([], write_price(tmp_path, text))
    assert any("missing" in p and parameter in p and "MZ" in p and "Add" in p for p in exc.value.problems)


@pytest.mark.parametrize("parameter", ["IDIS", "PAR1", "PAR2", "PAR3"])
@pytest.mark.parametrize("value", ["oops", "nan", "inf", "-inf"])
def test_every_price_value_must_be_finite_even_when_ignored(tmp_path, parameter, value):
    values = [-1, 0, 0, 0]
    values[("IDIS", "PAR1", "PAR2", "PAR3").index(parameter)] = value
    path = write_price(tmp_path, price_section(components={"GRAN": values}))
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([], path)
    assert any("finite number" in p and "GRAN" in p and parameter in p and "MZ" in p and "Set" in p
               for p in exc.value.problems)


@pytest.mark.parametrize("idis", [-2, 4, 1.5])
def test_unknown_idis(tmp_path, idis):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([], write_price(tmp_path, price_section(components={"GRAN": (idis, 0, 0, 0)})))
    assert any("unknown IDIS" in p and "GRAN" in p and "MZ" in p and "Use" in p for p in exc.value.problems)


@pytest.mark.parametrize("values,rule", [((1, 3, 2, 0), "PAR1 <= PAR2"),
                                        ((2, 3, 2, 4), "PAR1 <= PAR2 <= PAR3"),
                                        ((2, 1, 4, 3), "PAR1 <= PAR2 <= PAR3"),
                                        ((3, 1, -1, 0), "PAR2 >= 0")])
def test_bad_distribution_parameters(tmp_path, values, rule):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([], write_price(tmp_path, price_section(components={"GRAN": values})))
    assert any(rule in p and "GRAN" in p and "MZ" in p and "Set" in p for p in exc.value.problems)


@pytest.mark.parametrize("row,missing", [({"TRNO": 1}, "CR"), ({"CR": "MZ"}, "TRNO"),
                                        ({"CR": None, "TRNO": 1}, "CR"),
                                        ({"CR": "MZ", "TRNO": None, "treatment": 1}, "TRNO")])
def test_row_requires_cr_and_trno(tmp_path, row, missing):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([row], write_price(tmp_path, price_section()))
    assert any("Summary row 1" in p and missing in p and "Supply" in p for p in exc.value.problems)


def test_absent_used_quantity_column(tmp_path):
    path = write_price(tmp_path, price_section(components={"GRAN": (0, 0, 0, 0)}))
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([{"CR": "MZ", "TRNO": 1}], path)
    assert any("Summary row 1" in p and "missing quantity column HWAH" in p and "Supply" in p
               for p in exc.value.problems)


@pytest.mark.parametrize("value", [True, False, "1000", float("nan"), float("inf"), float("-inf")])
def test_used_quantities_must_be_finite_numbers(tmp_path, value):
    path = write_price(tmp_path, price_section(components={"GRAN": (0, 200, 0, 0)}))
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([{"CR": "MZ", "TRNO": 1, "HWAH": value}], path)
    assert any("Summary row 1" in p and "HWAH" in p and "finite number" in p and "Supply" in p
               for p in exc.value.problems)


@pytest.mark.parametrize("rows", [None, "bad", 123, {"CR": "MZ"}, (), [1], [{}, "bad"]])
def test_rows_must_be_a_list_of_dicts(tmp_path, rows):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns(rows, write_price(tmp_path, price_section()))
    assert "Summary rows: expected a list of dicts. Supply the rows from result.summary() or combine_summaries()." in exc.value.problems


def test_file_and_row_problems_collected_without_mutating_inputs(tmp_path):
    text = price_section(components={"GRAN": (0, 200, 0, 0), "BASE": (4, 0, 0, 0)})
    text += price_section("SB", components={"BYPR": (1, 3, 2, 0)})
    rows = [{"CR": "MZ", "TRNO": 1, "HWAH": True}, {"CR": "MZ"}, {"CR": "FA", "TRNO": 2}]
    original = deepcopy(rows)
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns(rows, write_price(tmp_path, text))
    assert len(exc.value.problems) == 5
    for part in ("unknown IDIS", "PAR1 <= PAR2", "HWAH", "TRNO", "available"):
        assert any(part in p for p in exc.value.problems)
    assert rows == original


def test_bad_rows_and_bad_price_file_collected_together(tmp_path):
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns("bad", tmp_path / "absent.PRI")
    assert len(exc.value.problems) == 2


@pytest.mark.parametrize("row", [{"CR": ["MZ"], "TRNO": 1},
                                 {"CR": "MZ", "TRNO": {"number": 1}}])
def test_unhashable_matching_keys_preserve_collected_problems(tmp_path, row):
    path = write_price(tmp_path, price_section(components={"BASE": (4, 0, 0, 0)}))
    with pytest.raises(lab.DSSATCheckError) as exc:
        lab.net_returns([{"TRNO": 1}, row], path)
    assert len(exc.value.problems) == 3
    assert any("unknown IDIS" in p for p in exc.value.problems)
    assert any("Summary row 1" in p and "missing CR" in p for p in exc.value.problems)
    assert any("Summary row 2" in p and "invalid CR/TRNO" in p and "Supply" in p
               for p in exc.value.problems)


@pytest.mark.parametrize("name", ["DEFAULT", "ITHY7501", "UAFD7465", "UFGA7805", "UFGA7812", "UFGA8201", "UFGA9701"])
def test_stock_price_files_parse(name):
    economic = Path(os.environ.get("DSSAT_HOME", r"C:\DSSAT48")) / "Economic"
    path = economic / f"{name}.PRI"
    if not path.is_file():
        pytest.skip(f"Stock Price file absent: {path}")
    # Empty rows still validate every section and every price-file value.
    assert lab.net_returns([], path) == []
