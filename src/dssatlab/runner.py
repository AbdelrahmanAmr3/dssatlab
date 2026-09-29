"""Run one existing FileX and collect the files DSSAT writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import subprocess

from .core import connect
from .errors import DSSATRunError


@dataclass(frozen=True)
class RunResult:
    """Exit status, run directory, output paths and console tail for one run."""

    returncode: int
    run_dir: Path
    outputs: list[Path]
    stdout_tail: str


def run(filex: str | Path) -> RunResult:
    """Run all treatments of an existing FileX and collect new or changed files."""
    filex = Path(filex).resolve()
    if len(filex.name) > 12:
        raise DSSATRunError(
            f"Cannot run FileX {filex.name!r}: its filename has {len(filex.name)} "
            "characters; DSSAT accepts at most 12. Rename the FileX to at most "
            "12 characters, including the extension, using DSSAT's 8.3 style."
        )

    executable = connect(interactive=False)
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

    before = {path.name: path.stat().st_mtime_ns
              for path in filex.parent.iterdir() if path.is_file()}
    command = [str(executable), "A", filex.name]
    completed = subprocess.run(
        command, cwd=filex.parent, stdin=subprocess.DEVNULL,
        capture_output=True, text=True,
    )
    after = {path.name: path.stat().st_mtime_ns
             for path in filex.parent.iterdir() if path.is_file()}

    outputs = []
    for name in sorted(after):
        if name not in before or after[name] != before[name]:
            destination = run_dir / name
            shutil.move(filex.parent / name, destination)
            outputs.append(destination)

    stdout_tail = "\n".join(completed.stdout.splitlines()[-20:])
    return RunResult(completed.returncode, run_dir, outputs, stdout_tail)
