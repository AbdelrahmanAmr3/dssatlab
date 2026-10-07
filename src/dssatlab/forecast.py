"""Private checks for a copied forecast FileX and its measured weather."""

from datetime import date, timedelta
from pathlib import Path

from .climate import _split_weather_inputs, _weather_requirements
from .controls import _filex_forecast_date, _selected_controls
from .experiment import _check_date


def _forecast_date(text, treatment, controls):
    """Resolve FODAT or its ISO override without the FileX century restriction."""
    if "forecast_date" in controls:
        value = controls["forecast_date"]
        return None if _check_date(value, "forecast_date", filex_year=False) else date.fromisoformat(value)
    return _filex_forecast_date(text, treatment)


def _forecast_start(start, years):
    """Keep the start day of year in the first historical weather year."""
    year = start.year - years
    if year >= date.min.year:
        return date(year, 1, 1) + timedelta(days=start.timetuple().tm_yday - 1)
    return None


def _check_forecast(sim, source, components, values, start, days):
    """Collect forecast problems independently; ordinary checks report bad inputs."""
    try:
        treatment = int(sim.treatment)
    except (TypeError, ValueError):
        treatment = sim.treatment
    where = f"FileX {sim.filex} treatment {treatment}"
    problems = []
    controls = _selected_controls(source, sim.treatment)
    try:
        text = Path(sim.filex).read_text(encoding="latin-1")
    except (OSError, TypeError, ValueError):
        text = ""
    forecast = _forecast_date(text, sim.treatment, controls)
    name = Path(sim.filex).name if isinstance(sim.filex, (str, Path)) else ""
    if len(name) != 12:
        problems.append(f"FileX filename {name!r} has {len(name)} characters; forecast mode Y needs "
                        "exactly 12. Rename the FileX to 12 characters including the extension, e.g. UFGA2301.FCX.")
    if _split_weather_inputs(sim.weather)[0] is None and not _split_weather_inputs(sim.weather)[1]:
        problems.append(f"{where}: a forecast needs measured weather from the historical seasons. "
                        "Supply weather data or .WTH paths.")
    if forecast is None:
        problems.append(f"{where} has no forecast date (SIMDATES FODAT). "
                        "Set controls forecast_date, e.g. 2023-05-17.")
    if values.get("START") not in ("S", "P") or start is None:
        problems.append(f"{where}: a forecast needs START S or P with a valid start date.")
    elif forecast is not None:
        if forecast < start:
            problems.append(f"Controls forecast_date {forecast} is before the start date {start} of "
                            f"{where}. Set forecast_date on or after the start date.")
        else:
            problems.extend(_forecast_coverage(controls, start, forecast, days, values.get("NYERS")))
    for level, method, _ in _weather_requirements(sim, source, components):
        if method != "M":
            problems.append(f"{where}, WTHER {method} in controls level {level}: "
                            "a forecast Simulation uses measured weather only. "
                            "Set controls weather_source to M.")
    for path in _split_weather_inputs(sim.weather)[1]:
        problems.append(f"{where}, climate file {path}: "
                        "a forecast Simulation uses measured weather only. "
                        "Supply weather data or .WTH paths.")
    if len(components) > 1:
        problems.append(f"{where} has {len(components)} rotation components: "
                        "a forecast Simulation needs one treatment with one rotation component. "
                        "Supply a .FCX with one rotation component for this treatment.")
    return problems


def _forecast_coverage(controls, start, forecast, days, nyers):
    """Require a contiguous range, keeping the start day of year in the historical year."""
    if not days:
        return []  # Weather checks explain unavailable daily dates.
    if "years" in controls:
        years, label = controls["years"], "Controls years"
        if type(years) is not int or not 1 <= years <= 99999:
            return []  # Ordinary controls checks report invalid years and column overflow.
    else:
        try:
            years = max(1, int(nyers))
        except (TypeError, ValueError):
            years = 1
        label = "FileX NYERS"
    year, doy = start.year - years, start.timetuple().tm_yday
    last = forecast - timedelta(days=1)
    first = f"day {doy} of {year}"
    historical = _forecast_start(start, years)
    if historical is not None:
        first = historical
        supplied = {day for day in days if first <= day <= last}
        if len(supplied) == (last - first).days + 1:
            return []
    return [f"{label} {years}: the forecast needs weather from {first} through {last}, "
            f"outside weather range ({min(days)} to {max(days)}). "
            "Supply weather covering the date range, or fewer years."]
