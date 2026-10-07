"""Read the management sections representable as experiment data."""

import math
from pathlib import Path
import re

from .errors import DSSATCheckError
from .filex import _filex_date, _section_row, _treatment_rows
from .filex_write import _columns, _PLANTING_FIELDS, _section_bounds
from .irrigation import _check_irrigation_events
from .management import _check_events, _check_planting


def _level_rows(text, section, key, level):
    """Read all blocks of a selected level, including unsupported columns."""
    lines = text.splitlines()
    bounds = _section_bounds(lines, section)
    where = f"{section} level {level}"
    if bounds is None:
        raise ValueError(f"{where}: section is missing. Supply the referenced section.")
    rows, columns = [], {}
    selected = False
    for line in lines[bounds[0] + 1:bounds[1]]:
        if line.startswith("@"):
            columns = _columns(line)
        elif key in columns and line.strip() and not line.lstrip().startswith("!"):
            # Stock FileX levels use I3, even when their header starts with @P/@I/@F.
            try:
                number = int(line[:3])
            except ValueError:
                continue
            # Irrigation events belong to the preceding control row's block.
            if section != "IRRIGATION AND WATER MANAGEMENT" or "EFIR" in columns:
                selected = number == level
            if selected:
                if number != level:
                    # IPIRR stops reading events when LN > LNIR; do not guess
                    # how a mismatched block should be rewritten by the writer.
                    raise ValueError(f"{where} column I: event number {number} differs "
                                     "from the control level. DSSAT stops the schedule "
                                     "when an event number exceeds that level. Supply "
                                     "matching event numbers or keep this section in "
                                     "the FileX without reading it.")
                row = {name: line[max(start, 3) if name != key else start:end].strip()
                       for name, (start, end) in columns.items()}
                row[key] = str(number)
                rows.append(row)
    return rows


def _number(value, column, where):
    try:
        number = float(value)
    except ValueError:
        number = math.nan
    if not math.isfinite(number):
        raise ValueError(f"{where} column {column}: {value!r} is not a finite number. "
                         "Supply a numeric value in DSSAT units.")
    return int(number) if number.is_integer() else number


def _date(value, column, where):
    day = _filex_date(value)
    if day is None:
        raise ValueError(f"{where} column {column}: {value!r} is not a FileX date. "
                         "Supply a valid five-digit YYDDD date (1936-2035).")
    return day.isoformat()


def _check_columns(row, allowed, where, constants=None):
    """Reject information the section writer would discard."""
    constants = constants or {}
    for column, value in row.items():
        if column in allowed or not value:
            continue
        try:
            number = float(value)
        except ValueError:
            number = None
        if number != -99 and (column not in constants or number != constants[column]):
            raise ValueError(f"{where} column {column}: {value!r} cannot be represented "
                             "in experiment data. Checked the section's accepted fields "
                             "and writer constants. Use a FileX with representable values "
                             "or keep this section in the FileX without reading it.")


def _required(row, columns, where):
    missing = set(columns) - row.keys()
    if missing:
        raise ValueError(f"{where}: missing columns {', '.join(sorted(missing))}. "
                         "Supply the needed columns together in the FileX header.")


def _read_planting(text, level):
    where = f"PLANTING DETAILS level {level}"
    rows = _level_rows(text, "PLANTING DETAILS", "P", level)
    if len(rows) != 1:
        raise ValueError(f"{where}: found {len(rows)} rows; expected one. "
                         "Supply exactly one planting row for the referenced level.")
    row = rows[0]
    _required(row, _PLANTING_FIELDS, where)
    _check_columns(row, {"P", "PLNAME", *_PLANTING_FIELDS}, where)
    planting = {}
    for column, field in _PLANTING_FIELDS.items():
        value = row[column]
        if column in ("PDATE", "EDATE"):
            if column == "PDATE" or value != "-99":
                planting[field] = _date(value, column, where)
        elif column in ("PLME", "PLDS"):
            planting[field] = value
        else:
            number = _number(value, column, where)
            # PPOE defaults to PPOP when omitted by the writer, so retain its -99.
            if number != -99 or column in ("PPOP", "PPOE", "PLRS", "PLDP"):
                planting[field] = number
    problems = _check_planting(planting, where)
    if problems:
        raise ValueError("; ".join(problems))
    return planting


def _management_code(text, treatment_row, column, where):
    try:
        sm = int(treatment_row["SM"])
    except ValueError:
        raise ValueError(f"{where}: TREATMENTS column SM {treatment_row['SM']!r} "
                         "is not an integer level. Supply an existing simulation controls level.") from None
    return _section_row(text, "SIMULATION CONTROLS", "N", sm,
                        ("MANAGEMENT", column))[column]


def _read_fertilizer(text, treatment_row, level):
    where = f"FERTILIZERS level {level}"
    code = _management_code(text, treatment_row, "FERTI", where)
    if code == "D":
        raise ValueError(f"{where} column FDATE: FERTI D at TREATMENTS SM level "
                         f"{treatment_row['SM']} means days after planting, which "
                         "fertilizer experiment data cannot represent. Use FERTI R "
                         "with calendar FDATE values or keep this section in the "
                         "FileX without reading it.")
    fields = {"FMCD": "material", "FACD": "application", "FDEP": "depth",
              "FAMN": "n", "FAMP": "p", "FAMK": "k"}
    rows = _level_rows(text, "FERTILIZERS", "F", level)
    if not rows:
        raise ValueError(f"{where}: no event rows found. Supply the referenced level "
                         "or set the treatment's MF to 0 for none.")
    events = []
    for row in rows:
        _required(row, {"FDATE", *fields}, where)
        _check_columns(row, {"F", "FDATE", "FERNAME", *fields}, where,
                       {"FAMC": 0, "FAMO": 0})
        event = {"date": _date(row["FDATE"], "FDATE", where)}
        for column, field in fields.items():
            event[field] = (row[column] if column in ("FMCD", "FACD") else
                            _number(row[column], column, where))
        events.append(event)
    problems, _ = _check_events(events, "fertilizer", where)
    if problems:
        raise ValueError("; ".join(problems))
    return events


def _read_irrigation(text, treatment_row, level):
    where = f"IRRIGATION AND WATER MANAGEMENT level {level}"
    rows = _level_rows(text, "IRRIGATION AND WATER MANAGEMENT", "I", level)
    controls = [row for row in rows if "EFIR" in row]
    if len(controls) != 1:
        raise ValueError(f"{where}: found {len(controls)} EFIR rows; expected one. "
                         "Supply exactly one efficiency row for the referenced level.")
    for row in rows:
        _check_columns(row, {"I", "EFIR", "IRNAME", "IDATE", "IROP", "IRVAL"}, where)
    efficiency = _number(controls[0]["EFIR"], "EFIR", where)
    code = _management_code(text, treatment_row, "IRRIG", where)
    events = []
    for row in rows:
        if "EFIR" in row:
            continue
        _required(row, ("IDATE", "IROP", "IRVAL"), where)
        if code == "D":
            value = row["IDATE"]
            if not re.fullmatch(r"[0-9]{1,5}", value):
                raise ValueError(f"{where} column IDATE: {value!r} cannot express days "
                                 "after planting under IRRIG D. Supply an integer 0-99999.")
            timing = {"days_after_planting": int(value)}
        elif code in ("R", "P", "W"):
            timing = {"date": _date(row["IDATE"], "IDATE", where)}
        else:
            raise ValueError(f"{where} column IDATE: event timing under IRRIG {code!r} "
                             "cannot be represented in experiment data. Checked the "
                             "treatment's SM management level. Use IRRIG R/P/W for dates "
                             "or D for days after planting, or remove ignored events.")
        events.append({**timing, "method": row["IROP"],
                       "amount": _number(row["IRVAL"], "IRVAL", where)})
    irrigation = {"efficiency": efficiency, "events": events}
    problems, _ = _check_irrigation_events(irrigation, where, code=code)
    if problems:
        raise ValueError("; ".join(problems))
    return irrigation


def read_experiment(filex: str | Path, treatment: int | str = 1) -> dict:
    """Read planting, fertilizer and irrigation for one FileX treatment.

    Returns one experiment data entry, with DSSAT units and ISO date strings.
    Sections at level 0 are omitted; level names are not read. The source is
    unchanged and no DSSAT executable is needed. Other experiment sections
    are retained by the FileX, rather than included in this entry.

    Example:
        entry = read_experiment("UFGA8201.MZX", treatment=1)
        sim = Simulation("UFGA8201.MZX", weather="weather.csv",
                         management={"treatments": {1: entry}})

    Raises:
        DSSATCheckError: The FileX/treatment cannot be read, is a sequence or
            forecast, or holds management values or timing the experiment
            data shape cannot preserve (including repeated event dates).
    """
    where = f"Cannot read experiment data from FileX {filex}, treatment {treatment}"
    try:
        if not isinstance(filex, (str, Path)):
            raise ValueError("expected a path. Supply a readable FileX as str/Path.")
        path = Path(filex)
        if path.suffix.upper() == ".FCX":
            raise ValueError("forecasts (.FCX) are not supported. Supply a one-row "
                             "treatment in a non-forecast FileX.")
        if (isinstance(treatment, bool) or not isinstance(treatment, (int, str)) or
                not re.fullmatch(r"[0-9]+", str(treatment)) or int(treatment) < 1):
            raise ValueError("invalid treatment number. Supply a positive int or digit string.")
        treatment = int(treatment)
        try:
            text = path.read_text(encoding="latin-1")
        except (OSError, ValueError) as error:
            raise ValueError(f"reading the FileX failed: {error}. "
                             "Supply a readable FileX path.") from error
        problems = []
        rows = _treatment_rows(text, problems)
        if problems:
            raise ValueError("; ".join(problems))
        if sum(int(number) == treatment for _, (number, _) in rows if number) > 1:
            raise ValueError("sequences (several TREATMENTS rows for this number) are "
                             "not supported. Choose a one-row treatment.")
        row = _section_row(text, "TREATMENTS", "N", treatment, ("MP", "MF", "MI", "SM"))
        entry = {}
        for column, section in (("MP", "planting"), ("MF", "fertilizer"), ("MI", "irrigation")):
            try:
                level = int(row[column])
                if level < 0:
                    raise ValueError
            except ValueError:
                raise ValueError(f"TREATMENTS column {column}: {row[column]!r} is not a "
                                 "nonnegative level. Supply 0 for none or an existing level.") from None
            if level:
                if section == "planting":
                    entry[section] = _read_planting(text, level)
                elif section == "fertilizer":
                    entry[section] = _read_fertilizer(text, row, level)
                else:
                    entry[section] = _read_irrigation(text, row, level)
        return entry
    except (OSError, ValueError) as error:
        raise DSSATCheckError([f"{where}: {error}"]) from error
