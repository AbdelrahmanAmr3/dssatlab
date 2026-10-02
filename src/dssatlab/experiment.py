"""Shared experiment field checks, including control values and section shapes."""

from datetime import date
import math
import re

from .weather import _show_value


# Field -> block, column, codes. Automatic values also carry a correction:
# a method pattern, or (minimum, maximum, exclusive minimum) for numbers.
_CONTROL_OPTIONS = {
    "water": ("OPTIONS", "WATER", ("Y", "N")),
    "nitrogen": ("OPTIONS", "NITRO", ("Y", "N")),
    "photosynthesis": ("METHODS", "PHOTO", ("C", "R", "L", "V")),
    "co2": ("OPTIONS", "CO2", ("M", "W", "D", "R")),
    "symbiosis": ("OPTIONS", "SYMBI", ("Y", "N", "U")),
    "phosphorus": ("OPTIONS", "PHOSP", ("Y", "N")),
    "potassium": ("OPTIONS", "POTAS", ("Y", "N")),
    "tillage": ("OPTIONS", "TILL", ("Y", "N")),
    "evapotranspiration": ("METHODS", "EVAPO", ("F", "R", "S", "T")),
    "infiltration": ("METHODS", "INFIL", ("R", "S", "N")),
    "soil_organic_matter": ("METHODS", "MESOM", ("G", "P")),
    "soil_evaporation": ("METHODS", "MESEV", ("R", "S")),
    "soil_layers": ("METHODS", "MESOL", (1, 2, 3)),
    "residue": ("MANAGEMENT", "RESID", ("N", "R", "D")),
    "irrigation_management": ("MANAGEMENT", "IRRIG", ("A", "N", "F", "R", "D", "P", "W")),
    "planting_management": ("MANAGEMENT", "PLANT", ("A", "F", "R")),
    "auto_irrigation_depth": ("IRRIGATION", "IMDEP", (0, None, True), "a number above 0"),
    "auto_irrigation_threshold": ("IRRIGATION", "ITHRL", (0, 100, False), "a number from 0 to 100"),
    "auto_irrigation_refill": ("IRRIGATION", "ITHRU", (0, 100, False), "a number from 0 to 100"),
    "auto_irrigation_method": ("IRRIGATION", "IMETH", r"[A-Za-z]{2}[0-9]{3}",
                               "two ASCII letters followed by three digits for the DSSAT code"),
    "auto_irrigation_amount": ("IRRIGATION", "IRAMT", (0, None, True), "a number above 0"),
    "auto_irrigation_efficiency": ("IRRIGATION", "IREFF", (0, 1, True),
                                   "a number above 0 and at most 1"),
}


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
    problems = _check_fields(data, (), ("start_date", *_CONTROL_OPTIONS, "output_interval", "years"),
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
        elif field in _CONTROL_OPTIONS:
            spec = _CONTROL_OPTIONS[field]
            _, column, rule = spec[:3]
            if len(spec) == 4:
                if isinstance(rule, str):
                    valid = isinstance(value, str) and re.fullmatch(rule, value)
                else:
                    minimum, maximum, exclusive = rule
                    valid = (not _check_number(value, location)
                             and (value > minimum if exclusive else value >= minimum)
                             and (maximum is None or value <= maximum))
                if not valid:
                    problems.append(f"{location}: found {_show_value(value)}. "
                                    f"Supply {spec[3]} (DSSAT {column}).")
            elif type(value) is not type(rule[0]) or value not in rule:
                if field in ("water", "nitrogen"):
                    instruction = 'Supply the quoted string "Y" or "N".'
                else:
                    choices = ", ".join(f'"{code}"' if isinstance(code, str) else str(code)
                                        for code in rule)
                    instruction = f"Supply one of {choices} (DSSAT {column})."
                problems.append(f"{location}: found {_show_value(value)}. "
                                f"{instruction}")
    return problems
