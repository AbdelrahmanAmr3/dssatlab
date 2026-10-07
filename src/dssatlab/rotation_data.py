"""Check Experiment data per rotation component and render its row-targeted edits."""

from datetime import date
from pathlib import Path

from .cultivar import _CROPS, _check_cultivar, _cultivar_text
from .experiment import _check_date, _unknown_keys
from .filex import _filex_date, _section_row, _section_rows
from .filex_write import _event_text, _planting_text
from .irrigation import _check_irrigation_events
from .management import (_check_events, _check_planting, _check_weather_date,
                         _report_lines)
from .operations import (_OPERATION_FIELDS, _check_operation_events,
                         _component_management, _harvest_end)
from .sequence import _rotation_components, _sequence_end, _sequence_stop


_SECTIONS = ('planting', 'cultivar', 'fertilizer', 'irrigation', *_OPERATION_FIELDS)


def _rotation_text(text, treatment, rotation):
    """Render all checked component edits; #150 can write the returned text to its copy.

    rotation is the selected treatment's rotation mapping, not the whole
    Experiment data. This same loop renders individual sections during checks.
    """
    for number, entry in rotation.items():
        for section in _SECTIONS:
            if section not in entry:
                continue
            options = dict(rotation=int(number))
            if section == 'planting':
                text = _planting_text(text, treatment, entry[section], **options)
            elif section == 'cultivar':
                text = _cultivar_text(text, treatment, entry[section], **options)
            else:
                text = _event_text(text, treatment, entry[section], section, **options)
    return text


def _calendar_date(value):
    return None if _check_date(value, '') else date.fromisoformat(value)


def _level_date(text, row, reference, section, key, column):
    """Read dates of a level; harvest uses its latest valid date."""
    try:
        rows = (_section_rows(text, section, key, int(row[reference]), (column,))
                if reference == 'MH' else
                [_section_row(text, section, key, int(row[reference]), (column,))])
        days = []
        for details in rows:
            day = _filex_date(details[column])
            if day is not None:
                days.append(day)
        return max(days, default=None)
    except (ValueError, KeyError, TypeError):
        pass
    return None


def _known_dates(components, template, text, edits, where):
    known, notes = [], []
    for index, row in enumerate(components):
        number, planting, end = int(row['R']), None, None
        entry = edits.get(number, {})
        skipped = []
        if template is not None:
            component = template[index]
            planting = component.get('planting', {})
            planting = _calendar_date(planting.get('date')) if isinstance(planting, dict) else None
            end = _calendar_date(component.get('end_date', component.get('harvest_date')))
        else:
            for reference, section, key, column in (
                    ('MP', 'PLANTING DETAILS', 'P', 'PDATE'),
                    ('MH', 'HARVEST DETAILS', 'H', 'HDATE')):
                if reference == 'MP' and row['CR'] == 'FA':
                    continue
                # MH=0 means maturity, not an unreadable scheduled harvest.
                if reference == 'MH' and row.get('MH') == '0':
                    continue
                day = _level_date(text, row, reference, section, key, column)
                if reference == 'MP':
                    planting = day
                else:
                    end = day
                if day is None:
                    skipped.append(column)
        code = _component_management(text, row, 'HARVS', 'R' if end is not None else 'M')
        end = _harvest_end(entry, end, code)
        if end is not None and 'HDATE' in skipped:
            skipped.remove('HDATE')
        if code == 'M':
            if 'HDATE' in skipped:
                skipped.remove('HDATE')
            notes.append(f'    Note: {where}, rotation component {number}: period bound '
                         'check was skipped because HARVS "M" harvests at maturity and ignores '
                         'HDATE; the end bound is unknown and not checked.')
        for column in skipped:
            notes.append(f"    Note: {where}, rotation component {number}: period bound "
                         f"check was skipped for unreadable {column} (including -99) "
                         "or unavailable level. Correct the FileX date to check this bound.")
        override = entry.get('planting') if isinstance(entry, dict) else None
        if isinstance(override, dict) and _calendar_date(override.get('date')) is not None:
            planting = _calendar_date(override['date'])
        known.append((number, planting, end, row['CR']))
    return known, notes


def _period_problems(day, location, index, known, start, *, check_end=True):
    number, planting, end, crop = known[index]
    bounds = []
    if index:
        previous, prev_planting, prev_end, _ = known[index - 1]
        lower = prev_end or prev_planting
        if lower is not None and day <= lower:
            bounds.append(f"is not after rotation component {previous}'s end ({lower})")
    elif start is not None and day < start:
        bounds.append(f"is before simulation start date ({start}); planting must be on or after it")
    if check_end and end is not None:
        if day > end:
            bounds.append(f"is after rotation component {number}'s harvest date ({end})")
    if index + 1 < len(known):
        following, next_planting, next_end, next_crop = known[index + 1]
        upper = next_end if next_crop == 'FA' else next_planting
        label = 'end date' if next_crop == 'FA' else 'planting date'
        if upper is not None and day >= upper:
            bounds.append(f"is not before rotation component {following}'s {label} ({upper})")
    return [f"{location}: {day} {bound}. DSSAT applies a component's events only while "
            "it runs and would skip this one without a warning. Move the date into the "
            "component's period." for bound in bounds]


def _rotation_keys(rotation, components, where):
    normalized, problems = {}, []
    if not isinstance(rotation, dict):
        return {}, [f"{where}: rotation must be a dict. Supply R numbers mapped to component edits."]
    numbers = [int(row['R']) for row in components]
    span = (f'{min(numbers)}-{max(numbers)}' if sorted(numbers) == list(range(min(numbers), max(numbers)+1))
            else ', '.join(map(str, numbers)))
    for key, entry in rotation.items():
        location = f'{where}, rotation component {key!r}'
        if not (type(key) is int or isinstance(key, str) and key.isascii() and key.isdigit()):
            problems.append(f'{location}: invalid rotation component key. Supply an int or digit string.')
            continue
        number = int(key)
        location = f'{where}, rotation component {number}'
        if number in normalized:
            problems.append(f'{location}: duplicate rotation component number for keys mapping to '
                            f'{number}. Keep one entry per rotation component number.')
        elif number not in numbers:
            problems.append(f'{location}: the sequence has rotation components R {span}. '
                            'Use one of those numbers.')
        else:
            normalized[number] = entry
    return normalized, problems


def _check_component(entry, row, index, known, where, filex, text, treatment,
                     start, weather_range, cultivar_path, executable=None, run_end=None):
    number = int(row['R'])
    where = f'{where}, rotation component {number}'
    if not isinstance(entry, dict):
        found = [f'{where}: entry must be a dict. Supply optional planting, cultivar, '
                 'fertilizer, irrigation, residues, tillage and harvest sections.']
        return found, _report_lines(f'    rotation component {number}', found), text
    if row['CR'] == 'FA' and entry.keys() - _OPERATION_FIELDS.keys():
        found = [f'{where}: is a fallow (FA). Supply only residues, tillage and harvest '
                 'sections; remove other sections.']
        return found, _report_lines(f'    rotation component {number}', found), text
    shape_problems = _unknown_keys(entry, _SECTIONS, where, 'Experiment')
    problems, report = list(shape_problems), []
    supplied_weather = weather_range
    if run_end is not None:
        weather_range = None  # Check simulated event dates individually below.
    for section in _SECTIONS:
        label = f'      {section}'
        if section not in entry:
            report.append(f'{label}: OK (omitted; keeps the FileX Level)')
            continue
        value = entry[section]
        if section == 'cultivar':
            excluded = ('coefficients', 'ecotype', 'name')
            found = []
            if isinstance(value, dict):
                for field in excluded:
                    if field in value:
                        verb = 'are' if field == 'coefficients' else 'is'
                        found.append(f"{where}, cultivar: {field} {verb} supported in a treatment's cultivar "
                                     f"section only, not per rotation component. Remove {field!r}.")
                value = {key: item for key, item in value.items() if key not in excluded}
            found.extend(_check_cultivar(value, where, filex, None, treatment,
                                         cultivar_path=cultivar_path, executable=executable))
            if isinstance(value, dict) and 'crop' in value and value['crop'] != row['CR']:
                found.append(f"{where}, cultivar: crop {value['crop']!r} differs from the component's "
                             f"crop {row['CR']!r}. Keep the component's crop and choose one of its cultivars.")
        elif section == 'planting':
            found = _check_planting(value, f'{where}, planting', weather_range=weather_range)
        elif section == 'irrigation':
            code = _component_management(text, row, 'IRRIG')
            found, _ = _check_irrigation_events(value, where, weather_range,
                                                code=code, date_only=True)
        elif section in _OPERATION_FIELDS:
            column = 'RESID' if section == 'residues' else 'HARVS'
            code = _component_management(text, row, column)
            found, _ = _check_operation_events(value, section, where, weather_range,
                                                code=code, component=True)
            if section == 'harvest' and row['CR'] == 'FA' and value == []:
                found.append(f'{where}, harvest: a fallow needs its scheduled end. Supply '
                             'harvest events, or omit harvest to keep the FileX Level.')
        else:
            found, _ = _check_events(value, section, where, weather_range)
        events = [value] if section == 'planting' else value
        if not isinstance(events, list):
            events = []
        for event_number, event in enumerate(events, 1):
            if not isinstance(event, dict):
                continue
            location = f'{where}, {section}' + (f', event {event_number}' if section != 'planting' else '')
            for field in ('date', 'emergence_date') if section == 'planting' else ('date',):
                day = _calendar_date(event.get(field))
                if day is not None:
                    location_field = f"{location}, field {field!r}"
                    if run_end is not None and day <= run_end:
                        found.extend(_check_weather_date(event[field], location_field, supplied_weather))
                    found.extend(_period_problems(
                        day, location_field, index, known, start,
                        check_end=not (section == 'planting' and field == 'date')))
                    if field == 'emergence_date':
                        found.extend(_check_weather_date(event[field], location_field, weather_range))
        if not found and text is not None:
            try:
                text = _rotation_text(text, treatment, {number: {section: value}})
            except ValueError as error:
                found.append(f'{where}, {section}: FileX {filex}: {error}')
        problems.extend(found)
        report.extend(_report_lines(label, found))
    return problems, _report_lines(f'    rotation component {number}', problems, details=shape_problems) + report, text


def _check_rotation_data(entry, treatment, filex, text, start, weather_range,
                         template=None, data_dir=None, *, inherited_harvest_checked=False,
                         executable=None):
    """Return ordinary sections, component problems and report; never write files."""
    if not isinstance(entry, dict):
        return entry, [], []
    ordinary = {key: value for key, value in entry.items() if key != 'rotation'}
    where = f'Management data treatment {treatment}'
    components = _rotation_components(filex, treatment, text=text)
    if isinstance(template, list) and all(isinstance(c, dict) for c in template):
        components = [dict(R=str(i), SM=str(i), CR='FA' if c.get('crop') == 'fallow' else
                           _CROPS.get(str(c.get('crop')), ('?',))[0])
                      for i, c in enumerate(template, 1)]
    if len(components) < 2:
        if 'rotation' not in entry:
            return entry, [], []
        problems = [f'{where}: rotation applies only to a sequence (a treatment with several '
                    'rotation components). Remove it, or move the sections up to the treatment.']
        return ordinary, problems, _report_lines('    rotation', problems)
    if any(not row['R'].isascii() or not row['R'].isdigit() for row in components):
        return ordinary, [], []  # Sequence checks already report invalid R numbers.
    edits, problems = _rotation_keys(entry.get('rotation', {}), components, where)
    known, notes = _known_dates(components, template, text, edits, where)
    run_end = None
    controls = entry.get('controls', {})
    years = controls.get('years') if isinstance(controls, dict) else None
    if start is not None and type(years) is int and 1 <= years <= 99999:
        stop = _sequence_stop(start, years)
        if stop is not None:
            run_end = _sequence_end({'treatments': {treatment: entry}}, treatment,
                                    start, stop, filex, template)
    cycle_start = (known[0][1] or _calendar_date(template[0].get('start_date'))
                   if template is not None else None)
    if cycle_start is not None and known[-1][2] is not None:
        for number, section in ((1, 'planting'), (known[-1][0], 'harvest')):
            if isinstance(edits.get(number), dict) and section in edits[number]:
                from .rotation import _check_cycle_closure
                problems.extend(_check_cycle_closure(
                    cycle_start, known[-1][2], f'{where}, rotation component {number}, {section}',
                    leading_fallow=known[0][3] == 'FA'))
                break
    report = _report_lines('    rotation', problems) if problems else []
    for index, row in enumerate(components):
        number = int(row['R'])
        cultivar_path = None
        if template is not None and data_dir is not None and row['CR'] != 'FA':
            crop = template[index].get('crop')
            if isinstance(crop, str) and crop in _CROPS:
                cultivar_path = data_dir / 'Genotype' / f'{_CROPS[crop][2]}.CUL'
        override = edits.get(number, {})
        planting_override = isinstance(override, dict) and 'planting' in override
        _, planting, end, crop = known[index]
        # A shortened sequence finishes the crossing component, then stops.
        # Later component dates are retained in the FileX but are not simulated.
        if index == 0 and crop == 'FA' and start is not None and end is not None and end <= start:
            problem = (f'{where}, rotation component {number}: the leading fallow ends on {end}, '
                       f'not after simulation start date {start}. Move controls start_date '
                       'before the fallow end, or the fallow end later.')
            problems.append(problem)
            report.append(f'      {problem}')
        if crop != 'FA' and planting is not None and end is not None and end <= planting:
            component = template[index] if template is not None else {}
            original_planting = component.get('planting')
            # The template crop check already reports this pair if neither date changed.
            already_checked = (isinstance(original_planting, dict)
                               and original_planting.get('date') == planting.isoformat()
                               and component.get('harvest_date') == end.isoformat())
            # The HARVS R check names each early inherited HDATE and its level.
            already_checked |= (inherited_harvest_checked and template is None
                                and (not isinstance(override, dict) or 'harvest' not in override)
                                and _component_management(text, row, 'HARVS') == 'R'
                                and end < planting)
            if not already_checked:
                problem = (f'{where}, rotation component {number}: harvest date {end} '
                           f'is not after planting date {planting}. Move the harvest after '
                           'planting or the planting before harvest.')
                problems.append(problem)
                report.append(f'      {problem}')
        # Supplied plantings are checked below; also check untouched known dates.
        for field, day in zip(('planting date', 'harvest/end date'), known[index][1:3]):
            if day is not None and not (field == 'planting date' and planting_override):
                coverage = weather_range if run_end is None or day <= run_end else None
                found = _check_weather_date(day.isoformat(), f'{where}, rotation component {number}, {field}', coverage)
                if index == 0 and field == 'planting date' and start is not None and day < start:
                    found.extend(_period_problems(day, f'{where}, rotation component {number}, planting',
                                                  index, known, start, check_end=False))
                problems.extend(found)
                report.extend(f'      {p}' for p in found)
        if number in edits:
            found, lines, text = _check_component(edits[number], row, index, known, where, filex,
                                                  text, treatment, start, weather_range, cultivar_path, executable, run_end)
            problems.extend(found)
            report.extend(lines)
    return ordinary, problems, report + notes


def _write_rotation_data(filex, treatment, experiment_data):
    """Apply checked rotation component edits to the FileX copy."""
    if experiment_data is None:
        return
    for key, entry in experiment_data['treatments'].items():
        if int(key) == int(treatment) and entry.get('rotation'):
            rotation = {int(r_key): value for r_key, value in entry['rotation'].items()}
            path = Path(filex)
            text = path.read_bytes().decode('latin-1')
            text = _rotation_text(text, int(treatment), dict(sorted(rotation.items())))
            path.write_bytes(text.encode('latin-1'))
            return
