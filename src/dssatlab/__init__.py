"""Small installation/discovery layer for DSSAT-CSM."""

from .core import DSSATConnection, EnvironmentInfo, connect, detect, install
from .errors import DSSATError, DSSATInstallError, DSSATNotFoundError

__all__ = [
    "DSSATConnection", "EnvironmentInfo", "DSSATError",
    "DSSATInstallError", "DSSATNotFoundError", "connect", "detect", "install",
]

__version__ = "0.1.1"
