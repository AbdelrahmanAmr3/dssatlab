import dssatlab
from dssatlab import DSSATError, DSSATRunError, connect, detect, install, run


def test_public_api_is_importable():
    assert callable(connect)
    assert callable(detect)
    assert callable(install)
    assert callable(run)
    assert issubclass(DSSATRunError, DSSATError)
    assert "run" in dssatlab.__all__
    assert "DSSATRunError" in dssatlab.__all__
