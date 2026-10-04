"""Read stock weather and follow the file selection measured in e2e22."""

from datetime import date, timedelta
from pathlib import Path
import re

from . import core


def _header_spans(header):
    """Return header names and their data slices, bounded by label ends."""
    # DSSAT-CSM v4.8.6.0, Weather/IPWTH_alt.for, IPWTH/IpWRec use
    # Utilities/READS.for, PARSE_HEADERS (1015, 1029-1032): end at the label;
    # the next span starts one past its following blank (a value flag column).
    columns, start = {}, 0
    for token in re.finditer(r"\S+", header.split("!", 1)[0]):
        name = token.group().lstrip("@").rstrip(".").upper()
        if name:
            columns[name] = slice(start, token.end())
            start = token.end() + 1
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


def _weather_date(value, previous_year, *, start_date=None):
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
        # DSSAT-CSM v4.8.6.0, Weather/IPWTH_alt.for, IpWRec (1073-1081):
        # only the first record read at simulation start moves back a century
        # when its resolved YRDOYW > YRSIM and the raw code is < 99366.
        if (start_date is not None and int(value) < 99366
                and year * 1000 + doy > start_date.year * 1000 + start_date.timetuple().tm_yday):
            year -= 100
    if not 1 <= year <= 9999:
        return None
    if not 1 <= doy <= date(year, 12, 31).timetuple().tm_yday:
        return None
    return date(year, 1, 1) + timedelta(days=doy - 1)


def _read_weather_file(path):
    """Return line-numbered weather template rows with unresolved date codes."""
    try:
        lines = path.read_text(encoding="latin-1").splitlines()
    except (OSError, ValueError) as error:
        return [], [f"Cannot read stock weather file {path}: {error}. "
                    "Supply a readable stock weather file path."]
    if lines:
        # DOS EOF is accepted only at the end; stock bytes are copied unchanged.
        lines[-1] = lines[-1].removesuffix("\x1a")
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
                    "Supply @DATE for YYDDD, or $WEATHER with @  DATE for YYYYDDD dates."]
    # DSSAT-CSM v4.8.6.0, InputModule/MAKEFILEW.f90, MAKEFILEW (348-398)
    # enables FirstWeatherDate only with $WEATHER; Weather/IPWTH_alt.for,
    # IpWRec (1002-1008) then reads I7, otherwise I5 regardless of the header.
    wide = any("$WEATHER" in line for line in lines[:daily_start - 1])
    if width != (7 if wide else 5):
        return [], [f"Stock weather file {path}: DATE header spans {width} characters "
                    f"but the $WEATHER marker is {'present' if wide else 'absent'}. "
                    "Checked the format marker and DATE width. Supply $WEATHER with "
                    "@  DATE and YYYYDDD dates, or omit $WEATHER and use @DATE with YYDDD dates."]
    rows = []
    for index in range(daily_start, len(lines)):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("!"):
            continue
        if line.startswith(("*", "$", "@")):
            break
        row = dict(metadata, station=path.name[:4].upper(), date=line[:width])
        for label in ("SRAD", "TMAX", "TMIN", "RAIN"):
            row[label.lower()] = _stock_number(line[daily_columns[label]])
        rows.append((index + 1, row))
    return rows, []


def _read_stock_weather(source, start_date=None) -> tuple[list[dict], list[str]]:
    """Read a stock path or list of paths into weather template rows and problems.

    Without start_date, check structure and leave date codes unresolved.
    Otherwise start_date supplies the weather century. Files and rows keep
    their given order, including duplicate days; the walk selects DSSAT's files.
    """
    paths = source if isinstance(source, list) else [source]
    rows, problems, seen = [], [], {}
    previous_year = start_date.year if start_date is not None else None
    initial_record = True
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
        if start_date is None:
            rows.extend(row for _, row in raw)
            continue
        for line, row in raw:
            day = _weather_date(row["date"], previous_year,
                                start_date=start_date if initial_record else None)
            initial_record = False
            if day is None:
                problems.append(f"Stock weather file {path}, line {line}: invalid date "
                                f"{row['date']!r}. Supply a valid YYDDD or YYYYDDD "
                                "calendar date matching the DATE header width.")
                continue
            row["date"] = day
            previous_year = day.year
            rows.append(row)
    return rows, problems


def _weather_directory(executable):
    """Read the installation's WED entry without connecting or writing config."""
    found = (core.detect()["dssat_path"] if executable is None
             else core.find_dssat_path(Path(executable)))
    if found is None:
        return None
    for name in ("DSSATPRO.v48", "DSSATPRO.L48"):
        try:
            lines = (found.parent / name).read_text(encoding="latin-1").splitlines()
        except OSError:
            continue
        for line in lines:
            entry = re.fullmatch(r"WED\s+(?:([A-Za-z]:|-99)\s+)?(.+?)\s*", line)
            if entry:
                drive, directory = entry.groups()
                path = Path((drive if drive not in (None, "-99") else "") + directory)
                # Relative WED paths resolve in the simulation folder, where only
                # supplied weather is copied; there is no installed shadow there.
                return path if path.is_absolute() else None
        return None
    return None


def _walk_weather_files(paths, station, sdate, start, end, *, wed=None, mode="C"):
    """MAKEFILEW's prerequisite, effective-start lookup, then IPWTH continuation.

    e2e22 sections 2-6 prove these branches in mode A. Simulation's mode C
    fails the four-character fallback on 4.8.5.017 (e2e22 mode C caveat), so
    require yearly-named or eight-character literal files in mode C.
    e2e23 proves mode Q reads the fallback throughout both rotation components.
    Installed weather is checked for shadowing, never used as supplied coverage.
    With no known end, stop at the end of the reachable supplied files.
    Return rows, problems and (first date, filename) for the initial $WEATHER file.
    """
    supplied = {path.name.upper(): path for path in paths}
    fallback = f"{station[:4]}.WTH"
    initial = f"{station}.WTH" if len(station) == 8 else f"{station}{sdate[:2]}01.WTH"
    selected, anchor = None, None
    for name in dict.fromkeys([initial, f"{station}.WTH" if len(station) == 8
                              else f"{station}{start.year % 100:02d}01.WTH"]):
        if name in supplied:
            selected = name
        elif wed is not None and (wed / name).is_file() and fallback in supplied:
            return [], [f"Installed weather file {wed / name} shadows supplied {fallback}. "
                        f"Checked supplied names: {', '.join(supplied)} and DSSATPRO WED {wed}. "
                        f"Supply {name} in the simulation folder to take priority."], anchor
        elif fallback in supplied and mode != "C":
            selected = fallback
        else:
            reason = f"; {fallback} is not usable as a fallback in mode C" if fallback in supplied else ""
            return [], [f"DSSAT requests {name}, but no supplied file meets this lookup{reason}. "
                        f"Checked supplied names: {', '.join(supplied)}; installed weather cannot supply coverage. "
                        f"Supply {name}, or correct the FileX WSTA and start dates."], anchor
        if name == initial:
            raw, problems = _read_weather_file(supplied[selected])
            if not problems and raw and len(raw[0][1]["date"]) == 7:
                first = _weather_date(raw[0][1]["date"], start.year)
                if first is not None:
                    anchor = first, selected

    rows, current = [], start
    while selected is not None:
        file_rows, problems = _read_stock_weather(supplied[selected], current)
        if problems:
            return rows, problems, anchor
        if not file_rows:
            return rows, [f"DSSAT requests records in {selected}, but it has no daily rows. "
                          "Checked the selected stock weather file. Supply daily weather in that file."], anchor
        rows.extend(file_rows)
        first, last = min(r["date"] for r in file_rows), max(r["date"] for r in file_rows)
        if end is not None and last >= end:
            return rows, [], anchor
        if (last >= current and first.year == last.year
                and len(selected) == 12 and selected[6:8] == "01"
                and last == date(last.year, 12, 31)):
            current = last + timedelta(days=1)
            selected = f"{station[:4]}{current.year % 100:02d}01.WTH"
            if selected in supplied:
                continue  # All supplied files are copied beside FileX: retain that directory.
            if end is None:
                return rows, [], anchor
            return rows, [f"DSSAT requests {selected} at rollover on {current}. "
                          "Checked supplied weather in the selected simulation folder; "
                          "rollover does not search WED or use the four-character fallback. "
                          f"Supply {selected} beside the FileX."], anchor
        if end is None and last >= current:
            return rows, [], anchor
        missing = max(current, last + timedelta(days=1))
        return rows, [f"DSSAT requests {missing} in {selected}, but its records end on {last}. "
                      "Checked the selected file; DSSAT keeps multi-year and four-character files "
                      "selected instead of borrowing another file. "
                      f"Supply weather through {end} in {selected}."], anchor
    return rows, [], anchor


def _weather_anchor_problems(anchor, dates):
    """Compare fixed FileX dates to MAKEFILEW's initial first-date window."""
    if anchor is None:
        return []
    first, name = anchor
    limit = first.year * 1000 + first.timetuple().tm_yday + 99000
    problems = []
    for field, day in dates:
        if day is None or first <= day and day.year * 1000 + day.timetuple().tm_yday <= limit:
            continue
        before = day < first
        relation = "before" if before else "more than 99 years after"
        advice = "on or before" if before else "within 99 years before"
        code = f"{day.year % 100:02d}{day.timetuple().tm_yday:03d}" if field.startswith("FileX ") else day
        checked = field.removeprefix("FileX ")
        problems.append(f"{field} {code} reads as {day}, {relation} {first}, the first date "
                        f"of stock weather {name}. A $WEATHER file anchors FileX years to "
                        "its first date: DSSAT reads this date in another century or stops. "
                        f"Checked {checked} against {name}. Supply weather starting {advice} "
                        f"{day}, or move the date.")
    return problems


