"""
DSSAT core: finds, validates and installs the DSSAT-CSM executable.

Most users only need connect():

    import dssatlab as dl
    dssat = dl.connect()     # Path to the DSSAT executable, remembered for next time

connect() looks for DSSAT in this order: an explicit path, saved config, DSSAT_HOME,
the platform default (PATH, or C:\\DSSAT48 on Windows), then a dssatlab-managed build.
If nothing is found it offers to install (Linux/Colab) or asks for a path (Windows).

Other public functions:
    detect()   report the OS, architecture and DSSAT path, without changing anything
    install()  build DSSAT from the official release on Linux (never prompts)

Everything else here (validate_dssat_path, find_dssat_path, _discover, ...) is
internal discovery machinery shared by these three functions.

History:
- 28/09/2026: Initial version and refactored by Abdelrahman Saleh

TODO: review install -> linstaller.py
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
from pathlib import Path

from . import config, installer
from .errors import DSSATInstallError, DSSATNotFoundError

_WINDOWS_DEFAULT = Path(r"C:\DSSAT48")

log = logging.getLogger(__name__)


def detect() -> dict:
    """Inspect the current environment without changing anything.

    Performs read-only discovery for the DSSAT executable without prompting
    the user or updating saved configuration.

    Returns:
        dict: A dictionary containing:
            - os_name (str): Operating system identifier ("windows", "linux", or "other").
            - architecture (str): Machine architecture.
            - dssat_path (Path | None): Path to the discovered DSSAT executable,
              or None if not found.
    """

    os_name = _os_name()
    return {
        "os_name": os_name,
        "architecture": platform.machine(),
        "dssat_path": _discover(os_name),
    }


def install(version: str = "latest") -> Path:
    """Install/build DSSAT-CSM on Linux, remembering and reusing managed builds.

    Clones and compiles the official DSSAT release using Git, CMake, and gfortran.
    Reuses cached managed builds if already present. Never prompts. Missing build
    tools are reported, never installed automatically.

    Args:
        version: Version tag to build, or "latest" to resolve the latest stable
            release from GitHub. Defaults to "latest".

    Returns:
        Path: Validated path to the installed DSSAT executable (dscsm048).
            The path is saved to configuration.

    Raises:
        DSSATInstallError: If called on a non-Linux platform, if required build tools
            (git, cmake, gfortran) are missing from PATH, if the installation prefix
            exceeds the 51-character limit, or if the build fails.
    """

    # Raise an error on non-Linux and MacOS platforms
    if platform.system() != "Linux":
        raise DSSATInstallError(
            "DSSAT installation is only supported on Linux/Colab in v0.1. "
            "Pass connect(path=...) to use an existing installation."
        )

    resolved = installer.resolve_version(version)
    install_dir = installer.cache_root() / resolved
    executable = installer.find_cached_install(resolved, install_dir)

    if executable is None:
        installer.check_prerequisites()
        executable = installer.build_dssat(resolved, install_dir)

    log.info("Found DSSAT %s via managed install: %s", resolved, executable)

    _save_path(executable)

    return executable


def connect(
    path: str | Path | None = None,
    *,
    interactive: bool = True,
) -> Path:
    """Find or configure DSSAT and return the validated path to its executable.

    When path is not specified, searches in order: saved config, DSSAT_HOME
    environment variable, platform default location (PATH, or C:\\DSSAT48 on Windows),
    and managed install cache on Linux. If not found and interactive is True,
    prompts for a path (Windows) or offers to build a managed install (Linux).

    Args:
        path: Explicit path to the DSSAT executable (dscsm048 or DSCSM048.EXE)
            or the directory containing it. If None, automatic discovery is performed.
        interactive: Whether to prompt for input if DSSAT cannot be found
            automatically. Defaults to True.

    Returns:
        Path: Validated path to the DSSAT executable. The path is saved to config
            for future sessions.

    Raises:
        DSSATNotFoundError: If a valid DSSAT executable cannot be located or the
            provided path is invalid.
    """

    if path is not None:
        # Accepts the executable file, or a directory that directly contains it.
        dssat_path = find_dssat_path(Path(path))
        if dssat_path is None:
            raise _invalid_path(Path(path))
        log.info("Found DSSAT via explicit path: %s", dssat_path)

    else:
        os_name = _os_name()
        dssat_path = _discover(os_name)

        if dssat_path is None and interactive:

            if os_name == "windows":
                answer = input(
                    "Enter the DSSAT directory or executable path: ").strip()
                dssat_path = find_dssat_path(Path(answer)) if answer else None

                if dssat_path is None:
                    raise _invalid_path(Path(answer))
                log.info("Found DSSAT via prompt: %s", dssat_path)

            elif os_name == "linux":
                answer = input(
                    "Install the latest stable DSSAT release? [y/N]: ").strip().lower()

                if answer in ("y", "yes"):
                    return install()

        if dssat_path is None:
            raise DSSATNotFoundError(
                "DSSAT was not found. Checked saved configuration, DSSAT_HOME, "
                "and PATH/platform defaults (including the managed cache on Linux). "
                'Pass connect(path="/path/to/dscsm048") or call install() on Linux.'
            )

    _save_path(dssat_path)
    return dssat_path


def _os_name() -> str:
    """Map platform.system() to the spec's windows/linux/other vocabulary."""
    name = platform.system().lower()
    return name if name in ("windows", "linux") else "other"


def validate_dssat_path(path: Path) -> bool:
    """Check the filename and permissions without running DSSAT."""
    try:
        return (
            path.name.lower() in ("dscsm048", "dscsm048.exe")
            and path.is_file()
            and (os.name != "posix" or os.access(path, os.X_OK))
        )
    except (OSError, ValueError):
        return False


def find_dssat_path(path: Path) -> Path | None:
    """
    Accept an executable or search the immediate contents of a directory.
    """

    try:
        path = path.expanduser()

        if validate_dssat_path(path):
            return path.resolve()

        # Case-insensitive match; sorted() tries DSCSM048.EXE before dscsm048.
        # iterdir() raises OSError on a non-directory, which is handled below.
        for candidate in sorted(path.iterdir()):
            if validate_dssat_path(candidate):
                return candidate.resolve()
    except (OSError, ValueError):
        pass
    return None


def _discover(os_name: str) -> Path | None:
    """
    Read-only discovery shared by detect() and connect(), in precedence order.
    """

    try:
        saved = config.load_config()
        if isinstance(saved, dict) and isinstance(saved.get("executable"), str):
            candidate = Path(saved["executable"]).expanduser()
            if validate_dssat_path(candidate):
                candidate = candidate.resolve()
                log.debug("Found DSSAT via saved config: %s", candidate)
                return candidate
    except (OSError, ValueError):
        pass

    home = os.environ.get("DSSAT_HOME")
    if home:
        candidate = find_dssat_path(Path(home))
        if candidate is not None:
            log.info("Found DSSAT via DSSAT_HOME: %s", candidate)
            return candidate

    if os_name == "windows":
        candidate = find_dssat_path(_WINDOWS_DEFAULT)
        if candidate is not None:
            log.info("Found DSSAT via default location: %s", candidate)
            return candidate
    elif os_name == "linux":
        on_path = shutil.which("dscsm048")
        if on_path and validate_dssat_path(Path(on_path)):
            candidate = Path(on_path).resolve()
            log.info("Found DSSAT via PATH: %s", candidate)
            return candidate
        try:
            installs = [d for d in installer.cache_root().iterdir()
                        if d.name not in ("work", "installs") and d.is_dir()]
        except OSError:
            installs = []
        installs.sort(key=lambda d: _version_sort_key(d.name), reverse=True)
        for install_dir in installs:
            candidate = installer.find_cached_install(
                install_dir.name, install_dir)
            if candidate is not None and validate_dssat_path(candidate):
                log.info("Found DSSAT via managed cache: %s", candidate)
                return candidate
    return None


def _version_sort_key(version: str) -> tuple:
    """Compare dotted version strings numerically per segment (e.g. "4.8.10.0" > "4.8.6.0")."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in version.split("."))


def _save_path(dssat_path: Path) -> None:
    config.save_config({"executable": str(dssat_path)})


def _invalid_path(path: Path) -> DSSATNotFoundError:
    return DSSATNotFoundError(
        f"No valid DSSAT executable found at {str(path)!r}. "
        "Checked for a dscsm048 or DSCSM048.EXE file with execute permission on POSIX. "
        "Pass connect(path=...) with the executable file or the directory "
        "that contains it."
    )
