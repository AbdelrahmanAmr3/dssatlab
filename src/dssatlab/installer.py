"""Internal Linux/Colab installation mechanics using Git, CMake, and the stdlib."""

from http.client import HTTPException
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import urllib.request

from .errors import DSSATInstallError


# DSSAT cannot read DSSATPRO.L48 with longer prefixes (measured on v4.8.6.0).
MAX_PREFIX_LENGTH = 51


def cache_root() -> Path:
    """Compute the managed-install cache path without creating directories."""
    location = os.environ.get("XDG_CACHE_HOME")
    base = Path(location) if location else Path.home() / ".cache"
    return base / "dssatlab"


def resolve_version(version: str) -> str:
    """Resolve latest through GitHub's stable-release endpoint, or keep a version."""
    if version != "latest":
        return version

    url = "https://api.github.com/repos/DSSAT/dssat-csm-os/releases/latest"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            release = json.load(response)
        tag = release.get("tag_name") if isinstance(release, dict) else None
        if not isinstance(tag, str) or not tag.removeprefix("v").strip():
            raise ValueError("response has no nonempty tag_name")
        return tag.removeprefix("v")
    except (OSError, ValueError, HTTPException) as exc:
        raise DSSATInstallError(
            f"Could not resolve the latest stable DSSAT release from {url}: {exc}. "
            "Check your network connection and GitHub access, retry, or pass a "
            "concrete version such as version='4.8.6.0'."
        ) from exc


def check_prerequisites() -> None:
    """Check PATH for the build tools without installing or executing anything."""
    missing = [tool for tool in ("git", "cmake", "gfortran") if not shutil.which(tool)]
    if missing:
        raise DSSATInstallError(
            f"Missing required tools on PATH: {', '.join(missing)}. "
            "Install the missing tools and retry. On Debian/Ubuntu, ask your "
            "administrator to use: apt install git cmake gfortran."
        )


def find_cached_install(version: str, install_dir: Path) -> Path | None:
    """Return an existing executable only when the manifest records an install prefix."""
    # The caller already selected this version's own directory.
    try:
        manifest = json.loads((install_dir / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            return None
        prefix = manifest.get("prefix")
        if not isinstance(prefix, str) or not prefix:
            return None
        executable = manifest.get("executable")
        if not isinstance(executable, str) or not executable:
            return None
        path = Path(executable)
        return path if path.is_file() else None
    except (OSError, ValueError):
        return None


def build_dssat(version: str, install_dir: Path) -> Path:
    """Clone, build and install a release, recording its installed executable."""
    prefix = install_dir.resolve()
    if len(str(prefix)) > MAX_PREFIX_LENGTH:
        raise DSSATInstallError(
            f"Cannot install DSSAT: prefix {prefix} is {len(str(prefix))} characters long; "
            f"the limit is {MAX_PREFIX_LENGTH}. "
            "Set the XDG_CACHE_HOME environment variable to a shorter folder "
            "(for example ~/dl) and try again."
        )
    work = prefix.parent / "work" / version
    source = work / "source"
    build = work / "build"
    tag = f"v{version}"
    try:
        work.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DSSATInstallError(
            f"Could not create work directory {work}: {exc}. "
            "Choose a writable installation directory and retry."
        ) from exc

    commands = [
        ("Git clone", ["git", "clone", "--depth", "1", "--branch", tag,
                       "https://github.com/DSSAT/dssat-csm-os", str(source)]),
        ("CMake configure", ["cmake", "-S", str(source), "-B", str(build),
                             "-DCMAKE_BUILD_TYPE=RELEASE", f"-DCMAKE_INSTALL_PREFIX={prefix}"]),
        ("CMake build", ["cmake", "--build", str(build), "--parallel"]),
        ("CMake install", ["cmake", "--install", str(build)]),
    ]
    for step, command in commands:
        # Reuse source from a previous build; cloning into it would fail.
        if step == "Git clone" and (source / "CMakeLists.txt").is_file():
            continue
        try:
            result = subprocess.run(command, capture_output=True, text=True)
        except OSError as exc:
            raise DSSATInstallError(
                f"{step} could not start. Command: {shlex.join(command)}\n{exc}\n"
                "Check the tool is installed and accessible on PATH, then retry."
            ) from exc
        if result.returncode != 0:
            stdout_tail = "\n".join((result.stdout or "").splitlines()[-20:])
            stderr_tail = "\n".join((result.stderr or "").splitlines()[-20:])
            raise DSSATInstallError(
                f"{step} failed with exit code {result.returncode}. "
                f"Command: {shlex.join(command)}\n"
                f"stdout (last 20 lines):\n{stdout_tail}\n"
                f"stderr (last 20 lines):\n{stderr_tail}\n"
                "Check the command output, network/tag, build tools, and directory "
                "permissions. Retry with a fresh installation directory if needed."
            )

    executable = prefix / "dscsm048"
    try:
        installed = executable.is_file()
    except OSError as exc:
        raise DSSATInstallError(
            f"Could not check the installed DSSAT executable at {executable}: "
            f"{exc}. Check directory permissions and retry."
        ) from exc
    if not installed:
        raise DSSATInstallError(
            "DSSAT build and install commands succeeded, but the installed DSSAT "
            f"executable was not found. Checked {executable} for a file. "
            "Inspect the CMake install output and directory permissions, then retry."
        )

    manifest = {"version": version, "tag": tag, "executable": str(executable),
                "platform": "linux", "prefix": str(prefix)}
    try:
        commit = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        )
        if commit.returncode == 0 and commit.stdout.strip():
            manifest["commit"] = commit.stdout.strip()
    except OSError:
        pass  # Optional provenance must not turn a successful build into a failure.
    manifest_path = prefix / "manifest.json"
    try:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise DSSATInstallError(
            f"DSSAT built at {executable}, but could not write {manifest_path}: {exc}. "
            "Check directory permissions or connect to the executable explicitly."
        ) from exc
    return executable
