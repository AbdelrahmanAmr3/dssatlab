"""Edit planting in FileX text; never build a model or rewrite existing sections."""

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

    start, end = _section_bounds(lines, "TREATMENTS")
    columns = {}
    for index in range(start + 1, end):
        line = lines[index]
        if line.startswith("@"):
            columns = _columns(line)
        elif "N" in columns and "MP" in columns:
            left, right = columns["N"]
            try:
                number = int(line[left:right])
            except ValueError:
                continue
            if number == treatment:
                left, right = columns["MP"]
                lines[index] = (line[:left] + _cell(level, right - left, "TREATMENTS", "MP")
                                + line[right:])
                break
    if bounds is None:
        lines = _insert_section(lines, "PLANTING DETAILS", [_PLANTING_HEADER, row])
    else:
        newline = _newline(lines)
        # An unterminated final row needs a separator before the appended row.
        prefix = "" if lines[insert_at - 1].endswith(("\r", "\n")) else newline
        lines.insert(insert_at, prefix + row + newline)
    return "".join(lines)


def _write_planting(filex, treatment, management):
    """Apply only the selected, checked entry to the already-copied FileX."""
    if management is None:
        return
    for key, entry in management["treatments"].items():
        if int(key) == int(treatment) and "planting" in entry:
            path = Path(filex)
            text = path.read_bytes().decode("latin-1")
            edited = _planting_text(text, int(treatment), entry["planting"])
            path.write_bytes(edited.encode("latin-1"))
            return
