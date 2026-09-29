"""Check and run one Simulation using a copy of its FileX and weather data."""

from datetime import date, timedelta
from pathlib import Path
import re
import shutil

from .errors import DSSATCheckError, DSSATRunError
from .filex import _read_filex, _weather_filename
from .runner import RunResult, _create_dated_folder, run
from .weather import _parse_weather, write_weather_file


class Simulation:
    """One FileX treatment and its weather data; construction only stores inputs.

    Represents a single simulation run configuring one treatment from a FileX
    experiment file with user-provided weather data. Construction records inputs
    without reading files or altering disk state. Validation and execution are
    performed by check() and run().

    Args:
        filex (str | Path): Path to the FileX experiment file (*.MZX, *.SBX, etc.).
        treatment (int | str): Treatment number (int or digit string) within the FileX.
        weather (str | Path | list[dict] | DataFrame): Weather data as a CSV file path, a list of dicts, or a pandas
            DataFrame conforming to the weather template.
        executable (str | Path | None): Optional explicit path to the DSSAT executable or directory.
    """

    def __init__(self, filex, treatment, weather, executable=None):
        self.filex = filex
        self.treatment = treatment
        self.weather = weather
        self.executable = executable

    def check(self) -> list[str]:
        """Return weather and FileX problems without running DSSAT.

        Performs strict validation: checks weather data column names, value
        ranges, date order, duplicates, and gaps; reads the FileX for treatment
        validity, field station code (WSTA), and start controls (START, SDATE);
        ensures FileX filename is at most 12 characters; verifies station code
        equality; and verifies that weather data covers SDATE when START is 'S'.

        Returns:
            list[str]: Descriptive problem messages found by the checks.
                An empty list indicates all checks passed.
        """
        rows, problems = _parse_weather(self.weather)
        values, filex_problems = _read_filex(self.filex, self.treatment)
        problems.extend(filex_problems)
        name = Path(self.filex).name if isinstance(self.filex, (str, Path)) else ""
        if len(name) > 12:
            problems.append(f"FileX filename {name!r} has {len(name)} characters; DSSAT "
                            "accepts at most 12. Rename the FileX to at most 12 "
                            "characters, including the extension (DSSAT's 8.3 style).")
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

    def run(self) -> RunResult:
        """Check inputs, copy them into a fresh simulation folder, and run DSSAT.

        Runs check() and raises DSSATCheckError if any problems are found.
        Creates a dated simulation folder (dssat_sim_YYYY-MM-DD_HHMMSS) beside the
        FileX, copies the FileX and sibling model files (*.SOL, *.CUL, *.ECO, *.SPE),
        generates the weather file (*.WTH), invokes the DSSAT executable for the
        treatment, and scans WARNING.OUT for missing weather records.

        Returns:
            RunResult: Run results including returncode, run directory, outputs,
                and stdout_tail.

        Raises:
            DSSATCheckError: If pre-run input checks identify one or more problems.
            DSSATRunError: If execution fails, DSSAT returns non-zero, ERROR.OUT is
                produced, or WARNING.OUT reports missing weather records.
        """
        problems = self.check()
        if problems:
            raise DSSATCheckError(problems)

        rows, _ = _parse_weather(self.weather)
        values, _ = _read_filex(self.filex, self.treatment)
        weather_name = _weather_filename(values["WSTA"], values["SDATE"])
        filex = Path(self.filex).resolve()
        sim_folder = _create_dated_folder(filex.parent, "dssat_sim_", "simulation folder")
        shutil.copy2(filex, sim_folder / filex.name)
        for sibling in filex.parent.iterdir():
            if sibling.is_file() and sibling.suffix.upper() in (".SOL", ".CUL", ".ECO", ".SPE"):
                shutil.copy2(sibling, sim_folder / sibling.name)
        write_weather_file(rows, sim_folder / weather_name)

        result = run(sim_folder / filex.name, treatment=int(self.treatment),
                     executable=self.executable)
        warning = result.run_dir / "WARNING.OUT"
        if warning.exists():
            for line in warning.read_text(encoding="utf-8", errors="replace").splitlines():
                missing = re.search(r"Weather record not found for YR DOY:\s+(\d{4})\s+(\d{1,3})", line)
                if missing:
                    year, day = map(int, missing.groups())
                    calendar_date = date(year, 1, 1) + timedelta(days=day - 1)
                    raise DSSATRunError(
                        f"DSSAT reported no weather for year {year}, day of year {day} "
                        f"({calendar_date}). DSSAT exits 0 in this case and gives -99 "
                        "for anything it could not reach.\n"
                        f"Run directory (kept): {result.run_dir}\n"
                        "Extend the weather data through that date and the days the "
                        "crop needs, then run again."
                    )
        return result
