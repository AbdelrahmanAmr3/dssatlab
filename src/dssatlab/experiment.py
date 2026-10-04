"""Shared experiment field checks, including control values and section shapes."""

from datetime import date
import math
import re

from .filex import _section_row
from .weather import _show_value


# Field -> block, column, codes. Automatic values also carry a correction:
# a method pattern, "date", or (minimum, maximum, exclusive minimum) for numbers.
_CONTROL_OPTIONS = {
    "weather_source": ("METHODS", "WTHER", ("M", "W", "S")),
    "replicates": ("GENERAL", "NREPS", (1, 99999, False), "a whole number from 1 to 99999"),
    "random_seed": ("GENERAL", "RSEED", (0, 99999, False), "a whole number from 0 to 99999"),
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
    "harvest_management": ("MANAGEMENT", "HARVS", ("A", "M", "R", "D")),
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
    "auto_planting_first": ("PLANTING", "PFRST", "date",
                            "a valid ISO calendar date as a quoted YYYY-MM-DD string"),
    "auto_planting_last": ("PLANTING", "PLAST", "date",
                           "a valid ISO calendar date as a quoted YYYY-MM-DD string"),
    "auto_planting_soil_water_low": ("PLANTING", "PH2OL", (0, 100, False), "a number from 0 to 100"),
    "auto_planting_soil_water_high": ("PLANTING", "PH2OU", (0, 100, False), "a number from 0 to 100"),
    "auto_planting_soil_water_depth": ("PLANTING", "PH2OD", (0, None, True), "a number above 0"),
    "auto_planting_max_temperature": ("PLANTING", "PSTMX", (None, None, False), "a finite number"),
    "auto_planting_min_temperature": ("PLANTING", "PSTMN", (None, None, False), "a finite number"),
}


def _unknown_keys(data, allowed, where, template="Management"):
    return [f"{where}: unknown key {_show_value(key)}. Use only "
            f"{', '.join(allowed)} from the {template} template."
            for key in data if key not in allowed]


def _check_date(value, location, *, iso_advice=None):
    """Check quoted calendar dates that will be written as FileX YYDDD dates."""
    try:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError
        day = date.fromisoformat(value)
    except ValueError:
        if iso_advice is not None:
            return [f"{location}: found {_show_value(value)}. Supply {iso_advice}."]
        return [f"{location}: found {_show_value(value)}. Supply a "
                'valid ISO calendar date as a quoted YYYY-MM-DD string '
                '(for example "2024-05-10"); quote the date, even in a dict.']
    if not 1936 <= day.year <= 2035:
        return [f"{location}: {value} cannot be written in a FileX: DSSAT stores two-digit years "
                "and reads 00-35 as 2000-2035 and 36-99 as 1936-1999. "
                "Use a date from 1936-01-01 to 2035-12-31."]
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
    follows the existing strict ISO contract. Replicates and random_seed are
    whole numbers; random_seed 0 selects DSSAT's default seed 2510.
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
                if rule == "date":
                    problems.extend(_check_date(value, location,
                                                iso_advice=f"{spec[3]} (DSSAT {column})"))
                    continue
                elif isinstance(rule, str):
                    valid = isinstance(value, str) and re.fullmatch(rule, value)
                else:
                    minimum, maximum, exclusive = rule
                    valid = (not _check_number(value, location)
                             and (field not in ("replicates", "random_seed") or type(value) is int)
                             and (minimum is None or (value > minimum if exclusive else value >= minimum))
                             and (maximum is None or value <= maximum))
                if not valid:
                    checked = f"Checked the DSSAT {column} value. " if field in ("replicates", "random_seed") else ""
                    problems.append(f"{location}: found {_show_value(value)}. "
                                    f"{checked}Supply {spec[3]} (DSSAT {column}).")
            elif type(value) is not type(rule[0]) or value not in rule:
                if field in ("water", "nitrogen"):
                    instruction = 'Supply the quoted string "Y" or "N".'
                else:
                    choices = ", ".join(f'"{code}"' if isinstance(code, str) else str(code)
                                        for code in rule)
                    instruction = f"Supply one of {choices} (DSSAT {column})."
                checked = f"Checked the DSSAT {column} code. " if field == "weather_source" else ""
                problems.append(f"{location}: found {_show_value(value)}. {checked}{instruction}")
    return problems


def _check_treatment_key(key, seen_numbers, text, filex):
    where = f"Management data treatment {_show_value(key)}"
    try:
        if (isinstance(key, bool) or not isinstance(key, (int, str)) or
                isinstance(key, str) and not re.fullmatch(r"[0-9]+", key)):
            raise ValueError
        number = int(key)
        where = f"Management data treatment {number}"
    except ValueError:
        return None, where, [f"{where}: invalid treatment key. Supply an int or digit string."]
    problems = []
    if number in seen_numbers:
        problems.append(f"{where}: duplicate treatment number for keys "
                        f"{_show_value(seen_numbers[number])} and {_show_value(key)}. "
                        "Keep one entry per treatment number.")
    else:
        seen_numbers[number] = key
    if text is not None:
        try:
            _section_row(text, "TREATMENTS", "N", number, ())
        except ValueError as error:
            problems.append(f"{where}: FileX {filex}: {error}")
    return number, where, problems


def _overrides_section(experiment_data, treatment, section=None, *, rotation=None):
    """True for a supplied section, or any experiment overrides when omitted."""
    treatments = experiment_data.get("treatments") if isinstance(experiment_data, dict) else None
    if not isinstance(treatments, dict):
        return False
    for key, entry in treatments.items():
        try:
            selected = int(key) == int(treatment)
        except (TypeError, ValueError, OverflowError):
            continue
        if selected and isinstance(entry, dict):
            if rotation is not None:
                edits = entry.get("rotation", {})
                if isinstance(edits, dict):
                    for number, component in edits.items():
                        if (str(number).isascii() and str(number).isdigit()
                                and int(number) == int(rotation) and isinstance(component, dict)):
                            return section in component
                return False
            return bool(entry) if section is None else section in entry
    return False
