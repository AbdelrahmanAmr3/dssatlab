"""Field operation fields, event checks and FileX row values."""

from datetime import date
from pathlib import Path
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


# Section -> (event kind, controls field, codes that read the events, FileX column, fix wording).
_CODE_RULES = {"residues": ("residue", "residue", ("R",), "RESID", '"R"'),
               "harvest": ("harvest", "harvest_management", ("R", "M"), "HARVS",
                           '"R" or "M"')}


def _check_operation(entry, treatment, section, where, text, weather_range=None):
    """Check treatment events against controls or the selected FileX SM level."""
    from .irrigation import _effective_management

    code = None
    if section in _CODE_RULES:
        column = "RESID" if section == "residues" else "HARVS"
        code = _effective_management(entry, text, treatment, _CODE_RULES[section][1], column)
    return _check_operation_events(entry[section], section, where, weather_range, code=code)


def _component_management(text, row, column, default=None):
    """Read the component's SM level, as for its irrigation events."""
    from .filex import _section_row

    if text is not None:
        try:
            return _section_row(text, 'SIMULATION CONTROLS', 'N', int(row['SM']),
                                ('MANAGEMENT', column))[column]
        except (ValueError, TypeError, KeyError):
            pass  # Existing FileX checks report unavailable layouts.
    return default


def _check_harvest(source, filex, selected_treatment=None, *, text=None):
    """Require dated harvests at or after known bounds under effective HARVS R."""
    from .controls import _harvest_bounds
    from .filex import _filex_date, _section_rows
    from .irrigation import _effective_management
    from .sequence import _rotation_components

    entries = source.get('treatments', {}) if isinstance(source, dict) else {}
    entries = entries if isinstance(entries, dict) else {}
    entries = {int(key): entry for key, entry in entries.items()
               if type(key) is int or isinstance(key, str) and key.isascii() and key.isdigit()}
    numbers = list(entries)
    if (type(selected_treatment) is int or isinstance(selected_treatment, str)
            and selected_treatment.isascii() and selected_treatment.isdigit()):
        number = int(selected_treatment)
        if number not in numbers:
            numbers.append(number)
    if not numbers:
        return []
    if text is None and isinstance(filex, (str, Path)):
        try:
            text = Path(filex).read_text(encoding='latin-1')
        except (OSError, ValueError):
            return []  # FileX checks report unreadable inputs.
    problems = []
    for treatment in numbers:
        entry = entries.get(treatment, {})
        entry = entry if isinstance(entry, dict) else {}
        components = _rotation_components(filex, treatment, text=text)
        sequence = len(components) > 1
        edits = entry.get('rotation', {})
        edits = edits if isinstance(edits, dict) else {}
        edits = {int(key): value for key, value in edits.items()
                 if type(key) is int or isinstance(key, str) and key.isascii() and key.isdigit()}
        for index, row in enumerate(components):
            if row['CR'] == 'FA':
                continue
            override = edits.get(int(row['R']), {}) if sequence and row['R'].isdigit() else entry
            override = override if isinstance(override, dict) else {}
            code = (_component_management(text, row, 'HARVS') if sequence else
                    _effective_management(entry, text, treatment, 'harvest_management', 'HARVS'))
            if code != 'R':
                continue
            where = f'Treatment {treatment}'
            if sequence:
                where += f", rotation[{row['R']}]"
            dated = []
            if 'harvest' in override:
                events = override['harvest']
                if isinstance(events, list):
                    for number, event in enumerate(events, 1):
                        if isinstance(event, dict) and not _check_date(event.get('date'), ''):
                            day = date.fromisoformat(event['date'])
                            dated.append((day, f"{where}, harvest, event {number}: "
                                          f"date {event['date']!r} ({day})"))
            else:
                try:
                    level = int(row['MH'])
                    if level > 0:
                        for event in _section_rows(text, 'HARVEST DETAILS', 'H', level, ('HDATE',)):
                            day = _filex_date(event['HDATE'])
                            if day is None:
                                continue
                            dated.append((day, f"{where}: FileX HDATE {event['HDATE']!r} ({day}) "
                                          f"in harvest level {level}"))
                except (ValueError, TypeError, KeyError):
                    pass  # An absent or unreadable harvest level has no usable events.
            bounds = _harvest_bounds(source, text, treatment, row, override, first=index == 0)
            for day, description in dated:
                failed = [f'{label} ({bound})' for label, bound in bounds
                          if bound is not None and day < bound]
                if failed:
                    problems.append(f"{description} is before {' and '.join(failed)}. "
                                    "Move HDATE on or after these bounds, "
                                    "or change the start or planting date.")
            if not dated:
                fix = 'Add a harvest event, or set controls harvest_management to another code.'
                if sequence:
                    fix = ('Add a harvest event to this component, or change HARVS in the '
                           'FileX simulation controls.')
                problems.append(f'{where}: harvest management is "R" (reported dates), '
                                f'but there are no harvest events with a date. {fix}')
    return problems


def _harvest_end(entry, end, code):
    """Reported harvests set the end; maturity ignores every scheduled date."""
    if code == 'M':
        return None
    events = entry.get('harvest') if isinstance(entry, dict) else None
    if code == 'R' and isinstance(events, list):
        days = [date.fromisoformat(event['date']) for event in events
                if isinstance(event, dict) and not _check_date(event.get('date'), '')]
        return max(days) if days else None
    return end


def _check_operation_events(events, section, where, weather_range=None, *, code=None, component=False):
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
        kind, field, needed, column, fix = _CODE_RULES[section]
        if code not in needed:
            dates = " (reported dates)" if section == "residues" else ""
            found = (f'it is "{code}"' if code is not None else
                     f'it could not be read (checked controls {field} and the FileX SM level column {column})')
            target = f"the component's FileX SM level column {column}" if component else f"controls {field}"
            problem = (f'{where}: {kind} events need the {kind} management {fix}{dates}, '
                       f'but {found}. Set {target} to {fix}, '
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
