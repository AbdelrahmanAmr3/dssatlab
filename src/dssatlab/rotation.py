"""Check and render a FileX template's rotation as one sequence."""

from datetime import date, timedelta
import re

from .experiment import _check_date, _check_fields
from .cultivar import _CROPS
from .controls import _controls_start_date, _selected_controls
from .filex_skeleton import _field_lines, _control_lines
from .template_checks import _parse_field_data
from .filex_template import _check_template_crop, _template_genotype_files
from .management import _check_management, _report_lines
from .sequence import _sequence_coverage, _sequence_experiment_data, _sequence_stop
from .filex_write import _columns, _planting_row, _PLANTING_HEADER, _repoint
from .weather import _dssat_date, _show_value
from .operations import _harvest_end


def _check_rotation_template(data, data_dir):
    """Check shape and reuse single-crop value checks, with component positions."""
    where = "FileX template"
    excluded = ("crop", "cultivar", "planting", "harvest_date", "treatments", "treatment_fields")
    problems = _check_fields(data, ("treatment_name", "rotation"), excluded, where, "FileX")
    for key in excluded:
        if key in data:
            problems.append(f"{where}, rotation: cannot be mixed with {key}. "
                            "Remove it from the top level and supply treatment_name and rotation.")
    if "treatment_name" in data:
        name = data["treatment_name"]
        if not isinstance(name, str) or not re.fullmatch(r"[ -~]{1,25}", name) or not name.strip():
            problems.append(f"{where}, treatment_name: found {_show_value(name)}. "
                            "Supply 1-25 printable ASCII characters, not just spaces.")
    components = data["rotation"]
    if not isinstance(components, list) or not 2 <= len(components) <= 99:
        problems.append(f"{where}, rotation: found {_show_value(components)}. "
                        "Supply a list of 2 to 99 rotation components.")
    if not isinstance(components, list):
        return problems
    valid_components = {}
    for number, component in enumerate(components, 1):
        location = f"{where}, rotation[{number}]"
        found = []
        if not isinstance(component, dict):
            found.append(f"{location}: expected a dict. Supply a crop with cultivar and "
                         "planting, or a fallow with end_date.")
        elif component.get("crop") == "fallow":
            found.extend(_check_fields(component, ("crop", "end_date"), ("start_date",), location, "FileX"))
            if "end_date" in component:
                found.extend(_check_date(component["end_date"], f"{location}, end_date"))
            if number == 1:
                if "start_date" not in component:
                    found.append(f"{location}: a leading fallow needs start_date. "
                                 "Supply start_date before end_date.")
                else:
                    found.extend(_check_date(component["start_date"], f"{location}, start_date"))
        else:
            found.extend(_check_fields(component, ("crop", "cultivar", "planting"),
                                       ("harvest_date", "start_date") if number > 1 else
                                       ("harvest_date",), location, "FileX"))
            found.extend(p.replace(where, location, 1)
                         for p in _check_template_crop(component, data_dir))
        if isinstance(component, dict) and number > 1 and "start_date" in component:
            found.append(f"{location}, start_date: only a leading fallow takes start_date. "
                         "Remove start_date from this component.")
        problems.extend(found)
        # Unrelated value problems must not hide rotation date problems.
        if not isinstance(component, dict):
            continue
        crop = component.get("crop")
        if crop == "fallow":
            dates = [component.get("end_date")]
            if number == 1:
                dates.append(component.get("start_date"))
        elif isinstance(crop, str) and crop in _CROPS:
            planting = component.get("planting")
            if not isinstance(planting, dict):
                continue
            dates = [planting.get("date")]
            if "harvest_date" in component:
                dates.append(component["harvest_date"])
        else:
            continue
        if all(not _check_date(value, location) for value in dates):
            valid_components[number] = component
    problems.extend(_check_rotation_dates(components, valid_components, where))
    return problems


def _check_rotation_dates(components, valid_components, where):
    """Check components with valid dates: leading fallow, end, order, closure."""
    problems = []
    if 1 in valid_components and valid_components[1].get("crop") == "fallow":
        first = valid_components[1]
        if first["start_date"] >= first["end_date"]:
            problems.append(f"{where}, rotation[1], start_date: {first['start_date']} is not "
                            f"before end_date ({first['end_date']}). Supply start_date before end_date.")
    last_number = len(components)
    if last_number in valid_components:
        last = valid_components[last_number]
        if last.get("crop") != "fallow" and not last.get("harvest_date"):
            problems.append(f"{where}, rotation[{last_number}]: the last component needs a known end "
                            "so the next cycle can start on time. Make it a fallow with end_date, "
                            "or give it a harvest_date.")
    for number in range(2, len(components) + 1):
        if (number - 1) in valid_components and number in valid_components:
            prev, curr = valid_components[number - 1], valid_components[number]
            if prev.get("crop") == "fallow":
                prev_end = prev["end_date"]
            elif prev.get("harvest_date"):
                prev_end = prev["harvest_date"]
            else:
                prev_end = prev["planting"]["date"]
            if curr.get("crop") == "fallow":
                curr_start, field = curr["end_date"], "end_date"
            else:
                curr_start, field = curr["planting"]["date"], "planting date"
            if date.fromisoformat(curr_start) <= date.fromisoformat(prev_end):
                problems.append(f"{where}, rotation[{number}], {field}: {curr_start} is not after "
                                f"rotation[{number - 1}]'s end ({prev_end}). "
                                "DSSAT would move it a year later. Supply rotation dates in order.")
    if 1 in valid_components and last_number in valid_components:
        first, last = valid_components[1], valid_components[last_number]
        last_end = last.get("end_date") if last.get("crop") == "fallow" else last.get("harvest_date")
        if last_end and (first.get("crop") != "fallow" or first["start_date"] < first["end_date"]):
            problems.extend(_check_cycle_closure(
                _rotation_start_date(components), date.fromisoformat(last_end), f"{where}, rotation",
                leading_fallow=first.get("crop") == "fallow"))
    return problems


def _check_cycle_closure(start_date, end_date, where, *, leading_fallow=False):
    """Check DSSAT's day-of-year boundary between successive rotation cycles."""
    problems = []
    label = "simulation start" if leading_fallow else "first planting"
    fix = "Start the leading fallow after January 1." if leading_fallow else "Plant the first crop after January 1."
    first_doy, last_doy = start_date.timetuple().tm_yday, end_date.timetuple().tm_yday
    if first_doy == 1:
        problems.append(
            f"{where}: the {label} is on day 1 of the year "
            f"({start_date}), so the last component cannot end before it in the year; "
            f"DSSAT would start the next cycle a year late. {fix}"
        )
    elif last_doy >= first_doy:
        example = date(end_date.year, 1, 1) + timedelta(days=first_doy - 2)
        problems.append(
            f"{where}: the last component ends on {end_date} "
            f"(day {last_doy} of the year), not before the {label}'s day of the year "
            f"(day {first_doy}, {start_date}); DSSAT would start the next cycle "
            f"a year late. End the last component before day {first_doy}, "
            f"for example on {example.isoformat()}."
        )
    return problems


def _rotation_start_date(components):
    """Return the checked leading fallow's start or first crop's planting date."""
    first = components[0]
    return date.fromisoformat(first["start_date"] if first["crop"] == "fallow" else first["planting"]["date"])


def _rotation_cycle_years(components, experiment_data=None, start=None):
    """Fewest cycle years from start (SDATE) whose DSSAT stopping day reaches the end.

    Date-order and cycle-closure checks belong to the caller. Do not clamp or
    repair dates here.
    """
    last = components[-1]
    end = last.get("end_date") if last["crop"] == "fallow" else last["harvest_date"]
    # SDATE stays put when the first planting is edited, so count years from it.
    start = start or _rotation_start_date(components)
    end = date.fromisoformat(end)
    from .rotation_data import _rotation_keys
    treatments = experiment_data.get('treatments', {}) if isinstance(experiment_data, dict) else {}
    if isinstance(treatments, dict):
        for key, entry in treatments.items():
            if (not isinstance(entry, dict) or not str(key).isascii()
                    or not str(key).isdigit() or int(key) != 1):
                continue
            rows = [dict(R=str(i)) for i in range(1, len(components) + 1)]
            edits, _ = _rotation_keys(entry.get('rotation', {}), rows, '')
            end = _harvest_end(edits.get(len(components)), end, 'R') or end
            break
    # Keep the cycle-year choice tied to CSM's shared stopping boundary.
    years = 1
    while (stop := _sequence_stop(start, years)) is not None and stop < end:
        years += 1
    return years


def _render_rotation(data, weather_rows, soil_rows):
    """Return a sequence filename and text from checked template/weather/soil."""
    components, name = data["rotation"], data["treatment_name"]
    weather = weather_rows[1] if isinstance(weather_rows, dict) else weather_rows
    soil = soil_rows[1] if isinstance(soil_rows, dict) else soil_rows
    start = _rotation_start_date(components)
    day, station = _dssat_date(start), weather[0]["station"]
    stem = f"{station}{start.year % 100:02d}01"
    years = _rotation_cycle_years(components)
    treatments, cultivars, plantings, harvests, controls = [], [], [], [], []
    for number, component in enumerate(components, 1):
        mp = mh = 0
        if component["crop"] == "fallow":
            crop, model, symbi, code = "FA", "", "N", "IB0001"
            end = component["end_date"]
        else:
            crop, model, _, _, symbi = _CROPS[component["crop"]]
            code, end = component["cultivar"]["code"], component.get("harvest_date")
            mp = len(plantings) + 1
            plantings.append(_planting_row(_columns(_PLANTING_HEADER), mp, component["planting"]))
        if end is not None:
            mh = len(harvests) + 1
            harvest_day = _dssat_date(date.fromisoformat(end))
            harvests.append(f"{mh:2d} {harvest_day} GS000   -99   -99   -99   -99 -99")
        cultivars.append(f"{number:2d} {crop} {code} -99")
        treatments.append(f" 1{number:2d} 0 0 {name:<25} {number:2d}  1  0  0 {mp:2d}"
                          f"  0  0  0  0  0  0 {mh:2d} {number:2d}")
        controls.extend(_control_lines(number, years if number == 1 else 1,
                                       day, name, model, symbi, bool(mh)))
    lines = [
        f"*EXP.DETAILS: {stem}SQ {name}", "",
        "*GENERAL", "@PEOPLE", " DSSATLab", "@ADDRESS", " -99", "@SITE", f" {station}", "",
        "*TREATMENTS                        -------------FACTOR LEVELS------------",
        "@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM",
        *treatments, "", "*CULTIVARS", "@C CR INGENO CNAME", *cultivars, "",
        *_field_lines({1: weather}, {1: soil}, 1),
        "*PLANTING DETAILS", _PLANTING_HEADER, *plantings, "",
    ]
    if harvests:
        lines.extend(["*HARVEST DETAILS", "@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME",
                      *harvests, ""])
    lines.extend(["*SIMULATION CONTROLS", *controls])
    return f"{stem}.SQX", "\n".join(lines)


def _check_rotation_simulation(sim, data, data_dir, template_problems, experiment_data, load_problems):
    """Check one field and sequence controls without writing a temporary FileX."""
    weather, wp, wr = _parse_field_data(sim.weather, 1, "weather")
    soil, sp, sr = _parse_field_data(sim.soil, 1, "soil")
    for kind in ("weather", "soil"):
        if isinstance(getattr(sim, kind), dict):
            template_problems.append(f"{kind.capitalize()} data per field needs treatment_fields. "
                                     f"Supply one {kind} source for a rotation FileX template.")
    valid_treatment = (not isinstance(sim.treatment, bool)
                       and isinstance(sim.treatment, (int, str))
                       and re.fullmatch(r"0*1", str(sim.treatment)))
    if not valid_treatment:
        template_problems.append("FileX template has only treatment 1. Supply treatment=1.")
    text, start, components, sequence_report = None, None, [], []
    # The checked template already fixes R=1..N, FL=1 and NREPS=1.
    if not template_problems:
        components = [{"CR": "FA" if c["crop"] == "fallow" else _CROPS[c["crop"]][0]}
                      for c in data["rotation"]]
        crops = ", ".join(c["CR"] for c in components)
        sequence_report = [f"FileX: treatment 1 is a sequence of {len(components)} rotation "
                           f"components (R 1-{len(components)}: {crops}); "
                           "it runs in DSSAT's sequence mode."]
        start = (_controls_start_date(experiment_data, 1)
                 or _rotation_start_date(data["rotation"]))
        days = [row["date"] for row in weather.get(1, []) if "date" in row]
        template_problems.extend(_sequence_coverage(
            experiment_data, 1, start, days, _rotation_cycle_years(data["rotation"], experiment_data, start),
            template=data["rotation"]))
        if days and start not in days:
            template_problems.append(f"Simulation start date {start} is not covered by weather "
                                     f"data ({min(days)} to {max(days)}). Supply weather for that date.")
        if not (wp or sp):
            _, text = _render_rotation(data, weather, soil)
    for path in _template_genotype_files(data, data_dir) if isinstance(data["rotation"], list) else []:
        if not path.is_file():
            template_problems.append(f"FileX template: missing genotype file {path}. "
                                     "Supply this file in the data directory's Genotype folder.")
    found, checked_data = _sequence_experiment_data(experiment_data, 1, components)
    template_problems.extend(found)
    problems = wp + sp + template_problems
    report = wr + sr + _report_lines("FileX template", template_problems) + sequence_report
    if sim.management is not None:
        if load_problems:
            found, lines = load_problems, _report_lines("Management data", load_problems)
        else:
            found, lines = _check_management(checked_data, None, sim.treatment,
                                             weather.get(1, []), start, text=text,
                                             rotation_template=data["rotation"], data_dir=data_dir)
        problems.extend(found)
        report.extend(lines)
    return problems, report


def _write_rotation_controls(filex, experiment_data, start, components):
    """Edit the checked sequence's first controls level, keeping component levels."""
    # The normal controls writer adds a new level and repoints SM; sequences
    # need NYERS/SDATE in level 1, so edit that level in this generated FileX.
    controls = _selected_controls(experiment_data, 1)
    lines = filex.read_text(encoding="ascii").splitlines(keepends=True)
    years = controls.get('years', _rotation_cycle_years(components, experiment_data, start))
    for key, column, value in (("years", "NYERS", years),
                               ("start_date", "SDATE", _dssat_date(start))):
        if key == 'years' or key in controls:
            _repoint(lines, 1, column, value, "SIMULATION CONTROLS", "N")
    filex.write_bytes("".join(lines).encode("ascii"))
