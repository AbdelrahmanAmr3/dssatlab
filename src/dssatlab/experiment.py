"""Shared experiment field checks and shape-only checks for the v0.6 sections."""

from datetime import date
import math
import re

from .weather import _show_value


def _unknown_keys(data, allowed, where, template="Management"):
    return [f"{where}: unknown key {_show_value(key)}. Use only "
            f"{', '.join(allowed)} from the {template} template."
            for key in data if key not in allowed]


def _check_date(value, location):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError
        date.fromisoformat(value)
    except ValueError:
        return [f"{location}: found {_show_value(value)}. Supply a "
                'valid ISO calendar date as a quoted YYYY-MM-DD string '
                '(for example "2024-05-10"); quote the date, even in a dict.']
    return []


def _check_number(value, location):
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError
    except (ValueError, OverflowError):
        return [f"{location}: found {_show_value(value)}. Supply a "
                "finite number in DSSAT's units, not a string or boolean."]
    return []


def _check_fields(data, required, optional, where, template="Management"):
    problems = _unknown_keys(data, required + optional, where, template)
    problems.extend(f"{where}: missing required field {field!r}. "
                    f"Add {field!r} following the {template} template."
                    for field in required if field not in data)
    return problems


def _check_experiment_section(data, section, where):
    """Check keys, required fields and scalar/container types, without FileX edits.

    Cultivar and initial conditions have their own checks; control values
    belong to the later controls ticket. Dates follow the existing strict ISO contract.
    """
    where = f"{where}, {section}"
    if not isinstance(data, dict):
        return [f"{where}: expected a dict. Supply fields from the Experiment "
                "template or omit the section to keep the FileX level."]
    required, optional = (), ("start_date", "water", "nitrogen", "output_interval")
    problems = _check_fields(data, required, optional, where, "Experiment")
    for field in required + optional:
        if field not in data:
            continue
        value, location = data[field], f"{where}, field {field!r}"
        if field in ("date", "start_date"):
            problems.extend(_check_date(value, location))
        elif field == "output_interval":
            if isinstance(value, bool) or not isinstance(value, int):
                problems.append(f"{location}: found {_show_value(value)}. "
                                "Supply an integer number of days, not a boolean.")
        elif not isinstance(value, str):
            problems.append(f"{location}: found {_show_value(value)}. "
                            "Supply a quoted string following the Experiment template.")
    return problems
