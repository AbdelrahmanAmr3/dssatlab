"""Field operation fields, event checks and FileX row values."""

from datetime import date
import re

from .experiment import _check_date, _check_number, _unknown_keys
from .weather import _dssat_date, _show_value


# Section -> field -> (DSSAT column, required, rule). Numbers use
# (minimum, maximum, exclusive minimum); new sections extend this one table.
_OPERATION_FIELDS = {
    "residues": {
        "date": ("RDATE", True, "date"),
        "material": ("RCOD", True, "code"),
        "amount": ("RAMT", True, (0, None, True)),
        "n": ("RESN", False, (0, 100, False)),
        "p": ("RESP", False, (0, 100, False)),
        "k": ("RESK", False, (0, 100, False)),
        "incorporation": ("RINP", False, (0, 100, False)),
        "depth": ("RDEP", False, (0, None, False)),
        "method": ("RMET", False, "code"),
    },
    "tillage": {
        "date": ("TDATE", True, "date"),
        "implement": ("TIMPL", True, "code"),
        "depth": ("TDEP", True, (0, None, False)),
    },
    "harvest": {
        "date": ("HDATE", True, "date"),
        "stage": ("HSTG", False, "code"),
        "component": ("HCOM", False, "text"),
        "size": ("HSIZE", False, "text"),
        "product_percent": ("HPC", False, (0, 100, False)),
        "byproduct_percent": ("HBPC", False, (0, 100, False)),
    },
}


def _check_operation_field(value, rule):
    """Return a correction for an invalid value, otherwise None."""
    if rule == "date":
        if _check_date(value, ""):
            return "a valid ISO calendar date as a quoted YYYY-MM-DD string"
    elif rule == "code":
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2}[0-9]{3}", value):
            return "two ASCII letters followed by three digits for the DSSAT code"
    elif rule == "text":
        if not isinstance(value, str) or not re.fullmatch(r"[!-~]{1,5}", value):
            return "1-5 printable ASCII characters without spaces"
    else:
        minimum, maximum, exclusive = rule
        if (_check_number(value, "")
                or (value <= minimum if exclusive else value < minimum)
                or maximum is not None and value > maximum):
            if maximum is not None:
                return f"a number from {minimum} to {maximum}"
            return f"a number {'above' if exclusive else 'at least'} {minimum}"
    return None


# Section -> (controls field, codes that read the events, every valid code).
_CODE_RULES = {"residues": ("residue", ("R",), ("N", "R", "D")),
               "harvest": ("harvest_management", ("R", "M"), ("A", "M", "R", "D"))}


def _check_operation(entry, treatment, section, where, text, weather_range=None):
    """Check treatment events against controls or the selected FileX SM level."""
    from .irrigation import _effective_management

    code = None
    if section in _CODE_RULES:
        column = "RESID" if section == "residues" else "HARVS"
        code = _effective_management(entry, text, treatment, _CODE_RULES[section][0], column)
    return _check_operation_events(entry[section], section, where, weather_range, code=code)


def _check_operation_events(events, section, where, weather_range=None, *, code=None):
    """Check shapes, fields and non-descending dates; allow same-date events."""
    from .management import _check_weather_date, _report_lines

    label, where = f"    {section}", f"{where}, {section}"
    fields = _OPERATION_FIELDS[section]
    if not isinstance(events, list):
        problems = [f"{where}, field {section!r}: expected a list of event dicts. "
                    "Supply a list, an empty list for none, or omit the section "
                    "to keep the FileX Level."]
        return problems, _report_lines(label, problems)
    if not events:
        return [], [f"{label}: OK (empty list; none for this treatment)"]
    problems, report, previous = [], [], None
    if section in _CODE_RULES:
        field, needed, codes = _CODE_RULES[section]
        if code in codes and code not in needed:
            fix = " or ".join(f'"{c}"' for c in needed)
            problem = (f'{where}: {section} events need the controls {field} {fix}, '
                       f'but it is "{code}". Set controls {field} to {fix}, '
                       f'or remove the {section} events.')
            problems.append(problem)
            report.append(f"      {problem}")
    for number, event in enumerate(events, 1):
        location = f"{where}, event {number}"
        if not isinstance(event, dict):
            found = [f"{location}: expected a dict of event fields. Supply the required "
                     f"fields: {', '.join(f for f, (_, required, _) in fields.items() if required)}."]
        else:
            found = _unknown_keys(event, tuple(fields), location, "Experiment")
            for field, (column, required, rule) in fields.items():
                if field not in event and not required:
                    continue
                value = event.get(field)
                correction = _check_operation_field(value, rule)
                if correction is None and rule == "date":
                    day = date.fromisoformat(value)
                    if previous is not None and day < previous:
                        correction = "events in non-descending date order"
                    previous = day
                    if _check_weather_date(value, location, weather_range):
                        # Report both date problems if order and coverage fail.
                        found.append(f"{location}, field {field!r}: found {_show_value(value)}. "
                                     f"Supply a date within the weather range ({weather_range[0]} "
                                     f"to {weather_range[1]}), or weather covering the date "
                                     f"(DSSAT {column}).")
                if correction is not None:
                    found.append(f"{location}, field {field!r}: found {_show_value(value)}. "
                                 f"Supply {correction} (DSSAT {column}).")
        problems.extend(found)
        report.extend(_report_lines(f"      event {number}", found))
    return problems, _report_lines(label, problems, details=[]) + report


def _operation_values(section, event, level):
    """Map checked fields to columns; omitted fields and names remain -99."""
    values = {column: (_dssat_date(date.fromisoformat(event[field]))
                       if rule == "date" else event.get(field, -99))
              for field, (column, _, rule) in _OPERATION_FIELDS[section].items()}
    values[section[0].upper()] = level
    return values
