"""Run a grid of experiment data sections as named scenarios."""

from copy import deepcopy
from itertools import product
import math
from pathlib import Path

from .errors import DSSATCheckError
from .management_file import _load_management
from .scenarios import _select_treatments, combine_summaries, run_treatments


_SECTIONS = ("planting", "irrigation", "fertilizer", "cultivar",
             "initial_conditions", "controls", "rotation")


def run_sweep(filex=None, weather=None, factors=None, treatments=None, soil=None,
              management=None, executable=None, filex_template=None) -> list[dict]:
    """Check every grid combination and treatment, then return labelled Summary rows.

    Supply a non-empty ``factors`` dict mapping experiment data section names to
    labelled complete section values. Labels are printable non-empty strings or
    finite numbers (not booleans). Combinations retain factor and value order;
    their scenario names join the labels with spaces.

    Each combination deep-copies the base experiment data (``management`` dict,
    optional PyYAML path, or None), replacing each factor's whole section on
    every selected treatment. Caller data is never changed. Other arguments
    and treatment selection mean exactly what they mean for run_treatments,
    including copied FileX and FileX template inputs.

    All sweep problems raise one DSSATCheckError before run_treatments is called.
    Its Simulation checks validate section values and scenario names before any
    run; the first DSSATRunError stops the sweep and names kept run directories.
    Base runs first. Each Summary row gains scenario, treatment, factor labels
    (None for base), and run_dir (Path). Missing or malformed Summary.OUT raises
    DSSATOutputError, as for combine_summaries.

    For a cultivar coefficient sweep, supply complete cultivar sections:
        factors={"cultivar": {p1: {"crop": "MZ", "code": "IB0035",
                 "coefficients": {"P1": p1}} for p1 in (200, 259, 320)}}
    """
    base, problems = _load_management(management)
    if management is None:
        base = {"treatments": {}}
    if not isinstance(factors, dict) or not factors:
        problems.append("Sweep factors: supply a non-empty dict of experiment data sections "
                        "to labelled values, such as {'fertilizer': {0: [], 60: [...]}}.")
        factors = {}
    for section, values in factors.items():
        if section not in _SECTIONS:
            problems.append(f"Sweep factor {section!r} is not an experiment data section. "
                            f"Use one of: {', '.join(_SECTIONS)}.")
        if not isinstance(values, dict) or not values:
            problems.append(f"Sweep factor {section!r}: supply a non-empty dict of labels "
                            "to complete section values.")
            continue
        for label in values:
            valid = ((isinstance(label, str) and bool(label) and label.isprintable())
                     or (isinstance(label, (int, float)) and not isinstance(label, bool)
                         and (not isinstance(label, float) or math.isfinite(label))))
            if not valid:
                problems.append(f"Sweep factor {section!r}, label {label!r}: "
                                "use a non-empty string or a finite number.")

    labels_by_name = {}
    if factors and all(isinstance(values, dict) and values for values in factors.values()):
        for labels in product(*(values for values in factors.values())):
            name = " ".join(str(label) for label in labels)
            if name in labels_by_name:
                problems.append(f"Sweep scenario name {name!r} is given by more than one "
                                "combination. Use labels that stay distinct when joined by spaces.")
            if name == "base":
                problems.append("Sweep scenario name 'base' is reserved for the unchanged "
                                "inputs. Use another label.")
            labels_by_name[name] = dict(zip(factors, labels))
    try:
        selected = _select_treatments(filex, filex_template, treatments)
    except DSSATCheckError as error:
        problems.extend(error.problems)
    if problems:
        raise DSSATCheckError(problems)

    scenarios = {}
    for name, labels in labels_by_name.items():
        merged = deepcopy(base)
        # Malformed experiment data is left for Simulation's existing checks.
        entries = merged.get("treatments") if isinstance(merged, dict) else None
        if isinstance(entries, dict):
            for treatment in selected:
                try:
                    number = int(treatment)
                except (TypeError, ValueError, OverflowError):
                    continue  # Simulation reports invalid selected treatment values.
                key = number
                for candidate in entries:
                    try:
                        if int(candidate) == number:
                            key = candidate
                            break
                    except (TypeError, ValueError, OverflowError):
                        continue
                entry = entries.setdefault(key, {})
                if isinstance(entry, dict):
                    entry = entries[key] = dict(entry)
                    for section, label in labels.items():
                        entry[section] = deepcopy(factors[section][label])
        scenarios[name] = {"management": merged}

    results = run_treatments(filex=filex, weather=weather, treatments=treatments,
                             soil=soil, management=management, executable=executable,
                             filex_template=filex_template, scenarios=scenarios)
    rows = combine_summaries(results)
    for row in rows:
        name = row["scenario"]
        row.update(labels_by_name.get(name, dict.fromkeys(factors)))
        row["run_dir"] = Path(results[name, row["treatment"]].run_dir)
    return rows
