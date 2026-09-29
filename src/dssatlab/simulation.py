"""Describe one Simulation and check its weather data without writing files."""

from .weather import _parse_weather


class Simulation:
    """One FileX treatment and its weather data; construction only stores inputs."""

    def __init__(self, filex, treatment, weather):
        self.filex = filex
        self.treatment = treatment
        self.weather = weather

    def check(self) -> list[str]:
        """Return all weather problems; FileX checks belong to a later ticket."""
        _, problems = _parse_weather(self.weather)
        return problems
