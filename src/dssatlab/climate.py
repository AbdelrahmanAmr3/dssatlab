"""Select weather inputs and narrowly check copied DSSAT climate files."""

from math import isfinite
from pathlib import Path
import re
import shutil

from .controls import _selected_controls
from .filex import _section_row
from .experiment import _overrides_section


def _split_weather_inputs(source):
    """Separate one CLI from WTH paths; leave weather-template data intact."""
    paths = source if isinstance(source, list) else [source]
    climate = [Path(path) for path in paths if isinstance(path, (str, Path))
               and Path(path).suffix.upper() == ".CLI"]
    if not climate:
        return source, [], []
    problems = []
    if len(climate) > 1:
        problems.append("Weather input contains more than one climate file. "
                        "Checked the supplied .CLI paths. Supply only one climate file.")
    if not all(isinstance(path, (str, Path)) and Path(path).suffix.upper() in (".CLI", ".WTH")
               for path in paths):
        problems.append("Weather input mixes a climate file with other weather data. "
                        "Checked weather input types. Supply a .CLI alone or with .WTH paths.")
    weather = [Path(path) for path in paths if isinstance(path, (str, Path))
               and Path(path).suffix.upper() == ".WTH"]
    return weather or None, climate, problems


def _template_climate_problems(source):
    """Reject CLI inputs, including per-field sources, for a FileX template."""
    sources = source.values() if isinstance(source, dict) else [source]
    if any(_split_weather_inputs(value)[1] for value in sources):
        return ["A climate file cannot supply weather for a FileX template. "
                "Checked the template's weather inputs. Supply weather data rows for every field."]
    return []


def _weather_requirements(sim, experiment_data, components):
    """Read each run component's SM and field, applying a weather-source edit.

    Missing METHODS rows, blank WTHER and -99 retain the existing measured-weather
    behavior. Unreadable FileX levels are reported by the ordinary FileX checks.
    """
    if not components:
        return []
    try:
        text = Path(sim.filex).read_text(encoding="latin-1")
    except (OSError, TypeError, ValueError):
        return []
    override = _selected_controls(experiment_data, sim.treatment).get("weather_source")
    requirements = []
    for row in components:
        if not row["SM"].isdigit():
            continue
        level = int(row["SM"])
        method = "M"
        try:
            method = _section_row(text, "SIMULATION CONTROLS", "N", level, ("WTHER",))["WTHER"]
        except ValueError:
            pass
        if override in ("M", "W", "S"):
            method = override
        method = "M" if method in ("", "-99") else method
        try:
            station = _section_row(text, "FIELDS", "L", int(row["FL"]), ("WSTA",))["WSTA"]
        except (ValueError, TypeError):
            station = ""
        requirement = (level, method, station)
        if requirement not in requirements:
            requirements.append(requirement)
    return requirements


def _measured_weather_source(sim, experiment_data, components):
    """Return daily input only if a run component uses M; never parse a CLI as CSV."""
    source, _, _ = _split_weather_inputs(sim.weather)
    requirements = _weather_requirements(sim, experiment_data, components)
    return source if not requirements or any(method == "M" for _, method, _ in requirements) else None


def _check_weather_requirements(sim, experiment_data, components, rows=()):
    """Check WTHER, required filenames and unused inputs before any run writes."""
    source, climate, split_problems = _split_weather_inputs(sim.weather)
    if split_problems:
        return []  # The weather-source checks already report malformed input lists.
    requirements = _weather_requirements(sim, experiment_data, components)
    if rows and _overrides_section(experiment_data, sim.treatment):
        changed_requirements = set()
        for component in components:
            if component["FL"] == components[0]["FL"]:
                changed_requirements.update(_weather_requirements(sim, experiment_data, [component]))
        requirements = [(level, method, rows[0]["station"] if (level, method, station)
                         in changed_requirements else station) for level, method, station in requirements]
    problems, checked_methods = [], set()
    for level, method, station in requirements:
        where = f"FileX WTHER '{method}' in controls level {level} (treatment {int(sim.treatment)})"
        if method not in ("M", "W", "S"):
            problems.append(f"{where}: unsupported weather source. Checked the run treatment's "
                            "SM level after experiment edits. Set WTHER to one of M, W, S.")
        elif method == "M":
            if source is None:
                problems.append(f"{where}: needs weather data. Checked the supplied weather "
                                "inputs. Supply weather data or .WTH paths for WTHER M.")
        elif station and len(station) in (4, 8):
            expected = station[:4].upper() + ".CLI"
            if not climate:
                problems.append(f"{where}: missing climate file {expected}. Checked WSTA "
                                f"{station!r}. Supply {expected} from DSSAT's Weather/Climate folder.")
            elif climate[0].name.upper() != expected:
                problems.append(f"{where}: climate file {climate[0].name} does not match "
                                f"{expected}. Checked WSTA {station!r} and the copied filename. "
                                f"Supply the matching {expected} from DSSAT's Weather/Climate folder.")
            else:
                if method not in checked_methods:
                    problems.extend(_read_climate_file(climate[0], method))
                    checked_methods.add(method)
    if climate and requirements and not any(method in ("W", "S") for _, method, _ in requirements):
        problems.append(f"Supplied climate file {climate[0].name} is unused. Checked all run "
                        "treatments' weather sources. Remove the climate file or use WTHER W or S.")
    if source is not None and any(method in ("W", "S") for _, method, _ in requirements) and not any(
            method == "M" for _, method, _ in requirements):
        problems.append("Supplied weather data is unused. Checked all run treatments' weather "
                        "sources. Remove the weather data or use WTHER M.")
    if _mixed_weather(sim, experiment_data, components):
        days = {row["date"] for row in rows if "date" in row}
        for level, start, end, _ in _measured_periods(sim, experiment_data, components):
            for label, day in (("start", start), ("end", end)):
                if day is not None and days and day not in days:
                    problems.append(f"Measured component in controls level {level}: {label} date "
                                    f"{day} is not covered by weather data. Checked only WTHER M "
                                    f"periods. Supply weather for {day}.")
    return problems


def _mixed_weather(sim, experiment_data, components):
    """Whether a sequence reads both measured and generated weather."""
    methods = {method for _, method, _ in _weather_requirements(sim, experiment_data, components)}
    return "M" in methods and bool(methods & {"W", "S"})


def _coverage_weather_rows(sim, experiment_data, components, rows):
    """Use ordinary coverage for M-only runs; mixed periods are checked separately."""
    return [] if _mixed_weather(sim, experiment_data, components) else rows


def _measured_periods(sim, experiment_data, components):
    """Locate scheduled M periods; stop when a run-time harvest makes timing unknown."""
    from datetime import timedelta
    from .filex import _filex_date, _section_rows
    from .operations import _component_management
    from .rotation_data import _calendar_date, _known_dates
    from .sequence import _sequence_shift, _sequence_stop, _simulation_start

    if any(not row["R"].isdigit() or not row["SM"].isdigit() for row in components):
        return []  # Ordinary sequence checks report unreadable references.
    text = Path(sim.filex).read_text(encoding="latin-1")
    controls = _selected_controls(experiment_data, sim.treatment)
    entries = experiment_data.get("treatments", {}) if isinstance(experiment_data, dict) else {}
    entries = entries if isinstance(entries, dict) else {}
    entry = next((v for k, v in entries.items() if str(k).isascii() and str(k).isdigit()
                  and int(k) == int(sim.treatment) and isinstance(v, dict)), {})
    edits = entry.get("rotation", {})
    edits = {int(k): v for k, v in edits.items() if str(k).isascii() and str(k).isdigit() and isinstance(v, dict)
             } if isinstance(edits, dict) else {}
    known, _ = _known_dates(components, None, text, edits, "")
    current = _simulation_start(text, sim.treatment, experiment_data)
    try:
        general = _section_row(text, "SIMULATION CONTROLS", "N", int(components[0]["SM"]), ("NYERS",))
        stop = _sequence_stop(current, int(controls.get("years", general["NYERS"]))) if current else None
    except (ValueError, TypeError, OverflowError):
        stop = None
    if stop is None:
        return []
    methods = {level: method for level, method, _ in _weather_requirements(sim, experiment_data, components)}
    periods, run = [], 0
    while current <= stop:
        for row, (_, planting, end, crop) in zip(components, known):
            actual_end = None
            code = _component_management(text, row, "HARVS", "R" if end else "M")
            if (end is not None and code in ("R", "W", "X", "Y", "Z") and
                    (crop == "FA" or planting is not None and _component_management(text, row, "PLANT") == "R")):
                override = edits.get(int(row["R"]), {}).get("harvest")
                if isinstance(override, list):
                    first = next((_calendar_date(e.get("date")) for e in override
                                  if isinstance(e, dict) and _calendar_date(e.get("date"))), None)
                else:
                    first = next((_filex_date(h["HDATE"]) for h in _section_rows(
                        text, "HARVEST DETAILS", "H", int(row["MH"]), ("HDATE",))), end)
                if first is not None:
                    shift = 0
                    if crop != "FA" or run:
                        anchor = first if crop == "FA" else planting
                        moved = _sequence_shift(anchor, current.year)
                        if moved < current:
                            moved = _sequence_shift(anchor, current.year + 1)
                        shift = moved.year - anchor.year
                    actual_end = _sequence_shift(end, end.year + shift) if first < current else end
            level = int(row["SM"])
            if methods.get(level) == "M":
                periods.append((level, current, actual_end, row))
            if actual_end is None or actual_end < current or actual_end >= stop:
                return periods
            current = actual_end + timedelta(days=1)
            run += 1
    return periods


def _mixed_stock_weather(sim, values, experiment_data, components, paths):
    """Walk and check only known measured periods of a mixed sequence."""
    if not _mixed_weather(sim, experiment_data, components):
        return None
    from .weather import _parse_weather
    from .filex import _filex_date
    from .weather_files import (_read_stock_weather, _walk_weather_files, _weather_directory,
                                _weather_anchor_problems)

    rows, problems = {}, []
    _, problems = _read_stock_weather(paths)
    if problems:
        return [], problems
    periods = _measured_periods(sim, experiment_data, components)
    if not periods:
        daily, problems = _read_stock_weather(paths, _filex_date(values.get("SDATE")))
        if daily:
            daily, checks = _parse_weather(daily)
            problems.extend(checks)
        return daily, problems
    for _, start, end, component in periods:
        station = _section_row(Path(sim.filex).read_text(encoding="latin-1"), "FIELDS", "L",
                               int(component["FL"]), ("WSTA",))["WSTA"]
        if _overrides_section(experiment_data, sim.treatment) and component["FL"] == components[0]["FL"]:
            if station[:4] != paths[0].name[:4].upper():
                station = paths[0].name[:4].upper()
        daily, checks, anchor = _walk_weather_files(paths, station, values.get("SDATE", ""), start, end,
                                               wed=_weather_directory(sim.executable), mode="Q")
        dates = [("Measured component start", start)]
        if end is not None:
            dates.append(("Measured component end", end))
        checks.extend(_weather_anchor_problems(anchor, dates))
        if daily:
            daily, parsed = _parse_weather(daily)
            checks.extend(parsed)
        problems.extend(checks)
        rows.update((row["date"], row) for row in daily if "date" in row)
    return list(rows.values()), problems


def _copy_climate_file(source, folder):
    """Copy the checked CLI unchanged under its uppercase filename."""
    for path in _split_weather_inputs(source)[1]:
        shutil.copy2(path, folder / path.name.upper())


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
