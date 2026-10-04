"""The fixed weather template, its reader and strict weather data checks."""

import csv
from datetime import date, datetime, timedelta
import math
from pathlib import Path
import re

from .errors import DSSATError

SRAD_RANGE = (0, 45)  # Daily solar radiation, MJ/m2 per day.
TEMPERATURE_RANGE = (-60, 60)  # Daily maximum and minimum, degrees C.
RAIN_RANGE = (0, 1000)  # Daily rainfall, mm; includes the nonnegative check.
LATITUDE_RANGE = (-90, 90)  # Latitude, degrees north.
LONGITUDE_RANGE = (-180, 180)  # Longitude, degrees east.
ELEVATION_RANGE = (-500, 9000)  # Station elevation, m.
REQUIRED = ("station", "latitude", "longitude", "elevation", "date",
            "srad", "tmax", "tmin", "rain")
OPTIONAL = ("tav", "amp", "refht", "wndht", "par")


def write_weather_template(path: str | Path) -> None:
    """Write a UTF-8 weather template with seven valid example days.

    Units: srad in MJ/m2 per day; tmax, tmin, tav and amp in degrees C;
    rain in mm; latitude/longitude in degrees; elevation/refht/wndht in m.
    Optional station values default to -99 (not given). Nothing is converted.
    Add optional par in mol/m2 per day (0 to 100), filled on every row, or omit it.
    An existing path raises DSSATError, preserving the user's data.

    Args:
        path: File destination path where the CSV weather template will be created.

    Raises:
        DSSATError: If the destination path already exists.
    """
    path = Path(path)
    exists_message = f"Weather template path {path} already exists. Choose another path."
    if path.exists():
        raise DSSATError(exists_message)
    try:
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(REQUIRED + tuple(name for name in OPTIONAL if name != "par"))
            for day in range(1, 8):
                writer.writerow(("DEMO", 45, -100, 200, f"2021-03-{day:02}",
                                 20, 25, 10, 0, -99, -99, -99, -99))
    except FileExistsError as error:
        raise DSSATError(exists_message) from error


def write_weather_file(rows: list[dict], path: str | Path) -> Path:
    """Write valid parsed weather rows to the caller's chosen weather file.

    Require nonempty rows from _parse_weather with no problems. Station values
    come from the first row, including -99 for unset optional values. The parent
    folder must exist; an existing file is overwritten.
    """
    path = Path(path)
    first = rows[0]
    daily_fields = ("srad", "tmax", "tmin", "rain") + (("par",) if "par" in first else ())
    station_fields = (("latitude", 9, 3), ("longitude", 9, 3),
                      ("elevation", 6, 0), ("tav", 6, 1), ("amp", 6, 1),
                      ("refht", 6, 2), ("wndht", 6, 2))
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(f"*WEATHER DATA : {first['station']} (written by dssatlab)\n\n")
        stream.write("@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n")
        stream.write(f"  {first['station']}")
        for name, width, decimals in station_fields:
            # Adding positive zero after rounding removes negative zero on 3.10.
            value = round(first[name], decimals) + 0.0
            stream.write(f"{value:{width}.{decimals}f}")
        stream.write("\n@DATE  SRAD  TMAX  TMIN  RAIN" + ("   PAR" if "par" in first else "") + "\n")
        for row in rows:
            day = row["date"]
            stream.write(_dssat_date(day))
            for name in daily_fields:
                value = round(row[name], 1) + 0.0
                stream.write(f"{value:6.1f}")
            stream.write("\n")
    return path


def _read_table(source, label="Weather data", *, comments=False):
    """Read a CSV path, plain rows or DataFrame without importing pandas.

    Return (line-numbered raw rows, declared columns or None, problems).
    comments=True skips blank lines and # comments in observed templates.
    """
    if isinstance(source, list):
        return list(enumerate(source, 2)), None, []
    if not isinstance(source, (str, Path)):
        try:
            if hasattr(source, "columns") and callable(getattr(source, "to_dict", None)):
                columns = list(source.columns)
                rows = source.to_dict("records")
                return list(enumerate(rows, 2)), columns, []
        except Exception as error:
            return [], None, [("source", f"Cannot read {label.lower()} DataFrame: "
                               f"{error}. Supply a DataFrame convertible to plain "
                               "rows with to_dict('records').")]
        return [], None, [("source", f"Cannot read {label.lower()}: expected a CSV "
                           "path, plain rows or a DataFrame. Pass a str/Path, "
                           "a list of dicts or a DataFrame with template columns.")]
    try:
        with Path(source).open(encoding="utf-8-sig", newline="") as stream:
            lines = (line for line in stream if line.strip() and not line.startswith("#")) if comments else stream
            reader = csv.reader(lines, strict=True)
            columns = next(reader, [])
            rows, problems = [], []
            while True:
                line = reader.line_num + 1
                values = next(reader, None)
                if values is None:
                    break
                if len(values) != len(columns):
                    problems.append(("row shape", f"{label} row {line} has "
                                     f"{len(values)} values for {len(columns)} columns. "
                                     "Supply one value per column."))
                rows.append((line, dict(zip(columns, values))))
            return rows, columns, problems
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        return [], None, [("source", f"Cannot read {label.lower()} CSV {source!s}: "
                           f"{error}. Supply a readable comma-separated UTF-8 CSV.")]


def _dssat_date(day):
    """DSSAT's YYDDD date code: two-digit year and day of year."""
    return f"{day.year % 100:02d}{day.timetuple().tm_yday:03d}"


def _show_value(value):
    """Keep bad data reportable even beyond Python's integer-string limit."""
    try:
        return repr(value)
    except (ValueError, OverflowError):
        return f"<unrepresentable {type(value).__name__}>"


def _check_columns(columns, where, problems):
    for name in REQUIRED:
        if name not in columns:
            problems.append((f"missing {name}", f"Weather data {where}: missing "
                             f"column {name!r}. Add the required column {name!r}."))
    for name in columns:
        if name not in REQUIRED + OPTIONAL:
            label = _show_value(name)
            problems.append((f"unknown {label}", f"Weather data {where}: unknown "
                             f"column {label}. Use exact lower-case names; valid "
                             f"columns are {', '.join(REQUIRED + OPTIONAL)}."))


def _check_dates(dated_rows, problems):
    seen, previous, out_of_order = {}, None, False
    for line, day in dated_rows:
        if previous is not None and day < previous and not out_of_order:
            problems.append(("order", f"Weather data row {line}, date {day}, is not "
                             "in ascending order. Sort rows by date ascending."))
            out_of_order = True
        if day in seen:
            problems.append(("duplicates", f"Weather data duplicate date {day} in "
                             f"rows {seen[day]} and {line}. Keep one row per day."))
        else:
            seen[day] = line
        previous = day
    days = sorted(seen)
    for earlier, later in zip(days, days[1:]):
        if (later - earlier).days > 1:
            start, end = earlier + timedelta(days=1), later - timedelta(days=1)
            missing = f"date {start}" if start == end else f"dates {start} to {end}"
            problems.append(("gaps", f"Weather data: missing {missing}. "
                             "Supply one row for each missing calendar day."))


def _all_messages(problems):
    return [message for _, message in problems]


def _parse_weather(source) -> tuple[list[dict], list[str]]:
    """Read and check weather data, returning parsed rows and all problem kinds.

    CSV paths, plain rows and DataFrames share the same checks. Dates may be
    YYYY-MM-DD text, date objects or midnight datetimes; they become date objects.
    Numbers become floats, absent optional station values -99; par stays absent.
    Invalid fields are omitted; consumers must require no problems before using
    parsed rows. The source is never mutated, sorted, repaired or written.
    """
    rows, columns, problems = _read_table(source)
    if problems and problems[0][0] == "source":
        return [], _all_messages(problems)
    if columns is not None:
        for column in dict.fromkeys(columns):
            if columns.count(column) > 1:
                problems.append(("columns", f"Weather template column {column!r} "
                                 "is repeated in line 1. Keep one column per name."))
        _check_columns(columns, "line 1", problems)
    if not rows:
        problems.append(("empty", "Weather data has no daily rows. Supply at least "
                         "one row following the weather template."))
    ranges = {"srad": (*SRAD_RANGE, "MJ/m2 per day"),
              "tmax": (*TEMPERATURE_RANGE, "degrees C"),
              "tmin": (*TEMPERATURE_RANGE, "degrees C"),
              "rain": (*RAIN_RANGE, "mm"), "latitude": (*LATITUDE_RANGE, "degrees"),
              "longitude": (*LONGITUDE_RANGE, "degrees"),
              "elevation": (*ELEVATION_RANGE, "m"), "par": (0, 100, "mol/m2 per day")}
    units = {name: bounds[2] for name, bounds in ranges.items()}
    units.update(tav="degrees C", amp="degrees C", refht="m", wndht="m")
    parsed, dated_rows, station_values = [], [], {}
    has_par = "par" in (columns or ()) or any(
        isinstance(row, dict) and "par" in row for _, row in rows)
    empty_par = 0
    for line, row in rows:
        if not isinstance(row, dict):
            problems.append(("row shape", f"Weather data row {line} is not a dict. "
                             "Supply a dict of weather template column values."))
            continue
        if columns is None:  # rows without a header: report each column problem once
            found = []
            _check_columns(row, f"row {line}", found)
            problems.extend(item for item in found if item[0] not in
                            {kind for kind, _ in problems})
        result = {}
        for name in REQUIRED + OPTIONAL:
            if name == "par" and not has_par:
                continue
            if name not in row and name not in OPTIONAL:
                if columns is not None and name in columns:
                    day = f" ({result['date']})" if "date" in result else ""
                    problems.append((f"missing {name}", f"Weather data row {line}{day}: "
                                     f"missing value for {name!r}. Supply a value."))
                continue
            value = row.get(name)
            where = f"Weather data row {line}, column {name!r}"
            if name in REQUIRED and "date" in result and (value is None or
                    isinstance(value, str) and not value.strip()):
                where += f" ({result['date']})"
            if name == "station":
                if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", value):
                    problems.append(("station", f"{where}: found {_show_value(value)}. "
                                     "Use exactly four ASCII letters or digits."))
                    continue
                result[name] = value
            elif name == "date":
                try:
                    if isinstance(value, datetime) and any((
                            value.hour, value.minute, value.second, value.microsecond,
                            getattr(value, "nanosecond", 0))):
                        problems.append(("date", f"{where}: found {_show_value(value)}; "
                                         "date has a time part; use a whole date."))
                        continue
                    if isinstance(value, date):
                        result[name] = date(value.year, value.month, value.day)
                    elif isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                        result[name] = date.fromisoformat(value)
                    else:
                        raise ValueError
                    dated_rows.append((line, result[name]))
                except (TypeError, ValueError):
                    problems.append(("date", f"{where}: found {_show_value(value)}. "
                                     "Use a valid calendar date: YYYY-MM-DD text, "
                                     "a date object or a midnight datetime."))
            else:
                if name in OPTIONAL and (value is None or
                                         isinstance(value, str) and not value.strip()):
                    if name == "par":
                        empty_par += 1
                        continue
                    value = -99
                try:
                    number = float(value)
                    if not math.isfinite(number):
                        value = number  # Report CSV and numeric NaN/inf identically.
                        raise ValueError
                except (TypeError, ValueError, OverflowError):
                    problems.append((f"numeric {name}", f"{where}: found {_show_value(value)}. "
                                     f"Supply a non-empty finite number in {units[name]}."))
                    continue
                result[name] = number
                if name in ranges:
                    low, high, unit = ranges[name]
                    if not low <= number <= high:
                        if number == -99 and name in REQUIRED and "date" in result:
                            where += f" ({result['date']})"
                        problems.append((f"range {name}", f"{where}: found {_show_value(value)}; "
                                         f"allowed range is {low} to {high} {unit}. "
                                         "Correct the value using DSSAT's units."))
        if "tmax" in result and "tmin" in result and result["tmax"] < result["tmin"]:
            problems.append(("temperature order", f"Weather data row {line}: "
                             f"tmax {result['tmax']} is below tmin {result['tmin']} "
                             "degrees C. Correct tmax or tmin so tmax >= tmin."))
        for name in ("station", "latitude", "longitude", "elevation"):
            if name not in result:
                continue
            if name not in station_values:
                station_values[name] = (line, result[name])
            first_line, first_value = station_values[name]
            if result[name] != first_value:
                problems.append((f"identical {name}", f"Weather data row {line}, "
                                 f"column {name!r}: found {result[name]!r}, but row "
                                 f"{first_line} has {first_value!r}. Use identical "
                                 f"{name} values on every row."))
        parsed.append(result)
    if empty_par:
        problems.append(("empty par", f"Weather column 'par' is empty on {empty_par} rows. "
                         "Supply par on every row or drop the column."))
    _check_dates(dated_rows, problems)
    return parsed, _all_messages(problems)
