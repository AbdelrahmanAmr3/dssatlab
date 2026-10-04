"""Narrow reads of stock DSSAT files, without rewriting or repairing them."""

from datetime import date
from pathlib import Path
import re
import shutil

from .controls import _controls_start_date, _selected_controls
from .climate import (_copy_climate_file, _measured_weather_source, _split_weather_inputs,
                      _template_climate_problems)
from .experiment import _overrides_section
from .filex import _filex_date, _read_filex, _section_rows, _weather_filename
from .irrigation import _effective_management
from .operations import _component_management, _harvest_end
from .rotation_data import _calendar_date, _level_date
from .sequence import _sequence_end, _sequence_shift, _sequence_stop
from .soil import _parse_soil, write_soil_file
from .weather import _parse_weather, write_weather_file
from .weather_files import (_read_stock_weather, _walk_weather_files, _weather_directory,
                            _weather_anchor_problems)


def _stock_weather_paths(source):
    """Return stock paths, or None for a weather-template source."""
    source, _, _ = _split_weather_inputs(source)
    paths = source if isinstance(source, list) else [source]
    if paths and all(isinstance(path, (str, Path)) and Path(path).suffix.upper() == ".WTH"
                     for path in paths):
        return [Path(path) for path in paths]
    return None


def _weather_source_problems(source, *, template=False):
    """Reject mixed lists and stock sources for a FileX template before reading."""
    problems = _template_climate_problems(source) if template else _split_weather_inputs(source)[2]
    if problems:
        return problems
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
    """Read daily weather only for M, sharing checks and the sequence end rule."""
    problems = _weather_source_problems(sim.weather)
    if problems:
        return [], problems
    source = _measured_weather_source(sim, experiment_data, components)
    if source is None:
        return ([], []) if components or _split_weather_inputs(sim.weather)[1] else _parse_weather(source)
    paths = _stock_weather_paths(source)
    if paths is None:
        return _parse_weather(source)
    if "WSTA" not in values:
        checked, checks = _read_filex(sim.filex, sim.treatment)
        if "WSTA" not in checked and checks:
            return [], []  # The FileX checks explain why the station is unavailable.
        return [], [f"Stock weather {sim.weather}: cannot check weather dates without WSTA. "
                    f"Checked the FileX field for treatment {sim.treatment}. "
                    "Supply a FileX with a four- or eight-character WSTA."]
    entries = experiment_data.get("treatments", {}) if isinstance(experiment_data, dict) else {}
    entry = next((value for key, value in entries.items()
                  if str(key).isascii() and str(key).isdigit() and int(key) == int(sim.treatment)
                  and isinstance(value, dict)), {}) if isinstance(entries, dict) else {}
    text = Path(sim.filex).read_text(encoding="latin-1")
    # DSSAT-CSM v4.8.6.0, InputModule/ipexp.for, IPEXP (655-663):
    # START P uses YRPLT, S uses YRSIM; E uses IEMRG, which we do not resolve.
    start = ((_controls_start_date(experiment_data, sim.treatment)
              or _filex_date(values.get("SDATE"))) if values.get("START") == "S" else None)
    if start is None and values.get("START") == "P" and components:
        planting_entry = entry
        if len(components) > 1:
            edits = entry.get("rotation", {})
            planting_entry = next((value for key, value in edits.items()
                                   if str(key).isascii() and str(key).isdigit()
                                   and components[0]["R"].isdigit()
                                   and int(key) == int(components[0]["R"]) and isinstance(value, dict)),
                                  {}) if isinstance(edits, dict) else {}
        planting = planting_entry.get("planting")
        start = (_calendar_date(planting.get("date")) if isinstance(planting, dict) else
                 _level_date(text, components[0], "MP", "PLANTING DETAILS", "P", "PDATE"))
    if (_filex_date(values.get("SDATE")) is None
            and re.fullmatch(r"[0-9]{5}", values.get("SDATE", ""))
            and (int(values["SDATE"]) > 0 or values.get("START") == "S")):
        sdate = values["SDATE"]
        year = _filex_date(sdate[:2] + "001").year
        last = date(year, 12, 31).timetuple().tm_yday
        return [], [f"FileX {sim.filex}: SDATE {sdate!r} is invalid: day {int(sdate[2:])} "
                    f"does not exist in {year} (DSSAT reads years 00-35 as 2000-2035 "
                    f"and 36-99 as 1936-1999). Supply a day of year from 1 to {last}."]
    station = values["WSTA"]
    if _overrides_section(experiment_data, sim.treatment) and station[:4] != paths[0].name[:4].upper():
        station = paths[0].name[:4].upper()  # Match the copied field's new station.
    # A station mismatch is reported by Simulation;
    # avoid a second name-lookup problem for the same mismatch.
    same_station = all(path.name[:4].upper() == station[:4] for path in paths)
    where = f"treatments.{int(sim.treatment)}"
    sdate_field = (f"{where}.controls.start_date"
                   if _controls_start_date(experiment_data, sim.treatment) is not None
                   else "FileX SDATE")
    dates = [(sdate_field, _filex_date(values.get("SDATE")))]
    harvest = None
    sequence = len(components) > 1
    edits = entry.get("rotation", {})
    edits = {int(key): value for key, value in edits.items()
             if str(key).isascii() and str(key).isdigit() and isinstance(value, dict)
             } if isinstance(edits, dict) else {}
    for row in components:
        if sequence and not row["R"].isdigit():
            continue  # Ordinary sequence checks report unreadable component numbers.
        override = edits.get(int(row["R"]), {}) if sequence else entry
        location = f"{where}.rotation.{int(row['R'])}" if sequence else where
        code = (_component_management(text, row, "HARVS") if sequence else
                _effective_management(entry, text, int(sim.treatment), "harvest_management", "HARVS"))
        if code == "R":
            end = _harvest_end(override, _level_date(
                text, row, "MH", "HARVEST DETAILS", "H", "HDATE"), code)
            if not sequence:
                harvest = end
            events = override.get("harvest")
            if isinstance(events, list):
                dates.extend((f"{location}.harvest.{i}.date", _calendar_date(event.get("date")))
                             for i, event in enumerate(events) if isinstance(event, dict))
            elif end is not None:
                field = f"FileX HDATE (rotation component {int(row['R'])})" if sequence else "FileX HDATE"
                dates.extend((field, _filex_date(event["HDATE"])) for event in
                             _section_rows(text, "HARVEST DETAILS", "H", int(row["MH"]),
                                           ("HDATE",)))
    if start is None:
        reason = " (START E needs an emergence date)" if values.get("START") == "E" else ""
        problems = [f"Stock weather {sim.weather}: cannot check weather dates because "
                    f"the simulation start is unknown{reason}. Checked START and "
                    f"SDATE/PDATE for treatment {sim.treatment}. "
                    "Use START S or P with a valid date, or pass the weather as rows."]
        sdate = dates[0][1]
        if sdate is not None and same_station:
            # SDATE still needs the initial anchor; no effective start is known.
            _, _, anchor = _walk_weather_files(paths, station, values["SDATE"], sdate, sdate,
                                               wed=_weather_directory(sim.executable),
                                               mode="Q" if len(components) > 1 else "C")
            problems.extend(_weather_anchor_problems(anchor, dates))
        return [], problems
    years = _selected_controls(experiment_data, sim.treatment).get("years", values.get("NYERS", 1))
    try:
        years = max(1, int(years))
    except (TypeError, ValueError, OverflowError):
        years = 1  # Ordinary controls checks report invalid years.
    end = _sequence_stop(start, years) or date.max
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
    # The preliminary read checks structure only; the walk decodes the dates.
    _, problems = _read_stock_weather(paths)
    stations = sorted({path.name[:4].upper() for path in paths})
    mixed = len(stations) > 1
    if problems or (not same_station and not mixed):
        return [], problems
    if mixed:
        return [], [f"Weather data row {row}, column 'station': found {code!r}, "
                    f"but row 2 has {stations[0]!r}. Use identical station values on every row."
                    for row, code in enumerate(stations[1:], 3)]
    else:
        # Maturity is unknown until DSSAT runs. Without a known end, check only
        # the files reachable through DSSAT's selection walk.
        walk_end = end if harvest is not None or len(components) > 1 else None
        initial = values.get("SDATE", f"{start.year % 100:02d}001")
        rows, problems, anchor = _walk_weather_files(paths, station, initial, start, walk_end,
                                                     wed=_weather_directory(sim.executable),
                                                     mode="Q" if len(components) > 1 else "C")
        if values.get("START") == "P":
            if len(components) > 1:
                where += f".rotation.{int(components[0]['R'])}"
            field = f"{where}.planting.date" if isinstance(planting, dict) else "FileX PDATE"
            dates.append((field, start))
        problems.extend(_weather_anchor_problems(anchor, dates))
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
    """Copy WTH/CLI bytes under uppercase names, or write measured weather."""
    _copy_climate_file(source, folder)
    paths = _stock_weather_paths(source)
    if paths is not None:
        for path in paths:
            shutil.copy2(path, folder / path.name.upper())
    elif rows:
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
