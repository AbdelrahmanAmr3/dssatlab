"""Public DSSAT discovery/install/connect API.

The implementation agent should keep this file easy to read. The public surface for
v0.1 is deliberately limited to detect(), install(), and connect().
"""
from __future__ import annotations

import importlib.util
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import config, installer
from .errors import DSSATInstallError, DSSATNotFoundError


_WINDOWS_DEFAULT = Path(r"C:\DSSAT48")


@dataclass(frozen=True)
class EnvironmentInfo:
    os_name: str
    is_colab: bool
    architecture: str
    dssat_executable: Path | None = None


@dataclass(frozen=True)
class DSSATConnection:
    executable: Path
    root: Path
    version: str | None
    source: str

    def __repr__(self) -> str:
        version = self.version or "unknown"
        return f"DSSATConnection(version={version!r}, executable={str(self.executable)!r})"


def detect() -> EnvironmentInfo:
    """Inspect the current environment without changing anything."""
    os_name = _os_name()
    try:
        is_colab = importlib.util.find_spec("google.colab") is not None
    except (ImportError, ValueError):
        is_colab = False
    connection = _discover(os_name)
    return EnvironmentInfo(
        os_name=os_name,
        is_colab=is_colab,
        architecture=platform.machine(),
        dssat_executable=connection.executable if connection else None,
    )


def install(version: str = "latest") -> DSSATConnection:
    """Install/build DSSAT-CSM on Linux, remembering and reusing managed builds.

    Never prompts. Missing build tools are reported, never installed automatically.
    """
    if platform.system() != "Linux":
        raise DSSATInstallError(
            "DSSAT installation is only supported on Linux/Colab in v0.1. "
            "Pass connect(executable=...) to use an existing installation."
        )
    resolved = installer.resolve_version(version)
    install_dir = installer.cache_root() / resolved
    executable = installer.find_cached_install(resolved, install_dir)
    if executable is None:
        installer.check_prerequisites()
        executable = installer.build_dssat(resolved, install_dir)
    connection = DSSATConnection(executable, install_dir, resolved, "managed")
    _save_connection(connection)
    return connection


def connect(
    path: str | Path | None = None,
    *,
    executable: str | Path | None = None,
    interactive: bool = True,
) -> DSSATConnection:
    """Find or configure DSSAT and return a validated connection."""
    if executable is not None:
        candidate = Path(executable).expanduser()
        if not _validate_executable(candidate):
            raise _invalid_path(candidate)
        candidate = candidate.resolve()
        connection = DSSATConnection(candidate, candidate.parent, None, "explicit")
    elif path is not None:
        candidate = _find_executable(Path(path))
        if candidate is None:
            raise _invalid_path(Path(path))
        connection = DSSATConnection(candidate, candidate.parent, None, "explicit")
    else:
        os_name = _os_name()
        connection = _discover(os_name)
        if connection is None and interactive:
            if os_name == "windows":
                answer = input("Enter the DSSAT directory or executable path: ").strip()
                candidate = _find_executable(Path(answer)) if answer else None
                if candidate is None:
                    raise _invalid_path(Path(answer))
                connection = DSSATConnection(candidate, candidate.parent, None, "manual")
            elif os_name == "linux":
                answer = input("Install the latest stable DSSAT release? [y/N]: ").strip().lower()
                if answer in ("y", "yes"):
                    return install()
        if connection is None:
            raise DSSATNotFoundError(
                "DSSAT was not found. Checked saved configuration, DSSAT_HOME, "
                "and PATH/platform defaults (including the managed cache on Linux). "
                'Pass connect(executable="/path/to/dscsm048") or call install() on Linux.'
            )
    _save_connection(connection)
    return connection


def _os_name() -> str:
    """Map platform.system() to the spec's windows/linux/other vocabulary."""
    name = platform.system().lower()
    return name if name in ("windows", "linux") else "other"


def _validate_executable(path: Path) -> bool:
    """Check the filename and permissions without running DSSAT."""
    try:
        return (
            path.name.lower() in ("dscsm048", "dscsm048.exe")
            and path.is_file()
            and (os.name != "posix" or os.access(path, os.X_OK))
        )
    except (OSError, ValueError):
        return False


def _find_executable(path: Path) -> Path | None:
    """Accept an executable or search the immediate contents of a directory."""
    try:
        path = path.expanduser()
        if _validate_executable(path):
            return path.resolve()
        if path.is_dir():
            for name in ("DSCSM048.EXE", "dscsm048"):
                candidate = path / name
                if _validate_executable(candidate):
                    return candidate.resolve()
            # Also honor case-insensitive filenames on case-sensitive filesystems.
            for candidate in sorted(path.iterdir()):
                if _validate_executable(candidate):
                    return candidate.resolve()
    except (OSError, ValueError):
        pass
    return None


def _discover(os_name: str) -> DSSATConnection | None:
    """Read-only discovery shared by detect() and connect(), in precedence order."""
    try:
        saved = config.load_config()
        if isinstance(saved, dict) and isinstance(saved.get("executable"), str):
            candidate = Path(saved["executable"]).expanduser()
            root = saved.get("root")
            version = saved.get("version")
            if (
                _validate_executable(candidate)
                and (root is None or isinstance(root, str))
                and (version is None or isinstance(version, str))
            ):
                candidate = candidate.resolve()
                return DSSATConnection(
                    candidate, Path(root).expanduser().resolve() if root else candidate.parent,
                    version, "config",
                )
    except (OSError, ValueError):
        pass

    home = os.environ.get("DSSAT_HOME")
    if home:
        candidate = _find_executable(Path(home))
        if candidate is not None:
            return DSSATConnection(candidate, candidate.parent, None, "env")

    if os_name == "windows":
        candidate = _find_executable(_WINDOWS_DEFAULT)
        if candidate is not None:
            return DSSATConnection(candidate, candidate.parent, None, "default")
    elif os_name == "linux":
        on_path = shutil.which("dscsm048")
        if on_path and _validate_executable(Path(on_path)):
            candidate = Path(on_path).resolve()
            return DSSATConnection(candidate, candidate.parent, None, "default")
        try:
            installs = [d for d in installer.cache_root().iterdir() if d.is_dir()]
        except OSError:
            installs = []
        installs.sort(key=lambda d: _version_sort_key(d.name), reverse=True)
        for install_dir in installs:
            candidate = installer.find_cached_install(install_dir.name, install_dir)
            if candidate is not None and _validate_executable(candidate):
                return DSSATConnection(candidate, install_dir, install_dir.name, "managed")
    return None


def _version_sort_key(version: str) -> tuple:
    """Compare dotted version strings numerically per segment (e.g. "4.8.10.0" > "4.8.6.0")."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in version.split("."))


def _save_connection(connection: DSSATConnection) -> None:
    config.save_config({
        "executable": str(connection.executable),
        "root": str(connection.root),
        "version": connection.version,
        "source": connection.source,
    })


def _invalid_path(path: Path) -> DSSATNotFoundError:
    return DSSATNotFoundError(
        f"No valid DSSAT executable found at {str(path)!r}. "
        "Checked for a dscsm048 or DSCSM048.EXE file with execute permission on POSIX. "
        "Pass connect(executable=...) with a valid executable or connect(path=...) "
        "with its directory."
    )
