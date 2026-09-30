"""Run one existing FileX and collect the files DSSAT writes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import shlex
import shutil
import subprocess

from . import core
from .core import connect
from .errors import DSSATRunError
from .outputs import (read_plant_growth, read_plant_nitrogen, read_soil_water,
                      read_summary, read_weather)


@dataclass(frozen=True)
class RunResult:
    """Exit status, run directory, output paths and console tail for one run."""

    returncode: int
    run_dir: Path
    outputs: list[Path] = field(repr=False)
    stdout_tail: str = field(repr=False)

    def __repr__(self) -> str:
        return (f"RunResult(returncode={self.returncode}, run_dir={str(self.run_dir)!r}, "
                f"{len(self.outputs)} output files)")

    def summary(self) -> list[dict]:
        """Read the Summary from this run directory."""
        return read_summary(self.run_dir)

    def plant_growth(self) -> list[dict]:
        """Read the Plant growth from this run directory."""
        return read_plant_growth(self.run_dir)

    def soil_water(self) -> list[dict]:
        """Read soil water from this run directory."""
        return read_soil_water(self.run_dir)

    def plant_nitrogen(self) -> list[dict]:
        """Read plant nitrogen from this run directory."""
        return read_plant_nitrogen(self.run_dir)

    def weather(self) -> list[dict]:
        """Read the weather DSSAT used from this run directory."""
        return read_weather(self.run_dir)

    def plot(self, variable: str):
        """Plot a Plant growth variable from this run directory."""
        from .plot import plot_plant_growth
        return plot_plant_growth(self.run_dir, variable)


def _create_dated_folder(parent: Path, prefix: str, label: str) -> Path:
    """Create a fresh dated folder, adding a suffix for each existing name."""
    directory_name = prefix + datetime.now().strftime("%Y-%m-%d_%H%M%S")
    folder = parent / directory_name
    suffix = 2
    while True:
        try:
            folder.mkdir(exist_ok=False)
            return folder
        except FileExistsError:
            folder = parent / f"{directory_name}-{suffix}"
            suffix += 1
        except OSError as error:
            raise DSSATRunError(
                f"Cannot create {label} {folder}: the FileX folder "
                f"{parent} is not writable ({error}). "
                "Move the FileX somewhere writable and try again."
            ) from error


# DSSAT removes <name>.csv from its working directory when it writes that Output file.
# Checked on real DSSAT 4.8 (Windows); other names may exist.
_DELETED_CSV = {"et", "evaluate", "mulch", "plantgro", "plantn", "soilni", "soilwat",
                "summary", "weather"}


def run(
    filex: str | Path,
    treatment: int | None = None,
    executable: str | Path | None = None,
) -> RunResult:
    """Run all treatments or one treatment, collecting outputs even on failure.

    Executes the DSSAT executable on the specified FileX. Creates a dated run
    directory beside the FileX (dssat_run_YYYY-MM-DD_HHMMSS) and moves all output
    files generated or updated during the run into it.

    Args:
        filex: Path to the FileX experiment file (*.MZX, *.SBX, etc.). The filename
            must be at most 12 characters.
        treatment: Specific treatment number to run (DSSAT batch option C). If None,
            runs all treatments in the FileX (DSSAT batch option A).
        executable: Optional explicit path to the DSSAT executable or its directory.
            Validated without modifying saved configuration. If None, uses
            connect(interactive=False) to locate the executable.

    Returns:
        RunResult: Dataclass containing returncode, run_dir, outputs, and stdout_tail.

    Raises:
        DSSATRunError: If the FileX does not exist, its filename exceeds 12 characters,
            the FileX folder holds a .csv file DSSAT would delete (such as weather.csv),
            the DSSAT executable cannot be executed, DSSAT exits with a non-zero code,
            or ERROR.OUT is generated during the run.
    """
    filex = Path(filex).resolve()
    if not filex.is_file():
        raise DSSATRunError(
            f"Cannot run FileX {filex}: it does not exist or is not a file. "
            "Pass the path to an existing FileX."
        )
    if len(filex.name) > 12:
        raise DSSATRunError(
            f"Cannot run FileX {filex.name!r}: its filename has {len(filex.name)} "
            "characters; DSSAT accepts at most 12. Rename the FileX to at most "
            "12 characters, including the extension, using DSSAT's 8.3 style."
        )

    at_risk = sorted(path.name for path in filex.parent.iterdir()
                     if path.is_file() and path.suffix.lower() == ".csv"
                     and path.stem.lower() in _DELETED_CSV)
    if at_risk:
        raise DSSATRunError(
            f"Cannot run FileX {filex.name}: DSSAT deletes files named like its own "
            f"Output files from the FileX folder, and {filex.parent} holds "
            f"{', '.join(at_risk)}. Nothing was run. Rename or move them "
            "(for example my_weather.csv), or use Simulation, which runs in its own folder."
        )

    if executable is None:
        executable = connect(interactive=False)
    else:
        path = Path(executable)
        executable = core.find_dssat_path(path)
        if executable is None:
            raise core._invalid_path(path)

    run_dir = _create_dated_folder(filex.parent, "dssat_run_", "run directory")

    before = {path.name: path.stat().st_mtime_ns
              for path in filex.parent.iterdir() if path.is_file()}
    command = [str(executable), "A", filex.name]
    if treatment is not None:
        command = [str(executable), "C", filex.name, str(treatment)]
    try:
        completed = subprocess.run(
            command, cwd=filex.parent, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
    except OSError as error:
        run_dir.rmdir()
        raise DSSATRunError(
            f"Could not start the DSSAT executable: {shlex.join(command)}\n"
            f"{error}\nCheck the DSSAT executable path and execute permission, "
            "then try again."
        ) from error
    after = {path.name: path.stat().st_mtime_ns
             for path in filex.parent.iterdir() if path.is_file()}

    outputs = []
    for name in sorted(after):
        if name not in before or after[name] != before[name]:
            destination = run_dir / name
            shutil.move(filex.parent / name, destination)
            outputs.append(destination)

    stdout_tail = "\n".join(completed.stdout.splitlines()[-20:])
    error_out = run_dir / "ERROR.OUT"
    if completed.returncode != 0 or error_out in outputs:
        console_lines = completed.stdout.splitlines() + completed.stderr.splitlines()
        console_tail = "\n".join(console_lines[-20:])
        message = (
            f"DSSAT run failed (return code {completed.returncode}).\n"
            f"Command: {shlex.join(command)}\n"
            f"Console output (last 20 lines):\n{console_tail}\n"
        )
        if error_out in outputs:
            error_head = "\n".join(error_out.read_text(
                encoding="utf-8", errors="replace").splitlines()[:20])
            message += f"ERROR.OUT (first 20 lines):\n{error_head}\n"
        raise DSSATRunError(
            message + f"Run directory: {run_dir}\n"
            "Open ERROR.OUT and WARNING.OUT in the run directory for details; "
            "correct the reported problem and try again."
        )
    return RunResult(completed.returncode, run_dir, outputs, stdout_tail)
