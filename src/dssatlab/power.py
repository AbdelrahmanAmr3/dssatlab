"""Import a user-downloaded NASA POWER file into the weather template."""

import csv
from datetime import date, timedelta
from pathlib import Path
import re

from .errors import DSSATError
from .weather import OPTIONAL, REQUIRED


def _invalid_csv(source, reason):
    return DSSATError(
        f"{source} is not a NASA POWER daily CSV: {reason}. "
        "Checked the header block and the column row. Download daily data with "
        "ALLSKY_SFC_SW_DWN, T2M_MAX, T2M_MIN and PRECTOTCORR in CSV format, or "
        "fill the weather template yourself.")


def _read_power(source):
    try:
        lines = source.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as error:
        raise DSSATError(
            f"Cannot read NASA POWER file {source}: {error}. "
            "Supply a readable comma-separated UTF-8 daily point CSV.") from error
    try:
        begin = lines.index("-BEGIN HEADER-")
        end = lines.index("-END HEADER-", begin + 1)
    except ValueError as error:
        raise _invalid_csv(source, "missing header block") from error
    header = "\n".join(lines[begin + 1:end])
    if "Daily Data" not in header:
        raise _invalid_csv(source, "missing daily data header (monthly/hourly data is not supported)")
    try:
        reader = csv.reader(lines[end + 1:], strict=True)
        columns = next(reader, [])
        rows = [row for row in reader if row]
    except csv.Error as error:
        raise _invalid_csv(source, f"invalid CSV table: {error}") from error
    if "HR" in columns:
        raise _invalid_csv(source, "hourly layout has an HR column")
    if "YEAR" not in columns:
        raise _invalid_csv(source, "missing YEAR column")
    if "DOY" not in columns and not {"MO", "DY"}.issubset(columns):
        raise _invalid_csv(source, "missing DOY or MO and DY columns (daily dates required)")
    parameters = {"srad": "ALLSKY_SFC_SW_DWN", "tmax": "T2M_MAX", "tmin": "T2M_MIN",
                  "rain": "PRECTOTCORR" if "PRECTOTCORR" in columns else "PRECTOT"}
    for name, column in parameters.items():
        if column not in columns:
            missing = "PRECTOTCORR or PRECTOT" if name == "rain" else column
            raise _invalid_csv(source, f"missing {missing} column")
    if len(set(columns)) != len(columns):
        raise _invalid_csv(source, "repeated column names")
    if not rows:
        raise _invalid_csv(source, "missing daily rows")
    for line, row in enumerate(rows, end + 3):
        if len(row) != len(columns):
            raise _invalid_csv(source, f"row {line} has {len(row)} values for {len(columns)} columns")
    unit = re.search(r"^ALLSKY_SFC_SW_DWN\s+.*\(([^()]*)\)\s*$", header, re.MULTILINE)
    found = unit.group(1) if unit else "not given"
    if found != "MJ/m^2/day":
        raise DSSATError(
            f"NASA POWER file {source}: ALLSKY_SFC_SW_DWN unit is {found!r}; "
            "expected MJ/m^2/day. Checked the parameter units in the header. "
            "Download daily data with the AG community in MJ/m^2/day.")
    fill = re.search(r"^.*missing source data.*:\s*(\S+)\s*$", header, re.MULTILINE)
    try:
        fill_value = float(fill.group(1)) if fill else None
    except ValueError as error:
        raise _invalid_csv(source, "invalid header fill value") from error
    if fill_value is None:
        raise _invalid_csv(source, "missing header fill value")
    return header, parameters, fill_value, [dict(zip(columns, row)) for row in rows]


def _coordinates(header, source, fill_value, overrides):
    number = r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    location = next((line for line in header.splitlines() if line.startswith("Location:")), "")
    patterns = {"latitude": (location, rf"\blatitude\s+{number}"),
                "longitude": (location, rf"\blongitude\s+{number}"),
                "elevation": (header, rf"^Elevation[^\n]*=\s*{number}\s+meters")}
    values = {}
    for name, override in overrides.items():
        text, pattern = patterns[name]
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        value = override if override is not None else match.group(1) if match else None
        if value is None or override is None and float(value) == fill_value:
            raise DSSATError(
                f"NASA POWER file {source}: missing {name}. "
                f"Checked the header and the {name} keyword. Pass {name}=... "
                "to supply the station value.")
        values[name] = value
    return values


def _daily_date(row, source, line):
    try:
        year = int(row["YEAR"])
        doy_day = calendar_day = None
        if "DOY" in row:
            doy = int(row["DOY"])
            doy_day = date(year, 1, 1) + timedelta(days=doy - 1)
            if doy < 1 or doy_day.year != year:
                raise ValueError("DOY is outside the year")
        if "MO" in row and "DY" in row:
            calendar_day = date(year, int(row["MO"]), int(row["DY"]))
        if doy_day is not None and calendar_day is not None and doy_day != calendar_day:
            raise _invalid_csv(source, f"row {line} date columns DOY and MO/DY disagree")
        return (doy_day or calendar_day).isoformat()
    except (ValueError, OverflowError) as error:
        raise _invalid_csv(source, f"row {line} has an impossible date: {error}") from error


def _weather_value(value, fill_value):
    try:
        return -99 if float(value) == fill_value else value
    except ValueError:
        return value  # The weather checks own numeric and range checks.


def import_nasa_power(source: str | Path, path: str | Path, *, station: str,
                      latitude=None, longitude=None, elevation=None) -> Path:
    """Write a NASA POWER daily point CSV as a new weather template CSV.

    Download with the AG community: ALLSKY_SFC_SW_DWN must be MJ/m^2/day.
    YEAR/DOY or YEAR/MO/DY dates and T2M_MAX, T2M_MIN, PRECTOTCORR (or PRECTOT)
    are required. Extra parameters are ignored. Station is four ASCII letters
    or digits; coordinates come from the header unless a keyword replaces them.
    The header fill marker becomes -99 and optional station values are -99.
    Nothing is converted, filled or range-checked; pass the written template
    as weather= to Simulation for the weather checks. An existing path raises
    DSSATError, preserving the user's data.
    """
    source, path = Path(source), Path(path)
    exists_message = f"Weather template path {path} already exists. Choose another path."
    if path.exists():
        raise DSSATError(exists_message)
    if not isinstance(station, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", station):
        raise DSSATError(
            f"NASA POWER station: found {station!r}. Checked the station keyword. "
            "Use exactly four ASCII letters or digits.")
    header, parameters, fill_value, raw = _read_power(source)
    coordinates = _coordinates(header, source, fill_value,
                               dict(latitude=latitude, longitude=longitude, elevation=elevation))
    columns = REQUIRED + tuple(name for name in OPTIONAL if name != "par")
    rows = []
    for line, row in enumerate(raw, 1):
        result = dict.fromkeys(columns, -99)
        result.update(station=station, **coordinates, date=_daily_date(row, source, line))
        result.update({name: _weather_value(row[column], fill_value)
                       for name, column in parameters.items()})
        rows.append(result)
    try:
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    except FileExistsError as error:
        raise DSSATError(exists_message) from error
    return path
