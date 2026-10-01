"""Plot Plant growth across simulations and Evaluation against observed data."""

from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from .errors import DSSATError, DSSATOutputError
from .evaluate import Evaluation
from .outputs import _SUMMARY_DATES, _date_value, read_plant_growth, read_summary


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


def plot_evaluation(evaluation: Evaluation, variable: str | None = None):
    """Draw simulated versus observed pairs with a dashed 1:1 line (v0.8 story 11).

    Parameters:
        evaluation: The Evaluation returned by evaluate().
        variable: DSSAT variable name, required when pairs contain multiple variables.

    Values retain their original units; date variables use calendar axes. Statistics
    are not required, so a variable with only one pair can also be plotted.

    Returns:
        The matplotlib Axes containing the scatter plot.

    Raises:
        DSSATError: If matplotlib is missing, there are no pairs, or the variable
            is unknown or must be selected to avoid mixing units.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise DSSATError(
            "Plotting needs matplotlib. Install it with: pip install dssatlab[plot]"
        ) from exc

    available = sorted({pair["variable"] for pair in evaluation.pairs})
    if not available:
        raise DSSATError(
            "Cannot plot an empty Evaluation: checked pairs and found none. "
            "Use evaluate() with observed measurements and matching results first."
        )
    if variable is None:
        if len(available) != 1:
            raise DSSATError(
                "Cannot plot multiple variables together because their units may differ. "
                "Checked Evaluation pairs. "
                f"Available variables are: {', '.join(available)}. "
                f"Choose one with plot_evaluation(evaluation, variable={available[0]!r})."
            )
        variable = available[0]
    if variable not in available:
        raise DSSATError(
            f"Unknown Evaluation variable {variable!r}. Checked Evaluation pairs. "
            f"Available variables are: {', '.join(available)}. "
            "Choose an available variable to plot."
        )

    pairs = [pair for pair in evaluation.pairs if pair["variable"] == variable]
    observed = [pair["observed"] for pair in pairs]
    simulated = [pair["simulated"] for pair in pairs]
    if variable in _SUMMARY_DATES:
        observed = [_date_value(variable, str(value)) for value in observed]
        simulated = [_date_value(variable, str(value)) for value in simulated]
    low, high = min(observed + simulated), max(observed + simulated)
    if low == high:
        padding = timedelta(days=1) if variable in _SUMMARY_DATES else abs(low) * 0.05 or 0.5
        low, high = low - padding, high + padding

    fig, ax = plt.subplots()
    ax.scatter(observed, simulated, label=variable)
    ax.plot([low, high], [low, high], linestyle="--", color="gray")
    ax.set_title(f"Evaluation: {variable}")
    ax.set_xlabel("Observed")
    ax.set_ylabel("Simulated")
    ax.legend()
    return ax
