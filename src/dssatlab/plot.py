"""Plot plant growth variables from DSSAT output files across simulations."""

from collections.abc import Sequence
from pathlib import Path

from .errors import DSSATError, DSSATOutputError
from .outputs import read_plant_growth, read_summary


_EXCLUDED_COLUMNS = {"YEAR", "DOY", "DATE", "RUNNO", "TRNO"}


def plot_plant_growth(run_dirs: str | Path | Sequence[str | Path], variable: str):
    """Draw a plant growth variable against date across simulations.

    One line is drawn per simulation (each distinct RUNNO/TRNO pair in each
    run directory), labelled by the treatment name from Summary.OUT.

    Parameters:
        run_dirs: A run directory path or sequence of run directory paths.
        variable: DSSAT plant growth variable name (e.g. 'LAID', 'CWAD').

    Returns:
        The matplotlib Axes containing the plotted lines.

    Raises:
        DSSATError: If matplotlib is not installed.
        DSSATOutputError: If output files are missing/malformed or variable is unknown.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise DSSATError(
            "Plotting needs matplotlib. Install it with: pip install dssatlab[plot]"
        ) from exc

    if isinstance(run_dirs, (str, Path)):
        run_dirs = [run_dirs]
    dirs = [Path(d) for d in run_dirs]

    if not dirs:
        raise DSSATOutputError(
            "No run directories were given to plot_plant_growth(). "
            "Pass one run directory, or a list of run directories to compare."
        )

    simulations = []
    for run_dir in dirs:
        growth_rows = read_plant_growth(run_dir)
        available = sorted({key for row in growth_rows for key in row
                            if key not in _EXCLUDED_COLUMNS})
        if variable not in available:
            raise DSSATOutputError(
                f"Unknown plant growth variable {variable!r} in {run_dir}. "
                f"Checked the columns of PlantGro.OUT there. "
                f"Available variables are: {', '.join(available)}. "
                "Choose an available growth variable to plot."
            )
        names = {(row["RUNNO"], row["TRNO"]): row["TNAM"] for row in read_summary(run_dir)}
        groups = {}
        for row in growth_rows:
            groups.setdefault((row["RUNNO"], row["TRNO"]), []).append(row)
        for key, rows in groups.items():
            simulations.append((names.get(key) or f"Run {key[0]} Treatment {key[1]}", rows))

    fig, ax = plt.subplots()
    for label, rows in simulations:
        dates = []
        values = []
        for row in rows:
            d = row.get("DATE")
            val = row.get(variable)
            if d is not None and val is not None:
                dates.append(d)
                values.append(val)
        ax.plot(dates, values, label=label)

    ax.set_title(f"Plant growth: {variable}")
    ax.set_xlabel("Date")
    ax.set_ylabel(variable)
    ax.legend()
    return ax
