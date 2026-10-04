"""Check and run one Simulation with a copied or generated FileX and user data."""

from datetime import date
from pathlib import Path
import shutil

from .errors import DSSATCheckError
from .controls import _controls_start_date, _season_coverage
from .climate import _check_weather_requirements, _coverage_weather_rows
from .filex import _filex_date, _irrigation_dates, _read_filex
from .filex_skeleton import _write_template_simulation
from .template_checks import _check_template_simulation
from .filex_write import _identity_text, _write_management
from .irrigation import _start_irrigation_code
from .management import _check_management, _report_lines
from .experiment import _overrides_section
from .operations import _check_harvest
from .management_file import _load_management
from .rotation_data import _write_rotation_data
from .runner import RunResult, _check_missing_weather, _create_dated_folder, run
from .sequence import (_check_sequence, _rotation_components, _run_sequence,
                       _sequence_coverage, _sequence_experiment_data,
                       _parse_sdate, _simulation_start, _simulation_start_date)
from .stock import (_simulation_soil, _simulation_weather, _stock_weather_paths,
                    _write_simulation_soil, _write_simulation_weather)


class Simulation:
    """One FileX treatment with measured or generated weather and optional soil data.

    Construction only stores inputs. Positional order remains filex, treatment,
    weather, executable; defaults None, 1, None allow filex to be omitted for a
    template. Exactly one of filex/filex_template is required by check() and run().
    A template requires soil data and a treatment within its treatments (1..N).

    Args:
        filex (str | Path | None): Path to the FileX (*.MZX, *.SBX, etc.).
        filex_template (str | Path | dict | None): Keyword-only. FileX template YAML
            path or dict, as accepted by write_filex. Alternative to filex (#90).
        treatment (int | str): Treatment number (int or digit string) within the FileX.
        weather (str | Path | list | DataFrame): Weather-template CSV path, rows or
            DataFrame, or .WTH paths and/or one .CLI path with a copied FileX.
            Stock files are copied unchanged under upper-case names.
        executable (str | Path | None): Optional explicit path to the DSSAT executable or directory.
        soil (str | Path | list[dict] | DataFrame | None): Keyword-only. Soil data following the
            soil template, describing one soil profile, or a stock .SOL path with
            a copied FileX. run() writes SOIL.SOL for template data or copies the
            stock file unchanged under its own name, replacing sibling soil files.
            None skips soil checks and keeps copying sibling soil files.
        management (str | Path | dict | None): Keyword-only. Experiment data as a
            path to a YAML file or a plain dict keyed by 'treatments', with optional
            planting, irrigation, fertilizer, cultivar, initial_conditions and controls
            per treatment. Construction only stores it; check() checks every entry
            and prints a report. Controls include weather_source M/W/S, replicates
            1-99999 (above 1 needs a generated-weather sequence) and random_seed
            0-99999 (a fixed seed repeats; 0 is passed as is).
        name (str | None): Scenario name written to the copied treatment, even
            without experiment overrides. None and "base" keep the FileX name.
            Sequences keep their component names. Other names must fit the column.
    """

    def __init__(self, filex=None, treatment=1, weather=None, executable=None, *, soil=None,
                 management=None, name=None, filex_template=None):
        self.filex = filex
        self.filex_template = filex_template
        self.treatment = treatment
        self.weather = weather
        self.soil = soil
        self.management = management
        self.executable = executable
        self.name = name

    def check(self, verbose: bool | None = None) -> list[str]:
        """Return all input problems without writing files or running DSSAT.

        Print Checks in weather, soil (if given), FileX and management order
        when verbose=True, or when verbose is left unset and management is given;
        verbose=False prints nothing. Management checks cover
        every treatment's shape, value ranges, unique and ascending dates for
        event lists, and compares the selected treatment's dates with the
        weather range and FileX simulation start date.
        An empty returned list means all checks passed.
        Both or neither FileX source raises DSSATCheckError; other problems are returned.
        """
        problems, report = self._check_inputs()
        if verbose or (verbose is None and self.management is not None):
            print("Checks")
            print("\n".join(report))
            print("Crop-specific fields are checked by DSSAT at run time.")
        return problems

    def _check_inputs(self, experiment_data=None, load_problems=None):
        """Collect input problems, using the loaded experiment data dict when supplied.

        Checks measured weather columns, values and dates or the required climate table;
        FileX treatment, WTHER, WSTA,
        START/SDATE and filename; START S/P coverage, soil and scenario name.
        Experiment overrides edit field identity; otherwise station and soil IDs must match.
        """
        if (self.filex is None) == (self.filex_template is None):
            raise DSSATCheckError(["Supply exactly one of filex or filex_template."])
        if load_problems is None:
            experiment_data, load_problems = _load_management(self.management)
        if self.filex_template is not None:
            return _check_template_simulation(self, experiment_data, load_problems)
        edit_identity = _overrides_section(experiment_data, self.treatment)
        override_start = _controls_start_date(experiment_data, self.treatment)
        values, filex_problems = _read_filex(self.filex, self.treatment, start_date=override_start)
        if values.get("START") != "S":
            override_start = None
        components = _rotation_components(self.filex, self.treatment)
        rows, weather_problems = _simulation_weather(self, values, experiment_data, components)
        if isinstance(self.weather, dict):
            weather_problems.append("Weather data per field needs a FileX template. "
                                    "Supply one weather source for a FileX.")
        sequence_problems, sequence_report = _check_sequence(self.filex, self.treatment, components)
        data_problems, checked_data = _sequence_experiment_data(
            experiment_data, self.treatment, components)
        filex_problems.extend(sequence_problems + data_problems)
        filex_problems.extend(_check_harvest(experiment_data, self.filex, self.treatment))
        filex_problems.extend(_check_weather_requirements(self, experiment_data, components, rows))
        name = Path(self.filex).name if isinstance(self.filex, (str, Path)) else ""
        if Path(name).suffix.upper() == ".FCX":
            filex_problems.append(f"FileX {name} is a forecast FileX: a Simulation "
                                  "does not run forecast mode (Y). "
                                  "Call run() on the FileX instead.")
        if len(name) > 12 and len(components) < 2:
            filex_problems.append(f"FileX filename {name!r} has {len(name)} characters; DSSAT "
                                  "accepts at most 12. Rename the FileX to at most 12 "
                                  "characters, including the extension (DSSAT's 8.3 style).")
        paths = _stock_weather_paths(self.weather)
        stations = {row["station"] for row in rows if "station" in row}
        if not rows and paths:
            stations = {path.name[:4].upper() for path in paths}
        if not edit_identity and "WSTA" in values and len(stations) == 1:
            station = stations.pop()
            expected = values["WSTA"][:4]
            if station != expected:
                source = f"stock weather file {paths[0].name}" if paths else "the weather template"
                filex_problems.append(f"FileX WSTA {values['WSTA']!r} expects station "
                                     f"{expected!r}, but {source} has station "
                                     f"{station!r}. Make the station codes exactly equal; "
                                     "filenames are case-sensitive on Linux.")
        coverage_rows = _coverage_weather_rows(self, experiment_data, components, rows)
        days = [row["date"] for row in coverage_rows if "date" in row]
        sdate = values.get("SDATE") if values.get("START") == "S" else None
        start_date, skip_reason = ((override_start, None) if override_start is not None
                                   else _simulation_start_date(sdate))
        if days and start_date is None and _parse_sdate(sdate) is not None:
            year = _filex_date(sdate[:2] + "001").year
            last = date(year, 12, 31).timetuple().tm_yday
            filex_problems.append(f"FileX {self.filex}: SDATE {sdate!r} is invalid: "
                                 f"day {int(sdate[2:])} does not exist in {year} (DSSAT reads "
                                 "years 00-35 as 2000-2035 and 36-99 as 1936-1999). "
                                 f"Supply a day of year from 1 to {last}.")
        if values.get("START") == "P":
            try:
                text = Path(self.filex).read_text(encoding="latin-1")
            except (OSError, TypeError, ValueError):
                text = ""
            start_date = _simulation_start(text, self.treatment, experiment_data)
            skip_reason = None if start_date is not None else "START P planting date is unavailable; check PDATE"
        if len(components) > 1:
            filex_problems.extend(_sequence_coverage(
                experiment_data, self.treatment, start_date, days, values.get("NYERS"), filex=self.filex))
        else:
            filex_problems.extend(_season_coverage(
                experiment_data, self.treatment, start_date, days, values.get("NYERS")))
        if override_start is not None and days:
            if override_start not in days:
                filex_problems.append(f"Controls start_date {override_start.isoformat()!r} is not "
                                     f"covered by weather data ({min(days)} to {max(days)}). "
                                     "Supply weather for the simulation's start date.")
        elif sdate is not None and start_date is not None and days and start_date not in days:
            filex_problems.append(f"FileX SDATE {sdate!r} is {start_date} (DSSAT reads two-digit "
                                 "years 00-35 as 2000-2035 and 36-99 as 1936-1999), not "
                                 f"covered by weather data ({min(days)} to {max(days)}). "
                                 f"Supply weather for {start_date}, or set controls.start_date.")
        if values.get("START") == "P" and start_date is not None and days and start_date not in days:
            filex_problems.append(f"Simulation start date {start_date.isoformat()!r} is not "
                                 f"covered by weather data ({min(days)} to {max(days)}). "
                                 "Supply weather for the simulation's start date.")
        if (override_start is not None or values.get("START") != "E") and start_date is not None and days and not _overrides_section(
                experiment_data, self.treatment, "irrigation",
                rotation=components[0]['R'] if len(components) > 1 else None):
            # DSSAT-CSM v4.8.6.0, InputModule/IPMAN.for, IPIRR: only IRRIG R
            # events are calendar dates that must not precede the start.
            code = _start_irrigation_code(experiment_data, self.filex, self.treatment, components)
            irrigation = [_filex_date(text) for text in _irrigation_dates(self.filex, self.treatment)
                          if code in ("R", None)]
            irrigation = [day for day in irrigation if day is not None]
            if irrigation and min(irrigation) < start_date:
                label = "Controls start_date" if override_start is not None else "Simulation start date"
                filex_problems.append(f"{label} {start_date.isoformat()!r} is "
                                     f"after the FileX's first irrigation date {min(irrigation)}; "
                                     "DSSAT stops with error IPIRR. Start on or before that date, "
                                     "or give irrigation in the management data.")
        _, soil_problems, template_id = _simulation_soil(self, values, edit_identity)
        problems = weather_problems + filex_problems + soil_problems
        report = _report_lines("Weather data", weather_problems)
        if self.soil is not None:
            report.extend(_report_lines("Soil data", soil_problems))
        report.extend(_report_lines("FileX", filex_problems))
        report.extend(sequence_report)
        if self.management is not None:
            if load_problems:
                problems.extend(load_problems)
                report.extend(_report_lines("Management data", load_problems))
            else:
                management_problems, management_report = _check_management(
                    checked_data, self.filex, self.treatment, coverage_rows, start_date,
                    start_date_note=skip_reason, check_harvest=False,
                )
                problems.extend(management_problems)
                report.extend(management_report)
        name = None if len(components) > 1 else self.name
        if (edit_identity or name not in (None, "base")) and not problems:
            try:
                _identity_text(Path(self.filex).read_bytes().decode("latin-1"),
                               int(self.treatment), name,
                               rows[0]["station"] if edit_identity and rows else None,
                               template_id if edit_identity else None)
            except ValueError as error:
                problems.append(f"FileX: {error}")
                report.extend(_report_lines("FileX identity", [str(error)]))
        return problems, report

    def run(self) -> RunResult:
        """Check inputs, copy them into a fresh simulation folder, and run DSSAT.

        Runs the same checks as check(), quietly, and raises DSSATCheckError
        if any problems are found.
        Creates a dated simulation folder (dssat_sim_YYYY-MM-DD_HHMMSS) beside the
        FileX, copies the FileX and sibling model files (*.CUL, *.ECO, *.SPE),
        and writes measured weather or copies stock .WTH/.CLI files unchanged.
        For a template, creates the folder beside its YAML (or in cwd for a dict),
        writes the FileX and SOIL.SOL, and copies the crop's genotype files from
        Genotype beside the DSSAT executable. Experiment edits then apply as usual.
        With management data, adds a new level for each section given (planting,
        irrigation, fertilizer, cultivar, initial conditions, controls) in the copy
        and repoints only the selected treatment; the original FileX is never changed.
        With experiment overrides, writes the weather station and supplied soil
        ID into that field; generated weather keeps the FileX station.
        Independently writes name into the copied treatment,
        except for sequences, None and "base", which retain the FileX names.
        With soil=, writes SOIL.SOL or copies stock soil and copies no sibling .SOL
        files. With soil=None, copies all sibling .SOL files. Invokes the DSSAT executable for the
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
        experiment_data, load_problems = _load_management(self.management)
        problems, _ = self._check_inputs(experiment_data, load_problems)
        if problems:
            raise DSSATCheckError(problems)
        executable = self.executable
        if self.filex_template is not None:
            prepared = _write_template_simulation(self, experiment_data=experiment_data)
        else:
            components = _rotation_components(self.filex, self.treatment)
            override_start = _controls_start_date(experiment_data, self.treatment)
            values, _ = _read_filex(self.filex, self.treatment, start_date=override_start)
            rows, weather_problems = _simulation_weather(self, values, experiment_data, components)
            if weather_problems:
                raise DSSATCheckError(weather_problems)
            station = rows[0]["station"] if rows and _overrides_section(experiment_data, self.treatment) else None
            if station is not None and _stock_weather_paths(self.weather) and values["WSTA"][:4] == station:
                station = values["WSTA"]  # Keep an explicit stock filename in the copied field.
            if station is not None:
                values["WSTA"] = station
            soil_rows, _, template_id = _simulation_soil(self, values, _overrides_section(experiment_data, self.treatment))
            filex = Path(self.filex).resolve()
            sim_folder = _create_dated_folder(filex.parent, "dssat_sim_", "simulation folder")
            shutil.copy2(filex, sim_folder / filex.name)
            for sibling in filex.parent.iterdir():
                if self.soil is not None and sibling.suffix.upper() == ".SOL":
                    continue
                if sibling.is_file() and sibling.suffix.upper() in (".SOL", ".CUL", ".ECO", ".SPE"):
                    shutil.copy2(sibling, sim_folder / sibling.name)
            soil_id = template_id if _overrides_section(experiment_data, self.treatment) else None
            _write_management(sim_folder / filex.name, self.treatment, experiment_data,
                              name=None if len(components) > 1 else self.name,
                              station=station, soil_id=soil_id)
            _write_rotation_data(sim_folder / filex.name, self.treatment, experiment_data)
            _write_simulation_weather(self.weather, rows, sim_folder, values)
            _write_simulation_soil(self.soil, soil_rows, sim_folder)
            prepared = sim_folder / filex.name

        components = _rotation_components(prepared, self.treatment)
        result = (_run_sequence(prepared, self.treatment, components, executable)
                  if len(components) > 1 else
                  run(prepared, treatment=int(self.treatment), executable=executable))
        _check_missing_weather(result)
        return result
