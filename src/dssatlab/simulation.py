"""Check and run one Simulation with a copied FileX, weather and optional soil data."""

from datetime import date, timedelta
from pathlib import Path
import re
import shutil

from .errors import DSSATCheckError, DSSATRunError
from .filex import _read_filex, _weather_filename
from .filex_write import _write_planting
from .management import _check_management, _report_lines
from .management_file import _load_management
from .runner import RunResult, _create_dated_folder, run
from .soil import _parse_soil, write_soil_file
from .weather import _parse_weather, write_weather_file


def _simulation_start_date(values, days):
    """Convert FileX SDATE to a calendar date using years from weather data."""
    if values.get("START", "S") != "S" or "SDATE" not in values or not days:
        return None
    sdate = values["SDATE"]
    if not (isinstance(sdate, str) and re.fullmatch(r"[0-9]{5}", sdate)):
        return None
    yy = int(sdate[:2])
    doy = int(sdate[2:])
    if doy < 1:
        return None
    min_year = min(day.year for day in days)
    max_year = max(day.year for day in days)
    matching_years = [y for y in range(min_year, max_year + 1) if y % 100 == yy]
    if len(matching_years) != 1:
        return None
    year = matching_years[0]
    try:
        candidate = date(year, 1, 1) + timedelta(days=doy - 1)
        if candidate.year != year:
            return None
        return candidate
    except (ValueError, OverflowError):
        return None


class Simulation:
    """One FileX treatment with weather data and optional soil data.

    Represents a single simulation run configuring one treatment from a FileX
    with user-provided weather data and optional soil data. Construction only
    stores inputs without reading files or altering disk state. Checks and execution are
    performed by check() and run().

    Args:
        filex (str | Path): Path to the FileX experiment file (*.MZX, *.SBX, etc.).
        treatment (int | str): Treatment number (int or digit string) within the FileX.
        weather (str | Path | list[dict] | DataFrame): Weather data as a CSV file path, a list of dicts, or a pandas
            DataFrame conforming to the weather template.
        executable (str | Path | None): Optional explicit path to the DSSAT executable or directory.
        soil (str | Path | list[dict] | DataFrame | None): Keyword-only. Soil data following the
            soil template, describing one soil profile. When given, run() writes
            SOIL.SOL instead of copying sibling soil files. None skips soil checks
            and keeps copying sibling soil files.
        management (str | Path | dict | None): Keyword-only. Management data as a
            path to a YAML file or a plain dict keyed by 'treatments', with optional
            planting, irrigation and fertilizer per treatment. Construction only stores
            it; check() checks every entry and prints a report.
    """

    def __init__(self, filex, treatment, weather, executable=None, *, soil=None, management=None):
        self.filex = filex
        self.treatment = treatment
        self.weather = weather
        self.soil = soil
        self.management = management
        self.executable = executable

    def check(self, verbose: bool = False) -> list[str]:
        """Return all input problems without writing files or running DSSAT.

        Print Checks in weather, soil (if given), FileX and management order
        when management is given or verbose=True. Management checks cover
        every treatment's shape, value ranges, unique and ascending dates for
        event lists, and compares the selected treatment's dates with the
        weather range and FileX simulation start date.
        An empty returned list means all checks passed.
        """
        problems, report = self._check_inputs()
        if self.management is not None or verbose:
            print("Checks")
            print("\n".join(report))
            print("Crop-specific fields are checked by DSSAT at run time.")
        return problems

    def _check_inputs(self):
        """Collect weather, soil, FileX and management problems and report lines.

        Performs strict validation: checks weather data column names, value
        ranges, date order, duplicates, and gaps; reads the FileX for treatment
        validity, field station code (WSTA), and start controls (START, SDATE);
        ensures FileX filename is at most 12 characters; verifies station code
        equality; and verifies that weather data covers SDATE when START is 'S'.
        When soil data is given, checks its columns, values, soil profile and
        layers, and requires its soil_id to equal the selected field's ID_SOIL.
        """
        rows, weather_problems = _parse_weather(self.weather)
        values, filex_problems = _read_filex(self.filex, self.treatment)
        name = Path(self.filex).name if isinstance(self.filex, (str, Path)) else ""
        if len(name) > 12:
            filex_problems.append(f"FileX filename {name!r} has {len(name)} characters; DSSAT "
                                  "accepts at most 12. Rename the FileX to at most 12 "
                                  "characters, including the extension (DSSAT's 8.3 style).")
        stations = {row["station"] for row in rows if "station" in row}
        if "WSTA" in values and len(stations) == 1:
            station = stations.pop()
            expected = values["WSTA"][:4]
            if station != expected:
                filex_problems.append(f"FileX WSTA {values['WSTA']!r} expects station "
                                     f"{expected!r}, but the weather template has station "
                                     f"{station!r}. Make the station codes exactly equal; "
                                     "filenames are case-sensitive on Linux.")
        days = [row["date"] for row in rows if "date" in row]
        if values.get("START") == "S" and "SDATE" in values and days:
            start = values["SDATE"]
            wanted = (int(start[:2]), int(start[2:]))
            if not any((day.year % 100, day.timetuple().tm_yday) == wanted for day in days):
                filex_problems.append(f"FileX start year {start[:2]} day {start[2:]} is not "
                                     f"covered by weather data ({min(days)} to {max(days)}). "
                                     "Supply weather for the simulation's start date.")
        soil_problems = []
        if self.soil is not None:
            soil_rows, soil_problems = _parse_soil(self.soil)
            soil_ids = {row["soil_id"] for row in soil_rows if "soil_id" in row}
            soil_id = values.get("ID_SOIL")
            if not soil_id or soil_id == "-99":
                soil_problems.append("FileX has no readable ID_SOIL in the selected "
                                     "treatment's FIELDS row. Supply ID_SOIL "
                                     "equal to the soil template's soil_id.")
            elif len(soil_ids) == 1:
                template_id = soil_ids.pop()
                if soil_id != template_id:
                    soil_problems.append(f"FileX ID_SOIL {soil_id!r} for treatment "
                                         f"{self.treatment} differs from the soil template's "
                                         f"soil_id {template_id!r}. Make the IDs exactly equal; "
                                         "filenames are case-sensitive on Linux.")
        problems = weather_problems + filex_problems + soil_problems
        report = _report_lines("Weather data", weather_problems)
        if self.soil is not None:
            report.extend(_report_lines("Soil data", soil_problems))
        report.extend(_report_lines("FileX", filex_problems))
        if self.management is not None:
            management_dict, load_problems = _load_management(self.management)
            if load_problems:
                problems.extend(load_problems)
                report.extend(_report_lines("Management data", load_problems))
            else:
                start_date = _simulation_start_date(values, days)
                management_problems, management_report = _check_management(
                    management_dict, self.filex, self.treatment, rows, start_date
                )
                problems.extend(management_problems)
                report.extend(management_report)
        return problems, report

    def run(self) -> RunResult:
        """Check inputs, copy them into a fresh simulation folder, and run DSSAT.

        Runs the same checks as check(), quietly, and raises DSSATCheckError
        if any problems are found.
        Creates a dated simulation folder (dssat_sim_YYYY-MM-DD_HHMMSS) beside the
        FileX, copies the FileX and sibling model files (*.CUL, *.ECO, *.SPE),
        and generates the weather file (*.WTH).
        With management planting, adds a new level in the copy and repoints only
        the selected treatment; the original FileX is never changed.
        When soil data is given, writes its soil profile to SOIL.SOL and copies
        no sibling .SOL files; otherwise
        copies all sibling .SOL files. Invokes the DSSAT executable for the
        treatment and scans WARNING.OUT for missing weather records. Soil
        failures use the existing run error, keeping ERROR.OUT in the run directory.

        Returns:
            RunResult: Run results including returncode, run directory, outputs,
                and stdout_tail.

        Raises:
            DSSATCheckError: If pre-run input checks identify one or more problems.
            DSSATRunError: If execution fails, DSSAT returns non-zero, ERROR.OUT is
                produced, or WARNING.OUT reports missing weather records.
        """
        problems, _ = self._check_inputs()
        if problems:
            raise DSSATCheckError(problems)

        rows, _ = _parse_weather(self.weather)
        values, _ = _read_filex(self.filex, self.treatment)
        weather_name = _weather_filename(values["WSTA"], values["SDATE"])
        filex = Path(self.filex).resolve()
        sim_folder = _create_dated_folder(filex.parent, "dssat_sim_", "simulation folder")
        shutil.copy2(filex, sim_folder / filex.name)
        management_dict = None
        if self.management is not None:
            management_dict, _ = _load_management(self.management)
        _write_planting(sim_folder / filex.name, self.treatment, management_dict)
        for sibling in filex.parent.iterdir():
            if self.soil is not None and sibling.suffix.upper() == ".SOL":
                continue
            if sibling.is_file() and sibling.suffix.upper() in (".SOL", ".CUL", ".ECO", ".SPE"):
                shutil.copy2(sibling, sim_folder / sibling.name)
        write_weather_file(rows, sim_folder / weather_name)
        if self.soil is not None:
            soil_rows, _ = _parse_soil(self.soil)
            write_soil_file(soil_rows, sim_folder / "SOIL.SOL")

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
