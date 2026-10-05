import dssatlab
from dssatlab import (DSSATError, DSSATOutputError, DSSATRunError, connect, detect,
                     install, net_returns, plot_plant_growth, read_plant_growth,
                     read_summary, run, summarize_seasons, to_dataframe)


def test_public_api_is_importable():
    assert callable(connect)
    assert callable(detect)
    assert callable(install)
    assert callable(run)
    assert callable(summarize_seasons)
    assert callable(net_returns)
    assert issubclass(DSSATRunError, DSSATError)
    assert "run" in dssatlab.__all__
    assert "summarize_seasons" in dssatlab.__all__
    assert "net_returns" in dssatlab.__all__
    assert "DSSATRunError" in dssatlab.__all__
    assert dssatlab.__version__ == "0.22.0"


def test_summary_public_api_is_exported():
    assert callable(read_summary)
    assert issubclass(DSSATOutputError, DSSATError)
    assert "read_summary" in dssatlab.__all__
    assert "DSSATOutputError" in dssatlab.__all__


def test_plant_growth_public_api_is_exported():
    assert callable(read_plant_growth)
    assert "read_plant_growth" in dssatlab.__all__


def test_daily_output_public_api_is_exported():
    for name in ("read_soil_water", "read_plant_nitrogen", "read_weather"):
        assert name in dssatlab.__all__
        assert callable(getattr(dssatlab, name))


def test_scenario_public_api_is_exported():
    for name in ("run_sweep", "run_treatments", "combine_summaries", "summarize_seasons", "write_scenario_template"):
        assert name in dssatlab.__all__
        assert callable(getattr(dssatlab, name))


def test_dataframe_public_api_is_exported():
    assert callable(to_dataframe)
    assert "to_dataframe" in dssatlab.__all__


def test_plot_public_api_is_exported():
    assert callable(plot_plant_growth)
    assert "plot_plant_growth" in dssatlab.__all__


def test_weather_public_api_is_exported():
    for name in ("Simulation", "write_weather_template", "write_soil_template",
                 "write_management_template", "DSSATCheckError"):
        assert name in dssatlab.__all__
        assert callable(getattr(dssatlab, name))


def test_dssat_evaluation_public_api_is_exported():
    assert callable(dssatlab.read_dssat_evaluation)
    assert "read_dssat_evaluation" in dssatlab.__all__


def test_crop_listing_public_api_is_exported():
    for name in ("list_crops", "list_cultivars"):
        assert name in dssatlab.__all__
        assert callable(getattr(dssatlab, name))

