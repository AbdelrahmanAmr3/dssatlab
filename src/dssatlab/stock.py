"""Narrow reads of stock DSSAT files, without rewriting or repairing them."""

from datetime import date, timedelta
from pathlib import Path
import re
import shutil

from .controls import _controls_start_date, _selected_controls
from .experiment import _overrides_section
from .filex import _filex_date, _weather_filename
from .irrigation import _effective_management
from .operations import _harvest_end
from .rotation_data import _level_date
from .sequence import _sequence_end, _sequence_shift, _sequence_stop
from .soil import _parse_soil, write_soil_file
from .weather import _parse_weather, write_weather_file


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
    # WSTA4 + '.WTH'. WEATHR calls IPWTH at RATE; when YRDOY passes
    # LastWeatherDay, IPWTH rewrites WFile(5:6) with CurrentWeatherYear
    # for a single-year file, even within one season crossing New Year.
    # https://github.com/DSSAT/dssat-csm-os/blob/v4.8.6.0/Weather/IPWTH_alt.for
    # https://github.com/DSSAT/dssat-csm-os/blob/v4.8.6.0/Weather/weathr.for
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
                    "Supply @DATE for YYDDD or @  DATE for YYYYDDD dates."]
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


def _read_stock_weather(source, station, start_date, end_date=None, *,
                        check_names=True) -> tuple[list[dict], list[str]]:
    """Read a stock path or list of paths into weather template rows and problems.

    station is the checked FileX WSTA (four or eight characters). start_date
    supplies the weather century; end_date bounds the simulated filename years
    and defaults to start_date. Both are calendar dates supplied by the caller.
    Files and rows keep their given order, including duplicate days. Numbers
    remain uncorrected; pass the returned rows to _parse_weather for the usual
    range, station, ordering, duplicate and gap checks. No files are written.
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
        if check_names and name not in names:
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


def _stock_weather_paths(source):
    """Return stock paths, or None for a weather-template source."""
    paths = source if isinstance(source, list) else [source]
    if paths and all(isinstance(path, (str, Path)) and Path(path).suffix.upper() == ".WTH"
                     for path in paths):
        return [Path(path) for path in paths]
    return None


def _weather_source_problems(source, *, template=False):
    """Reject mixed lists and stock sources for a FileX template before reading."""
    if isinstance(source, list):
        paths = [isinstance(item, (str, Path)) for item in source]
        if any(paths) and not all(paths):
            return ["Weather data mixes file paths and data rows. Supply only stock "
                    "weather file paths, or only weather data rows or a DataFrame."]
    sources = source.values() if isinstance(source, dict) else [source]
    if template and any(_stock_weather_paths(value) for value in sources):
        return ["A stock weather file needs a copied FileX. "
                "Supply weather data rows for a FileX template."]
    return []


def _parse_template_weather(source):
    problems = _weather_source_problems(source, template=True)
    return ([], problems) if problems else _parse_weather(source)


def _simulation_weather(sim, values, experiment_data, components):
    """Read either weather source, sharing checks and the sequence end rule."""
    problems = _weather_source_problems(sim.weather)
    if problems:
        return [], problems
    paths = _stock_weather_paths(sim.weather)
    if paths is None:
        return _parse_weather(sim.weather)
    start = (_controls_start_date(experiment_data, sim.treatment)
             or _filex_date(values.get("SDATE")))
    if start is None and re.fullmatch(r"[0-9]{5}", values.get("SDATE", "")):
        return [], [f"FileX {sim.filex}: SDATE {values['SDATE']!r} is invalid. "
                    "Supply five digits: two-digit year followed by three-digit day of year."]
    if start is None or "WSTA" not in values:
        # The FileX checks explain what is missing; do not guess a weather century.
        return [], []
    years = _selected_controls(experiment_data, sim.treatment).get("years", values.get("NYERS", 1))
    try:
        years = max(1, int(years))
    except (TypeError, ValueError, OverflowError):
        years = 1  # Ordinary controls checks report invalid years.
    end = _sequence_stop(start, years) or date.max
    harvest = None
    if len(components) == 1:
        entries = experiment_data.get("treatments", {}) if isinstance(experiment_data, dict) else {}
        entry = next((value for key, value in entries.items()
                      if str(key).isascii() and str(key).isdigit() and int(key) == int(sim.treatment)
                      and isinstance(value, dict)), {}) if isinstance(entries, dict) else {}
        text = Path(sim.filex).read_text(encoding="latin-1")
        code = _effective_management(entry, text, int(sim.treatment), "harvest_management", "HARVS")
        if code == "R":
            harvest = _harvest_end(entry, _level_date(
                text, components[0], "MH", "HARVEST DETAILS", "H", "HDATE"), code)
            if harvest is not None:
                try:
                    harvest = _sequence_shift(harvest, harvest.year + years - 1)
                except (ValueError, OverflowError):
                    harvest = None  # The season checks report years outside the calendar.
                if harvest is not None:
                    end = harvest
    if len(components) > 1:
        stop = _sequence_stop(start, years)
        if stop is not None:
            end = _sequence_end(experiment_data, sim.treatment, start, stop, sim.filex, None)
    station = values["WSTA"]
    if _overrides_section(experiment_data, sim.treatment) and station[:4] != paths[0].name[:4].upper():
        station = paths[0].name[:4].upper()  # Match the copied field's new station.
    # A station mismatch is reported by Simulation;
    # avoid a second name-lookup problem for the same mismatch.
    same_station = all(path.name[:4].upper() == station[:4] for path in paths)
    rows, problems = _read_stock_weather(paths, station, start, end, check_names=same_station)
    if not rows and problems:
        return [], problems  # Do not add "no daily rows" for unreadable stock files.
    rows, checks = _parse_weather(rows)
    if harvest is not None and rows and harvest > max(row["date"] for row in rows if "date" in row):
        label = "Controls years" if "years" in _selected_controls(experiment_data, sim.treatment) else "FileX NYERS"
        problems.append(f"{label} {years}: the fixed harvest is on {harvest}, "
                        f"after the weather data ends ({max(row['date'] for row in rows)}). "
                        f"Supply weather through {harvest}, or fewer years.")
    return rows, problems + checks


def _write_simulation_weather(source, rows, folder, values):
    """Copy stock bytes under uppercase names, or write template weather."""
    paths = _stock_weather_paths(source)
    if paths is not None:
        for path in paths:
            shutil.copy2(path, folder / path.name.upper())
    else:
        write_weather_file(rows, folder / _weather_filename(values["WSTA"], values["SDATE"]))


def _stock_soil_path(source):
    """Return a stock path, or None for a soil-template source."""
    if isinstance(source, (str, Path)) and Path(source).suffix.upper() == ".SOL":
        return Path(source)
    return None


def _soil_source_problems(source, *, template=False):
    """Reject stock soil for a FileX template before reading any field source."""
    sources = source.values() if isinstance(source, dict) else [source]
    if template and any(_stock_soil_path(value) is not None for value in sources):
        return ["A stock soil file needs a copied FileX. "
                "Supply soil data rows for a FileX template."]
    return []


def _read_stock_soil(path, soil_id):
    """Check only profile IDs and the filename DSSAT opens, without layer parsing."""
    try:
        lines = path.read_text(encoding="latin-1").splitlines()
    except (OSError, ValueError) as error:
        return [f"Cannot read stock soil file {path}: {error}. "
                "Supply a readable stock soil file path."]
    if lines:
        lines[-1] = lines[-1].removesuffix("\x1a")
    ids = []
    for line in lines:
        if line.startswith("*"):
            tokens = line[1:].split()
            if tokens and tokens[0].upper() not in ("SOILS", "SOILS:") and tokens[0] not in ids:
                ids.append(tokens[0])
    if not soil_id or soil_id == "-99":
        return ["FileX has no readable ID_SOIL in the selected treatment's FIELDS row. "
                f"Supply ID_SOIL matching a profile in stock soil file {path}. "
                f"IDs found: {', '.join(ids) or 'none'}."]
    problems = []
    if soil_id not in ids:
        problems.append(f"Stock soil file {path}: FileX ID_SOIL {soil_id!r} is not in the file. "
                        f"IDs found: {', '.join(ids) or 'none'}. "
                        "Supply a file containing that ID or correct the FileX ID_SOIL.")
    # DSSAT-CSM, InputModule/ipexp.for, IPEXP (soil profile input selection):
    # FILES_a = 'SOIL.SOL'; FILES_b = SLNO(1:2)//'.SOL '. INQUIRE checks
    # these exact names in the current directory before the data directory.
    # https://github.com/DSSAT/dssat-csm-os/blob/develop/InputModule/ipexp.for
    names = (f"{soil_id[:2]}.SOL", "SOIL.SOL")
    if path.name not in names:
        problems.append(f"Stock soil file {path}: DSSAT does not look up this name "
                        f"for ID_SOIL {soil_id!r}. Expected {', '.join(names)}. "
                        "Rename the file or correct the FileX ID_SOIL; "
                        "filenames are case-sensitive on Linux.")
    return problems


def _simulation_soil(sim, values, edit_identity):
    """Read either soil source; stock profiles keep the copied FileX's ID_SOIL."""
    if sim.soil is None:
        return [], [], None
    path = _stock_soil_path(sim.soil)
    soil_id = values.get("ID_SOIL")
    if path is not None:
        return [], _read_stock_soil(path, soil_id), None
    rows, problems = _parse_soil(sim.soil)
    if isinstance(sim.soil, dict):
        problems.append("Soil data per field needs a FileX template. "
                        "Supply one soil source for a FileX.")
    template_id = rows[0]["soil_id"] if not problems else None
    soil_ids = {row["soil_id"] for row in rows if "soil_id" in row}
    if not edit_identity and (not soil_id or soil_id == "-99"):
        problems.append("FileX has no readable ID_SOIL in the selected "
                        "treatment's FIELDS row. Supply ID_SOIL "
                        "equal to the soil template's soil_id.")
    elif not edit_identity and len(soil_ids) == 1:
        template_id = soil_ids.pop()
        if soil_id != template_id:
            problems.append(f"FileX ID_SOIL {soil_id!r} for treatment "
                            f"{sim.treatment} differs from the soil template's "
                            f"soil_id {template_id!r}. Make the IDs exactly equal; "
                            "filenames are case-sensitive on Linux.")
    return rows, problems, template_id


def _write_simulation_soil(source, rows, folder):
    """Copy stock bytes under their own name, or write template soil."""
    path = _stock_soil_path(source)
    if path is not None:
        shutil.copy2(path, folder / path.name)
    elif source is not None:
        write_soil_file(rows, folder / "SOIL.SOL")
