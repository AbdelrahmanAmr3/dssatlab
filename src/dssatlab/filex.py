"""Read only a treatment's field, weather station, soil profile and start."""

from pathlib import Path
import re


def _section_row(text, section, key, level, required):
    """Find a level across blocks with the needed columns, using header token ends."""
    in_section = False
    matching_header = False
    columns = None
    for line in text.splitlines():
        if line.startswith("*"):
            if in_section:
                break
            name = line[1:].strip()
            in_section = name == section or name.startswith(section + " ")
            continue
        if not in_section:
            continue
        if line.startswith("@"):
            columns = []
            previous_end = 0
            for token in re.finditer(r"\S+", line):
                name = token.group().lstrip("@").rstrip(".")
                # ID_SOIL's ten-character value extends past its short header.
                end = token.start() + 10 if name == "ID_SOIL" else token.end()
                columns.append((name, previous_end, end))
                previous_end = end
            if set((key,) + required) <= {name for name, _, _ in columns}:
                matching_header = True
            else:
                columns = None
        elif columns is not None:
            if not line.strip():
                columns = None
                continue
            row = {name: line[start:end].strip() for name, start, end in columns}
            try:
                number = int(row[key])
            except ValueError:
                continue
            if number == level:
                return row
    if not in_section:
        raise ValueError(f"missing {section} section. Supply that section in the FileX.")
    if not matching_header:
        raise ValueError(f"{section} has no header block containing columns "
                         f"{', '.join((key,) + required)}. Supply the needed columns together.")
    label = "treatment number" if section == "TREATMENTS" else f"row {key}="
    raise ValueError(f"{section}: {label} {level} does not exist in any matching header "
                     "block. Choose an existing level or correct the FileX.")


def _read_filex(source, treatment) -> tuple[dict[str, str], list[str]]:
    """Return available WSTA/ID_SOIL/START/SDATE values and problems, without writing.

    Partial results let check() compare a valid station even if the start is bad,
    or compare a valid start even if the field cannot be resolved.
    """
    if (isinstance(treatment, bool) or
            not isinstance(treatment, (int, str)) or
            isinstance(treatment, str) and not re.fullmatch(r"[0-9]+", treatment)):
        return {}, ["FileX treatment number is invalid. Supply an int or digit string."]
    try:
        treatment = int(treatment)
        str(treatment)  # Check that the number can also be reported in a problem.
    except ValueError:
        return {}, ["FileX treatment number is invalid. Supply an int or digit string."]
    if not isinstance(source, (str, Path)):
        return {}, ["Cannot read FileX: expected a path. Supply a readable FileX as str/Path."]
    try:
        text = Path(source).read_text(encoding="latin-1")
    except (OSError, ValueError) as error:
        return {}, [f"Cannot read FileX {source}: {error}. Supply a readable FileX path."]
    try:
        row = _section_row(text, "TREATMENTS", "N", treatment, ("FL", "SM"))
    except ValueError as error:
        return {}, [f"FileX {source}: {error}"]

    values, problems = {}, []
    for reference, section, key, required in (
        ("FL", "FIELDS", "L", ("WSTA",)),
        ("SM", "SIMULATION CONTROLS", "N", ("START", "SDATE")),
    ):
        try:
            level = int(row[reference])
        except ValueError:
            problems.append(f"FileX {source}: treatment {treatment} has invalid "
                            f"{reference} {row[reference]!r}. Supply an integer level.")
            continue
        try:
            selected = _section_row(text, section, key, level, required)
        except ValueError as error:
            problems.append(f"FileX {source}: {error}")
            continue
        values.update((name, selected[name]) for name in required)
        if section == "FIELDS" and "ID_SOIL" in selected:
            values["ID_SOIL"] = selected["ID_SOIL"]

    if "WSTA" in values and len(values["WSTA"]) not in (4, 8):
        problems.append(f"FileX {source}: WSTA {values['WSTA']!r} has an invalid length. "
                        "Supply a four-character station or eight-character weather file name.")
        del values["WSTA"]
    if "SDATE" in values and not re.fullmatch(r"[0-9]{5}", values["SDATE"]):
        problems.append(f"FileX {source}: SDATE {values['SDATE']!r} is invalid. "
                        "Supply five digits: two-digit year followed by three-digit day of year.")
        del values["SDATE"]
    return values, problems


def _weather_filename(station: str, start_date: str) -> str:
    """Name DSSAT's weather file from checked WSTA and SDATE, for any START option."""
    if len(station) == 8:
        return f"{station}.WTH"
    if len(station) == 4:
        return f"{station}{start_date[:2]}01.WTH"
    raise ValueError("WSTA must have four or eight characters.")
