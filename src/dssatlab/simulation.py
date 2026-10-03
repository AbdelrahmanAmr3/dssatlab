"""Check and run one Simulation with a copied or generated FileX and user data."""

from pathlib import Path
import shutil

from .errors import DSSATCheckError
from .controls import _controls_start_date, _season_coverage
from .filex import _check_filex_controls, _irrigation_dates, _read_filex
from .filex_skeleton import _check_template_simulation, _write_template_simulation
from .filex_write import _identity_text, _write_management
from .management import _check_management, _report_lines
from .experiment import _overrides_section
from .operations import _check_harvest
from .management_file import _load_management
from .rotation_data import _write_rotation_data
from .runner import RunResult, _check_missing_weather, _create_dated_folder, run
from .sequence import (_check_sequence, _rotation_components, _run_sequence,
                       _sequence_coverage, _sequence_experiment_data,
                       _parse_sdate, _simulation_start_date)
from .soil import _parse_soil, write_soil_file
from .stock import _simulation_weather, _write_simulation_weather


class Simulation:
    """One FileX treatment with weather data and optional soil data.

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
            DataFrame, or a stock .WTH path/list of paths with a copied FileX.
            Stock files are copied unchanged under upper-case names.
        executable (str | Path | None): Optional explicit path to the DSSAT executable or directory.
        soil (str | Path | list[dict] | DataFrame | None): Keyword-only. Soil data following the
            soil template, describing one soil profile. When given, run() writes
            SOIL.SOL instead of copying sibling soil files. None skips soil checks
            and keeps copying sibling soil files.
        management (str | Path | dict | None): Keyword-only. Experiment data as a
            path to a YAML file or a plain dict keyed by 'treatments', with optional
            planting, irrigation, fertilizer, cultivar, initial_conditions and controls
            per treatment. Construction only stores it; check() checks every entry
            and prints a report.
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

        Performs strict validation: checks weather data column names, value
        ranges, date order, duplicates, and gaps; reads the FileX for treatment
        validity, field station code (WSTA), and start controls (START, SDATE);
        ensures FileX filename is at most 12 characters and weather data covers
        SDATE when START is 'S'. Checks soil data and scenario name column fit.
        With experiment overrides, checks field edits in memory; otherwise
        requires matching weather station and soil profile IDs.
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
        filex_problems.extend(_check_filex_controls(self.filex, self.treatment,
                                                    [row["SM"] for row in components]))
        name = Path(self.filex).name if isinstance(self.filex, (str, Path)) else ""
        if Path(name).suffix.upper() == ".FCX":
            filex_problems.append(f"FileX {name} is a forecast FileX: a Simulation "
                                  "does not run forecast mode (Y). "
                                  "Call run() on the FileX instead.")
        if len(name) > 12 and len(components) < 2:
            filex_problems.append(f"FileX filename {name!r} has {len(name)} characters; DSSAT "
                                  "accepts at most 12. Rename the FileX to at most 12 "
                                  "characters, including the extension (DSSAT's 8.3 style).")
        stations = {row["station"] for row in rows if "station" in row}
        if not edit_identity and "WSTA" in values and len(stations) == 1:
            station = stations.pop()
            expected = values["WSTA"][:4]
            if station != expected:
                filex_problems.append(f"FileX WSTA {values['WSTA']!r} expects station "
                                     f"{expected!r}, but the weather template has station "
                                     f"{station!r}. Make the station codes exactly equal; "
                                     "filenames are case-sensitive on Linux.")
        days = [row["date"] for row in rows if "date" in row]
        sdate = values.get("SDATE") if values.get("START") == "S" else None
        start_date, skip_reason = ((override_start, None) if override_start is not None
                                   else _simulation_start_date(sdate, days))
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
        elif sdate is not None and days:
            parsed = _parse_sdate(sdate)
            if parsed is not None and not any(
                    (day.year % 100, day.timetuple().tm_yday) == parsed for day in days):
                start = values["SDATE"]
                filex_problems.append(f"FileX start year {start[:2]} day {start[2:]} is not "
                                     f"covered by weather data ({min(days)} to {max(days)}). "
                                     "Supply weather for the simulation's start date.")
        if override_start is not None and days and not _overrides_section(
                experiment_data, self.treatment, "irrigation",
                rotation=components[0]['R'] if len(components) > 1 else None):
            irrigation = [_simulation_start_date(text, days)[0]
                          for text in _irrigation_dates(self.filex, self.treatment)]
            irrigation = [day for day in irrigation if day is not None]
            if irrigation and min(irrigation) < override_start:
                filex_problems.append(f"Controls start_date {override_start.isoformat()!r} is "
                                     f"after the FileX's first irrigation date {min(irrigation)}; "
                                     "DSSAT stops with error IPIRR. Start on or before that date, "
                                     "or give irrigation in the management data.")
        soil_problems, soil_depth, template_id = [], None, None
        if self.soil is not None:
            soil_rows, soil_problems = _parse_soil(self.soil)
            if isinstance(self.soil, dict):
                soil_problems.append("Soil data per field needs a FileX template. "
                                     "Supply one soil source for a FileX.")
            if not soil_problems:
                soil_depth = max(row["slb"] for row in soil_rows)
                template_id = soil_rows[0]["soil_id"]
            soil_ids = {row["soil_id"] for row in soil_rows if "soil_id" in row}
            soil_id = values.get("ID_SOIL")
            if not edit_identity and (not soil_id or soil_id == "-99"):
                soil_problems.append("FileX has no readable ID_SOIL in the selected "
                                     "treatment's FIELDS row. Supply ID_SOIL "
                                     "equal to the soil template's soil_id.")
            elif not edit_identity and len(soil_ids) == 1:
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
        report.extend(sequence_report)
        if self.management is not None:
            if load_problems:
                problems.extend(load_problems)
                report.extend(_report_lines("Management data", load_problems))
            else:
                management_problems, management_report = _check_management(
                    checked_data, self.filex, self.treatment, rows, start_date, soil_depth,
                    start_date_note=skip_reason, check_harvest=False,
                )
                problems.extend(management_problems)
                report.extend(management_report)
        name = None if len(components) > 1 else self.name
        if (edit_identity or name not in (None, "base")) and not problems:
            try:
                _identity_text(Path(self.filex).read_bytes().decode("latin-1"),
                               int(self.treatment), name,
                               rows[0]["station"] if edit_identity else None,
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
        and writes template weather or copies stock weather files unchanged.
        For a template, creates the folder beside its YAML (or in cwd for a dict),
        writes the FileX and SOIL.SOL, and copies the crop's genotype files from
        Genotype beside the DSSAT executable. Experiment edits then apply as usual.
        With management data, adds a new level for each section given (planting,
        irrigation, fertilizer, cultivar, initial conditions, controls) in the copy
        and repoints only the selected treatment; the original FileX is never changed.
        With experiment overrides, writes the weather station and supplied soil
        ID into that field. Independently writes name into the copied treatment,
        except for sequences, None and "base", which retain the FileX names.
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
        experiment_data, load_problems = _load_management(self.management)
        problems, _ = self._check_inputs(experiment_data, load_problems)
        if problems:
            raise DSSATCheckError(problems)
        if self.filex_template is not None:
            prepared = _write_template_simulation(self, experiment_data=experiment_data)
        else:
            components = _rotation_components(self.filex, self.treatment)
            override_start = _controls_start_date(experiment_data, self.treatment)
            values, _ = _read_filex(self.filex, self.treatment, start_date=override_start)
            rows, _ = _simulation_weather(self, values, experiment_data, components)
            station = rows[0]["station"] if _overrides_section(experiment_data, self.treatment) else None
            if station is not None:
                values["WSTA"] = station
            soil_rows, _ = _parse_soil(self.soil) if self.soil is not None else ([], [])
            filex = Path(self.filex).resolve()
            sim_folder = _create_dated_folder(filex.parent, "dssat_sim_", "simulation folder")
            shutil.copy2(filex, sim_folder / filex.name)
            for sibling in filex.parent.iterdir():
                if self.soil is not None and sibling.suffix.upper() == ".SOL":
                    continue
                if sibling.is_file() and sibling.suffix.upper() in (".SOL", ".CUL", ".ECO", ".SPE"):
                    shutil.copy2(sibling, sim_folder / sibling.name)
            soil_id = soil_rows[0]["soil_id"] if soil_rows and station is not None else None
            _write_management(sim_folder / filex.name, self.treatment, experiment_data,
                              name=None if len(components) > 1 else self.name,
                              station=station, soil_id=soil_id)
            _write_rotation_data(sim_folder / filex.name, self.treatment, experiment_data)
            _write_simulation_weather(self.weather, rows, sim_folder, values)
            if self.soil is not None:
                write_soil_file(soil_rows, sim_folder / "SOIL.SOL")
            prepared = sim_folder / filex.name

        components = _rotation_components(prepared, self.treatment)
        result = (_run_sequence(prepared, self.treatment, components, self.executable)
                  if len(components) > 1 else
                  run(prepared, treatment=int(self.treatment), executable=self.executable))
        _check_missing_weather(result)
        return result
