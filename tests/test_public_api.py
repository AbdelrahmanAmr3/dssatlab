import dssatlab
from dssatlab import (DSSATError, DSSATOutputError, DSSATRunError, connect, detect,
                     install, read_summary, run)


def test_public_api_is_importable():
    assert callable(connect)
    assert callable(detect)
    assert callable(install)
    assert callable(run)
    assert issubclass(DSSATRunError, DSSATError)
    assert "run" in dssatlab.__all__
    assert "DSSATRunError" in dssatlab.__all__


def test_summary_public_api_is_exported():
    assert callable(read_summary)
    assert issubclass(DSSATOutputError, DSSATError)
    assert "read_summary" in dssatlab.__all__
    assert "DSSATOutputError" in dssatlab.__all__


def test_weather_public_api_is_exported():
    for name in ("Simulation", "write_weather_template", "write_soil_template",
                 "write_management_template", "DSSATCheckError"):
        assert name in dssatlab.__all__
        assert callable(getattr(dssatlab, name))
