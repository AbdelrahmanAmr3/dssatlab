"""Check and run FileX treatments under named whole-input overrides."""

from pathlib import Path
import statistics

from .errors import DSSATCheckError, DSSATError, DSSATRunError
from .filex import read_treatment_numbers
from .filex_template import _load_filex_template, _template_treatment_names
from .management_file import _load_yaml
from .outputs import read_summary
from .runner import RunResult, _resolve_directory
from .simulation import Simulation
from .climate import _select_batch_weather


_ALLOWED = ("weather", "soil", "management")


def _scenario_inputs(source, include_base=True):
    """Return (name, overrides, problems) entries, optionally starting with base."""
    data, problems = _load_yaml(source, "Scenario", "scenario names as keys")
    if source is not None and not problems and not isinstance(data, dict):
        problems.append("Scenarios must be a mapping of names to override dicts. "
                        "Supply a dict or a YAML path.")
    entries = [("base", {}, problems)] if include_base else []
    if source is None or problems:
        if problems and not include_base:
            raise DSSATCheckError(problems)
        return entries
    for name, overrides in data.items():
        found = []
        if not isinstance(name, str) or not name.strip():
            found.append("Scenario name must be a non-empty string. Quote names in YAML.")
        if not isinstance(overrides, dict):
            found.append("Scenario overrides must be a dict. Use only weather, soil, "
                         "management, or {} to keep all inputs.")
            overrides = {}
        found.extend(f"Unknown scenario key {key!r}. Allowed keys: weather, soil, management. "
                     "Correct or remove the unknown key."
                     for key in overrides if key not in _ALLOWED)
        if name == "base":
            if overrides:
                found.append("The scenario name 'base' is reserved for unchanged inputs. "
                             "Use another name for overrides, or supply base: {}.")
            problems.extend(found)
        else:
            entries.append((name, {k: v for k, v in overrides.items() if k in _ALLOWED}, found))
    if problems and not include_base:
        raise DSSATCheckError(problems)
    return entries


def _select_treatments(filex, filex_template, treatments):
    """Select treatment numbers without changing their order or validation."""
    if (filex is None) == (filex_template is None):
        raise DSSATCheckError(["Supply exactly one of filex or filex_template."])
    if treatments is None and filex_template is not None:
        data, _ = _load_filex_template(filex_template)
        # Simulation reports malformed or unreadable templates through its checks.
        treatments = list(range(1, len(_template_treatment_names(data)) + 1))
    elif treatments is None:
        try:
            treatments = list(dict.fromkeys(read_treatment_numbers(filex)))
        except ValueError as error:
            raise DSSATCheckError([f"Scenario 'base', treatment all: {error}"]) from error
    if not isinstance(treatments, (list, tuple)) or not treatments:
        raise DSSATCheckError([
            "Scenario 'base', treatment selection: supply a non-empty list or tuple of "
            "treatment numbers, or None for all treatments."
        ])

    return treatments


def run_treatments(filex=None, weather=None, treatments=None, soil=None, management=None,
                   executable=None, scenarios=None, filex_template=None, *,
                   directory=None, _include_base=True) -> dict[tuple[str, int], RunResult]:
    """Check every scenario/treatment, then run each in its own simulation folder.

    Supply exactly one of ``filex`` (a FileX path) or ``filex_template`` (a YAML
    path or dict). Templates require soil data, as for Simulation. Simulation
    folders go beside the FileX or template YAML, or in the current directory
    for a template dict. With ``directory=`` (str or Path), simulation folders
    go inside that directory, with run directories inside each simulation folder.
    Relative paths are resolved against cwd at this call; missing parents are created.

    ``treatments=None`` selects each FileX treatment number once in file order, or 1..N
    in template name order (one for ``treatment_name``). Otherwise,
    pass a non-empty list or tuple of distinct treatment numbers (ints or digit
    strings, as for Simulation); their order is retained in the results.

    ``scenarios`` is a dict {name: overrides} or a strict YAML file path (needs
    optional PyYAML). Each weather, soil or management override replaces that
    whole input. Omitted keys inherit the base input; None explicitly clears
    optional soil or management. Paths use the current working directory,
    just as in Simulation. Names must be non-empty strings. ``base: {}`` is
    accepted; base overrides are rejected. Base always runs first, followed by
    scenarios in mapping order, with treatments in the selected order.

    Uses Simulation's input checks, including scenario name column fit. Each
    scenario checks unused weather across its selected treatments; each Simulation
    receives measured weather for WTHER M or a climate file for WTHER W/S.
    Each copied treatment receives its scenario name, except "base", which keeps
    the FileX treatment name. With experiment overrides, the field receives
    the weather station and supplied soil ID. Otherwise the FileX station
    and soil ID must match the supplied data.
    All problems are labelled by scenario and treatment
    in one DSSATCheckError, before any files are written or DSSAT is run.
    The first DSSATRunError stops the batch and names earlier kept run
    directories. ``executable`` selects the DSSAT executable as for Simulation.
    """
    directory = _resolve_directory(directory)
    treatments = _select_treatments(filex, filex_template, treatments)

    base = dict(weather=weather, soil=soil, management=management)
    simulations, problems = [], []
    for name, overrides, scenario_problems in _scenario_inputs(scenarios, include_base=_include_base):
        inputs = {**base, **overrides}
        selected = [Simulation(filex, treatment, filex_template=filex_template,
                               executable=executable, name=name, directory=directory, **inputs)
                    for treatment in treatments]
        if filex_template is None:
            problems.extend(f"Scenario {name!r}, treatment all: {problem}"
                            for problem in _select_batch_weather(selected, inputs["weather"]))
        seen = set()
        for treatment, sim in zip(treatments, selected):
            found, _ = sim._check_inputs()
            # Simulation reports invalid treatment types/values; only normalize
            # here to detect aliases such as 1 and "01" before results overwrite.
            try:
                number = int(treatment)
            except (TypeError, ValueError, OverflowError):
                number = None
            duplicate = []
            if number is not None:
                if number in seen:
                    duplicate.append("Duplicate treatment number. Select each treatment only once.")
                seen.add(number)
            problems.extend(f"Scenario {name!r}, treatment {treatment}: {problem}"
                            for problem in scenario_problems + found + duplicate)
            simulations.append((name, number, sim))
    if problems:
        raise DSSATCheckError(problems)

    results = {}
    for name, treatment, sim in simulations:
        try:
            results[name, treatment] = sim.run()
        except DSSATRunError as error:
            kept = "\n".join(str(result.run_dir) for result in results.values()) or "None."
            raise DSSATRunError(
                f"Scenario {name!r}, treatment {treatment}: {error}\n"
                f"Earlier run directories (kept):\n{kept}\n"
                "Batch stopped. Inspect the run directories and correct the reported problem "
                "before running again."
            ) from error
    return results


def combine_summaries(results: dict[tuple[str, int], RunResult]) -> list[dict]:
    """Read every run's Summary rows, adding scenario and treatment result keys.

    Retains result and row order, DSSAT column names, dates and missing values.
    Returns [] for no results; the rows can be passed directly to to_dataframe.
    Missing or malformed Summary.OUT files raise DSSATOutputError.
    """
    return [dict(row, scenario=scenario, treatment=treatment)
            for (scenario, treatment), result in results.items()
            for row in read_summary(result.run_dir)]


def summarize_seasons(rows: list[dict], variables=("HWAM",)) -> list[dict]:
    """Return season statistics per scenario, treatment, rotation component and variable.

    Takes result.summary() rows (scenario "base", treatment = TRNO) or combine_summaries()
    rows. A sequence's Summary has one row per component run: R# names the rotation
    component (1 when absent or None), and CR names the crop. Groups retain first
    appearance order and take the crop from their first row. Missing values (None)
    are counted and left out of the statistics.
    """
    problems = []
    if (not isinstance(variables, (list, tuple)) or not variables
            or not all(isinstance(name, str) for name in variables)):
        problems.append(f"Variables: found {variables!r}. "
                        "Supply variables as a list of Summary column names, such as ['HWAM'].")
        variables = ()
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise DSSATCheckError(["Summary rows: expected a list of dicts. Supply the rows from "
                               "result.summary() or combine_summaries().", *problems])
    if not rows:
        if problems:
            raise DSSATCheckError(problems)
        return []
    groups = {}
    for number, row in enumerate(rows, 1):
        treatment = row["treatment"] if row.get("treatment") is not None else row.get("TRNO")
        if treatment is None:
            problems.append(f"Summary row {number}: found neither 'treatment' nor 'TRNO'. "
                            "Supply rows from result.summary() or combine_summaries().")
        component = row["R#"] if row.get("R#") is not None else 1
        groups.setdefault((row.get("scenario") or "base", treatment, component), []).append(row)
    for name in variables:
        if not any(name in row for row in rows):
            problems.append(f"Variable {name!r} is not a Summary column. "
                            "Use a column name from the Summary rows, such as HWAM.")
    for (scenario, treatment, component), group in groups.items():
        for name in variables:
            bad = [value for value in (row.get(name) for row in group) if value is not None
                   and (isinstance(value, bool) or not isinstance(value, (int, float)))]
            if bad:  # One problem per group, not one per season.
                problems.append(f"Variable {name!r} has a non-numeric value {bad[0]!r} (scenario "
                                f"{scenario!r}, treatment {treatment}). Choose a numeric Summary column.")
    if problems:
        raise DSSATCheckError(problems)

    summary = []
    for (scenario, treatment, component), group in groups.items():
        for name in variables:
            values = [row[name] for row in group if row.get(name) is not None]
            stats = dict.fromkeys(("mean", "sd", "min", "p25", "median", "p75", "max"))
            if values:
                quartiles = (statistics.quantiles(values, n=4, method="inclusive")
                             if len(values) > 1 else values * 3)
                stats.update(mean=statistics.mean(values), min=min(values), max=max(values),
                             sd=statistics.stdev(values) if len(values) > 1 else None,
                             p25=quartiles[0], median=quartiles[1], p75=quartiles[2])
            summary.append({"scenario": scenario, "treatment": treatment,
                            "component": component, "crop": group[0].get("CR"), "variable": name,
                            "seasons": len(group), "missing": len(group) - len(values), **stats})
    return summary


_SCENARIO_TEMPLATE = """# DSSATLab Scenario Template
# Map each quoted scenario name directly to its overrides (no enclosing key).
# The unchanged "base" scenario is always included; do not override it.
# Allowed keys: weather, soil, management. Omitted keys keep the base input.
# An override replaces the WHOLE input; nested management data is never merged.
# YAML loading needs optional PyYAML: pip install pyyaml.
# Paths are relative to the current working directory, as for Simulation.
# Weather must match the WSTA of EVERY selected FileX treatment.
# Quote all dates in inline management as "YYYY-MM-DD"; quote names and paths.
# Select treatments in Python, not as a key in this YAML:
{treatments_comment}
# This empty example is valid and keeps every base input. Replace {{}} with
# any of the commented fields below after supplying your data files.
"example": {{}}
#  weather: "weather.csv"       # Full weather template CSV
#  soil: "soil.csv"             # Full soil template CSV; null uses sibling soil files
#  management: "management.yaml" # Full management template YAML (or inline dict)
#  management: null             # Alternative: keep the FileX management unchanged
"""


def write_scenario_template(path: str | Path, filex=None) -> None:
    """Write a commented UTF-8 YAML template without requiring PyYAML.

    Refuses an existing path with DSSATError. When filex is supplied, reads only
    its treatment numbers and lists them in a Python-call comment; treatment
    selection remains the run_treatments argument, not a scenario override.
    No weather, soil or management values are read from the FileX.
    """
    path = Path(path)
    message = f"Scenario template path {path} already exists. Choose another path."
    if path.exists():
        raise DSSATError(message)
    treatments = "None" if filex is None else str(list(dict.fromkeys(read_treatment_numbers(filex))))
    text = _SCENARIO_TEMPLATE.format(
        treatments_comment=f"# run_treatments(filex, weather, treatments={treatments}, scenarios=path)\n")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as error:
        raise DSSATError(message) from error
