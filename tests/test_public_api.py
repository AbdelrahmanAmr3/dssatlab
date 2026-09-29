from dssatlab import connect, detect, install


def test_public_api_is_importable():
    assert callable(connect)
    assert callable(detect)
    assert callable(install)
