"""Checks and report lines for Management data supplied as a plain dict."""

from datetime import date
from pathlib import Path
import re

from .filex import _section_row
from .cultivar import _CROPS, _check_cultivar
from .filex_write import _event_text, _planting_text
from .experiment import (_check_controls, _check_date, _check_fields,
                         _check_number, _check_treatment_key, _unknown_keys)
from .weather import _show_value
from .initial_conditions import _check_initial_conditions, _initial_conditions_text
from .soil_analysis import _check_soil_analysis, _soil_analysis_text
from .environment import _check_environment, _environment_text
from .controls import _check_inherited_planting, _check_planting_window, _controls_text


_REQUIRED = ("date", "method", "distribution", "population", "row_spacing", "depth")
_OPTIONAL = ("emergence_date", "emergence_population", "row_direction",
             "planting_material_weight", "transplant_age", "transplant_environment",
             "plants_per_hill", "sprout_length")


def _report_lines(label, problems, *, details=None):
    status = "REJECTED" if problems else "OK"
    indent = " " * (len(label) - len(label.lstrip()) + 2)
    details = problems if details is None else details
    return [f"{label}: {status}"] + [f"{indent}{problem}" for problem in details]


def _check_planting(planting, where, start_date=None, weather_range=None):
    if not isinstance(planting, dict) or not planting:
        return [f"{where}: planting must be a non-empty dict. Supply the required "
                f"fields: {', '.join(_REQUIRED)}; omit planting to keep the FileX Level."]
    problems = _check_fields(planting, _REQUIRED, _OPTIONAL, where)
    for field in _REQUIRED + _OPTIONAL:
        if field not in planting:
            continue
        value = planting[field]
        location = f"{where}, field {field!r}"
        if field in ("date", "emergence_date"):
            date_problems = _check_date(value, location)
            problems.extend(date_problems)
            if not date_problems and field == "date":
                d = date.fromisoformat(value)
                if start_date is not None and d < start_date:
                    problems.append(
                        f"{location}: planting date {_show_value(value)} is before simulation "
                        f"start date {_show_value(start_date.isoformat())}. Planting must be "
                        "on or after the simulation start date."
                    )
                problems.extend(_check_weather_date(value, location, weather_range))
        elif field in ("method", "distribution"):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]", value):
                problems.append(f"{location}: found {_show_value(value)}. Supply a "
                                "single ASCII letter for the DSSAT code.")
        else:
            number_problems = _check_number(value, location)
            if number_problems:
                problems.extend(number_problems)
                continue
            if field in ("population", "row_spacing") and value <= 0:
                unit = "plants per m2" if field == "population" else "cm"
                problems.append(f"{location}: found {_show_value(value)}. "
                                f"Supply a number above zero in {unit}.")
            elif field == "depth" and value < 0:
                problems.append(f"{location}: found {_show_value(value)}. "
                                "Supply a nonnegative depth in cm.")
    return problems


def _check_weather_date(value, location, weather_range):
    if weather_range is None or weather_range[0] <= date.fromisoformat(value) <= weather_range[1]:
        return []
    return [f"{location}: date {_show_value(value)} is outside weather range "
            f"({weather_range[0]} to {weather_range[1]}). Supply weather covering "
            "the date or choose a date within the weather range."]


def _check_event_field(value, field, location):
    if field in ("method", "material", "application"):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2}[0-9]{3}", value):
            return [f"{location}: found {_show_value(value)}. "
                    "Supply two ASCII letters followed by three digits for the DSSAT code."]
        return []
    problems = _check_number(value, location)
    if not problems and field == "amount" and value <= 0:
        problems.append(f"{location}: found {_show_value(value)}. Supply a number above zero, in mm.")
    elif not problems and value < 0:
        unit = "cm" if field == "depth" else "kg per ha"
        problems.append(f"{location}: found {_show_value(value)}. Supply a nonnegative number in {unit}.")
    return problems


def _check_event(event, section, where, number, seen_dates, previous_date, weather_range):
    required = (("date", "amount", "method") if section == "irrigation" else
                ("date", "material", "application", "depth", "n"))
    optional = () if section == "irrigation" else ("p", "k")
    if not isinstance(event, dict):
        return [f"{where}: expected a dict of event fields. "
                f"Supply the required fields: {', '.join(required)}."], previous_date
    problems = _check_fields(event, required, optional, where)
    for field in required + optional:
        if field not in event:
            continue
        value, location = event[field], f"{where}, field {field!r}"
        if field != "date":
            problems.extend(_check_event_field(value, field, location))
            continue
        date_problems = _check_date(value, location)
        problems.extend(date_problems)
        if date_problems:
            continue
        d = date.fromisoformat(value)
        if previous_date is not None and d < previous_date:
            problems.append(f"{location}: date {_show_value(value)} is not in ascending order. "
                            "Order events by date ascending.")
        if value in seen_dates:
            problems.append(f"{location}: duplicate date {_show_value(value)} in "
                            f"events {seen_dates[value]} and {number}. Keep one event per date.")
        else:
            seen_dates[value] = number
        previous_date = d
        problems.extend(_check_weather_date(value, location, weather_range))
    return problems, previous_date


def _check_events(events, section, where, weather_range=None):
    label, where = f"    {section}", f"{where}, {section}"
    if not isinstance(events, list):
        problems = [f"{where}, field {section!r}: expected a list of event dicts. "
                    "Supply a list, an empty list for none, or omit the section "
                    "to keep the FileX Level."]
        return problems, _report_lines(label, problems)
    if not events:
        return [], [f"{label}: OK (empty list; none for this treatment)"]
    problems, report, seen_dates = [], [], {}
    previous_date = None
    for number, event in enumerate(events, 1):
        event_problems, previous_date = _check_event(
            event, section, f"{where}, event {number}", number, seen_dates, previous_date, weather_range)
        problems.extend(event_problems)
        report.extend(_report_lines(f"      event {number}", event_problems))
    return problems, _report_lines(label, problems, details=[]) + report


def _check_entry(entry, number, where, entry_problems, text, filex, start_date, weather_range,
                 cultivar_path, *, start_date_note=None, new_cultivars=None):
    from .irrigation import _check_irrigation
    from .operations import _OPERATION_FIELDS, _check_operation

    sections = ("planting", "irrigation", "fertilizer", *_OPERATION_FIELDS,
                "cultivar", "initial_conditions", "soil_analysis", "environment", "controls")
    if not isinstance(entry, dict):
        entry_problems.append(f"{where}: entry must be a dict. Supply a dict "
                              f"with optional {', '.join(sections)}, "
                              "or an empty dict to keep the FileX Levels.")
        return entry_problems, []
    entry_problems.extend(_unknown_keys(entry, sections, where, "Experiment"))
    problems, report = list(entry_problems), []
    for section in ("planting", "irrigation", "fertilizer", *_OPERATION_FIELDS):
        label = f"    {section}"
        if section not in entry and section != "irrigation":
            found = _check_inherited_planting(text, number, entry, filex) if section == "planting" else []
            problems.extend(found)
            report.extend(_report_lines(label, found) if found else
                          [f"{label}: OK (omitted; keeps the FileX Level)"])
            continue
        if section == "irrigation":
            section_problems, lines = _check_irrigation(entry, number, where, text, weather_range)
        elif section == "planting":
            section_problems = _check_planting(entry[section], f"{where}, planting", start_date, weather_range)
            if cultivar_path is not None and Path(cultivar_path).name[:2] == "PT":
                for field in ("planting_material_weight", "sprout_length"):
                    if not isinstance(entry[section], dict) or field not in entry[section]:
                        section_problems.append(
                            f"{where}, planting: missing {field!r}; treatment {number}'s crop is potato. "
                            f"Checked the treatment's crop entry. Supply planting.{field}.")
            lines = _report_lines(label, section_problems)
        elif section in _OPERATION_FIELDS:
            section_problems, lines = _check_operation(entry, number, section, where, text, weather_range)
        else:
            section_problems, lines = _check_events(entry[section], section, where, weather_range)
        if section in entry and not section_problems and not entry_problems and text is not None:
            try:
                if section == "planting":
                    _planting_text(text, number, entry[section])
                else:
                    _event_text(text, number, entry[section], section)
            except ValueError as error:
                detail = f"FileX {filex}: {error}" if section == "planting" else str(error)
                section_problems.append(f"{where}, {section}: {detail}")
                lines = _report_lines(label, section_problems)
        if section == "planting":
            reason = start_date_note
            planting_date = entry[section].get("date") if isinstance(entry[section], dict) else None
            if reason is None and _check_date(planting_date, where):
                reason = "planting date is missing or invalid; supply yyyy-mm-dd"
            if reason is None and start_date is None:
                reason = "simulation start date is unavailable; check the FileX start controls"
            if reason is not None:
                lines.append(f"      Note: planting-date-versus-start-date check was skipped ({reason}).")
        problems.extend(section_problems)
        report.extend(lines)
    if "cultivar" in entry:
        section_problems = _check_cultivar(entry["cultivar"], where, filex, text, number,
                                          cultivar_path=cultivar_path, new_cultivars=new_cultivars)
        problems.extend(section_problems)
        report.extend(_report_lines("    cultivar", section_problems))
    else:
        report.append("    cultivar: OK (omitted; keeps the FileX Level)")
    for section in ("initial_conditions", "soil_analysis", "environment", "controls"):
        if section in entry:
            if section in ("initial_conditions", "soil_analysis", "environment"):
                check, render = ((_check_initial_conditions, _initial_conditions_text)
                                 if section == "initial_conditions" else
                                 (_check_soil_analysis, _soil_analysis_text)
                                 if section == "soil_analysis" else
                                 (_check_environment, _environment_text))
                section_problems = check(entry[section], where)
                if not section_problems and not entry_problems and text is not None:
                    try:
                        render(text, number, entry[section])
                    except ValueError as error:
                        section_problems.append(f"{where}, {section}: FileX {filex}: {error}")
            else:
                from .climate import _check_weather_controls
                section_problems = _check_controls(entry[section], where)
                if isinstance(entry[section], dict) and not entry_problems and text is not None:
                    section_problems.extend(_check_weather_controls(
                        text, number, entry[section], where, template=filex is None))
                if not section_problems and not entry_problems and text is not None:
                    try:
                        _controls_text(text, number, entry[section])
                        section_problems.extend(_check_planting_window(
                            text, number, entry[section], where, start_date, weather_range))
                    except ValueError as error:
                        section_problems.append(f"{where}, controls: FileX {filex}: {error}")
            problems.extend(section_problems)
            lines = _report_lines(f"    {section}", section_problems)
            report.extend(lines)
        else:
            report.append(f"    {section}: OK (omitted; keeps the FileX Level)")
    return problems, report


def _check_management(source, filex, selected_treatment=None, weather_rows=None, start_date=None,
                      *, text=None, cultivar_path=None, start_date_note=None,
                      rotation_template=None, filex_template=None, data_dir=None, check_harvest=True):
    """Check treatments without mutation; unreadable FileX still permits shape checks."""
    from .rotation_data import _check_rotation_data
    from .operations import _check_harvest
    if filex_template is not None:
        from .filex_template import _template_crop_entry, _template_treatment_names

    label = "Management data"
    if not isinstance(source, dict):
        problems = ["Management data must be a dict. Supply a Management template "
                    "dict with a 'treatments' mapping."]
        return problems, _report_lines(label, problems)
    problems = _unknown_keys(source, ("treatments",), label)
    if "treatments" not in source:
        problems.append("Management data: missing 'treatments'. Add a 'treatments' "
                        "dict keyed by treatment number.")
    elif not isinstance(source["treatments"], dict):
        problems.append("Management data 'treatments' must be a dict. Supply "
                        "treatment numbers mapped to dicts of management sections.")
    if not isinstance(source.get("treatments"), dict):
        return problems, _report_lines(label, problems)
    root_problems = list(problems)
    if text is None and isinstance(filex, (str, Path)):
        try:
            text = Path(filex).read_text(encoding="latin-1")
        except (OSError, ValueError):
            pass
    if check_harvest:
        found = _check_harvest(source, filex, selected_treatment, text=text)
        problems.extend(found)
        root_problems.extend(found)
    selected_number = None
    try:
        if not isinstance(selected_treatment, bool):
            selected_number = int(selected_treatment)
    except (TypeError, ValueError):
        pass
    weather_dates = [r["date"] for r in weather_rows
                     if isinstance(r, dict) and isinstance(r.get("date"), date)] if weather_rows else []
    weather_range = (min(weather_dates), max(weather_dates)) if weather_dates else None
    report, seen_numbers = [], {}
    # Template treatments share one folder's .CUL copy; copied-FileX runs do not.
    new_cultivars = {} if cultivar_path is not None or filex_template is not None else None
    for key, entry in source["treatments"].items():
        number, where, entry_problems = _check_treatment_key(key, seen_numbers, text, filex)
        is_selected = number is not None and number == selected_number
        treatment_cultivar_path = cultivar_path
        if isinstance(filex_template, dict):
            treatment_cultivar_path = None
            crop_entry = None
            if number is not None and 1 <= number <= len(_template_treatment_names(filex_template)):
                crop_entry = _template_crop_entry(filex_template, number)
            crop = crop_entry.get("crop") if isinstance(crop_entry, dict) else None
            if isinstance(crop, str) and crop in _CROPS and data_dir is not None:
                treatment_cultivar_path = data_dir / "Genotype" / f"{_CROPS[crop][2]}.CUL"
        entry, rotation_problems, rotation_report = _check_rotation_data(
            entry, number, filex, text, start_date if is_selected else None,
            weather_range if is_selected else None, rotation_template, data_dir,
            inherited_harvest_checked=True)
        treatment_problems, lines = _check_entry(
            entry, number, where, entry_problems, text, filex,
            start_date if is_selected else None, weather_range if is_selected else None,
            treatment_cultivar_path,
            new_cultivars=new_cultivars,
            start_date_note=start_date_note if is_selected else
            "only the selected treatment has a resolved simulation start date")
        treatment_problems.extend(rotation_problems)
        lines.extend(rotation_report)
        treatment_label = f"  Treatment {number}" if number is not None else f"  Treatment {_show_value(key)}"
        report.extend(_report_lines(treatment_label, treatment_problems, details=entry_problems))
        report.extend(lines)
        problems.extend(treatment_problems)
    return problems, _report_lines(label, problems, details=root_problems) + report
