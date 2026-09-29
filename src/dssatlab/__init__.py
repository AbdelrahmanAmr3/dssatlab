"""Small installation/discovery layer for DSSAT-CSM."""

from .core import DSSATConnection, PlatformInfo, connect, detect, install
from .errors import DSSATError, DSSATInstallError, DSSATNotFoundError

__all__ = [
    "DSSATConnection", "PlatformInfo", "DSSATError",
    "DSSATInstallError", "DSSATNotFoundError", "connect", "detect", "install",
]

__version__ = "0.1.1"
