"""Edit management in FileX text without rewriting existing sections."""

from datetime import date
from pathlib import Path
import re

from .filex import _section_row


_PLANTING_HEADER = (
    "@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE"
    "  PENV  PLPH  SPRL                        PLNAME"
)
_PLANTING_FIELDS = {
    "PDATE": "date", "EDATE": "emergence_date", "PPOP": "population",
    "PPOE": "emergence_population", "PLME": "method", "PLDS": "distribution",
    "PLRS": "row_spacing", "PLRD": "row_direction", "PLDP": "depth",
    "PLWT": "planting_material_weight", "PAGE": "transplant_age",
    "PENV": "transplant_environment", "PLPH": "plants_per_hill", "SPRL": "sprout_length",
}
_IRRIGATION_HEADERS = (
    "@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME",
    "@I IDATE  IROP IRVAL",
)
_FERTILIZER_HEADER = "@F FDATE  FMCD  FACD  FDEP  FAMN  FAMP  FAMK  FAMC  FAMO  FOCD FERNAME"


def _section_bounds(lines, section):
    """Return the section's line range, or None when absent."""
    start = None
    for index, line in enumerate(lines):
        if not line.startswith("*"):
            continue
        if start is not None:
            return start, index
        name = line[1:].strip()
        if name == section or name.startswith(section + " "):
            start = index
    return (start, len(lines)) if start is not None else None


def _columns(header):
    """Use the same header-token ends as the narrow FileX reader."""
    columns, start = {}, 0
    for token in re.finditer(r"\S+", header):
        columns[token.group().lstrip("@").rstrip(".")] = (start, token.end())
        start = token.end()
    return columns


def _newline(lines):
    for line in lines:
        match = re.search(r"\r\n|\n|\r", line)
        if match:
            return match.group()
    return "\n"


def _insert_section(lines, section, body):
    """Insert any missing management section before SIMULATION CONTROLS.

    Return new lines, leaving every existing line unchanged. Body contains
    header/row strings without line endings; future writers can pass multiple
    header blocks (for example irrigation controls and events).
    """
    bounds = _section_bounds(lines, "SIMULATION CONTROLS")
    if bounds is None:
        raise ValueError("missing SIMULATION CONTROLS section. Supply that section "
                         "so management can be inserted before it.")
    newline = _newline(lines)
    block = [line + newline for line in ["*" + section, *body, ""]]
    return lines[:bounds[0]] + block + lines[bounds[0]:]


def _cell(value, width, section, column):
    text = str(value)
    if len(text) > width:
        raise ValueError(f"{section} column {column}: value {text!r} does not fit "
                         f"its {width}-character field. Supply a value that fits "
                         "the FileX column without rounding or truncation.")
    return text.rjust(width)


def _planting_row(columns, level, planting):
    values = {column: planting.get(field, -99)
              for column, field in _PLANTING_FIELDS.items()}
    values.update(P=level, PLNAME=-99)
    values["PPOE"] = planting.get("emergence_population", planting["population"])
    for column in ("PDATE", "EDATE"):
        if values[column] != -99:
            day = date.fromisoformat(values[column])
            values[column] = f"{day.year % 100:02d}{day.timetuple().tm_yday:03d}"
    return "".join(_cell(values.get(column, -99), end - start,
                         "PLANTING DETAILS", column)
                   for column, (start, end) in columns.items())


def _planting_text(text, treatment, planting):
    """Check and render one planting edit in memory, preserving untouched bytes.

    Called by management checks for each valid planting entry, then by run()
    for the selected entry only. Invalid layouts/field overflow raise ValueError
    before Simulation creates a folder. Input planting has already been checked.
    """
    _section_row(text, "TREATMENTS", "N", treatment, ("MP",))
    lines = text.splitlines(keepends=True)
    bounds = _section_bounds(lines, "PLANTING DETAILS")
    highest, insert_at = 0, None
    columns = _columns(_PLANTING_HEADER)
    if bounds is not None:
        columns = None
        for index in range(bounds[0] + 1, bounds[1]):
            line = lines[index]
            if line.startswith("@"):
                columns = _columns(line)
                missing = {"P", *_PLANTING_FIELDS} - columns.keys()
                if missing:
                    raise ValueError("PLANTING DETAILS header is missing columns "
                                     f"{', '.join(sorted(missing))}. Supply the needed columns.")
                insert_at = index + 1
            elif columns is not None:
                start, end = columns["P"]
                try:
                    level = int(line[start:end])
                except ValueError:
                    continue
                highest = max(highest, level)
                insert_at = index + 1
        if columns is None:
            raise ValueError("PLANTING DETAILS has no header containing columns "
                             f"P, {', '.join(_PLANTING_FIELDS)}. Supply the needed columns.")
    level = highest + 1
    row = _planting_row(columns, level, planting)

    _repoint(lines, treatment, "MP", level)
    if bounds is None:
        lines = _insert_section(lines, "PLANTING DETAILS", [_PLANTING_HEADER, row])
    else:
        _append_rows(lines, insert_at, [row])
    return "".join(lines)


def _repoint(lines, treatment, column, level):
    start, end = _section_bounds(lines, "TREATMENTS")
    columns = {}
    for index in range(start + 1, end):
        line = lines[index]
        if line.startswith("@"):
            columns = _columns(line)
        elif "N" in columns and column in columns:
            left, right = columns["N"]
            try:
                number = int(line[left:right])
            except ValueError:
                continue
            if number == treatment:
                left, right = columns[column]
                lines[index] = (line[:left] + _cell(level, right - left, "TREATMENTS", column)
                                + line[right:])
                break


def _append_rows(lines, index, rows):
    newline = _newline(lines)
    prefix = "" if lines[index - 1].endswith(("\r", "\n")) else newline
    lines[index:index] = [prefix + newline.join(rows) + newline]


def _event_blocks(lines, section, headers):
    """Check every header and find the last insertion point for each block."""
    expected = [_columns(header) for header in headers]
    blocks, highest = {}, 0
    bounds = _section_bounds(lines, section.split()[0])
    if bounds is None:
        return [(columns, None, header) for columns, header in zip(expected, headers)], highest
    active = None
    for index in range(bounds[0] + 1, bounds[1]):
        line = lines[index]
        if line.startswith("@"):
            columns = _columns(line)
            active = max(range(len(expected)), key=lambda n: len(expected[n].keys() & columns.keys()))
            missing = expected[active].keys() - columns.keys()
            if missing:
                raise ValueError(f"{section} header is missing columns {', '.join(sorted(missing))}. "
                                 "Supply the needed columns.")
            blocks[active] = (columns, index + 1, line.rstrip("\r\n"))
        elif active is not None:
            columns, _, header = blocks[active]
            left, right = next(iter(columns.values()))
            try:
                level = int(line[left:right])
            except ValueError:
                continue
            highest = max(highest, level)
            blocks[active] = (columns, index + 1, header)
    for number, columns in enumerate(expected):
        if number not in blocks:
            raise ValueError(f"{section} has no header containing columns {', '.join(columns)}. "
                             "Supply the needed columns.")
    return [blocks[number] for number in range(len(expected))], highest


def _event_row(columns, values, section):
    return "".join(_cell(values.get(column, -99), end - start, section, column)
                   for column, (start, end) in columns.items())


def _event_text(text, treatment, events, section="irrigation"):
    """Render checked events in memory, also used by pre-write checks."""
    name, column, headers = "IRRIGATION AND WATER MANAGEMENT", "MI", _IRRIGATION_HEADERS
    if section == "fertilizer":
        name, column, headers = "FERTILIZERS (INORGANIC)", "MF", (_FERTILIZER_HEADER,)
    _section_row(text, "TREATMENTS", "N", treatment, (column,))
    lines = text.splitlines(keepends=True)
    blocks, highest = _event_blocks(lines, name, headers)
    level = highest + 1 if events else 0
    _repoint(lines, treatment, column, level)
    if not events:
        return "".join(lines)
    rows = [[]]
    if section == "irrigation":
        rows.insert(0, [_event_row(blocks[0][0], {"I": level, "EFIR": 1}, name)])
    for event in events:
        day = date.fromisoformat(event["date"])
        day_code = f"{day.year % 100:02d}{day.timetuple().tm_yday:03d}"
        if section == "irrigation":
            values = {"I": level, "IDATE": day_code, "IROP": event["method"], "IRVAL": event["amount"]}
        else:
            values = {"F": level, "FDATE": day_code, "FMCD": event["material"],
                      "FACD": event["application"], "FDEP": event["depth"], "FAMN": event["n"],
                      "FAMP": event.get("p", 0), "FAMK": event.get("k", 0), "FAMC": 0, "FAMO": 0}
        rows[-1].append(_event_row(blocks[-1][0], values, name))
    body = [line for (_, _, header), added in zip(blocks, rows) for line in [header, *added]]
    if blocks[0][1] is None:
        lines = _insert_section(lines, name, body)
    elif section == "irrigation":
        # DSSAT reads all events after the selected control block. A new header
        # pair isolates this schedule from the preceding level's events.
        _append_rows(lines, max(block[1] for block in blocks), body)
    else:
        _append_rows(lines, blocks[0][1], rows[0])
    return "".join(lines)


def _cultivar_text(text, treatment, cultivar):
    """Add a CULTIVARS level and repoint CU, using the management edit helpers."""
    _section_row(text, "TREATMENTS", "N", treatment, ("CU",))
    lines = text.splitlines(keepends=True)
    header = "@C CR INGENO CNAME"
    blocks, highest = _event_blocks(lines, "CULTIVARS", (header,))
    columns, index, _ = blocks[0]
    level = highest + 1
    # CNAME is descriptive; -99 avoids retaining the previous cultivar's name.
    row = _event_row(columns, {"C": level, "CR": cultivar["crop"],
                               "INGENO": cultivar["code"], "CNAME": -99}, "CULTIVARS")
    _repoint(lines, treatment, "CU", level)
    if index is None:
        lines = _insert_section(lines, "CULTIVARS", [header, row])
    else:
        _append_rows(lines, index, [row])
    return "".join(lines)


def _write_management(filex, treatment, management):
    """Apply only the selected, checked entry to the already-copied FileX."""
    if management is None:
        return
    for key, entry in management["treatments"].items():
        if int(key) == int(treatment):
            path = Path(filex)
            text = path.read_bytes().decode("latin-1")
            if "cultivar" in entry:
                text = _cultivar_text(text, int(treatment), entry["cultivar"])
            if "planting" in entry:
                text = _planting_text(text, int(treatment), entry["planting"])
            for section in ("irrigation", "fertilizer"):
                if section in entry:
                    text = _event_text(text, int(treatment), entry[section], section)
            path.write_bytes(text.encode("latin-1"))
            return
