"""Read DSSAT FileA/FileT measurements into observed data (ADR 0008)."""

from datetime import date, timedelta
import math
from pathlib import Path
import re

from .errors import DSSATCheckError
from .filex import _read_filex
from .observed import _PLANT_COLUMNS, _SUMMARY_COLUMNS
from .outputs import _SUMMARY_DATES


_METADATA = {"TRNO", "RUNNO", "YEAR", "DOY", "DAS", "DAP", "R#", "O#", "P#",
             "WYEAR", "HYEAR", "XLAT", "LONG", "ELEV"}


def _year_day(year, doy):
    result = date(year, 1, 1) + timedelta(days=doy - 1)
    if doy < 1 or result.year != year:
        raise ValueError(f"day {doy} does not exist in {year}")
    return result


def _anchor(path, treatment):
    expected = path.with_suffix(path.suffix[:-1] + "X")
    try:
        sibling = next((p for p in path.parent.iterdir()
                        if p.name.casefold() == expected.name.casefold()), expected)
        values, problems = _read_filex(sibling, treatment)
        if problems:
            raise ValueError("; ".join(problems))
        sdate = values["SDATE"]
        yy, doy = int(sdate[:2]), int(sdate[2:])
        # Y4K_DOY's unanchored fallback: 00..35 are 2000..2035, else 1900..1999.
        return _year_day(2000 + yy if yy <= 35 else 1900 + yy, doy)
    except (OSError, KeyError, ValueError, OverflowError) as error:
        raise ValueError(f"cannot resolve SDATE for treatment {treatment} in FileX "
                         f"{expected}: {error}. Supply a readable sibling FileX "
                         "with this treatment and a valid SDATE") from error


def _read_date(value, path, treatment, anchors):
    if not re.fullmatch(r"[0-9]{1,3}|[0-9]{5}|[0-9]{7}", value):
        raise ValueError(f"bad date {value!r}. Use YYYYDDD, YYDDD or day of year")
    code = int(value)
    if len(value) == 7:
        return _year_day(code // 1000, code % 1000).isoformat()
    if treatment is None:
        raise ValueError(f"cannot resolve short date {value!r} without a valid TRNO")
    if treatment not in anchors:
        try:
            anchors[treatment] = _anchor(path, treatment)
        except ValueError as error:
            anchors[treatment] = str(error)
    anchor = anchors[treatment]
    if isinstance(anchor, str):
        raise ValueError(anchor)
    if len(value) == 5:
        year, doy = (anchor.year // 100) * 100 + code // 1000, code % 1000
        candidate = date(year, 1, 1) + timedelta(days=doy - 1)
        # Y4K_DOY: use the anchor's century; add 100 years if before the anchor date.
        if candidate < anchor:
            year += 100
    else:
        doy = code
        year = anchor.year + (doy < anchor.timetuple().tm_yday)
    return _year_day(year, doy).isoformat()


def read_dssat_observed(path: str | Path) -> list[dict]:
    """Read FileA/FileT by its *EXP. DATA (A)/(T) header, for any crop.

    Rows contain scenario='base', integer treatment, date (ISO yyyy-mm-dd for
    FileT, None for FileA), and float measurements; Summary dates are ISO strings.
    Only supported Summary/Plant growth measurements are read: other columns
    (e.g. GN%M, SW1D) and metadata are silently ignored. Missing -99 cells and
    rows without measurements are omitted. Tables merge by treatment and date;
    conflicting measurements are check problems, never silently overwritten.

    Short dates need the sibling FileX's treatment SDATE. Its two-digit year
    uses DSSAT Y4K's unanchored 2035 crossover. Observed YYDDD dates then use
    the anchor's century, advancing a century if before SDATE; bare days use
    the anchor year or the next year. Seven-digit dates need no FileX.
    All problems raise one DSSATCheckError with source paths and line numbers.
    """
    path = Path(path)
    try:
        lines = path.read_text(encoding="latin-1").splitlines()
    except (OSError, ValueError) as error:
        raise DSSATCheckError([f"{path}, line 1: cannot read FileA/FileT: {error}. "
                               "Supply a readable FileA/FileT path."]) from error
    kinds = {match[1] for line in lines
             if (match := re.match(r"\s*\*EXP\. DATA \(([AT])\)", line))}
    problems = []
    if len(kinds) != 1:
        problems.append(f"{path}, line 1: not a FileA/FileT with one unambiguous "
                        "*EXP. DATA (A)/(T) header. Supply the correct header.")
    kind = next(iter(kinds)) if len(kinds) == 1 else None
    allowed = (_PLANT_COLUMNS if kind == "T" else _SUMMARY_COLUMNS) - _METADATA
    rows, anchors, names = {}, {}, None
    for number, line in enumerate(lines, 1):
        line = line.strip()
        where = f"{path}, line {number}"
        if not line or line.startswith("!"):
            continue
        if line.startswith("*"):
            names = None
            continue
        if line.startswith("@"):
            names = line[1:].split()
            required = {"TRNO", "DATE"} if kind == "T" else {"TRNO"}
            if not required <= set(names) or len(names) != len(set(names)):
                problems.append(f"{where}: invalid table header. Supply unique columns "
                                f"including {', '.join(sorted(required))}.")
                names = None
            continue
        if names is None:
            continue
        cells = line.split()
        if len(cells) != len(names):
            problems.append(f"{where}: {len(cells)} values for {len(names)} columns. "
                            "Supply one value per header column.")
        raw = dict(zip(names, cells))
        treatment = None
        try:
            treatment = int(raw.get("TRNO", ""))
            if treatment <= 0:
                raise ValueError
        except ValueError:
            problems.append(f"{where}: invalid TRNO {raw.get('TRNO')!r}. "
                            "Supply a positive integer treatment number.")
            treatment = None
        measured, day, missing_date = {}, None, False
        for name, value in raw.items():
            is_date = name in _SUMMARY_DATES or name == "DATE" and kind == "T"
            if name not in allowed and not (name == "DATE" and kind == "T"):
                continue
            try:
                numeric = float(value)
                if numeric == -99:
                    missing_date = missing_date or name == "DATE"
                    continue
                if is_date:
                    parsed = _read_date(value, path, treatment, anchors)
                    if name == "DATE":
                        day = parsed
                    else:
                        measured[name] = parsed
                else:
                    if not math.isfinite(numeric):
                        raise ValueError("measurement must be finite")
                    measured[name] = numeric
            except (ValueError, OverflowError) as error:
                problems.append(f"{where}, {name}: bad {'date' if is_date else 'number'} "
                                f"{value!r}: {error}. Correct this cell in the FileA/FileT.")
        if missing_date and measured:
            problems.append(f"{where}: missing DATE (-99). Supply a date for the FileT row.")
        if not measured or treatment is None or kind == "T" and day is None:
            continue
        row = rows.setdefault((treatment, day),
                              dict(scenario="base", treatment=treatment, date=day))
        for name, value in measured.items():
            if name in row and row[name] != value:
                problems.append(f"{where}, {name}: conflicting measurements for treatment "
                                f"{treatment}, date {day}. Keep one value for this key.")
            else:
                row[name] = value
    if problems:
        raise DSSATCheckError(problems)
    return list(rows.values())
