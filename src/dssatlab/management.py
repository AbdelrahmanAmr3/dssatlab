"""Checks and report lines for Management data supplied as a plain dict."""

from datetime import date
import math
from pathlib import Path
import re

from .filex import _section_row
from .filex_write import _planting_text
from .weather import _show_value


_REQUIRED = ("date", "method", "distribution", "population", "row_spacing", "depth")
_OPTIONAL = ("emergence_date", "emergence_population", "row_direction",
             "planting_material_weight", "transplant_age", "transplant_environment",
             "plants_per_hill", "sprout_length")


def _report_lines(label, problems):
    status = "REJECTED" if problems else "OK"
    indent = " " * (len(label) - len(label.lstrip()) + 2)
    return [f"{label}: {status}"] + [f"{indent}{problem}" for problem in problems]


def _unknown_keys(data, allowed, where):
    return [f"{where}: unknown key {_show_value(key)}. Use only "
            f"{', '.join(allowed)} from the Management template."
            for key in data if key not in allowed]


def _check_date(value, location):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError
        date.fromisoformat(value)
    except ValueError:
        return [f"{location}: found {_show_value(value)}. Supply a "
                'valid ISO calendar date as a quoted YYYY-MM-DD string '
                '(for example "2024-05-10"); quote the date, even in a dict.']
    return []


def _check_number(value, location):
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError
    except (ValueError, OverflowError):
        return [f"{location}: found {_show_value(value)}. Supply a "
                "finite number in DSSAT's units, not a string or boolean."]
    return []


def _check_planting(planting, where, start_date=None, weather_range=None):
    if not isinstance(planting, dict) or not planting:
        return [f"{where}: planting must be a non-empty dict. Supply the required "
                f"fields: {', '.join(_REQUIRED)}; omit planting to keep the FileX Level."]
    problems = _unknown_keys(planting, _REQUIRED + _OPTIONAL, where)
    for field in _REQUIRED:
        if field not in planting:
            problems.append(f"{where}: missing required field {field!r}. "
                            f"Add {field!r} following the Management template.")
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
                if weather_range is not None and not (weather_range[0] <= d <= weather_range[1]):
                    problems.append(
                        f"{location}: date {_show_value(value)} is outside weather range "
                        f"({weather_range[0]} to {weather_range[1]}). Supply weather covering "
                        "the date or choose a date within the weather range."
                    )
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


def _check_events(events, section, where, weather_range=None):
    label = f"    {section}"
    where = f"{where}, {section}"
    if not isinstance(events, list):
        problems = [f"{where}, field {section!r}: expected a list of event dicts. "
                    "Supply a list, an empty list for none, or omit the section "
                    "to keep the FileX Level."]
        return problems, _report_lines(label, problems)
    if not events:
        return [], [f"{label}: OK (empty list; none for this treatment)"]
    required = (("date", "amount", "method") if section == "irrigation" else
                ("date", "material", "application", "depth", "n"))
    optional = () if section == "irrigation" else ("p", "k")
    problems, report = [], []
    seen_dates = {}
    previous_date = None
    for number, event in enumerate(events, 1):
        location = f"{where}, event {number}"
        if not isinstance(event, dict):
            event_problems = [f"{location}: expected a dict of event fields. "
                              f"Supply the required fields: {', '.join(required)}."]
        else:
            event_problems = _unknown_keys(event, required + optional, location)
            for field in required:
                if field not in event:
                    event_problems.append(f"{location}: missing required field {field!r}. "
                                          f"Add {field!r} following the Management template.")
            for field in required + optional:
                if field not in event:
                    continue
                value = event[field]
                field_location = f"{location}, field {field!r}"
                if field == "date":
                    date_problems = _check_date(value, field_location)
                    event_problems.extend(date_problems)
                    if not date_problems:
                        d = date.fromisoformat(value)
                        if previous_date is not None and d < previous_date:
                            event_problems.append(
                                f"{field_location}: date {_show_value(value)} is not in ascending order. "
                                "Order events by date ascending."
                            )
                        if value in seen_dates:
                            event_problems.append(
                                f"{field_location}: duplicate date {_show_value(value)} in "
                                f"events {seen_dates[value]} and {number}. Keep one event per date."
                            )
                        else:
                            seen_dates[value] = number
                        previous_date = d
                        if weather_range is not None and not (weather_range[0] <= d <= weather_range[1]):
                            event_problems.append(
                                f"{field_location}: date {_show_value(value)} is outside weather range "
                                f"({weather_range[0]} to {weather_range[1]}). Supply weather covering "
                                "the date or choose a date within the weather range."
                            )
                elif field in ("method", "material", "application"):
                    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2}[0-9]{3}", value):
                        event_problems.append(f"{field_location}: found {_show_value(value)}. "
                                              "Supply two ASCII letters followed by three digits "
                                              "for the DSSAT code.")
                else:
                    number_problems = _check_number(value, field_location)
                    event_problems.extend(number_problems)
                    if not number_problems and value < 0:
                        unit = "mm" if field == "amount" else "cm" if field == "depth" else "kg per ha"
                        event_problems.append(f"{field_location}: found {_show_value(value)}. "
                                              f"Supply a nonnegative number in {unit}.")
        problems.extend(event_problems)
        report.extend(_report_lines(f"      event {number}", event_problems))
    status = "REJECTED" if problems else "OK"
    return problems, [f"{label}: {status}"] + report


def _check_management(source, filex, selected_treatment=None, weather_rows=None, start_date=None):
    """Check every treatment, returning problems and report lines without mutation.

    Treatment membership and planting writer columns are read from the FileX.
    When it is unreadable, Simulation's FileX checks report that failure and
    shape checks still run.
    Optional planting numbers pass through without crop-specific range checks.
    Date order and uniqueness are checked within event lists. The selected
    treatment's planting date is checked against the FileX simulation start date,
    and its planting, irrigation and fertilizer dates against the weather range.
    """
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
    text = None
    if isinstance(filex, (str, Path)):
        try:
            text = Path(filex).read_text(encoding="latin-1")
        except (OSError, ValueError):
            pass
    selected_number = None
    try:
        if not isinstance(selected_treatment, bool):
            selected_number = int(selected_treatment)
    except (TypeError, ValueError):
        selected_number = None
    weather_dates = [r["date"] for r in weather_rows if isinstance(r, dict) and isinstance(r.get("date"), date)] if weather_rows else []
    weather_range = (min(weather_dates), max(weather_dates)) if weather_dates else None

    report = []
    for key, entry in source["treatments"].items():
        where = f"Management data treatment {_show_value(key)}"
        number = None
        entry_problems = []
        try:
            if (isinstance(key, bool) or not isinstance(key, (int, str)) or
                    isinstance(key, str) and not re.fullmatch(r"[0-9]+", key)):
                raise ValueError
            number = int(key)
            where = f"Management data treatment {number}"
        except ValueError:
            number = None
            entry_problems.append(f"{where}: invalid treatment key. Supply an int or digit string.")
        if number is not None and text is not None:
            try:
                _section_row(text, "TREATMENTS", "N", number, ())
            except ValueError as error:
                entry_problems.append(f"{where}: FileX {filex}: {error}")
        if not isinstance(entry, dict):
            entry_problems.append(f"{where}: entry must be a dict. Supply a dict "
                                  "with optional planting, irrigation and fertilizer, "
                                  "or an empty dict to keep the FileX Levels.")
        else:
            entry_problems.extend(_unknown_keys(entry, ("planting", "irrigation", "fertilizer"), where))
        is_selected = (number is not None and number == selected_number)
        treat_start = start_date if is_selected else None
        treat_weather = weather_range if is_selected else None

        planting_problems = []
        has_planting = isinstance(entry, dict) and "planting" in entry
        if has_planting:
            planting_problems = _check_planting(entry["planting"], f"{where}, planting",
                                                start_date=treat_start, weather_range=treat_weather)
            if not planting_problems and not entry_problems and text is not None:
                try:
                    _planting_text(text, number, entry["planting"])
                except ValueError as error:
                    planting_problems.append(f"{where}, planting: FileX {filex}: {error}")
        treatment_problems = entry_problems + planting_problems
        event_report = []
        if isinstance(entry, dict):
            for section in ("irrigation", "fertilizer"):
                if section in entry:
                    event_problems, lines = _check_events(entry[section], section, where,
                                                          weather_range=treat_weather)
                    treatment_problems.extend(event_problems)
                    event_report.extend(lines)
                else:
                    event_report.append(f"    {section}: OK (omitted; keeps the FileX Level)")
        treatment_label = f"  Treatment {number}" if number is not None else f"  Treatment {_show_value(key)}"
        status = "REJECTED" if treatment_problems else "OK"
        report.append(f"{treatment_label}: {status}")
        report.extend(f"    {problem}" for problem in entry_problems)
        if has_planting:
            report.extend(_report_lines("    planting", planting_problems))
        elif isinstance(entry, dict):
            report.append("    planting: OK (omitted; keeps the FileX Level)")
        report.extend(event_report)
        problems.extend(treatment_problems)
    status = "REJECTED" if problems else "OK"
    return problems, [f"{label}: {status}"] + [f"  {p}" for p in root_problems] + report
