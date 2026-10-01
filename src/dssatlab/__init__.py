"""Small installation/discovery layer for DSSAT-CSM."""

from .core import connect, detect, install
from .dssat_observed import read_dssat_observed
from .errors import (DSSATCheckError, DSSATError, DSSATInstallError,
                     DSSATNotFoundError, DSSATOutputError, DSSATRunError)
from .evaluate import evaluate
from .observed import write_observed_template
from .management_file import write_experiment_template, write_management_template
from .cultivar import list_crops, list_cultivars
from .filex_template import write_filex_template
from .outputs import (read_dssat_evaluation, read_plant_growth,
                      read_plant_nitrogen, read_soil_water, read_summary,
                      read_weather, to_dataframe)
from .plot import plot_evaluation, plot_observed, plot_plant_growth
from .runner import run
from .scenarios import (combine_summaries, run_treatments, summarize_seasons,
                        write_scenario_template)
from .simulation import Simulation
from .soil import write_soil_template
from .weather import write_weather_template

__all__ = ["DSSATError", "DSSATInstallError", "DSSATNotFoundError", "DSSATRunError",
           "connect", "detect", "install", "run",
           "Simulation", "write_weather_template", "write_soil_template",
           "evaluate", "write_observed_template", "plot_evaluation", "plot_observed",
           "read_dssat_observed",
           "write_management_template", "write_experiment_template", "write_filex_template", "DSSATCheckError",
           "list_crops", "list_cultivars",
           "read_summary", "read_plant_growth", "to_dataframe", "plot_plant_growth", "DSSATOutputError",
           "read_soil_water", "read_plant_nitrogen", "read_weather", "read_dssat_evaluation",
           "run_treatments", "combine_summaries", "summarize_seasons", "write_scenario_template",
           ]

__version__ = "0.13.2"
