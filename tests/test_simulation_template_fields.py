"""Per-field sources are checked and written for each template treatment."""

import csv
from copy import deepcopy
from datetime import date

import pytest

from dssatlab import DSSATCheckError, Simulation, run_treatments
from dssatlab.filex import _section_row
from test_filex_template import data, rows
from test_simulation_run import fake_dssat
from test_simulation_template import installed


@pytest.fixture
def fields(data, rows):
    data.pop("treatment_name")
    data.update(treatments=["First", "Second", "Third"], treatment_fields=[1, 2, 2])
    return dict(filex_template=data,
                weather={2: [dict(rows[0][0], station="AMES")], 1: rows[0]},
                soil={2: [dict(rows[1][0], soil_id="SECOND", slb=60)], 1: rows[1]})


@pytest.mark.parametrize("keys", [int, str])
@pytest.mark.parametrize("form", ["rows", "csv", "dataframe"])
def test_field_sources_run_selected_treatment(fields, installed, tmp_path, keys, form):
    for kind in ("weather", "soil"):
        converted = {}
        for number, source in fields[kind].items():
            if form == "csv":
                path = tmp_path / f"{kind}{number}.csv"
                with path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(source[0]))
                    writer.writeheader()
                    writer.writerows(source)
                source = path
            elif form == "dataframe":
                source = pytest.importorskip("pandas").DataFrame(source)
            converted[keys(number)] = source
        fields[kind] = converted
    sim = Simulation(**fields, treatment="3")
    assert sim.check() == []
    folder = sim.run().run_dir.parent
    assert {p.name for p in folder.glob("*.WTH")} == {"TEST2101.WTH", "AMES2101.WTH"}
    assert [p.name for p in folder.glob("*.SOL")] == ["SOIL.SOL"]
    soil = (folder / "SOIL.SOL").read_text()
    assert soil.index("*SOIL123456") < soil.index("*SECOND")
    text = (folder / "TEST2101.MZX").read_text()
    for number, field in enumerate([1, 2, 2], 1):
        assert _section_row(text, "TREATMENTS", "N", number, ("FL",))["FL"] == str(field)
    for number, station, soil_id in [(1, "TEST", "SOIL123456"), (2, "AMES", "SECOND")]:
        values = _section_row(text, "FIELDS", "L", number, ("WSTA", "ID_SOIL"))
        assert values["WSTA"] == station and values["ID_SOIL"] == soil_id
    assert installed.calls[0][0][-2:] == ["TEST2101.MZX", "3"]


@pytest.mark.parametrize("kind", ["weather", "soil"])
@pytest.mark.parametrize("keys,shown", [([1], "1"), ([3, 1, 2], "1, 2, 3"),
    ([2], "2"), ([], "none"), ([True, 2], "2, True"), ([1.0, 2], "2, 1.0"),
    (["bad", 1], "1, 'bad'"), ([1, "1", 2], "1, 2, '1'"), (None, "1")])
def test_field_keys_must_match(fields, installed, kind, keys, shown):
    source = fields[kind][1]
    fields[kind] = source if keys is None else {key: source for key in keys}
    problems = Simulation(**fields).check()
    assert problems == [f"FileX template has fields 1 to 2, but {kind} data has fields {shown}. "
                        f"Supply {kind} data for every field: {kind}={{1: ..., 2: ...}}."]
    with pytest.raises(DSSATCheckError):
        Simulation(**fields).run()
    assert installed.calls == []


@pytest.mark.parametrize("kind", ["weather", "soil"])
def test_copied_filex_rejects_dict(rows, kind):
    inputs = dict(filex="unused.MZX", weather=rows[0], soil=rows[1])
    inputs[kind] = {1: inputs[kind]}
    assert (
        f"{kind.capitalize()} data per field needs a FileX template. "
        f"Supply one {kind} source for a FileX.") in Simulation(**inputs).check()


@pytest.mark.parametrize("kind,column", [("weather", "rain"), ("soil", "sbdm")])
def test_field_problems_and_report_are_labelled(fields, installed, capsys, kind, column):
    fields[kind][2][0][column] = -1
    problems = Simulation(**fields).check(verbose=True)
    label = f"{kind.capitalize()} data, field 2"
    assert any(p.startswith(label) and column in p for p in problems)
    report = capsys.readouterr().out
    assert f"{label}: REJECTED" in report
    assert f"{kind.capitalize()} data, field 1: OK" in report


@pytest.mark.parametrize("kind,identity,column,label,own", [
    ("weather", "station", "rain", "station", "station code"),
    ("soil", "soil_id", "salb", "soil ID", "soil ID")])
@pytest.mark.parametrize("different", [False, True])
def test_shared_identity_requires_equal_parsed_rows(
        fields, installed, kind, identity, column, label, own, different):
    source = fields[kind][1]
    fields[kind][2] = deepcopy(source)
    # Numeric CSV-style strings compare equal after parsing.
    fields[kind][2][0][column] = str(source[0][column] + (0.1 if different else 0))
    sim = Simulation(**fields)
    if different:
        assert sim.check() == [f"Fields 1 and 2 both use {label} {source[0][identity]!r} "
            f"but their {kind} data differs. Give each field's {kind} its own {own}, or the same data."]
    else:
        assert sim.check() == []
        folder = sim.run().run_dir.parent
        if kind == "weather":
            assert len(list(folder.glob("*.WTH"))) == 1
        else:
            assert (folder / "SOIL.SOL").read_text().count("*SOIL123456") == 1


@pytest.mark.parametrize("check", ["start", "harvest", "management"])
def test_selected_field_supplies_dates(fields, installed, check):
    data = fields["filex_template"]
    if check == "start":
        fields["weather"][2][0]["date"] = date(2021, 3, 2)
    elif check in ("harvest", "management"):
        fields["weather"][1].append(dict(fields["weather"][1][0], date=date(2021, 3, 2)))
        if check == "harvest":
            data["harvest_date"] = "2021-03-02"
        else:
            planting = dict(data["planting"], date="2021-03-02")
            fields["management"] = {"treatments": {k: {"planting": planting} for k in (1, 2)}}
    assert Simulation(**fields, treatment=1).check(verbose=False) == []
    problems = Simulation(**fields, treatment=2).check(verbose=False)
    assert problems
    word = {"start": "start date", "harvest": "harvest_date",
            "management": "weather"}[check]
    assert any(word in p for p in problems)


@pytest.mark.parametrize("treatment", [1, 2])
def test_deep_initial_conditions_are_allowed_for_each_field(fields, installed, treatment):
    fields["soil"][1][0]["slb"] = 150
    entry = dict(initial_conditions=dict(date="2021-03-01", layers=[
        dict(depth=180, water=0.2, nh4=1, no3=2)]))
    fields["management"] = {"treatments": {k: entry for k in (1, 2)}}
    assert Simulation(**fields, treatment=treatment).check(verbose=False) == []


@pytest.mark.parametrize("kind", ["weather", "soil"])
def test_batch_scenario_replaces_whole_field_dict(fields, installed, kind):
    replacement = deepcopy(fields[kind])
    column, values = (("station", ["UFGA", "KSAS"]) if kind == "weather"
                      else ("soil_id", ["NEW1", "NEW2"]))
    for number, value in enumerate(values, 1):
        replacement[number][0][column] = value
    original = deepcopy(fields)
    results = run_treatments(**fields, scenarios={"changed": {kind: replacement}})
    assert list(results) == [(name, k) for name in ("base", "changed") for k in (1, 2, 3)]
    assert [call[0][-1] for call in installed.calls] == ["1", "2", "3"] * 2
    for (name, treatment), result in results.items():
        folder = result.run_dir.parent
        text = next(folder.glob("*.MZX")).read_text()
        field = 1 if treatment == 1 else 2
        expected = (replacement if name == "changed" else fields[kind])[field][0][column]
        header = "WSTA" if kind == "weather" else "ID_SOIL"
        assert _section_row(text, "FIELDS", "L", field, (header,))[header] == expected
    assert fields == original


def test_single_field_dict_and_plain_sources_write_identical_files(data, rows, installed):
    plain = Simulation(filex_template=data, weather=rows[0], soil=rows[1]).run().run_dir.parent
    keyed = Simulation(filex_template=data, weather={"1": rows[0]}, soil={1: rows[1]}).run().run_dir.parent
    assert {p.name: p.read_bytes() for p in plain.iterdir() if p.is_file()} == {
        p.name: p.read_bytes() for p in keyed.iterdir() if p.is_file()}


@pytest.mark.parametrize("treatment_fields", [[1, 3, 3], [1, 2], "1"])
def test_invalid_treatment_fields_give_no_field_key_problem(fields, installed, treatment_fields):
    fields["filex_template"]["treatment_fields"] = treatment_fields
    problems = Simulation(**fields).check()
    assert problems and all("treatment_fields" in p for p in problems)
