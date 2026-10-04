"""Run one existing FileX and collect the files DSSAT writes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from . import core
from .core import connect
from .errors import DSSATRunError
from .filex import _treatment_rows
from .outputs import (read_dssat_evaluation, read_plant_growth,
                      read_plant_nitrogen, read_soil_water, read_summary,
                      read_weather)


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

    def dssat_evaluation(self) -> list[dict]:
        """Read the DSSAT evaluation from this run directory."""
        return read_dssat_evaluation(self.run_dir)

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


def _run_mode(filex, treatment, rows):
    """Pick the run mode from the selected (treatment, R) rows and FileX suffix."""
    numbers = [number for number, _ in rows]
    if filex.suffix.upper() == ".FCX":
        return "Y"
    if len(set(numbers)) == len(numbers):
        return "A" if treatment is None else "C"
    if treatment is None and len(set(numbers)) > 1:
        raise DSSATRunError(
            f"Cannot run FileX {filex.name} in sequence mode (Q) without a treatment: "
            f"it has treatments {', '.join(map(str, sorted(set(numbers))))}, and DSSAT "
            "runs one continuous batch, carrying each treatment into the next. "
            "Nothing was run. Pass run(filex, treatment=n) for each treatment."
        )
    return "Q"


def _batch_text(filex_name, mode, rows):
    """Render Q/Y batch rows in DSSAT's fixed columns, with CRLF line endings."""
    header = "@FILEX                                                                                        TRTNO     RP     SQ     OP     CO"
    lines = ["$BATCH(SEQUENCE)" if mode == "Q" else "$BATCH(FORECAST)", "", header]
    if mode == "Y":
        rows = [(number, 0) for number in dict.fromkeys(number for number, _ in rows)]
    lines.extend(f"{filex_name:<92}{int(number):7d}{1:7d}{int(rotation):7d}{0:7d}{0:7d}"
                 for number, rotation in rows)
    return "\r\n".join(lines) + "\r\n"


def run(
    filex: str | Path,
    treatment: int | None = None,
    executable: str | Path | None = None,
) -> RunResult:
    """Run all treatments or one treatment, collecting outputs even on failure.

    Executes the DSSAT executable on the specified FileX. Creates a dated run
    directory beside the FileX (dssat_run_YYYY-MM-DD_HHMMSS) and moves all output
    files generated or updated during the run into it. Picks forecast mode Y for
    .FCX, sequence mode Q for a selected treatment with several TREATMENTS rows,
    otherwise A (all treatments) or C (one treatment). Q/Y write DSSBatch.v48 and
    collect it with the outputs; a failed launch removes it.

    Args:
        filex: Path to the FileX experiment file (*.MZX, *.SBX, etc.). The filename
            must be at most 12 characters, and exactly 12 for Q/Y.
        treatment: Specific treatment number to run. If None, runs all treatments;
            a FileX containing a sequence must have just one treatment number.
        executable: Optional explicit path to the DSSAT executable or its directory.
            Validated without modifying saved configuration. If None, uses
            connect(interactive=False) to locate the executable.

    Returns:
        RunResult: Dataclass containing returncode, run_dir, outputs, and stdout_tail.

    Raises:
        DSSATRunError: If the FileX does not exist, its filename has an invalid length,
            a Q/Y run finds DSSBatch.v48 or Q needs a treatment selected,
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

    rows = [(int(number), rotation) for _, (number, rotation) in
            _treatment_rows(filex.read_text(encoding="latin-1")) if number]
    selected = int(treatment) if isinstance(treatment, str) and treatment.isdigit() else treatment
    rows = [row for row in rows if treatment is None or row[0] == selected]
    mode = _run_mode(filex, treatment, rows)
    batch_text = None
    if mode in ("Q", "Y"):
        label = "sequence mode (Q)" if mode == "Q" else "forecast mode (Y)"
        if (filex.parent / "DSSBatch.v48").exists():
            raise DSSATRunError(
                f"Cannot run FileX {filex.name} in {label}: {filex.parent} already holds "
                "DSSBatch.v48, which run() writes. Nothing was run. Move or rename it"
                + (", or use Simulation, which runs in its own folder." if mode == "Q" else
                   ", or copy the forecast FileX and its inputs to their own folder.")
            )
        if len(filex.name) != 12:
            raise DSSATRunError(
                f"Cannot run FileX {filex.name!r}: its filename has {len(filex.name)} "
                f"characters; DSSAT's {label} accepts exactly 12. Rename the FileX "
                "to exactly 12 characters, including the extension, using DSSAT's 8.3 style."
            )
        arguments = [mode, "DSSBatch.v48"]
        batch_text = _batch_text(filex.name, mode, rows)
    else:
        arguments = ["A", filex.name] if treatment is None else ["C", filex.name, str(treatment)]
    return _run_command(filex.parent, arguments, executable, batch_text)


def _run_command(folder: Path, arguments: list[str], executable=None, batch_text=None) -> RunResult:
    """Resolve DSSAT, execute its arguments, and collect outputs in a run directory."""
    if executable is None:
        executable = connect(interactive=False)
    else:
        path = Path(executable)
        executable = core.find_dssat_path(path)
        if executable is None:
            raise core._invalid_path(path)

    run_dir = _create_dated_folder(folder, "dssat_run_", "run directory")

    before = {path.name: path.stat().st_mtime_ns
              for path in folder.iterdir() if path.is_file()}
    if batch_text is not None:
        (folder / "DSSBatch.v48").write_bytes(batch_text.encode("latin-1"))
    command = [str(executable), *arguments]
    try:
        completed = subprocess.run(
            command, cwd=folder, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
    except OSError as error:
        if batch_text is not None:
            (folder / "DSSBatch.v48").unlink()
        run_dir.rmdir()
        raise DSSATRunError(
            f"Could not start the DSSAT executable: {shlex.join(command)}\n"
            f"{error}\nCheck the DSSAT executable path and execute permission, "
            "then try again."
        ) from error
    after = {path.name: path.stat().st_mtime_ns
             for path in folder.iterdir() if path.is_file()}

    outputs = []
    for name in sorted(after):
        if name not in before or after[name] != before[name]:
            destination = run_dir / name
            shutil.move(folder / name, destination)
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


def _check_missing_weather(result):
    """Raise when DSSAT silently ran out of measured weather."""
    warning = result.run_dir / "WARNING.OUT"
    if warning.exists():
        for line in warning.read_text(encoding="utf-8", errors="replace").splitlines():
            missing = re.search(r"Weather record not found for YR DOY:\s+(\d{4})\s+(\d{1,3})", line)
            if missing:
                year, day = map(int, missing.groups())
                calendar_date = date(year, 1, 1) + timedelta(days=day - 1)
                raise DSSATRunError(
                    f"DSSAT reported no weather for year {year}, day of year {day} "
                    f"({calendar_date}). DSSAT exits 0 in this case and gives -99 "
                    "for anything it could not reach.\n"
                    f"Run directory (kept): {result.run_dir}\n"
                    "Extend the weather data through that date and the days the "
                    "crop needs, then run again."
                )
