"""Check and render a FileX template's rotation as one sequence."""

from datetime import date, timedelta
import re

from .experiment import _check_date, _check_fields
from .cultivar import _CROPS
from .filex_template import _check_template_crop
from .filex_write import _columns, _planting_row, _PLANTING_HEADER
from .weather import _dssat_date, _show_value


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
    if not isinstance(components, list) or not 2 <= len(components) <= 9:
        problems.append(f"{where}, rotation: found {_show_value(components)}. "
                        "Supply a list of 2 to 9 rotation components.")
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
            found.extend(_check_fields(component, ("crop", "end_date"), (), location, "FileX"))
            if "end_date" in component:
                found.extend(_check_date(component["end_date"], f"{location}, end_date"))
        else:
            found.extend(_check_fields(component, ("crop", "cultivar", "planting"),
                                       ("harvest_date",), location, "FileX"))
            found.extend(p.replace(where, location, 1)
                         for p in _check_template_crop(component, data_dir))
        problems.extend(found)
        if not found:
            valid_components[number] = component
    problems.extend(_check_rotation_dates(components, valid_components, where))
    return problems


def _check_rotation_dates(components, valid_components, where):
    """Check dates of components whose shape passed: leading crop, end, order, closure."""
    problems = []
    if 1 in valid_components and valid_components[1].get("crop") == "fallow":
        problems.append(f"{where}, rotation[1]: the first component must be a crop; "
                        "the simulation starts on its planting date. Move the fallow later in the rotation.")
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
        if first.get("crop") != "fallow":
            start_date = date.fromisoformat(first["planting"]["date"])
            last_end = last.get("end_date") if last.get("crop") == "fallow" else last.get("harvest_date")
            if last_end:
                end_date = date.fromisoformat(last_end)
                first_doy, last_doy = start_date.timetuple().tm_yday, end_date.timetuple().tm_yday
                if last_doy >= first_doy:
                    if first_doy > 1:
                        example = date(end_date.year, 1, 1) + timedelta(days=first_doy - 2)
                    else:
                        example = date(end_date.year - 1, 12, 31)
                    problems.append(
                        f"{where}, rotation: the last component ends on {last_end} "
                        f"(day {last_doy} of the year), not before the first planting's day of the year "
                        f"(day {first_doy}, {first['planting']['date']}); DSSAT would start the next cycle "
                        f"a year late. End the last component before day {first_doy}, "
                        f"for example on {example.isoformat()}."
                    )
    return problems


def _rotation_cycle_years(components):
    """Cycle years for checked components; the end plus one day gives the next cycle's year.

    Date-order and cycle-closure checks belong to the caller. Do not clamp or
    repair dates here: the end plus one day determines the next cycle's year.
    """
    last = components[-1]
    end = last.get("end_date") if last["crop"] == "fallow" else last["harvest_date"]
    start = date.fromisoformat(components[0]["planting"]["date"])
    end = date.fromisoformat(end)
    # Avoid overflowing datetime at 9999-12-31; only the resulting year is needed.
    next_year = end.year + 1 if (end.month, end.day) == (12, 31) else (end + timedelta(days=1)).year
    return next_year - start.year


def _render_rotation(data, weather_rows, soil_rows):
    """Return a sequence filename and text from checked template/weather/soil."""
    from .filex_skeleton import _field_lines, _control_lines

    components, name = data["rotation"], data["treatment_name"]
    weather = weather_rows[1] if isinstance(weather_rows, dict) else weather_rows
    soil = soil_rows[1] if isinstance(soil_rows, dict) else soil_rows
    start = date.fromisoformat(components[0]["planting"]["date"])
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
        treatments.append(f" 1 {number} 0 0 {name:<25} {number:2d}  1  0  0 {mp:2d}"
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
