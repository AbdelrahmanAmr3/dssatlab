"""Check template simulations and per-field sources before writing any files."""

from datetime import date

from .controls import _controls_start_date, _season_coverage
from .cultivar import _template_data_dir
from .errors import DSSATCheckError
from .experiment import _check_date
from .filex_template import (_check_filex_template, _load_filex_template,
                             _template_crop_entry, _template_treatment_fields,
                             _template_treatment_names, _shared_field_problems,
                             _template_genotype_files)
from .filex_write import _identity_text
from .management import _check_management, _report_lines
from .soil import _parse_soil
from .stock import _parse_template_weather, _soil_source_problems, _weather_source_problems


def _parse_field_data(source, count, kind):
    """Check field keys against fields 1..count (any keys if count is None) and parse each source."""
    label = f"{kind.capitalize()} data"
    parser = _parse_template_weather if kind == "weather" else _parse_soil
    source_problems = _weather_source_problems if kind == "weather" else _soil_source_problems
    if problems := source_problems(source, template=True):
        return {}, problems, _report_lines(label, problems)
    if source is None and kind == "soil":
        problems = ["Soil data is required with a FileX template. Supply soil=..."]
        return {}, problems, _report_lines(label, problems)
    sources = source if isinstance(source, dict) else {1: source}
    normalized, invalid = {}, []
    for key, value in sources.items():
        if (type(key) is int or isinstance(key, str) and key.isascii() and key.isdigit()):
            number = int(key)
            if number not in normalized:
                normalized[number] = value
                continue
        invalid.append(repr(key))
    if invalid or count is not None and set(normalized) != set(range(1, count + 1)):
        count = count or max(normalized, default=1)
        keys = ", ".join([str(k) for k in sorted(normalized)] + invalid) or "none"
        example = ", ".join(f"{k}: ..." for k in range(1, count + 1))
        problems = [f"FileX template has fields 1 to {count}, but {kind} data has fields {keys}. "
                    f"Supply {kind} data for every field: {kind}={{{example}}}."]
        return {}, problems, _report_lines(label, problems)
    rows, problems, report = {}, [], []
    for number, value in sorted(normalized.items()):
        rows[number], found = parser(value)
        field_label = f"{label}, field {number}" if isinstance(source, dict) else label
        if isinstance(source, dict):
            found = [p.replace(label, field_label, 1) if p.startswith(label)
                     else f"{field_label}: {p}" for p in found]
        problems.extend(found)
        report.extend(_report_lines(field_label, found))
    return rows, problems, report


def _check_template_simulation(sim, experiment_data, load_problems):
    """Check template inputs and the loaded experiment data dict in memory."""
    from .filex_skeleton import _render_filex

    data, template_problems = _load_filex_template(sim.filex_template)
    data_dir = None
    try:
        data_dir = _template_data_dir(sim.executable)
    except DSSATCheckError as error:
        template_problems.extend(error.problems)
    # Shape/value checks still run when executable discovery fails.
    if data is not None:
        template_problems.extend(_check_filex_template(data, data_dir))
    if isinstance(data, dict) and "rotation" in data:
        # Import only at dispatch: rotation uses the shared skeleton helpers.
        from .rotation import _check_rotation_simulation
        return _check_rotation_simulation(sim, data, data_dir, template_problems,
                                          experiment_data, load_problems)
    fields = _template_treatment_fields(data) if isinstance(data, dict) else [1]
    # Template checks report malformed field lists; skip comparing their keys.
    if (not isinstance(fields, list) or not fields
            or any(type(k) is not int or not 1 <= k <= 99 for k in fields)):
        fields = [1]
        count = None
    else:
        count = max(fields) if not any("treatment_fields" in p for p in template_problems) else None
    weather_fields, weather_problems, weather_report = _parse_field_data(sim.weather, count, "weather")
    soil_fields, soil_problems, soil_report = _parse_field_data(sim.soil, count, "soil")
    for rows, found, kind in ((weather_fields, weather_problems, "weather"),
                              (soil_fields, soil_problems, "soil")):
        if not found:
            template_problems.extend(_shared_field_problems(rows, kind))
    selected_field = fields[int(sim.treatment) - 1] if (
        str(sim.treatment).isascii() and str(sim.treatment).isdigit()
        and 1 <= int(sim.treatment) <= len(fields)) else 1
    weather, soil = weather_fields.get(selected_field, []), soil_fields.get(selected_field, [])
    count = len(_template_treatment_names(data))
    valid_treatment = (not isinstance(sim.treatment, bool) and isinstance(sim.treatment, (int, str))
                       and str(sim.treatment).isascii() and str(sim.treatment).isdigit()
                       and 1 <= int(sim.treatment) <= count)
    if not valid_treatment:
        if count == 1:
            template_problems.append("FileX template has only treatment 1. Supply treatment=1.")
        else:
            template_problems.append(f"FileX template has treatments 1 to {count}. "
                                     f"Supply treatment=<k> with 1 <= k <= {count}.")
    # Unrelated value errors must not hide the selected entry's date checks.
    entry = (_template_crop_entry(data, sim.treatment) if isinstance(data, dict)
             and ("crops" not in data or valid_treatment) else None)
    start = _controls_start_date(experiment_data, sim.treatment)
    if start is None and isinstance(entry, dict) and isinstance(entry.get("planting"), dict):
        planting_date = entry["planting"].get("date")
        if not _check_date(planting_date, "planting date"):
            start = date.fromisoformat(planting_date)
    text = None
    if not (weather_problems or soil_problems or template_problems):
        _, text = _render_filex(data, weather_fields, soil_fields)
    if isinstance(data, dict):
        for path in _template_genotype_files(data, data_dir):
            if not path.is_file():
                template_problems.append(f"FileX template: missing genotype file {path}. "
                                         "Supply this file in the data directory's Genotype folder.")
    days = [row["date"] for row in weather if "date" in row]
    template_problems.extend(_season_coverage(experiment_data, sim.treatment, start, days))
    if start is not None and days and start not in days:
        template_problems.append(f"Simulation start date {start} is not covered by weather "
                                 f"data ({min(days)} to {max(days)}). Supply weather for that date.")
    if isinstance(entry, dict) and "harvest_date" in entry:
        harvest = entry["harvest_date"]
        location = "FileX template"
        if "crops" in data:
            number = data["treatment_crops"][int(sim.treatment) - 1]
            location += f", crops[{number}]"
        if (not _check_date(harvest, "harvest_date") and days
                and date.fromisoformat(harvest) not in days):
            template_problems.append(f"{location}, harvest_date: {harvest} is not covered by "
                                     f"weather data ({min(days)} to {max(days)}). "
                                     "Supply weather for that date.")
    problems = weather_problems + soil_problems + template_problems
    report = weather_report + soil_report + _report_lines("FileX template", template_problems)
    if sim.management is not None:
        if load_problems:
            problems.extend(load_problems)
            report.extend(_report_lines("Management data", load_problems))
        else:
            found, lines = _check_management(
                experiment_data, None, sim.treatment, weather, start,
                text=text, filex_template=data, data_dir=data_dir)
            problems.extend(found)
            report.extend(lines)
    if not problems and text is not None:
        selected = int(sim.treatment)
        has_override = (isinstance(experiment_data, dict)
                        and isinstance(experiment_data.get("treatments"), dict)
                        and any(int(k) == selected and v for k, v in experiment_data["treatments"].items()))
        if has_override or sim.name not in (None, "base"):
            try:
                _identity_text(text, selected, sim.name, weather[0]["station"], soil[0]["soil_id"])
            except ValueError as error:
                problems.append(f"FileX: {error}")
                report.extend(_report_lines("FileX identity", [str(error)]))
    return problems, report
