"""Narrow checks of the required tables in copied DSSAT climate files."""

from math import isfinite
from pathlib import Path
import re


def _climate_rows(lines):
    """Read one header and its rows, stopping at the next header or section."""
    columns, rows = {}, []
    for number, line in lines:
        if not line.strip() or line.lstrip().startswith("!"):
            continue
        if line.startswith("*"):
            break
        if line.startswith("@"):
            if columns:
                break
            start = 0
            # Stock CLI fields end at their header labels, as stock WTH fields do.
            for token in re.finditer(r"\S+", line.split("!", 1)[0]):
                name = token.group().lstrip("@").upper()
                if name:
                    columns[name] = slice(start, token.end())
                    start = token.end() + 1
        elif columns:
            rows.append((number, {name: line[span].strip()
                                  for name, span in columns.items()}))
    return columns, rows


def _climate_number_problems(row, fields, where, *, missing=False):
    """Check only required numeric fields; station -99 stays numeric by spec."""
    problems = []
    for field in fields:
        value = row.get(field, "")
        try:
            number = float(value)
        except ValueError:
            number = float("nan")
        if not isfinite(number) or (missing and number == -99):
            requirement = "finite numeric value other than -99" if missing else "finite numeric value"
            problems.append(f"{where}: {field} {value!r} is not a {requirement}. "
                            f"Checked the {field} column. Supply a {requirement} for {field}.")
    return problems


def _read_climate_file(path, method):
    """Return problems for W (WGEN) or S (SIMMETEO), without changing the file.

    Only the first line, station row and the method's required table are checked.
    The required WGEN column names come from stock UFGA.CLI and DTCM.CLI;
    real-DSSAT table-requirement probes remain unverified (ADR 0032).
    """
    if method not in ("W", "S"):
        raise ValueError("Climate-file method must be W or S.")
    path = Path(path)
    try:
        lines = path.read_text(encoding="latin-1").splitlines()
    except (OSError, ValueError) as error:
        return [f"Cannot read climate file {path}: {error}. Checked the supplied path. "
                "Supply a readable climate file path."]
    problems = []
    where = f"Climate file {path}"
    if not lines or not lines[0].startswith("*CLIMATE"):
        problems.append(f"{where}: missing *CLIMATE header. Checked the first line. "
                        "Supply a climate file whose first line starts with *CLIMATE.")
    numbered = list(enumerate(lines, 1))
    station_start = next((i for i, line in enumerate(lines)
                          if line.startswith("@")
                          and line.lstrip("@").split()[:1] == ["INSI"]), None)
    if station_start is None:
        problems.append(f"{where}: missing @ INSI station row. Checked station headers. "
                        "Supply @ INSI with INSI, LAT, LONG, ELEV, TAV and AMP.")
    else:
        _, rows = _climate_rows(numbered[station_start:])
        if not rows:
            problems.append(f"{where}: missing station values. Checked the @ INSI row. "
                            "Supply INSI, LAT, LONG, ELEV, TAV and AMP beneath @ INSI.")
        else:
            number, row = rows[0]
            insi = row.get("INSI", "")
            station = path.name[:4]
            if insi.upper() != station.upper():
                problems.append(f"{where}: INSI {insi!r} differs from filename station {station!r}. "
                                "Checked @ INSI against the filename's first four characters "
                                "(case-insensitive). Correct INSI or supply the matching climate file.")
            problems.extend(_climate_number_problems(
                row, ("LAT", "LONG", "ELEV", "TAV", "AMP"), f"{where}, line {number}"))

    section = "MONTHLY AVERAGES" if method == "S" else "WGEN PARAMETERS"
    fields = (("SAMN", "XAMN", "NAMN", "RTOT", "RNUM") if method == "S" else
              ("SDMN", "SDSD", "SWMN", "SWSD", "XDMN", "XDSD", "XWMN", "XWSD",
               "NAMN", "NASD", "ALPHA", "RTOT", "PDW", "RNUM"))
    start = next((i for i, line in enumerate(lines) if line.startswith("*" + section)), None)
    if start is None:
        problems.append(f"{where}: missing *{section} for method {method}. "
                        f"Checked climate section headers. Supply *{section} with months 1 to 12.")
        return problems
    columns, rows = _climate_rows(numbered[start + 1:])
    absent = [field for field in ("MTH",) + fields if field not in columns]
    if absent:
        problems.append(f"{where}: *{section} is missing required columns {', '.join(absent)}. "
                        f"Checked its @ MTH header for method {method}. "
                        f"Supply the missing columns in *{section}.")
        return problems
    months = set()
    for number, row in rows:
        month = row["MTH"]
        if not month.isascii() or not month.isdigit() or not 1 <= int(month) <= 12:
            problems.append(f"{where}, *{section}, line {number}: invalid MTH {month!r}. "
                            "Checked the month number. Supply a whole month number from 1 to 12.")
            continue
        months.add(int(month))
        problems.extend(_climate_number_problems(
            row, fields, f"{where}, *{section}, month {int(month)}, line {number}", missing=True))
    for month in range(1, 13):
        if month not in months:
            problems.append(f"{where}: *{section} is missing month {month}. "
                            f"Checked MTH rows for months 1 to 12 for method {method}. "
                            f"Supply month {month} in *{section}.")
    return problems
