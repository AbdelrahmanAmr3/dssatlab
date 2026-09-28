"""Report the local Python environment without changing it."""

import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentInfo:
    """Operating system, machine architecture, and Python interpreter version."""

    os_name: str
    architecture: str
    python_version: str


def detect() -> EnvironmentInfo:
    """Return environment details without prompts, downloads, or file changes.

    OS names are lowercase (macOS is ``darwin``). Architecture uses the
    platform's original spelling. Unavailable OS or architecture is ``unknown``.
    This function does not search for or validate a DSSAT installation.
    """
    return EnvironmentInfo(
        os_name=platform.system().lower() or "unknown",
        architecture=platform.machine() or "unknown",
        python_version=platform.python_version(),
    )
