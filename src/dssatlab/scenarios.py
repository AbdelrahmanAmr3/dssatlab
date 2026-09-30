"""Check and run FileX treatments under named whole-input overrides."""

from pathlib import Path

from .errors import DSSATCheckError, DSSATError, DSSATRunError
from .filex import read_treatment_numbers
from .management_file import _load_yaml
from .outputs import read_summary
from .runner import RunResult
from .simulation import Simulation


_ALLOWED = ("weather", "soil", "management")


def _scenario_inputs(source):
    """Return (name, overrides, problems) entries, starting with unchanged base."""
    data, problems = _load_yaml(source, "Scenario", "scenario names as keys")
    entries = [("base", {}, problems)]
    if source is None or problems:
        return entries
    if not isinstance(data, dict):
        problems.append("Scenarios must be a mapping of names to override dicts. "
                        "Supply a dict or a YAML path.")
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
    return entries


def run_treatments(filex, weather, treatments=None, soil=None, management=None,
                   executable=None, scenarios=None) -> dict[tuple[str, int], RunResult]:
    """Check every scenario/treatment, then run each in its own simulation folder.

    ``treatments=None`` selects every FileX treatment in file order. Otherwise,
    pass a non-empty list or tuple of distinct treatment numbers (ints or digit
    strings, as for Simulation); their order is retained in the results.

    ``scenarios`` is a dict {name: overrides} or a strict YAML file path (needs
    optional PyYAML). Each weather, soil or management override replaces that
    whole input. Omitted keys inherit the base input; None explicitly clears
    optional soil or management. Paths use the current working directory,
    just as in Simulation. Names must be non-empty strings. ``base: {}`` is
    accepted; base overrides are rejected. Base always runs first, followed by
    scenarios in mapping order, with treatments in the selected order.

    Uses Simulation's input checks. With experiment overrides for a treatment,
    its copy receives the scenario name, weather station and supplied soil ID.
    Otherwise the FileX station and soil ID must match the supplied data.
    All problems are labelled by scenario and treatment
    in one DSSATCheckError, before any files are written or DSSAT is run.
    The first DSSATRunError stops the batch and names earlier kept run
    directories. ``executable`` selects the DSSAT executable as for Simulation.
    """
    if treatments is None:
        try:
            treatments = read_treatment_numbers(filex)
        except ValueError as error:
            raise DSSATCheckError([f"Scenario 'base', treatment all: {error}"]) from error
    if not isinstance(treatments, (list, tuple)) or not treatments:
        raise DSSATCheckError([
            "Scenario 'base', treatment selection: supply a non-empty list or tuple of "
            "treatment numbers, or None for all FileX treatments."
        ])

    base = dict(weather=weather, soil=soil, management=management)
    simulations, problems = [], []
    for name, overrides, scenario_problems in _scenario_inputs(scenarios):
        inputs = {**base, **overrides}
        seen = set()
        for treatment in treatments:
            sim = Simulation(filex, treatment, executable=executable, name=name, **inputs)
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
    treatments = "None" if filex is None else str(read_treatment_numbers(filex))
    text = _SCENARIO_TEMPLATE.format(
        treatments_comment=f"# run_treatments(filex, weather, treatments={treatments}, scenarios=path)\n")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as error:
        raise DSSATError(message) from error
