"""Shared experiment field checks, including control values and section shapes."""

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


def _check_controls(data, where):
    """Check the controls section's keys and value types, without FileX edits.

    Cultivar and initial conditions have their own checks. The start date
    follows the existing strict ISO contract.
    """
    where = f"{where}, controls"
    if not isinstance(data, dict):
        return [f"{where}: expected a dict. Supply fields from the Experiment "
                "template or omit the section to keep the FileX level."]
    problems = _check_fields(data, (), ("start_date", "water", "nitrogen", "output_interval", "years"),
                             where, "Experiment")
    for field, value in data.items():
        location = f"{where}, field {field!r}"
        if field == "start_date":
            problems.extend(_check_date(value, location))
        elif field == "years":
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                problems.append(f"{location}: found {_show_value(value)}. "
                                "Supply a positive integer number of seasons, not a boolean.")
        elif field == "output_interval":
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                problems.append(f"{location}: found {_show_value(value)}. "
                                "Supply a positive integer number of days, not a boolean.")
            else:
                # _check_number also rejects integers too large to convert to a float.
                problems.extend(_check_number(value, location))
        elif field in ("water", "nitrogen"):
            if value not in ("Y", "N"):
                problems.append(f"{location}: found {_show_value(value)}. "
                                'Supply the quoted string "Y" or "N".')
    return problems
