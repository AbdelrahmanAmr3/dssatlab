"""Small installation/discovery layer for DSSAT-CSM."""

from .core import connect, detect, install
from .errors import (DSSATCheckError, DSSATError, DSSATInstallError,
                     DSSATNotFoundError, DSSATRunError)
from .runner import run
from .simulation import Simulation
from .weather import write_weather_template

__all__ = ["DSSATError", "DSSATInstallError", "DSSATNotFoundError", "DSSATRunError",
           "connect", "detect", "install", "run",
           "Simulation", "write_weather_template", "DSSATCheckError",
           ]

__version__ = "0.3.0"
