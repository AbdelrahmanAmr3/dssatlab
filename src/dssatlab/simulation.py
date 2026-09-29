"""Describe one Simulation and check its FileX and weather without writing files."""

from .filex import _read_filex
from .weather import _parse_weather


class Simulation:
    """One FileX treatment and its weather data; construction only stores inputs."""

    def __init__(self, filex, treatment, weather):
        self.filex = filex
        self.treatment = treatment
        self.weather = weather

    def check(self) -> list[str]:
        """Return weather/FileX problems; check SDATE coverage only for START S."""
        rows, problems = _parse_weather(self.weather)
        values, filex_problems = _read_filex(self.filex, self.treatment)
        problems.extend(filex_problems)
        stations = {row["station"] for row in rows if "station" in row}
        if "WSTA" in values and len(stations) == 1:
            station = stations.pop()
            expected = values["WSTA"][:4]
            if station != expected:
                problems.append(f"FileX WSTA {values['WSTA']!r} expects station "
                                f"{expected!r}, but the weather template has station "
                                f"{station!r}. Make the station codes exactly equal; "
                                "filenames are case-sensitive on Linux.")
        days = [row["date"] for row in rows if "date" in row]
        if values.get("START") == "S" and "SDATE" in values and days:
            start = values["SDATE"]
            wanted = (int(start[:2]), int(start[2:]))
            if not any((day.year % 100, day.timetuple().tm_yday) == wanted for day in days):
                problems.append(f"FileX start year {start[:2]} day {start[2:]} is not "
                                f"covered by weather data ({min(days)} to {max(days)}). "
                                "Supply weather for the simulation's start date.")
        return problems
