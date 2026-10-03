"""Narrow reads of stock DSSAT files, without rewriting or repairing them."""

from datetime import date, timedelta
from pathlib import Path
import re


def _header_spans(header):
    """Return header names and their data slices, bounded by label ends."""
    # DSSAT-CSM v4.8.6.0, Weather/IPWTH_alt.for, IPWTH/IpWRec use
    # Utilities/READS.for, PARSE_HEADERS: each span ends at its header label.
    columns, start = {}, 0
    for token in re.finditer(r"\S+", header.split("!", 1)[0]):
        name = token.group().lstrip("@").rstrip(".").upper()
        if name:
            columns[name] = slice(start, token.end())
            start = token.end()
    return columns


def _stock_number(value):
    """Drop one trailing letter flag; leave bad values for weather checks."""
    value = value.strip()
    flagged = re.fullmatch(r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))[A-Za-z]", value)
    if flagged:
        value = flagged[1]
    try:
        return float(value)
    except ValueError:
        return value


def _weather_date(value, previous_year):
    """Resolve a stock date with the weather century, or return None."""
    if not re.fullmatch(r"[0-9]{5}|[0-9]{7}", value):
        return None
    year, doy = int(value[:-3]), int(value[-3:])
    if len(value) == 5:
        # DSSAT-CSM v4.8.6.0, Utilities/DATES.for, Y2K_DOYW:
        # YEAR = CENTURY * 100 + YY; the supplied century comes from
        # simulation dates (IpWRec in Weather/IPWTH_alt.for). After a year
        # ending in 99, a smaller year advances the century. No FileX cutoff.
        year += previous_year // 100 * 100
        if year < previous_year and previous_year % 100 == 99:
            year += 100
    if not 1 <= year <= 9999:
        return None
    if not 1 <= doy <= date(year, 12, 31).timetuple().tm_yday:
        return None
    return date(year, 1, 1) + timedelta(days=doy - 1)


def _weather_names(station, start_date, end_date):
    """Names DSSAT looks up for measured weather during the given years."""
    # DSSAT-CSM v4.8.6.0, InputModule/MAKEFILEW.f90, MAKEFILEW:
    # WSTA4 + YY + '01.WTH', or an explicit WSTA8 + '.WTH'; fallback
    # WSTA4 + '.WTH'. Weather/IPWTH_alt.for, IPWTH changes positions 5:6
    # for yearly files at SEASINIT and when CurrentWeatherYear advances.
    station = station.upper()
    names = [f"{station}.WTH"] if len(station) == 8 else []
    if len(station) == 4 or station[6:8] == "01":
        names.extend(f"{station[:4]}{year % 100:02d}01.WTH"
                     for year in range(start_date.year, end_date.year + 1))
    return list(dict.fromkeys([*names, f"{station[:4]}.WTH"]))


def _read_weather_file(path):
    """Return line-numbered weather template rows with unresolved date codes."""
    try:
        lines = path.read_text(encoding="latin-1").splitlines()
    except (OSError, ValueError) as error:
        return [], [f"Cannot read stock weather file {path}: {error}. "
                    "Supply a readable stock weather file path."]
    station_columns, daily_columns, metadata = {}, {}, {}
    daily_start = None
    for index, line in enumerate(lines):
        if not line.startswith("@"):
            continue
        columns = _header_spans(line)
        if "INSI" in columns:
            station_columns = columns
            if index + 1 < len(lines):
                metadata = {name: _stock_number(lines[index + 1][columns[label]])
                            for label, name in (("LAT", "latitude"), ("LONG", "longitude"),
                                                ("ELEV", "elevation")) if label in columns}
        elif "DATE" in columns:
            daily_columns, daily_start = columns, index + 1
            break
    problems = []
    for label, columns in (("LAT", station_columns), ("LONG", station_columns),
                           ("ELEV", station_columns), ("DATE", daily_columns),
                           ("SRAD", daily_columns), ("TMAX", daily_columns),
                           ("TMIN", daily_columns), ("RAIN", daily_columns)):
        if label not in columns:
            problems.append(f"Stock weather file {path}: missing required column {label}. "
                            f"Supply a stock weather file with column {label}.")
    if problems:
        return [], problems
    width = daily_columns["DATE"].stop
    if width not in (5, 7):
        return [], [f"Stock weather file {path}: DATE header spans {width} characters. "
                    "Supply @DATE for YYDDD or @  DATE for YYYYDDD dates."]
    rows = []
    for index in range(daily_start, len(lines)):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("!"):
            continue
        if line.startswith(("*", "$", "@")):
            break
        row = dict(metadata, station=path.name[:4].upper(), date=line[:width])
        for label in ("SRAD", "TMAX", "TMIN", "RAIN", "PAR"):
            if label in daily_columns:
                row[label.lower()] = _stock_number(line[daily_columns[label]])
        rows.append((index + 1, row))
    return rows, []


def _read_stock_weather(source, station, start_date, end_date=None) -> tuple[list[dict], list[str]]:
    """Read a stock path or list of paths into weather template rows and problems.

    station is the checked FileX WSTA (four or eight characters). start_date
    supplies the weather century; end_date bounds the simulated filename years
    and defaults to start_date. Both are calendar dates supplied by the caller.
    Files and rows keep their given order, including duplicate days. Numbers
    remain uncorrected; pass the returned rows to _parse_weather for the usual
    range, station, PAR, ordering, duplicate and gap checks. No files are written.
    """
    paths = source if isinstance(source, list) else [source]
    names = _weather_names(station, start_date, end_date or start_date)
    rows, problems, seen = [], [], {}
    previous_year = start_date.year
    for source_path in paths:
        path = Path(source_path)
        name = path.name.upper()
        if name in seen:
            problems.append(f"Stock weather files {seen[name]} and {path} have the same "
                            f"file name {name} after upper-casing. Supply only one file "
                            "with each name for the simulation folder.")
        else:
            seen[name] = path
        raw, read_problems = _read_weather_file(path)
        problems.extend(read_problems)
        if read_problems:
            continue
        if name not in names:
            problems.append(f"Stock weather file {path}: DSSAT does not look up this name "
                            f"for WSTA {station!r} in the simulated years. Expected "
                            f"{', '.join(names)}. Rename the file or correct the FileX WSTA.")
        for line, row in raw:
            day = _weather_date(row["date"], previous_year)
            if day is None:
                problems.append(f"Stock weather file {path}, line {line}: invalid date "
                                f"{row['date']!r}. Supply a valid YYDDD or YYYYDDD "
                                "calendar date matching the DATE header width.")
                continue
            row["date"] = day
            previous_year = day.year
            rows.append(row)
    return rows, problems
