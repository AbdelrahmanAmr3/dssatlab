"""Select weather inputs and narrowly check copied DSSAT climate files."""

from pathlib import Path
import shutil

from .climate_file import _read_climate_file
from .controls import _selected_controls
from .filex import _section_row
from .experiment import _overrides_section


def _split_weather_inputs(source):
    """Separate one CLI from WTH paths; leave weather-template data intact."""
    paths = source if isinstance(source, list) else [source]
    climate = [Path(path) for path in paths if isinstance(path, (str, Path))
               and Path(path).suffix.upper() == ".CLI"]
    if not climate:
        return source, [], []
    problems = []
    if len(climate) > 1:
        problems.append("Weather input contains more than one climate file. "
                        "Checked the supplied .CLI paths. Supply only one climate file.")
    if not all(isinstance(path, (str, Path)) and Path(path).suffix.upper() in (".CLI", ".WTH")
               for path in paths):
        problems.append("Weather input mixes a climate file with other weather data. "
                        "Checked weather input types. Supply a .CLI alone or with .WTH paths.")
    weather = [Path(path) for path in paths if isinstance(path, (str, Path))
               and Path(path).suffix.upper() == ".WTH"]
    return weather or None, climate, problems


def _template_climate_problems(source):
    """Reject CLI inputs, including per-field sources, for a FileX template."""
    sources = source.values() if isinstance(source, dict) else [source]
    if any(_split_weather_inputs(value)[1] for value in sources):
        return ["A climate file cannot supply weather for a FileX template. "
                "Checked the template's weather inputs. Supply weather data rows for every field."]
    return []


def _weather_requirements(sim, experiment_data, components):
    """Read each run component's SM and field, applying a weather-source edit.

    Missing METHODS rows, blank WTHER and -99 retain the existing measured-weather
    behavior. Unreadable FileX levels are reported by the ordinary FileX checks.
    """
    if not components:
        return []
    try:
        text = Path(sim.filex).read_text(encoding="latin-1")
    except (OSError, TypeError, ValueError):
        return []
    override = _selected_controls(experiment_data, sim.treatment).get("weather_source")
    requirements = []
    for row in components:
        if not row["SM"].isdigit():
            continue
        level = int(row["SM"])
        method = "M"
        try:
            method = _section_row(text, "SIMULATION CONTROLS", "N", level, ("WTHER",))["WTHER"]
        except ValueError:
            pass
        if override in ("M", "W", "S"):
            method = override
        method = "M" if method in ("", "-99") else method
        try:
            station = _section_row(text, "FIELDS", "L", int(row["FL"]), ("WSTA",))["WSTA"]
        except (ValueError, TypeError):
            station = ""
        requirement = (level, method, station)
        if requirement not in requirements:
            requirements.append(requirement)
    return requirements


def _measured_weather_source(sim, experiment_data, components):
    """Return daily input only if a run component uses M; never parse a CLI as CSV."""
    source, _, _ = _split_weather_inputs(sim.weather)
    requirements = _weather_requirements(sim, experiment_data, components)
    return source if not requirements or any(method == "M" for _, method, _ in requirements) else None


def _check_weather_requirements(sim, experiment_data, components, rows=()):
    """Check WTHER, required filenames and unused inputs before any run writes."""
    source, climate, split_problems = _split_weather_inputs(sim.weather)
    if split_problems:
        return []  # The weather-source checks already report malformed input lists.
    requirements = _weather_requirements(sim, experiment_data, components)
    if rows and "station" in rows[0] and _overrides_section(experiment_data, sim.treatment):
        changed_requirements = set()
        for component in components:
            if component["FL"] == components[0]["FL"]:
                changed_requirements.update(_weather_requirements(sim, experiment_data, [component]))
        requirements = [(level, method, rows[0]["station"] if (level, method, station)
                         in changed_requirements else station) for level, method, station in requirements]
    problems, checked_methods = [], set()
    for level, method, station in requirements:
        where = f"FileX WTHER '{method}' in controls level {level} (treatment {int(sim.treatment)})"
        if method not in ("M", "W", "S"):
            problems.append(f"{where}: unsupported weather source. Checked the run treatment's "
                            "SM level after experiment edits. Set WTHER to one of M, W, S.")
        elif method == "M":
            if source is None:
                problems.append(f"{where}: needs weather data. Checked the supplied weather "
                                "inputs. Supply weather data or .WTH paths for WTHER M.")
        elif station and len(station) in (4, 8):
            expected = station[:4].upper() + ".CLI"
            if not climate:
                problems.append(f"{where}: missing climate file {expected}. Checked WSTA "
                                f"{station!r}. Supply {expected} from DSSAT's Weather/Climate folder.")
            elif climate[0].name.upper() != expected:
                problems.append(f"{where}: climate file {climate[0].name} does not match "
                                f"{expected}. Checked WSTA {station!r} and the copied filename. "
                                f"Supply the matching {expected} from DSSAT's Weather/Climate folder.")
            else:
                if method not in checked_methods:
                    problems.extend(_read_climate_file(climate[0], method))
                    checked_methods.add(method)
    methods = {method for _, method, _ in requirements}
    problems.extend(_unused_weather_problems(source, climate, methods))
    if len(components) > 1:
        if len(methods) > 1:
            problems.append(f"Sequence treatment {sim.treatment} has different WTHER codes "
                            f"({', '.join(sorted(methods))}). Checked every component's controls "
                            "level after experiment edits. Use one WTHER across the sequence.")
        controls = _selected_controls(experiment_data, sim.treatment)
        if methods == {"M"} and "replicates" not in controls:
            try:
                general = _section_row(Path(sim.filex).read_text(encoding="latin-1"),
                                       "SIMULATION CONTROLS", "N", int(components[0]["SM"]),
                                       ("GENERAL",))
                nreps = general.get("NREPS", "1")
            except ValueError:
                nreps = "1"
            if nreps not in ("", "-99") and (not nreps.lstrip("-").isdigit() or int(nreps) != 1):
                problems.append(f"FileX NREPS {nreps} for sequence treatment {sim.treatment}: with "
                                "measured weather every replicate repeats the same rows. Checked "
                                "the first component's GENERAL NREPS and sequence WTHER. Set NREPS to 1.")
    return problems


def _unused_weather_problems(source, climate, methods):
    """Check supplied input against weather sources across the selected run treatments."""
    problems = []
    if climate and methods and not methods & {"W", "S"}:
        problems.append(f"Supplied climate file {climate[0].name} is unused. Checked all run "
                        "treatments' weather sources. Remove the climate file or use WTHER W or S.")
    if source is not None and methods & {"W", "S"} and "M" not in methods:
        problems.append("Supplied weather data is unused; DSSAT would ignore it. Checked all run "
                        "treatments' weather sources. Remove it from weather= or set WTHER to M.")
    return problems


def _coverage_weather_rows(sim, experiment_data, components, rows):
    """Check daily coverage only for a uniform measured-weather treatment."""
    methods = {method for _, method, _ in _weather_requirements(sim, experiment_data, components)}
    return rows if not methods or methods == {"M"} else []


def _check_weather_controls(text, treatment, controls, where, *, template=False):
    """Check replicate edits in their run context; templates retain measured weather."""
    from .sequence import _rotation_components

    problems = []
    components = _rotation_components(None, treatment, text=text) if text else []
    if template and controls.get("weather_source") in ("W", "S"):
        problems.append(f"{where}, controls, field 'weather_source': generated weather needs a copied "
                        "FileX. Checked the FileX template controls. Use a copied FileX for generated weather.")
    reps = controls.get("replicates")
    if type(reps) is not int or not 1 < reps <= 99999:
        return problems
    if not text:
        return problems  # Ordinary checks explain an unreadable FileX.
    if len(components) < 2:
        problems.append(f"{where}, controls, field 'replicates': DSSAT ignores NREPS outside a sequence. "
                        "Checked the treatment's TREATMENTS rows. Set replicates to 1 or use a sequence.")
    else:
        methods = set()
        for component in components:
            method = controls.get("weather_source")
            if method is None:
                try:
                    method = _section_row(text, "SIMULATION CONTROLS", "N", int(component["SM"]),
                                          ("WTHER",))["WTHER"]
                except ValueError:
                    method = "M"
            methods.add("M" if method in ("", "-99") else str(method))
        if "M" in methods:
            problems.append(f"{where}, controls, field 'replicates': with measured weather every "
                            "replicate repeats the same rows. Checked the sequence's effective WTHER. "
                            "Set replicates to 1 or use weather_source W or S with a climate file.")
    return problems


def _select_batch_weather(simulations, source):
    """Check unused input across one scenario, then give each Simulation its required kind."""
    from .management_file import _load_management
    from .sequence import _rotation_components

    daily, climate, problems = _split_weather_inputs(source)
    if problems:
        return problems  # Keep malformed sources intact for the ordinary checks.
    selected, methods = [], set()
    for sim in simulations:
        data, _ = _load_management(sim.management)
        needs = {method for _, method, _ in _weather_requirements(
            sim, data, _rotation_components(sim.filex, sim.treatment))}
        methods.update(needs)
        selected.append((sim, needs))
    problems.extend(_unused_weather_problems(daily, climate, methods))
    for sim, needs in selected:
        if needs == {"M"}:
            sim.weather = daily
        elif needs and needs <= {"W", "S"}:
            sim.weather = climate[0] if climate else None
    return problems


def _copy_climate_file(source, folder):
    """Copy the checked CLI unchanged under its uppercase filename."""
    for path in _split_weather_inputs(source)[1]:
        shutil.copy2(path, folder / path.name.upper())
