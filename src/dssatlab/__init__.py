"""Small installation/discovery layer for DSSAT-CSM."""

from .core import connect, detect, install
from .errors import DSSATError, DSSATInstallError, DSSATNotFoundError

__all__ = ["DSSATError", "DSSATInstallError", "DSSATNotFoundError", "connect", "detect", "install",
           ]

__version__ = "0.1.1"
