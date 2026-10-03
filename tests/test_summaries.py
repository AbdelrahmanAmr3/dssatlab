"""Weather and soil summaries through the public template functions."""

import csv
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

import dssatlab


@pytest.fixture
def weather():
    return [dict(station="UFGA", latitude=45, longitude=-100, elevation=200,
                 date=day, srad=srad, tmax=tmax, tmin=tmin, rain=rain)
            for day, srad, tmax, tmin, rain in (
                ("2020-12-30", 10.004, 20.004, 0.004, 0.004),
                ("2020-12-31", 20.004, 22.004, 2.004, 0.004),
                ("2021-01-01", 30.004, 24.004, 4.004, 1.004),
                ("2021-01-02", 40.004, 26.004, 6.004, 2.004))]


@pytest.fixture
def soil():
    return [dict(soil_id="IBMZ910214", salb=0.134, slro=60.126, sldr=0.504,
                 slpf=0.954, slb=depth, slll=lower, sdul=upper, ssat=0.45, srgf=1)
            for depth, lower, upper in ((5, 0.10123, 0.23456),
                                        (15, 0.12345, 0.26567),
                                        (30, 0.14567, 0.28789))]


@pytest.fixture
def filex(tmp_path):
    path = tmp_path / "UFGA2001.MZX"
    path.write_text("""*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 RAINFED LOW NITROGEN       1  1  0  1  1  1  1  0  0  0  0  0  1

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910214 Field section

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 20365  2150 N X IRRIGATION
""", encoding="latin-1")
    return path


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_weather_summary_spans_new_year(weather):
    before = deepcopy(weather)
    assert dssatlab.summarize_weather(weather) == {
        "station": "UFGA", "latitude": 45, "longitude": -100, "elevation": 200,
        "first_date": date(2020, 12, 30), "last_date": date(2021, 1, 2), "days": 4,
        "variables": {
            "srad": {"min": 10, "mean": 25, "max": 40},
            "tmax": {"min": 20, "mean": 23, "max": 26},
            "tmin": {"min": 0, "mean": 3, "max": 6},
            "rain": {"min": 0, "mean": 0.75, "max": 2}},
        "rain_total": 3.02,
        "years": [
            {"year": 2020, "days": 2, "srad_mean": 15, "tmax_mean": 21,
             "tmin_mean": 1, "rain_total": 0.01},
            {"year": 2021, "days": 2, "srad_mean": 35, "tmax_mean": 25,
             "tmin_mean": 5, "rain_total": 3.01}]}
    assert weather == before


def test_soil_summary_three_layers(soil):
    before = deepcopy(soil)
    # Layer water: 6.6665 + 14.222 + 21.333 = 42.2215 mm.
    assert dssatlab.summarize_soil(soil) == {
        "soil_id": "IBMZ910214", "layers": 3, "depth": 30,
        "extractable_water": 42.22, "salb": 0.13, "slro": 60.13,
        "sldr": 0.5, "slpf": 0.95}
    assert soil == before


@pytest.mark.parametrize("kind", ["weather", "soil"])
def test_summary_csv_matches_rows(tmp_path, weather, soil, kind):
    rows = weather if kind == "weather" else soil
    summarize = getattr(dssatlab, f"summarize_{kind}")
    path = write_csv(tmp_path / f"{kind}.csv", rows)
    assert summarize(path) == summarize(str(path)) == summarize(rows)


@pytest.mark.parametrize("kind", ["weather", "soil"])
def test_summary_dataframe_matches_csv_and_rows(tmp_path, weather, soil, kind):
    pd = pytest.importorskip("pandas")
    rows = weather if kind == "weather" else soil
    summarize = getattr(dssatlab, f"summarize_{kind}")
    frame = pd.DataFrame(rows, index=[10 * n for n in range(len(rows))])
    path = write_csv(tmp_path / f"{kind}.csv", rows)
    assert summarize(frame) == summarize(path) == summarize(rows)


def test_weather_summary_par_present(weather):
    for row, par in zip(weather, (10.004, 20.004, 30.004, 40.004)):
        row["par"] = par
    summary = dssatlab.summarize_weather(weather)
    assert summary["variables"]["par"] == {"min": 10, "mean": 25, "max": 40}
    assert [year["par_mean"] for year in summary["years"]] == [15, 35]


def test_weather_summary_par_absent(weather):
    summary = dssatlab.summarize_weather(weather)
    assert "par" not in summary["variables"]
    assert all("par_mean" not in year for year in summary["years"])


def test_weather_summary_explicit_missing_elevation(weather):
    for row in weather:
        row["elevation"] = -99
    assert dssatlab.summarize_weather(weather)["elevation"] == -99


def test_weather_summary_blank_elevation_fails(weather):
    weather[0]["elevation"] = ""
    with pytest.raises(dssatlab.DSSATCheckError) as caught:
        dssatlab.summarize_weather(weather)
    assert len(caught.value.problems) == 1
    assert "'elevation'" in caught.value.problems[0]
    assert "non-empty finite number" in caught.value.problems[0]


@pytest.mark.parametrize("kind", ["weather", "soil"])
@pytest.mark.parametrize("form", ["rows", "csv", "dataframe"])
def test_invalid_summary_matches_simulation_problems(tmp_path, filex, weather, soil, kind, form):
    assert dssatlab.Simulation(filex, 1, weather, soil=soil).check() == []
    if kind == "weather":
        weather[0]["rain"] = -1
        weather[1]["srad"] = "oops"
        weather[2]["tmax"] = 0
        rows = weather
    else:
        soil[0]["sdul"] = soil[0]["slll"]
        soil[1]["srgf"] = 2
        soil[2]["slb"] = 15
        rows = soil
    source = rows
    if form == "csv":
        source = write_csv(tmp_path / f"{kind}.csv", rows)
    elif form == "dataframe":
        pd = pytest.importorskip("pandas")
        source = pd.DataFrame(rows)
    simulation = dssatlab.Simulation(filex, 1,
                                    source if kind == "weather" else weather,
                                    soil=source if kind == "soil" else soil)
    problems = simulation.check()
    assert len(problems) >= 3
    with pytest.raises(dssatlab.DSSATCheckError) as caught:
        getattr(dssatlab, f"summarize_{kind}")(source)
    assert caught.value.problems == problems


@pytest.mark.parametrize("kind", ["weather", "soil"])
@pytest.mark.parametrize("source, file_kind", [
    ("stock.WTH", "weather"), (Path("stock.wth"), "weather"),
    (Path("stock.SOL"), "soil"), ("stock.sol", "soil")])
def test_summary_rejects_stock_files(kind, source, file_kind):
    with pytest.raises(dssatlab.DSSATCheckError) as caught:
        getattr(dssatlab, f"summarize_{kind}")(source)
    assert caught.value.problems == [
        f"summarize_{kind} reads the {kind} template, not stock {file_kind} file {source}. "
        f"Checked the file suffix. Supply {kind} template rows, a CSV path or a "
        f"DataFrame; Simulation copies stock {file_kind} files unchanged."]


@pytest.mark.parametrize("kind", ["weather", "soil"])
@pytest.mark.parametrize("source", [["one.WTH", Path("two.wth")], [Path("one.SOL")],
                                    ["one.csv", Path("two.csv")]])
def test_summary_rejects_path_lists(kind, source):
    with pytest.raises(dssatlab.DSSATCheckError) as caught:
        getattr(dssatlab, f"summarize_{kind}")(source)
    assert caught.value.problems == [
        f"summarize_{kind} reads the {kind} template, not a list of file paths {source}. "
        f"Checked the source type. Supply {kind} template rows, a CSV path or a "
        f"DataFrame; Simulation copies stock {kind} files unchanged."]


@pytest.mark.parametrize("kind", ["weather", "soil"])
def test_written_template_summarizes(tmp_path, kind):
    path = tmp_path / f"{kind}.csv"
    getattr(dssatlab, f"write_{kind}_template")(path)
    summary = getattr(dssatlab, f"summarize_{kind}")(path)
    if kind == "weather":
        assert summary["days"] == 7
        assert summary["rain_total"] == 0
    else:
        assert summary["layers"] == 3
        assert summary["depth"] == 30
        assert summary["extractable_water"] == 42


def test_summary_public_names_exported():
    assert "summarize_weather" in dssatlab.__all__
    assert "summarize_soil" in dssatlab.__all__
