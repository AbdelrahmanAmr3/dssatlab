"""Narrow reads of stock DSSAT files, without rewriting or repairing them."""

from datetime import date
from pathlib import Path
import re
import shutil

from .controls import _selected_controls
from .experiment import _overrides_section
from .filex import _read_filex, _weather_filename
from .irrigation import _effective_management
from .operations import _harvest_end
from .rotation_data import _level_date
from .sequence import _sequence_end, _sequence_shift, _sequence_stop, _simulation_start
from .soil import _parse_soil, write_soil_file
from .weather import _parse_weather, write_weather_file
from .weather_files import (_read_stock_weather, _read_weather_file, _weather_date,
                            _walk_weather_files, _weather_directory)


def _stock_weather_paths(source):
    """Return stock paths, or None for a weather-template source."""
    paths = source if isinstance(source, list) else [source]
    if paths and all(isinstance(path, (str, Path)) and Path(path).suffix.upper() == ".WTH"
                     for path in paths):
        return [Path(path) for path in paths]
    return None


def _weather_start_dates(source):
    """Give start checks explicit weather dates; legacy weather supplies no century."""
    paths = _stock_weather_paths(source)
    if paths is None:
        return []  # write_weather_file emits legacy YYDDD for template data.
    raw, _ = _read_weather_file(paths[0])
    code = raw[0][1]["date"] if raw else ""
    first = _weather_date(code, None) if len(code) == 7 else None
    return [first] if first is not None else []


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
    # e2e22: only seven-digit $WEATHER supplies a century before start selection.
    explicit = _weather_start_dates(sim.weather)
    start = _simulation_start(text, sim.treatment, experiment_data, explicit)
    if (start is None and values.get("START") == "S"
            and re.fullmatch(r"[0-9]{5}", values.get("SDATE", ""))):
        return [], [f"FileX {sim.filex}: SDATE {values['SDATE']!r} is invalid. "
                    "Supply five digits: two-digit year followed by three-digit day of year."]
    if start is None:
        return [], [f"Stock weather {sim.weather}: cannot check weather dates because "
                    f"the simulation start is unknown. Checked START and "
                    f"SDATE/PDATE/EDATE for treatment {sim.treatment}. "
                    "Supply a valid simulation start date, or pass the weather as rows."]
    years = _selected_controls(experiment_data, sim.treatment).get("years", values.get("NYERS", 1))
    try:
        years = max(1, int(years))
    except (TypeError, ValueError, OverflowError):
        years = 1  # Ordinary controls checks report invalid years.
    end = _sequence_stop(start, years) or date.max
    harvest = None
    if len(components) == 1:
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
    rows, problems = _read_stock_weather(paths, station, start)
    if same_station and not problems:
        # Maturity is unknown until DSSAT runs. Keep the existing harvest/season
        # bounds; check selection through the supplied period when no end is known.
        last = max((row["date"] for row in rows), default=start)
        walk_end = end if harvest is not None or len(components) > 1 else min(end, last)
        initial = values.get("SDATE", f"{start.year % 100:02d}001")
        rows, problems = _walk_weather_files(paths, station, initial, start, walk_end,
                                             wed=_weather_directory(sim.executable))
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
