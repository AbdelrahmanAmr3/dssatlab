"""
A JSON configuration helper for the build cache, last executable path, and more.

It's helps to store and retrieve the last executable DSSAT path.
Without it, every new python session would require re-finding the DSSAT executable.

History:
- 28/09/2026: Initial version and refactored by Abdelrahman Saleh <
"""

import json
import os
from pathlib import Path
from typing import Any


def config_file() -> Path:
    """
    Return the path to the dssatlab configuration file. Based
    on the os.name.
    """
    
    if os.name == "nt": # Windows
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    else: # Linux, MacOS, and others
        base = os.getenv("XDG_CONFIG_HOME")
    
    dir = Path(base) / "dssatlab" if base else Path.home() / ".config" / "dssatlab"
    # return:
    ## Win: %LOCALAPPDATA%\dssatlab\config.json
    ## Linux/MacOS: $XDG_CONFIG_HOME/dssatlab/config.json or 
    ## Other: ~/.config/dssatlab/config.json
    return dir / "config.json"


def load_config() -> dict[str, Any]:
    try:
        return json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(data: dict[str, Any]) -> None:
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")