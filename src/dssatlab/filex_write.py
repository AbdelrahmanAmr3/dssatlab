"""Edit management in FileX text without rewriting existing sections."""

from datetime import date
from pathlib import Path
import re

from .filex import _section_row, _treatment_rows
from .weather import _dssat_date
from .operations import _OPERATION_FIELDS, _operation_values


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
_RESIDUES_HEADER = "@R RDATE  RCOD  RAMT  RESN  RESP  RESK  RINP  RDEP  RMET RENAME"
_TILLAGE_HEADER = "@T TDATE TIMPL  TDEP TNAME"
_HARVEST_HEADER = "@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME"


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
    tokens = list(re.finditer(r"\S+", header))
    for index, token in enumerate(tokens):
        name, end = token.group().lstrip("@").rstrip("."), token.end()
        if name == "ID_SOIL":
            end = token.start() + 10
            if index + 1 < len(tokens):
                end = min(end, tokens[index + 1].start())
        columns[name] = (start, end)
        start = end
    return columns


def _newline(lines):
    for line in lines:
        match = re.search(r"\r\n|\n|\r", line)
        if match:
            return match.group()
    return "\n"


def _insert_section(lines, section, body):
    """Insert header/row strings before harvest or controls, preserving existing lines."""
    bounds = _section_bounds(lines, "SIMULATION CONTROLS")
    if bounds is None:
        raise ValueError("missing SIMULATION CONTROLS section. Supply that section "
                         "so management can be inserted before it.")
    harvest = _section_bounds(lines, "HARVEST DETAILS")
    if harvest is not None and harvest[0] < bounds[0]:
        bounds = harvest
    newline = _newline(lines)
    block = [line + newline for line in ["*" + section, *body, ""]]
    return lines[:bounds[0]] + block + lines[bounds[0]:]


def _cell(value, width, section, column, *, first_column=False):
    text = str(value)
    limit = width if first_column else width - 1
    if len(text) > limit and isinstance(value, float) and value.is_integer():
        text = str(int(value))
    if len(text) > limit:
        blank = "" if first_column else " The field needs one leading blank."
        raise ValueError(f"{section} column {column}: value {str(value)!r} does not fit "
                         f"its {width}-character field.{blank} Supply a shorter value "
                         "that fits the FileX column without rounding or truncation.")
    return text.rjust(width)


def _planting_row(columns, level, planting):
    values = {column: planting.get(field, -99)
              for column, field in _PLANTING_FIELDS.items()}
    values.update(P=level, PLNAME=-99)
    values["PPOE"] = planting.get("emergence_population", planting["population"])
    for column in ("PDATE", "EDATE"):
        if values[column] != -99:
            day = date.fromisoformat(values[column])
            values[column] = _dssat_date(day)
    return "".join(_cell(values.get(column, -99), end - start, "PLANTING DETAILS",
                         column, first_column=start == 0)
                   for column, (start, end) in columns.items())


def _planting_text(text, treatment, planting, *, rotation=None):
    """Check and render one planting edit in memory, preserving untouched bytes.

    Called by management checks for each valid planting entry, then by run()
    for the selected entry only. Invalid layouts/field overflow raise ValueError
    before Simulation creates a folder. Input planting has already been checked.
    """
    if rotation is None:
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
    level = _new_level(lines, treatment, "MP", highest, "PLANTING DETAILS", rotation=rotation)
    row = _planting_row(columns, level, planting)

    _repoint(lines, treatment, "MP", level, rotation=rotation)
    if bounds is None:
        lines = _insert_section(lines, "PLANTING DETAILS", [_PLANTING_HEADER, row])
    else:
        _append_rows(lines, insert_at, [row])
    return "".join(lines)


def _repoint(lines, treatment, column, level, section="TREATMENTS", key="N", *, rotation=None):
    """Repoint the first matching row, optionally selecting its R as well as N."""
    if rotation is None:
        _section_row("".join(lines), section, key, treatment, (column,))
    treatments = _treatment_rows("".join(lines)) if section == "TREATMENTS" else {}
    start, end = _section_bounds(lines, section) or (0, 0)
    columns = {}
    for index in range(start + 1, end):
        line = lines[index]
        if line.startswith("@"):
            columns = _columns(line)
        elif key in columns and (rotation is not None or column in columns):
            left, right = columns[key]
            try:
                n, r = treatments.get(line.rstrip("\r\n"), (line[left:right], ""))
                number = int(n)
                if rotation is not None:
                    if int(r) != rotation:
                        continue
            except ValueError:
                continue
            if number == treatment:
                if column not in columns:
                    raise ValueError(f"{section} header is missing columns {column}. "
                                     "Supply the needed columns together.")
                left, right = columns[column]
                if line[left:right].strip() == str(level):
                    return
                cell = _cell(level, right - left, section, column, first_column=left == 0)
                if column == "WSTA":  # DSSAT's sequence mode reads WSTA left-justified (A8).
                    cell = " " + cell.strip().ljust(right - left - 1)
                lines[index] = line[:left] + cell + line[right:]
                return
    if rotation is not None:
        raise ValueError(f"{section}: treatment {treatment}, rotation component R {rotation} "
                         "has no matching row. Choose an existing (N, R) pair in the FileX.")


def _new_level(lines, treatment, column, highest, section, *, rotation=None):
    """Past 99, replace the lowest level free after repointing this row."""
    if highest < 99:
        return highest + 1
    _repoint(lines, treatment, column, 0, rotation=rotation)
    start, end = _section_bounds(lines, "TREATMENTS")
    used, left, right = set(), 0, 0
    for line in lines[start + 1:end]:
        if line.startswith("@"):
            left, right = _columns(line).get(column, (0, 0))
        else:
            try:
                used.add(int(line[left:right]))
            except ValueError:
                continue
    level = next((n for n in range(1, 100) if n not in used), highest + 1)
    start, end = _section_bounds(lines, section) or (0, 0)
    for index in range(start + 1, end):
        if lines[index].startswith("@"):
            left, right = next(iter(_columns(lines[index]).values()))
        elif lines[index][left:right].strip() == str(level):
            # Empty strings remove rows from the text without shifting insertion points.
            lines[index] = ""
    return level


def _append_rows(lines, index, rows):
    newline = _newline(lines)
    prefix = "" if not lines[index - 1] or lines[index - 1].endswith(("\r", "\n")) else newline
    lines[index:index] = [prefix + newline.join(rows) + newline]


def _event_blocks(lines, section, headers, *, optional_columns=()):
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
            missing = expected[active].keys() - columns.keys() - set(optional_columns)
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
    return "".join(_cell(values.get(column, -99), end - start, section, column, first_column=start == 0)
                   for column, (start, end) in columns.items())


def _event_text(text, treatment, events, section="irrigation", *, rotation=None):
    """Render checked events in memory, also used by pre-write checks."""
    name, column, headers = "IRRIGATION AND WATER MANAGEMENT", "MI", _IRRIGATION_HEADERS
    efficiency, has_level = 1, bool(events)
    if section == "irrigation" and isinstance(events, dict):
        efficiency, events = events["efficiency"], events["events"]
        has_level = True  # An empty dict schedule still writes its EFIR level.
    if section == "fertilizer":
        name, column, headers = "FERTILIZERS (INORGANIC)", "MF", (_FERTILIZER_HEADER,)
    elif section == "residues":
        name, column, headers = "RESIDUES AND ORGANIC FERTILIZER", "MR", (_RESIDUES_HEADER,)
    elif section == "tillage":
        name, column, headers = "TILLAGE AND ROTATIONS", "MT", (_TILLAGE_HEADER,)
    elif section == "harvest":
        name, column, headers = "HARVEST DETAILS", "MH", (_HARVEST_HEADER,)
    if rotation is None:
        _section_row(text, "TREATMENTS", "N", treatment, (column,))
    lines = text.splitlines(keepends=True)
    blocks, highest = _event_blocks(lines, name, headers)
    level = _new_level(lines, treatment, column, highest, name, rotation=rotation) if has_level else 0
    _repoint(lines, treatment, column, level, rotation=rotation)
    if not has_level:
        return "".join(lines)
    rows = [[]]
    if section == "irrigation":
        rows.insert(0, [_event_row(blocks[0][0], {"I": level, "EFIR": efficiency}, name)])
    for event in events:
        day_code = event["days_after_planting"] if "days_after_planting" in event else _dssat_date(date.fromisoformat(event["date"]))
        if section == "irrigation":
            values = {"I": level, "IDATE": day_code, "IROP": event["method"], "IRVAL": event["amount"]}
        elif section in _OPERATION_FIELDS:
            values = _operation_values(section, event, level)
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


def _identity_text(text, treatment, name, station, soil_id):
    """Render the selected treatment's label and field IDs, also for checks."""
    row = _section_row(text, "TREATMENTS", "N", treatment, ("FL",))
    lines = text.splitlines(keepends=True)
    if name not in (None, "base"):
        if not isinstance(name, str) or not name.strip() or not name.isprintable():
            raise ValueError("Scenario name must be a non-empty printable string.")
        name.encode("latin-1")
        _repoint(lines, treatment, "TNAM" if "TNAM" in row else "TNAME", name)
    field = int(row["FL"])
    if station is not None:
        _repoint(lines, field, "WSTA", station, "FIELDS", "L")
    if soil_id is not None:
        _repoint(lines, field, "ID_SOIL", soil_id, "FIELDS", "L")
    return "".join(lines)


def _write_management(filex, treatment, management, *, name=None, station=None, soil_id=None):
    """Apply a checked label, optional site IDs and experiment edits to the copy."""
    path = Path(filex)
    if name not in (None, "base") or station is not None or soil_id is not None:
        text = path.read_bytes().decode("latin-1")
        text = _identity_text(text, int(treatment), name, station, soil_id)
        path.write_bytes(text.encode("latin-1"))
    if management is None:
        return
    for key, entry in management["treatments"].items():
        if int(key) == int(treatment) and entry:
            text = path.read_bytes().decode("latin-1")
            if "cultivar" in entry:
                from .cultivar import _cultivar_text
                from .cultivar_coefficients import _changed_cultivar
                text = _cultivar_text(text, int(treatment), _changed_cultivar(path, entry["cultivar"]))
            if "planting" in entry:
                text = _planting_text(text, int(treatment), entry["planting"])
            for section in ("irrigation", "fertilizer", *_OPERATION_FIELDS):
                if section in entry:
                    text = _event_text(text, int(treatment), entry[section], section)
            if "initial_conditions" in entry:
                from .initial_conditions import _initial_conditions_text
                text = _initial_conditions_text(text, int(treatment), entry["initial_conditions"])
            if "controls" in entry:
                from .controls import _controls_text
                text = _controls_text(text, int(treatment), entry["controls"])
            path.write_bytes(text.encode("latin-1"))
            return
