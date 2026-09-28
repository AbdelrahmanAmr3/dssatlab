"""Tiny JSON configuration helper.

Keep this module boring. It stores only the selected DSSAT executable/root/version.
Do not turn it into a general settings framework.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "dssatlab"
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "dssatlab"
    return Path.home() / ".config" / "dssatlab"


def config_file() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = config_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(data: dict[str, Any]) -> None:
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
