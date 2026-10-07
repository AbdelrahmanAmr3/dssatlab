"""Summaries of the user's weather and soil data after the template checks."""

from pathlib import Path

from .errors import DSSATCheckError
from .soil import _parse_soil
from .weather import _parse_weather


def _reject_stock(source, kind):
    if isinstance(source, (str, Path)) and Path(source).suffix.upper() in (".WTH", ".SOL"):
        file_kind = "weather" if Path(source).suffix.upper() == ".WTH" else "soil"
        raise DSSATCheckError([
            f"summarize_{kind} reads the {kind} template, not stock {file_kind} file {source}. "
            f"Checked the file suffix. Supply {kind} template rows, a CSV path or a "
            f"DataFrame; Simulation copies stock {file_kind} files unchanged."])
    if (isinstance(source, list) and source
            and all(isinstance(item, (str, Path)) for item in source)):
        raise DSSATCheckError([
            f"summarize_{kind} reads the {kind} template, not a list of file paths {source}. "
            f"Checked the source type. Supply {kind} template rows, a CSV path or a "
            f"DataFrame; Simulation copies stock {kind} files unchanged."])


def summarize_weather(source) -> dict:
    """Check weather template data and return station, daily and yearly values.

    Accept a CSV path, plain row dicts or a DataFrame. Dates are datetime.date
    values; years are in calendar order, with the actual day count of each.
    Variables use DSSAT's units, including PAR only when supplied on the rows.
    Each year has year, days, variables (min/mean/max per variable) and rain_total,
    using the same nested variables layout as the overall summary.
    Statistics and rain totals are rounded once to two decimals.
    Raise DSSATCheckError with all template problems, or for stock file sources.
    """
    _reject_stock(source, "weather")
    rows, problems = _parse_weather(source)
    if problems:
        raise DSSATCheckError(problems)
    first = rows[0]
    names = ("srad", "tmax", "tmin", "rain") + (("par",) if "par" in first else ())
    variables = {}
    for name in names:
        values = [row[name] for row in rows]
        variables[name] = {"min": round(min(values), 2),
                           "mean": round(sum(values) / len(values), 2),
                           "max": round(max(values), 2)}
    by_year = {}
    for row in rows:
        by_year.setdefault(row["date"].year, []).append(row)
    years = []
    for year, days in sorted(by_year.items()):
        entry = {"year": year, "days": len(days), "variables": {}}
        for name in names:
            values = [row[name] for row in days]
            entry["variables"][name] = {"min": round(min(values), 2),
                                        "mean": round(sum(values) / len(values), 2),
                                        "max": round(max(values), 2)}
        entry["rain_total"] = round(sum(row["rain"] for row in days), 2)
        years.append(entry)
    return {
        "station": first["station"], "latitude": first["latitude"],
        "longitude": first["longitude"], "elevation": first["elevation"],
        "first_date": first["date"], "last_date": rows[-1]["date"], "days": len(rows),
        "variables": variables, "rain_total": round(sum(row["rain"] for row in rows), 2),
        "years": years}


def summarize_soil(source) -> dict:
    """Check soil template data and return one profile's depth and water values.

    Accept a CSV path, plain row dicts or a DataFrame. Depth is the deepest
    layer bottom in cm; extractable water sums (sdul - slll) times each layer's
    thickness in mm. Numeric summary values are rounded once to two decimals.
    Raise DSSATCheckError with all template problems, or for stock file sources.
    """
    _reject_stock(source, "soil")
    rows, problems = _parse_soil(source)
    if problems:
        raise DSSATCheckError(problems)
    previous_depth, water = 0, 0
    for row in rows:
        water += (row["sdul"] - row["slll"]) * (row["slb"] - previous_depth) * 10
        previous_depth = row["slb"]
    first = rows[0]
    return {
        "soil_id": first["soil_id"], "layers": len(rows),
        "depth": round(max(row["slb"] for row in rows), 2),
        "extractable_water": round(water, 2),
        "salb": round(first["salb"], 2), "slro": round(first["slro"], 2),
        "sldr": round(first["sldr"], 2), "slpf": round(first["slpf"], 2)}
