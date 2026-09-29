"""Run one existing FileX and collect the files DSSAT writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shlex
import shutil
import subprocess

from . import core
from .core import connect
from .errors import DSSATRunError


@dataclass(frozen=True)
class RunResult:
    """Exit status, run directory, output paths and console tail for one run."""

    returncode: int
    run_dir: Path
    outputs: list[Path]
    stdout_tail: str


def run(
    filex: str | Path,
    treatment: int | None = None,
    executable: str | Path | None = None,
) -> RunResult:
    """Run all treatments or one treatment, collecting outputs even on failure.

    An explicit DSSAT executable is validated without changing saved config.
    Failed runs raise DSSATRunError; completed runs keep their run directory.
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

    if executable is None:
        executable = connect(interactive=False)
    else:
        path = Path(executable)
        executable = core.find_dssat_path(path)
        if executable is None:
            raise core._invalid_path(path)

    directory_name = "dssat_run_" + datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = filex.parent / directory_name
    suffix = 2
    while True:
        try:
            run_dir.mkdir(exist_ok=False)
            break
        except FileExistsError:
            run_dir = filex.parent / f"{directory_name}-{suffix}"
            suffix += 1
        except OSError as error:
            raise DSSATRunError(
                f"Cannot create run directory {run_dir}: the FileX folder "
                f"{filex.parent} is not writable ({error}). "
                "Move the FileX somewhere writable and try again."
            ) from error

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
