"""Small installation/discovery layer for DSSAT-CSM."""

from .core import connect, detect, install
from .errors import (DSSATCheckError, DSSATError, DSSATInstallError,
                     DSSATNotFoundError, DSSATOutputError, DSSATRunError)
from .management_file import write_management_template
from .outputs import read_plant_growth, read_summary, to_dataframe
from .plot import plot_plant_growth
from .runner import run
from .simulation import Simulation
from .soil import write_soil_template
from .weather import write_weather_template

__all__ = ["DSSATError", "DSSATInstallError", "DSSATNotFoundError", "DSSATRunError",
           "connect", "detect", "install", "run",
           "Simulation", "write_weather_template", "write_soil_template",
           "write_management_template", "DSSATCheckError",
           "read_summary", "read_plant_growth", "to_dataframe", "plot_plant_growth", "DSSATOutputError",
           ]

__version__ = "0.3.2"
