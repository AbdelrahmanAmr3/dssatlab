"""Read only a treatment's field, weather station, soil profile and start."""

from datetime import date, timedelta
from pathlib import Path
import re

from .weather import _dssat_date


def _filex_date(value):
    """Return a FileX YYDDD calendar date, or None for an unreadable date."""
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{5}', value):
        return None
    # DSSAT-CSM v4.8.6.0, Utilities/DATES.for, Y2K_DOY:
    # YY <= 40 means 2000 + YY; larger YY means 1900 + YY.
    yy, doy = int(value[:2]), int(value[2:])
    year = (2000 if yy <= 40 else 1900) + yy
    if not 1 <= doy <= date(year, 12, 31).timetuple().tm_yday:
        return None
    return date(year, 1, 1) + timedelta(days=doy - 1)


def _treatment_rows(text, problems=None):
    """Read N/R once per text; valid repeated component rows select mode Q's layout.

    In a sequence FileX only the rows of a repeated N use the sequence columns: a one-row
    treatment runs in a normal mode, where DSSAT reads it with the normal columns.
    When supplied, problems collects collisions between those two readings.
    """
    rows, active, header = [], False, False
    for line in text.splitlines():
        if line.startswith("*"):
            active = line[1:].strip().split(" ")[0] == "TREATMENTS"
            header = False
        elif active and line.startswith("@"):
            header = line.split()[:1] == ["@N"]
        elif active and header and line.strip() and not line.startswith("!"):
            rows.append(line)
    numbers = [int(line[:2]) for line in rows if line[:2].strip().isascii()
               and line[:2].strip().isdigit()]
    # Fortran I2 writes positive R as " 1".." 9" or "10".."99".
    # Ordinary treatments 100 and 101 share N=10 under sequence columns.
    sequence = len(numbers) == len(rows) and all(
        re.fullmatch(r" [1-9]|[1-9][0-9]", line[2:4]) for line in rows)
    repeated = {n for n in numbers if numbers.count(n) > 1} if sequence else set()
    result = {}
    for line in rows:
        width = 2 if sequence and int(line[:2]) in repeated else 3
        n = line[:width].strip()
        result[line] = (n if n.isascii() and n.isdigit() else "", line[width:4].strip())
        if problems is not None and width == 3 and result[line][0] and int(n) in repeated:
            sequence_row = next(row for row in rows if int(row[:2]) == int(n))
            problems.append(
                f"TREATMENTS rows {line!r} (one-row treatment {int(n)}) and "
                f"{sequence_row!r} (sequence {int(n)}) collide: DSSAT reads the treatment "
                "number from columns 1-3 (1-2 in a sequence FileX). "
                "Renumber the one-row treatment or the sequence.")
    return result


def _section_row(text, section, key, level, required):
    """Find a level across blocks with the needed columns, using header token ends."""
    return next(_section_rows(text, section, key, level, required))


def _section_rows(text, section, key, level, required):
    """Yield all rows of a level across blocks with the needed columns."""
    treatments = _treatment_rows(text) if section == "TREATMENTS" else {}
    in_section = False
    matching_header = False
    found = False
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
            tokens = list(re.finditer(r"\S+", line))
            for index, token in enumerate(tokens):
                name = token.group().lstrip("@").rstrip(".")
                end = token.end()
                if name == "ID_SOIL":
                    # Its ten-character value extends past the short header, but
                    # never into the next column.
                    end = token.start() + 10
                    if index + 1 < len(tokens):
                        end = min(end, tokens[index + 1].start())
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
            if section == "TREATMENTS":
                if line not in treatments:
                    continue
                row["N"], row["R"] = treatments[line]
                if not row["N"].isascii() or not row["N"].isdigit():
                    raise ValueError(f"TREATMENTS row {line!r}: DSSAT reads the treatment number "
                                     "from columns 1-3 (1-2 in a sequence FileX). Correct the FileX row.")
            try:
                number = int(row[key])
            except ValueError:
                continue
            if number == level:
                found = True
                yield row
    if found:
        return
    if not in_section:
        raise ValueError(f"missing {section} section. Supply that section in the FileX.")
    if not matching_header:
        raise ValueError(f"{section} has no header block containing columns "
                         f"{', '.join((key,) + required)}. Supply the needed columns together.")
    label = "treatment number" if section == "TREATMENTS" else f"row {key}="
    raise ValueError(f"{section}: {label} {level} does not exist in any matching header "
                     "block. Choose an existing level or correct the FileX.")


def _read_filex(source, treatment, *, start_date=None) -> tuple[dict[str, str], list[str]]:
    """Return available WSTA/ID_SOIL/START/SDATE/NYERS values and problems, without writing.

    Partial results let check() compare a valid station even if the start is bad,
    or compare a valid start even if the field cannot be resolved.
    A checked start_date override replaces SDATE before its value is checked.
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
    problems = []
    _treatment_rows(text, problems)
    problems = [f"FileX {source}: {problem}" for problem in problems]
    try:
        row = _section_row(text, "TREATMENTS", "N", treatment, ("FL", "SM"))
    except ValueError as error:
        return {}, [*problems, f"FileX {source}: {error}"]

    values = {}
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
        if reference == "SM":
            try:
                general = _section_row(text, section, key, level, ("GENERAL", "NYERS"))
                values["NYERS"] = general["NYERS"]
            except ValueError:
                pass  # Missing/unreadable NYERS defaults to one season.
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
    if "SDATE" in values and start_date is not None:
        values["SDATE"] = _dssat_date(start_date)
    if "SDATE" in values and not re.fullmatch(r"[0-9]{5}", values["SDATE"]):
        problems.append(f"FileX {source}: SDATE {values['SDATE']!r} is invalid. "
                        "Supply five digits: two-digit year followed by three-digit day of year.")
    return values, problems


def _irrigation_dates(source, treatment):
    """Return the IDATE values (five digits) of the treatment's irrigation level.

    Best effort: any unreadable FileX or missing irrigation level gives [], because
    the FileX problems are already reported by _read_filex.
    """
    try:
        text = Path(source).read_text(encoding="latin-1")
        level = int(_section_row(text, "TREATMENTS", "N", int(treatment), ("MI",))["MI"])
    except (OSError, ValueError, TypeError, KeyError):
        return []
    if level == 0:
        return []
    dates, in_section, has_date = [], False, False
    for line in text.splitlines():
        if line.startswith("*"):
            in_section = line[1:].strip().startswith("IRRIGATION")
        elif in_section and line.startswith("@"):
            has_date = "IDATE" in line.split()
        elif in_section and has_date and line.strip():
            parts = line.split()
            if parts[0] == str(level) and len(parts) > 1 and re.fullmatch(r"[0-9]{5}", parts[1]):
                dates.append(parts[1])
    return dates


def _weather_filename(station: str, start_date: str) -> str:
    """Name DSSAT's weather file from checked WSTA and SDATE, for any START option."""
    if len(station) == 8:
        return f"{station}.WTH"
    if len(station) == 4:
        return f"{station}{start_date[:2]}01.WTH"
    raise ValueError("WSTA must have four or eight characters.")


def _check_filex_controls(source, treatment, levels) -> list[str]:
    """Report WTHER other than M in the controls levels (SM) a run uses."""
    sm_levels = list(dict.fromkeys(int(level) for level in levels if level.isdigit()))
    if not sm_levels:
        return []
    try:
        treatment_num = int(treatment)
        path = Path(source)
        text = path.read_text(encoding="latin-1")
    except (OSError, TypeError, ValueError):
        return []

    problems = []
    for level in sm_levels:
        try:
            methods = _section_row(text, "SIMULATION CONTROLS", "N", level, ("WTHER",))
            wther = methods.get("WTHER", "").strip()
            if wther and wther != "-99" and wther != "M":
                problems.append(
                    f"FileX WTHER '{wther}' in controls level {level} (treatment {treatment_num}): "
                    "DSSAT would generate weather and ignore the weather data supplied. "
                    "Set WTHER to M."
                )
        except ValueError:
            pass

    return problems


def read_treatment_numbers(source) -> list[int]:
    """Return the treatment numbers (column N) of the FileX TREATMENTS section, in file order."""
    try:
        text = Path(source).read_text(encoding="latin-1")
    except (OSError, ValueError, TypeError) as error:
        raise ValueError(f"Cannot read FileX {source}: {error}. Supply a readable FileX path.") from error
    in_section = found_section = has_header = False
    numbers = []
    rows = _treatment_rows(text)
    for line in text.splitlines():
        if line.startswith("*"):
            in_section = line[1:].strip().split(" ")[0] == "TREATMENTS"
            found_section = found_section or in_section
        elif in_section and line.startswith("@"):
            has_header = line.split()[:1] == ["@N"]
            if not has_header:
                raise ValueError(f"FileX {source}: TREATMENTS header does not start with @N. "
                                 "Correct the FileX header.")
        elif in_section and has_header and line.strip() and not line.startswith("!"):
            try:
                number = rows[line][0]
                if not number.isascii() or not number.isdigit():
                    raise ValueError
                numbers.append(int(number))
            except ValueError:
                raise ValueError(f"FileX {source}: TREATMENTS row {line!r}: DSSAT reads the treatment number "
                                 "from columns 1-3 (1-2 in a sequence FileX). Correct the FileX row.") from None
    if not found_section:
        raise ValueError(f"FileX {source}: missing TREATMENTS section. Supply that section in the FileX.")
    if not numbers:
        raise ValueError(f"FileX {source}: TREATMENTS section has no treatment rows. "
                         "Add at least one treatment row.")
    return numbers
