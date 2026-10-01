"""Copy a FileX simulation controls level and replace only named controls."""

from datetime import date, timedelta
import re

from .experiment import _check_date
from .filex import _section_row
from .weather import _dssat_date
from .filex_write import _append_rows, _cell, _columns, _repoint, _section_bounds


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


def _season_coverage(source, treatment, start, days, nyers=None):
    """Check the last season's start using DSSAT's fixed day-of-year rule."""
    if start is None or not days:
        return []
    controls = _selected_controls(source, treatment)
    if "years" in controls:
        years, label = controls["years"], "Controls years"
        if type(years) is not int or years < 1:
            return []  # The controls checks report invalid overrides.
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


def _controls_text(text, treatment, controls):
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
        base = int(treatment_row["SM"])
    except ValueError:
        raise ValueError(f"TREATMENTS: invalid SM {treatment_row['SM']!r}. "
                         "Supply an integer level.") from None
    _section_row(text, section, "N", base, ("GENERAL", "START", "SDATE"))
    changes = {}
    if "start_date" in controls:
        day = date.fromisoformat(controls["start_date"])
        changes["GENERAL", "SDATE"] = _dssat_date(day)
    for field, block, column in (("years", "GENERAL", "NYERS"),
                                 ("water", "OPTIONS", "WATER"),
                                 ("nitrogen", "OPTIONS", "NITRO"),
                                 ("output_interval", "OUTPUTS", "FROPT")):
        if field in controls:
            changes[block, column] = controls[field]

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

    level, body, applied = highest + 1, [], set()
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
            row = row[:left] + _cell(value, right - left, section, column) + row[right:]
        body.extend([header, row])
    missing = changes.keys() - applied
    if missing:
        names = ", ".join(f"{block}/{column}" for block, column in sorted(missing))
        raise ValueError(f"{section} level {base} has no row with columns {names}. "
                         "Supply the needed headers and selected level rows.")
    _repoint(lines, treatment, "SM", level)
    _append_rows(lines, insert_at, ["", *body])
    return "".join(lines)
