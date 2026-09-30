class DSSATError(RuntimeError):
    """Base error for dssatlab."""


class DSSATNotFoundError(DSSATError):
    """Raised when DSSAT cannot be located and installation is not performed."""


class DSSATInstallError(DSSATError):
    """Raised when DSSAT installation or compilation fails."""


class DSSATRunError(DSSATError):
    """Raised when a DSSAT run cannot be performed."""


class DSSATOutputError(DSSATError):
    """Raised when a DSSAT output file is missing or malformed."""


class DSSATCheckError(DSSATError):
    """Problems found by the checks before a Simulation can run.

    Attributes:
        problems: List of descriptive problem messages identified by the checks.
    """

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__(f"Simulation checks found {len(self.problems)} problems:\n"
                         + "\n".join(self.problems))
