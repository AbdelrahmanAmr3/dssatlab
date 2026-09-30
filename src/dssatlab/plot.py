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
            "No run directories provided. "
            "Checked run_dirs argument; expected at least one run directory. "
            "Pass one or more run directories to plot_plant_growth()."
        )

    simulations = []
    all_available_vars = set()

    for run_dir in dirs:
        growth_rows = read_plant_growth(run_dir)
        summary_rows = read_summary(run_dir)
        summary_map = {
            (row["RUNNO"], row["TRNO"]): row.get("TNAM")
            for row in summary_rows
        }

        sim_groups = {}
        for row in growth_rows:
            sim_key = (row["RUNNO"], row["TRNO"])
            if sim_key not in sim_groups:
                sim_groups[sim_key] = []
            sim_groups[sim_key].append(row)
            for k in row:
                if k not in _EXCLUDED_COLUMNS:
                    all_available_vars.add(k)

        for (runno, trno), rows in sim_groups.items():
            tnam = summary_map.get((runno, trno))
            label = tnam or f"Run {runno} Treatment {trno}"
            simulations.append((label, rows))

    if variable not in all_available_vars:
        available_list = sorted(all_available_vars)
        checked = "Checked PlantGro.OUT in the run directory for plant growth variables."
        next_step = (
            f"Available variables are: {', '.join(available_list)}. "
            "Choose an available growth variable to plot."
        )
        raise DSSATOutputError(
            f"Unknown plant growth variable {variable!r}. {checked} {next_step}"
        )

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

    ax.legend()
    return ax
