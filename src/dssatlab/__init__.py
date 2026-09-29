"""Small installation/discovery layer for DSSAT-CSM."""

from .core import connect, detect, install
from .errors import DSSATError, DSSATInstallError, DSSATNotFoundError, DSSATRunError
from .runner import run

__all__ = ["DSSATError", "DSSATInstallError", "DSSATNotFoundError", "DSSATRunError",
           "connect", "detect", "install", "run",
           ]

__version__ = "0.1.1"
