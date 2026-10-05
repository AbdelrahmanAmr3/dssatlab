"""Copy a FileX simulation controls level and replace only named controls."""

from datetime import date, timedelta
import re

from .experiment import _check_date, _CONTROL_OPTIONS
from .filex import _filex_date, _section_row
from .weather import _dssat_date
from .filex_write import _append_rows, _cell, _columns, _new_level, _repoint, _section_bounds


def _selected_controls(source, treatment):
    """Return selected controls even when other experiment fields fail."""
    if not isinstance(source, dict) or not isinstance(source.get("treatments"), dict):
        return {}
    for key, entry in source["treatments"].items():
        if (isinstance(key, bool) or not isinstance(key, (int, str)) or
                isinstance(key, str) and not re.fullmatch(r"[0-9]+", key)):
            continue
        try:
            selected = int(key) == int(treatment)
        except (TypeError, ValueError):
            continue
        if not selected or not isinstance(entry, dict):
            continue
        controls = entry.get("controls")
        if isinstance(controls, dict):
            return controls
    return {}


def _controls_start_date(source, treatment):
    """Return a valid selected override even when other experiment fields fail."""
    value = _selected_controls(source, treatment).get("start_date")
    if not _check_date(value, "start_date"):
        return date.fromisoformat(value)
    return None


def _harvest_bounds(source, text, treatment, row, override, *, first=True):
    """Read known start and planting bounds after experiment edits."""
    from .irrigation import _effective_management
    from .operations import _component_management
    from .sequence import _simulation_start

    # DSSAT-CSM v4.8.6.0, CSM_Main/CSM.for, CSM (381-390): later Q
    # components start the day after the previous one ends, ignoring SDATE.
    # DSSAT-CSM v4.8.6.0, InputModule/ipexp.for (655-663): START E sets
    # start and planting to EDATE whatever PLANT is; emergence bounds harvest only here.
    start, start_label, emergence = None, 'simulation start date', False
    planting_edit = override.get('planting')
    planting = (date.fromisoformat(planting_edit['date']) if isinstance(planting_edit, dict)
                and not _check_date(planting_edit.get('date'), '') else None)
    for reference, section, key, column in (
            ('SM', 'SIMULATION CONTROLS', 'N', 'SDATE'),
            ('MP', 'PLANTING DETAILS', 'P', 'PDATE')):
        try:
            details = _section_row(text, section, key, int(row[reference]), (column,))
            if reference == 'SM' and first and details.get('START') == 'S':
                start = _controls_start_date(source, treatment) or _filex_date(details[column])
            elif reference == 'SM' and first and details.get('START') == 'P':
                start = _simulation_start(text, treatment, source)
            elif reference == 'SM' and first and details.get('START') == 'E':
                start_label, emergence = 'simulation start date (START E emergence date)', True
                if 'planting' in override:
                    if (isinstance(planting_edit, dict)
                            and not _check_date(planting_edit.get('emergence_date'), '')):
                        start = date.fromisoformat(planting_edit['emergence_date'])
                else:
                    details = _section_row(text, 'PLANTING DETAILS', 'P', int(row['MP']), ('EDATE',))
                    start = _filex_date(details['EDATE'])
            elif reference == 'MP' and 'planting' not in override:
                planting = _filex_date(details[column])
        except (ValueError, TypeError, KeyError):
            pass  # Existing checks report unavailable levels and invalid edits.
    code = _effective_management(override, None, treatment, 'planting_management', 'PLANT')
    if code is None:
        code = _component_management(text, row, 'PLANT')
    # DSSAT-CSM v4.8.6.0, Management/AUTPLT.for, AUTPLT (98-99):
    # PLANT A/F discard the reported PDATE; keep only a known simulation start.
    # START E also sets the planting date to EDATE, so PDATE is no bound.
    if code in ('A', 'F') or emergence:
        planting = None
    return [(start_label, start), ('planting date', planting)]


def _season_coverage(source, treatment, start, days, nyers=None):
    """Check the last season's start using DSSAT's fixed day-of-year rule."""
    if start is None or not days:
        return []
    controls = _selected_controls(source, treatment)
    if "years" in controls:
        years, label = controls["years"], "Controls years"
        if type(years) is not int or not 1 <= years <= 99999:
            return []  # The controls checks and the NYERS column-fit check report these.
    else:
        try:
            years = int(nyers)
        except (TypeError, ValueError):
            years = 1
        label = "FileX NYERS"
    if years <= 1:
        return []
    year, day = start.year + years - 1, start.timetuple().tm_yday
    end = max(days)
    if (year, day) <= (end.year, end.timetuple().tm_yday):
        return []
    season_start = f"day {day} of {year}"
    if year <= date.max.year and day <= date(year, 12, 31).timetuple().tm_yday:
        last = date(year, 1, 1) + timedelta(days=day - 1)
        season_start = f"{last} ({season_start})"
    return [f"{label} {years}: season {years} starts on {season_start}, "
            f"after the weather data ends ({end}). "
            "Supply weather for every season, or fewer years."]


def _check_inherited_planting(text, treatment, entry, filex):
    """Compare inherited PLANT R planting with a valid controls-only effective start."""
    from .irrigation import _effective_management
    from .sequence import _rotation_components, _simulation_start

    controls = entry.get("controls")
    if (text is None or not isinstance(controls, dict)
            or _check_date(controls.get("start_date"), "start_date")
            or _effective_management(entry, text, treatment, "planting_management", "PLANT") != "R"):
        return []
    if len(_rotation_components(None, treatment, text=text)) > 1:
        return []  # Sequence checks already compare effective component planting dates.
    start = _simulation_start(text, treatment, {"treatments": {treatment: entry}})
    try:
        row = _section_row(text, "TREATMENTS", "N", treatment, ("MP",))
        planting = _section_row(text, "PLANTING DETAILS", "P", int(row["MP"]), ("PDATE",))
        day = _filex_date(planting["PDATE"])
    except (ValueError, TypeError):
        return []  # Unavailable levels cannot establish an inherited planting date.
    if start is None or day is None or day >= start:
        return []
    return [f"Controls start_date {start} is after the planting date {day} recorded in "
            f"FileX {filex if filex is not None else 'template'} treatment {treatment}. "
            "Set start_date on or before planting."]


def _check_planting_window(text, treatment, controls, where, start_date=None, weather_range=None):
    """Check a changed automatic window against inherited dates and selected weather."""
    from .management import _check_weather_date
    from .sequence import _simulation_start

    fields = ("auto_planting_first", "auto_planting_last")
    if not any(field in controls for field in (*fields, "planting_management", "start_date")):
        return []
    plant = controls.get("planting_management")
    if plant == "R":
        return []
    level = int(_section_row(text, "TREATMENTS", "N", treatment, ("SM",))["SM"])
    if plant is None:
        try:
            plant = _section_row(text, "SIMULATION CONTROLS", "N", level,
                                 ("MANAGEMENT", "PLANT"))["PLANT"]
        except ValueError:
            return []  # No effective A/F code; preserve checks for older FileX layouts.
    if plant not in ("A", "F"):
        return []
    if "start_date" in controls:
        general = _section_row(text, "SIMULATION CONTROLS", "N", level, ("GENERAL", "START", "SDATE"))
        if general["START"] == "S":
            start_date = date.fromisoformat(controls["start_date"])

    if start_date is None:
        general = _section_row(text, "SIMULATION CONTROLS", "N", level, ("GENERAL", "START", "SDATE"))
        if general["START"] == "S":
            start_date = _filex_date(general["SDATE"])
        elif general["START"] == "P":
            start_date = _simulation_start(
                text, treatment, {"treatments": {treatment: {"controls": controls}}})
    row = _section_row(text, "SIMULATION CONTROLS", "N", level, ("PLANTING", "PFRST", "PLAST"))
    first, last = (date.fromisoformat(controls[field]) if field in controls else _filex_date(row[column])
                   for field, column in zip(fields, ("PFRST", "PLAST")))
    where = f"{where}, controls"
    location = f"{where}, field 'auto_planting_first'"
    problems = []
    if first is not None and last is not None and first > last:
        problems.append(f"{location}: date {first.isoformat()!r} is after auto_planting_last "
                        f"{last.isoformat()!r}. Supply an automatic planting first date on or "
                        "before the last date (DSSAT PFRST/PLAST).")
    if first is not None and start_date is not None and first < start_date:
        problems.append(f"{location}: date {first.isoformat()!r} is before simulation start date "
                        f"{start_date.isoformat()!r}. Supply an automatic planting first date on or "
                        "after the simulation start date, or an earlier controls start_date.")
    for field in fields:
        if field in controls:
            problems.extend(_check_weather_date(controls[field], f"{where}, field {field!r}", weather_range))
    return problems


def _controls_text(text, treatment, controls):
    """Copy selected controls; sequence weather keys reach every used SM level.

    Other sequence controls apply to its first component as before. Each copied
    level retains omitted cells and each original level stays unchanged.
    """
    from .sequence import _rotation_components

    components = _rotation_components(None, treatment, text=text)
    text = _controls_level_text(text, treatment, controls)
    shared = {key: value for key, value in controls.items()
              if key in ("weather_source", "replicates", "random_seed")}
    if len(components) < 2 or not shared:
        return text
    first = _section_row(text, "TREATMENTS", "N", treatment, ("SM",))["SM"]
    copied = {components[0]["SM"]: int(first)}
    for component in components[1:]:
        base, rotation = component["SM"], int(component["R"])
        if base not in copied:
            text = _controls_level_text(text, treatment, shared, base=int(base), rotation=rotation)
            edited = _rotation_components(None, treatment, text=text)
            copied[base] = int(next(row["SM"] for row in edited if int(row["R"]) == rotation))
        else:
            lines = text.splitlines(keepends=True)
            _repoint(lines, treatment, "SM", copied[base], rotation=rotation)
            text = "".join(lines)
    return text


def _controls_level_text(text, treatment, controls, *, base=None, rotation=None):
    """Dry-run the same copy operation used by run(), preserving other cells.

    Header token ends follow the DSSAT 4.8 UFGA8201.MZX layout. Copy all
    selected @N blocks, including automatic management, into one new level.
    Only requested columns must exist; omitted fields keep their base values.
    """
    if not controls:
        return text
    section = "SIMULATION CONTROLS"
    treatment_row = _section_row(text, "TREATMENTS", "N", treatment, ("SM",))
    try:
        base = int(treatment_row["SM"]) if base is None else base
    except ValueError:
        raise ValueError(f"TREATMENTS: invalid SM {treatment_row['SM']!r}. "
                         "Supply an integer level.") from None
    _section_row(text, section, "N", base, ("GENERAL", "START", "SDATE"))
    changes = {}
    if "start_date" in controls:
        day = date.fromisoformat(controls["start_date"])
        changes["GENERAL", "SDATE"] = _dssat_date(day)
    for field, block, column in (("years", "GENERAL", "NYERS"),
                                 ("output_interval", "OUTPUTS", "FROPT")):
        if field in controls:
            changes[block, column] = controls[field]
    for field, spec in _CONTROL_OPTIONS.items():
        if field in controls:
            block, column = spec[:2]
            value = controls[field]
            changes[block, column] = _dssat_date(date.fromisoformat(value)) if spec[2] == "date" else value

    lines = text.splitlines(keepends=True)
    start, end = _section_bounds(lines, section)
    highest, insert_at = 0, start + 1
    header, columns, marker = None, {}, None
    selected = []
    for index in range(start + 1, end):
        line = lines[index]
        if line.startswith("@"):
            if line.split() == ["@", "AUTOMATIC", "MANAGEMENT"]:
                marker, header, columns = line.rstrip("\r\n"), None, {}
                continue
            header, columns = line.rstrip("\r\n"), _columns(line)
            if "N" not in columns:
                raise ValueError(f"{section} header has no N column: {header!r}. "
                                 "Supply a numbered @N header.")
        elif header is not None:
            left, right = columns["N"]
            try:
                level = int(line[left:right])
            except ValueError:
                continue
            highest = max(highest, level)
            insert_at = index + 1
            if level == base:
                selected.append((marker, header, columns, line.rstrip("\r\n")))
                marker = None

    level = _new_level(lines, treatment, "SM", highest, section, rotation=rotation)
    body, applied = [], set()
    for marker, header, columns, row in selected:
        if marker is not None:
            body.extend(["", marker])
        updates = {"N": level}
        for (block, column), value in changes.items():
            if block in columns and column in columns:
                updates[column] = value
                applied.add((block, column))
        for column, value in updates.items():
            left, right = columns[column]
            if len(row) < right:
                raise ValueError(f"{section} {column}: selected row is truncated. "
                                 "Supply a complete FileX row.")
            row = row[:left] + _cell(value, right - left, section, column,
                                     first_column=left == 0) + row[right:]
        body.extend([header, row])
    missing = changes.keys() - applied
    if missing:
        names = ", ".join(f"{block}/{column}" for block, column in sorted(missing))
        raise ValueError(f"{section} level {base} has no row with columns {names}. "
                         "Supply the needed headers and selected level rows.")
    _repoint(lines, treatment, "SM", level, rotation=rotation)
    _append_rows(lines, insert_at, ["", *body])
    return "".join(lines)
