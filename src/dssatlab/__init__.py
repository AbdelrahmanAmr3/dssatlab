"""Small installation/discovery layer for DSSAT-CSM."""

from .core import connect, detect, install
from .errors import (DSSATCheckError, DSSATError, DSSATInstallError,
                     DSSATNotFoundError, DSSATOutputError, DSSATRunError)
from .management_file import write_experiment_template, write_management_template
from .outputs import (read_plant_growth, read_plant_nitrogen, read_soil_water,
                      read_summary, read_weather, to_dataframe)
from .plot import plot_plant_growth
from .runner import run
from .scenarios import combine_summaries, run_treatments, write_scenario_template
from .simulation import Simulation
from .soil import write_soil_template
from .weather import write_weather_template

__all__ = ["DSSATError", "DSSATInstallError", "DSSATNotFoundError", "DSSATRunError",
           "connect", "detect", "install", "run",
           "Simulation", "write_weather_template", "write_soil_template",
           "write_management_template", "write_experiment_template", "DSSATCheckError",
           "read_summary", "read_plant_growth", "to_dataframe", "plot_plant_growth", "DSSATOutputError",
           "read_soil_water", "read_plant_nitrogen", "read_weather",
           "run_treatments", "combine_summaries", "write_scenario_template",
           ]

__version__ = "0.6.0"
