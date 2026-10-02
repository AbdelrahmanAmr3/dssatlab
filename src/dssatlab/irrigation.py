"""Check irrigation timing against the treatment's effective management codes."""

from datetime import date

from .experiment import _check_date, _check_fields
from .filex import _section_row
from .management import _check_event, _check_event_field, _report_lines
from .weather import _show_value


def _effective_management(entry, text, treatment, field, column):
    """Read only the selected SM level; an explicit controls value takes precedence."""
    controls = entry.get('controls')
    if isinstance(controls, dict) and field in controls:
        return controls[field]
    if text is not None:
        try:
            row = _section_row(text, 'TREATMENTS', 'N', treatment, ('SM',))
            return _section_row(text, 'SIMULATION CONTROLS', 'N', int(row['SM']),
                                ('MANAGEMENT', column))[column]
        except (ValueError, TypeError):
            pass  # Existing FileX and controls checks report unavailable layouts.
    return None


def _management_problem(kind, code, where):
    if code == 'D' and kind == 'date':
        message = ('uses a date but the irrigation management is "D" (days after planting). '
                   'Use days_after_planting, or set controls irrigation_management to "R".')
    elif code in ('R', 'P', 'W') and kind == 'days_after_planting':
        message = (f'uses days after planting but the irrigation management is "{code}" (dates). '
                   'Use date, or set controls irrigation_management to "D".')
    elif code in ('A', 'F', 'N'):
        fix = 'D' if kind == 'days_after_planting' else 'R'
        message = (f'has an event but the irrigation management is "{code}" (no events). '
                   f'Remove the events (irrigation: []), or set controls irrigation_management to "{fix}".')
    else:
        return []
    return [f'{where}: {message}']


def _check_day_event(event, where, number, seen, previous, planting_date, weather_range):
    problems = _check_fields(event, ('amount', 'method'), ('date', 'days_after_planting'), where)
    for field in ('amount', 'method'):
        if field in event:
            problems.extend(_check_event_field(event[field], field, f'{where}, field {field!r}'))
    value = event['days_after_planting']
    location = f"{where}, field 'days_after_planting'"
    if type(value) is not int or value < 0:
        problems.append(f'{location}: found {_show_value(value)}. '
                        'Supply an integer at least 0 (DSSAT IDATE).')
        return problems, previous
    shown = _show_value(value)
    if previous is not None and value < previous:
        problems.append(f'{location}: days after planting {shown} is not in ascending order. '
                        'Order events by days after planting ascending.')
    if value in seen:
        problems.append(f'{location}: duplicate days after planting {shown} in '
                        f'events {seen[value]} and {number}. Keep one event per day after planting.')
    else:
        seen[value] = number
    if planting_date is not None and weather_range is not None:
        # Ordinals avoid overflow even for a day count too large to write into IDATE.
        ordinal = planting_date.toordinal() + value
        if not weather_range[0].toordinal() <= ordinal <= weather_range[1].toordinal():
            day = date.fromordinal(ordinal).isoformat() if ordinal <= date.max.toordinal() else 'beyond 9999-12-31'
            problems.append(f'{location}: planting date {planting_date} plus {shown} days is {day}, '
                            f'outside weather range ({weather_range[0]} to {weather_range[1]}). '
                            'Supply weather covering the date or choose days within the weather range.')
    return problems, value


def _check_irrigation_events(events, where, weather_range=None, *, code=None,
                             planting_date=None, skip_reason=None, date_only=False):
    label, where = '    irrigation', f'{where}, irrigation'
    if not isinstance(events, list):
        problems = [f"{where}, field 'irrigation': expected a list of event dicts. "
                    'Supply a list, an empty list for none, or omit the section '
                    'to keep the FileX Level.']
        return problems, _report_lines(label, problems)
    if not events:
        return [], [f'{label}: OK (empty list; none for this treatment)']
    problems, report, kinds = [], [], set()
    seen_dates, seen_days, previous_date, previous_day = {}, {}, None, None
    has_day = False
    for number, event in enumerate(events, 1):
        location = f'{where}, event {number}'
        if date_only and isinstance(event, dict) and 'days_after_planting' in event:
            found = [f"{location}: days_after_planting is not supported per rotation component; "
                     "irrigation management belongs to the treatment. Use date events in a list."]
        elif not isinstance(event, dict):
            found, previous_date = _check_event(event, 'irrigation', location, number,
                                               seen_dates, previous_date, weather_range)
        elif ('date' in event) == ('days_after_planting' in event):
            found = _check_fields(event, ('amount', 'method'), ('date', 'days_after_planting'), location)
            for field in ('amount', 'method'):
                if field in event:
                    found.extend(_check_event_field(event[field], field, f'{location}, field {field!r}'))
            detail = 'both are given' if 'date' in event else "missing required field 'date' or 'days_after_planting'"
            found.append(f'{location}: {detail}. Add exactly one of date or days_after_planting.')
        else:
            kind = 'date' if 'date' in event else 'days_after_planting'
            kinds.add(kind)
            if kind == 'date':
                found, previous_date = _check_event(event, 'irrigation', location, number,
                                                   seen_dates, previous_date, weather_range)
                valid_timing = not _check_date(event['date'], location)
            else:
                found, previous_day = _check_day_event(event, location, number, seen_days,
                                                       previous_day, planting_date, weather_range)
                valid_timing = type(event[kind]) is int and event[kind] >= 0
                has_day = has_day or valid_timing
            if valid_timing:
                found.extend(_management_problem(kind, code, location))
        problems.extend(found)
        report.extend(_report_lines(f'      event {number}', found))
    if len(kinds) > 1:
        problem = (f'{where}: list mixes date and days_after_planting events. '
                   'Use one timing kind for every event in the list.')
        problems.append(problem)
        report.append(f'      {problem}')
    if has_day and skip_reason is not None:
        report.append(f'      Note: day-event-weather-range check was skipped ({skip_reason}).')
    return problems, _report_lines(label, problems, details=[]) + report


def _check_irrigation(entry, treatment, where, text, weather_range):
    code = _effective_management(entry, text, treatment, 'irrigation_management', 'IRRIG')
    if 'irrigation' not in entry:
        controls = entry.get('controls')
        if (isinstance(controls, dict) and 'irrigation_management' in controls
                and code in ('A', 'N', 'F', 'R', 'D', 'P', 'W') and text is not None):
            try:
                row = _section_row(text, 'TREATMENTS', 'N', treatment, ('MI', 'SM'))
                _section_row(text, 'SIMULATION CONTROLS', 'N', int(row['SM']), ('MANAGEMENT', 'IRRIG'))
                mi = int(row['MI'])
            except (ValueError, TypeError):
                mi = 0
            if mi != 0:
                problems = [f'{where}, irrigation: controls irrigation_management is "{code}" '
                            f'but irrigation is omitted and the treatment inherits MI {mi}. '
                            'Supply the irrigation section with events matching the code, or [].']
                return problems, _report_lines('    irrigation', problems)
        return [], ['    irrigation: OK (omitted; keeps the FileX Level)']
    plant = _effective_management(entry, text, treatment, 'planting_management', 'PLANT')
    planting, planting_date, reason = entry.get('planting'), None, None
    if plant in ('A', 'F'):
        reason = f'planting management is "{plant}"; DSSAT chooses the planting date'
    elif 'planting' not in entry:
        reason = 'planting section is omitted; planting date is unknown'
    elif not isinstance(planting, dict) or _check_date(planting.get('date'), where):
        reason = 'planting date is missing or invalid; supply yyyy-mm-dd'
    else:
        planting_date = date.fromisoformat(planting['date'])
    if reason is None and weather_range is None:
        reason = 'weather range is unavailable for this treatment'
    return _check_irrigation_events(entry['irrigation'], where, weather_range, code=code,
                                    planting_date=planting_date, skip_reason=reason)
