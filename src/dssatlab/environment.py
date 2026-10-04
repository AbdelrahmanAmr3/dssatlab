"""Check environment modifications and render one new level in a copied FileX."""

from datetime import date

from .experiment import _check_date, _check_fields, _check_number, _unknown_keys
from .filex import _section_row
from .filex_write import (_append_rows, _cell, _event_blocks, _insert_section,
                          _new_level, _repoint, _section_bounds)
from .weather import _dssat_date, _show_value


# DSSAT-CSM v4.8.6.0 InputModule/IPENV.for, format 1000:
# (I3,I5,8(1X,A1,F4.0)); its preceding (I2) read selects the event level.
# InputModule/ipexp.for, formats 55/56, reads the treatment's ME as I3.
_HEADER = "@E ODATE EDAY  ERAD  EMAX  EMIN  ERAIN ECO2  EDEW  EWIND ENVNAME"
_FIELDS = {"day_length": "EDAY", "srad": "ERAD", "tmax": "EMAX", "tmin": "EMIN",
           "rain": "ERAIN", "co2": "ECO2", "dew_point": "EDEW", "wind": "EWIND"}
_KINDS = {"add": "A", "subtract": "S", "multiply": "M", "replace": "R"}


def _check_environment(data, where):
    where = f"{where}, environment"
    if not isinstance(data, list):
        return [f"{where}: expected a list of event dicts. Supply dated environment "
                "modifications, [] to set ME to 0, or omit the section to keep the FileX level."]
    problems, previous = [], None
    if len(data) > 100:
        problems.append(f"{where}: found {len(data)} events. DSSAT reads at most 100 "
                        "(WTHMOD NMODS); supply 100 or fewer events.")
    for number, event in enumerate(data, 1):
        location = f"{where}, event {number}"
        if not isinstance(event, dict):
            problems.append(f"{location}: expected a dict. Supply a date and at least one "
                            f"variable: {', '.join(_FIELDS)}.")
            continue
        problems.extend(_check_fields(event, ("date",), tuple(_FIELDS), location, "Experiment"))
        if "date" in event:
            date_location = f"{location}, field 'date'"
            date_problems = _check_date(event["date"], date_location)
            problems.extend(date_problems)
            if not date_problems:
                day = date.fromisoformat(event["date"])
                if previous is not None and day <= previous:
                    problems.append(f"{date_location}: date {_show_value(event['date'])} follows "
                                    f"{previous}. Supply event dates in strictly ascending order.")
                previous = day
        if not any(field in event for field in _FIELDS):
            problems.append(f"{location}, field 'variables': supply at least one variable "
                            f"to change: {', '.join(_FIELDS)}.")
        for field, column in _FIELDS.items():
            if field not in event:
                continue
            change, field_location = event[field], f"{location}, field {field!r}"
            if not isinstance(change, dict):
                problems.append(f"{field_location}: expected a dict with exactly one kind. "
                                f"Supply one of {', '.join(_KINDS)} with a number.")
                continue
            problems.extend(_unknown_keys(change, tuple(_KINDS), field_location, "Experiment"))
            if len(change) != 1:
                problems.append(f"{field_location}: expected exactly one kind. "
                                f"Supply one of {', '.join(_KINDS)} with a number.")
                continue
            kind, value = next(iter(change.items()))
            if kind not in _KINDS:
                continue
            numeric_problems = _check_number(value, field_location)
            problems.extend(numeric_problems)
            if numeric_problems:
                continue
            # FILEIO (InputModule/optempy2k.for, formats 90-94) may use F4.2,
            # F4.1 or I4; IPENV replaces values <= -90 with 0.
            if kind == "multiply" and not 0 <= value <= 9.99:
                problems.append(f"{field_location}: found {_show_value(value)}. "
                                "Supply a multiply value from 0 to 9.99 inclusive.")
            if field == "co2":
                if not -89 <= value <= 9999 or value != int(value):
                    problems.append(f"{field_location}: found {_show_value(value)}. "
                                    "Supply a whole number from -89 to 9999 inclusive.")
            elif not -9.9 <= value <= 99.9:
                problems.append(f"{field_location}: found {_show_value(value)}. "
                                "Supply a number from -9.9 to 99.9 inclusive.")
            try:
                _cell(value, 4, "ENVIRONMENT MODIFICATIONS", column, first_column=True)
            except ValueError as error:
                problems.append(f"{field_location}: {error}")
    return problems


def _environment_text(text, treatment, data):
    """Dry-run during checks; apply only to the selected treatment's copy at run."""
    name = "ENVIRONMENT MODIFICATIONS"
    _section_row(text, "TREATMENTS", "N", treatment, ("ME",))
    lines = text.splitlines(keepends=True)
    if not data:
        _repoint(lines, treatment, "ME", 0)
        return "".join(lines)
    # Discover and reuse I3 inherited levels without changing their original bytes.
    level_lines = list(lines)
    bounds = _section_bounds(lines, name)
    if bounds is not None:
        for index in range(bounds[0] + 1, bounds[1]):
            try:
                inherited = int(lines[index][:3])
            except ValueError:
                continue
            level_lines[index] = f"{inherited:2d} " + lines[index][3:]
    blocks, highest = _event_blocks(level_lines, name, (_HEADER,), optional_columns=("ENVNAME",))
    level = _new_level(level_lines, treatment, "ME", highest, name)
    if bounds is not None:
        for index in range(bounds[0] + 1, bounds[1]):
            if not level_lines[index]:
                lines[index] = ""  # Remove only rows of a reused, unreferenced level.
    prefix = _cell(level, 2, name, "E", first_column=True) + " "
    rows = []
    for event in data:
        row = prefix + _dssat_date(date.fromisoformat(event["date"]))
        for field, column in _FIELDS.items():
            kind, value = next(iter(event.get(field, {"add": 0}).items()))
            row += " " + _KINDS[kind] + _cell(value, 4, name, column, first_column=True)
        rows.append(row)
    _repoint(lines, treatment, "ME", level)
    if blocks[0][1] is None:
        lines = _insert_section(lines, name, [_HEADER, *rows])
    else:
        _append_rows(lines, blocks[0][1], rows)
    return "".join(lines)
