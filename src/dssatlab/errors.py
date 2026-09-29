class DSSATError(RuntimeError):
    """Base error for dssatlab."""


class DSSATNotFoundError(DSSATError):
    """Raised when DSSAT cannot be located and installation is not performed."""


class DSSATInstallError(DSSATError):
    """Raised when DSSAT installation or compilation fails."""


class DSSATRunError(DSSATError):
    """Raised when a DSSAT run cannot be performed."""
