import json
from dssatlab import config


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_file", lambda: tmp_path / "config.json")
    data = {"executable": "/tmp/dscsm048", "version": "4.8.6.0"}
    config.save_config(data)
    assert config.load_config() == data
    parsed = json.loads((tmp_path / "config.json").read_text())
    assert parsed["version"] == "4.8.6.0"
