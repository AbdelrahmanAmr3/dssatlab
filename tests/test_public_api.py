from dssatlab import DSSATConnection, EnvironmentInfo, connect, detect, install


def test_public_api_is_importable():
    assert callable(connect)
    assert callable(detect)
    assert callable(install)
    assert DSSATConnection is not None
    assert EnvironmentInfo is not None
