"""Checks and report lines for Management data supplied as a plain dict."""

from datetime import date
import math
from pathlib import Path
import re

from .filex import _section_row
from .weather import _show_value


_REQUIRED = ("date", "method", "distribution", "population", "row_spacing", "depth")
_OPTIONAL = ("emergence_date", "emergence_population", "row_direction",
             "planting_material_weight", "transplant_age", "transplant_environment",
             "plants_per_hill", "sprout_length")


def _report_lines(label, problems):
    status = "REJECTED" if problems else "OK"
    indent = " " * (len(label) - len(label.lstrip()) + 2)
    return [f"{label}: {status}"] + [f"{indent}{problem}" for problem in problems]


def _unknown_keys(data, allowed, where):
    return [f"{where}: unknown key {_show_value(key)}. Use only "
            f"{', '.join(allowed)} from the Management template."
            for key in data if key not in allowed]


def _check_planting(planting, where):
    if not isinstance(planting, dict) or not planting:
        return [f"{where}: planting must be a non-empty dict. Supply the required "
                f"fields: {', '.join(_REQUIRED)}; omit planting to keep the FileX Level."]
    problems = _unknown_keys(planting, _REQUIRED + _OPTIONAL, where)
    for field in _REQUIRED:
        if field not in planting:
            problems.append(f"{where}: missing required field {field!r}. "
                            f"Add {field!r} following the Management template.")
    for field in _REQUIRED + _OPTIONAL:
        if field not in planting:
            continue
        value = planting[field]
        location = f"{where}, field {field!r}"
        if field in ("date", "emergence_date"):
            try:
                if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError
                date.fromisoformat(value)
            except ValueError:
                problems.append(f"{location}: found {_show_value(value)}. Supply a "
                                'valid ISO calendar date as a quoted YYYY-MM-DD string '
                                '(for example "2024-05-10"); quote the date, even in a dict.')
        elif field in ("method", "distribution"):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]", value):
                problems.append(f"{location}: found {_show_value(value)}. Supply a "
                                "single ASCII letter for the DSSAT code.")
        else:
            try:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError
            except (ValueError, OverflowError):
                problems.append(f"{location}: found {_show_value(value)}. Supply a "
                                "finite number in DSSAT's units, not a string or boolean.")
                continue
            if field in ("population", "row_spacing") and value <= 0:
                unit = "plants per m2" if field == "population" else "cm"
                problems.append(f"{location}: found {_show_value(value)}. "
                                f"Supply a number above zero in {unit}.")
            elif field == "depth" and value < 0:
                problems.append(f"{location}: found {_show_value(value)}. "
                                "Supply a nonnegative depth in cm.")
    return problems


def _check_management(source, filex):
    """Check every treatment, returning problems and report lines without mutation.

    Only treatment membership is read from the FileX. When it is unreadable,
    Simulation's FileX checks report that failure and shape checks still run.
    Optional numeric fields pass through without crop-specific range checks.
    """
    label = "Management data"
    if not isinstance(source, dict):
        problems = ["Management data must be a dict. Supply a Management template "
                    "dict with a 'treatments' mapping."]
        return problems, _report_lines(label, problems)
    problems = _unknown_keys(source, ("treatments",), label)
    if "treatments" not in source:
        problems.append("Management data: missing 'treatments'. Add a 'treatments' "
                        "dict keyed by treatment number.")
    elif not isinstance(source["treatments"], dict):
        problems.append("Management data 'treatments' must be a dict. Supply "
                        "treatment numbers mapped to dicts of planting fields.")
    if not isinstance(source.get("treatments"), dict):
        return problems, _report_lines(label, problems)
    root_problems = list(problems)
    text = None
    if isinstance(filex, (str, Path)):
        try:
            text = Path(filex).read_text(encoding="latin-1")
        except (OSError, ValueError):
            pass
    report = []
    for key, entry in source["treatments"].items():
        where = f"Management data treatment {_show_value(key)}"
        number = None
        entry_problems = []
        try:
            if (isinstance(key, bool) or not isinstance(key, (int, str)) or
                    isinstance(key, str) and not re.fullmatch(r"[0-9]+", key)):
                raise ValueError
            number = int(key)
            where = f"Management data treatment {number}"
        except ValueError:
            number = None
            entry_problems.append(f"{where}: invalid treatment key. Supply an int or digit string.")
        if number is not None and text is not None:
            try:
                _section_row(text, "TREATMENTS", "N", number, ())
            except ValueError as error:
                entry_problems.append(f"{where}: FileX {filex}: {error}")
        if not isinstance(entry, dict):
            entry_problems.append(f"{where}: entry must be a dict. Supply a dict "
                                  "with optional planting, or an empty dict to keep the FileX Levels.")
        else:
            entry_problems.extend(_unknown_keys(entry, ("planting",), where))
        planting_problems = []
        has_planting = isinstance(entry, dict) and "planting" in entry
        if has_planting:
            planting_problems = _check_planting(entry["planting"], f"{where}, planting")
        treatment_problems = entry_problems + planting_problems
        treatment_label = f"  Treatment {number}" if number is not None else f"  Treatment {_show_value(key)}"
        status = "REJECTED" if treatment_problems else "OK"
        report.append(f"{treatment_label}: {status}")
        report.extend(f"    {problem}" for problem in entry_problems)
        if has_planting:
            report.extend(_report_lines("    planting", planting_problems))
        elif isinstance(entry, dict):
            report.append("    planting: OK (omitted; keeps the FileX Level)")
        problems.extend(treatment_problems)
    status = "REJECTED" if problems else "OK"
    return problems, [f"{label}: {status}"] + [f"  {p}" for p in root_problems] + report
