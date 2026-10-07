"""Effective rotation bounds from inherited FileX dates and component edits."""

from datetime import date

from test_rotation_data import (sim, edits, fertilizer, data, rows, rotation,
                                installed, fake_dssat)

import pytest

from dssatlab.rotation_data import _check_rotation_data
from dssatlab.filex_template import _check_template_crop


FILEX = """*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 Rotation                   1  1  0  0  1  0  0  0  0  0  0  0  1
 1 2 0 0 Rotation                   2  1  0  0  0  0  0  0  0  0  0  1  2
 1 3 0 0 Rotation                   3  1  0  0  2  0  0  0  0  0  0  2  3
 1 4 0 0 Rotation                   2  1  0  0  0  0  0  0  0  0  0  3  4

*CULTIVARS
@C CR INGENO CNAME
 1 MZ IB0035 -99
 2 FA IB0001 -99
 3 WH IB1500 -99

*PLANTING DETAILS
@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE  PENV  PLPH  SPRL                        PLNAME
 1 78074   -99   7.2   7.2     S     R    75     0     5   -99   -99   -99   -99   -99                        -99
 2 78325   -99   7.2   7.2     S     R    75     0     5   -99   -99   -99   -99   -99                        -99

*HARVEST DETAILS
@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME
 1 78274 GS000   -99   -99   -99   -99 -99
 1 78318 GS000   -99   -99   -99   -99 -99
 2 79060 GS000   -99   -99   -99   -99 -99
 3 79073 GS000   -99   -99   -99   -99 -99

*SIMULATION CONTROLS
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              R     R     R     N     M
 2 MA              R     R     R     N     R
 3 MA              R     R     R     N     R
 4 MA              R     R     R     N     R
"""


@pytest.mark.parametrize('day,valid', [
    ('1978-10-15', True), ('1978-11-14', True), ('1978-11-15', False),
])
@pytest.mark.parametrize('reverse', [False, True])
def test_inherited_multirow_harvest_matches_explicit_schedule(day, valid, reverse):
    text = FILEX
    if reverse:
        text = text.replace(
            ' 1 78274 GS000   -99   -99   -99   -99 -99\n'
            ' 1 78318 GS000   -99   -99   -99   -99 -99',
            ' 1 78318 GS000   -99   -99   -99   -99 -99\n'
            ' 1 78274 GS000   -99   -99   -99   -99 -99')
    results = []
    for explicit in (False, True):
        component = {'tillage': [dict(date=day, implement='TI005', depth=20)]}
        if explicit:
            component['harvest'] = [dict(date='1978-10-01'), dict(date='1978-11-14')]
        _, problems, _ = _check_rotation_data(
            {'rotation': {2: component}}, 1, 'ZZZZ7801.SQX', text,
            date(1978, 3, 15), None)
        results.append(problems)
    expected = [] if valid else [
        "Management data treatment 1, rotation component 2, tillage, event 1, field 'date': "
        "1978-11-15 is after rotation component 2's harvest date (1978-11-14). "
        "DSSAT applies a component's events only while it runs and would skip this one "
        "without a warning. Move the date into the component's period."]
    assert results == [expected, expected]


@pytest.mark.parametrize('value', ['-99', 'XXXXX', '78367'])
@pytest.mark.parametrize('readable', [False, True])
def test_unreadable_harvest_rows_skip_only_unavailable_bound(value, readable):
    text = FILEX.replace(' 1 78274 GS000', f' 1 {value:>5} GS000')
    if not readable:
        text = text.replace(' 1 78318 GS000', f' 1 {value:>5} GS000')
    _, problems, report = _check_rotation_data(
        {'rotation': {2: {'tillage': [dict(date='1978-10-15', implement='TI005', depth=20)]}}},
        1, 'ZZZZ7801.SQX', text, date(1978, 3, 15), None)
    assert problems == []
    assert any('rotation component 2: period bound check was skipped for unreadable HDATE'
               in line for line in report) == (not readable)


@pytest.fixture
def template():
    planting = dict(date='1978-03-15', method='S', distribution='R',
                    population=7, row_spacing=75, depth=5)
    return [dict(crop='maize', planting=planting),
            dict(crop='fallow', end_date='1978-11-14'),
            dict(crop='wheat', planting=dict(planting, date='1978-11-21'),
                 harvest_date='1979-03-01'),
            dict(crop='fallow', end_date='1979-03-14')]


@pytest.mark.parametrize('use_template', [False, True])
@pytest.mark.parametrize('section,day,valid,planting,end', [
    ('harvest', '1978-11-16', False, '1978-11-21', '1978-11-16'),
    ('harvest', '1978-11-21', False, '1978-11-21', '1978-11-21'),
    ('harvest', '1978-11-22', True, '1978-11-21', '1978-11-22'),
    ('planting', '1979-03-02', False, '1979-03-02', '1979-03-01'),
    ('planting', '1979-03-01', False, '1979-03-01', '1979-03-01'),
    ('planting', '1979-02-28', True, '1979-02-28', '1979-03-01'),
])
def test_effective_crop_end_must_follow_planting(
        template, use_template, section, day, valid, planting, end):
    value = ([dict(date=day)] if section == 'harvest' else
             dict(template[2]['planting'], date=day))
    _, problems, report = _check_rotation_data(
        {'rotation': {3: {section: value}}}, 1, 'ZZZZ7801.SQX', FILEX,
        date(1978, 3, 15), None, template if use_template else None)
    expected = [] if valid else [
        f'Management data treatment 1, rotation component 3: harvest date {end} '
        f'is not after planting date {planting}. Move the harvest after planting '
        'or the planting before harvest.']
    assert problems == expected
    assert all(any(problem in line for line in report) for problem in problems)


def test_unchanged_filex_crop_end_must_follow_planting():
    _, problems, _ = _check_rotation_data(
        {}, 1, 'ZZZZ7801.SQX', FILEX.replace(' 2 79060 GS000', ' 2 78320 GS000'),
        date(1978, 3, 15), None)
    assert problems == [
        'Management data treatment 1, rotation component 3: harvest date 1978-11-16 '
        'is not after planting date 1978-11-21. Move the harvest after planting '
        'or the planting before harvest.']


@pytest.mark.parametrize('explicit', [False, True])
def test_shortened_sequence_checks_only_simulated_component_dates(tmp_path, explicit):
    # Four components end at the one-year boundary. A later crop/fallow stays
    # in the FileX, like the dated components in stock MSKB8902.SQX.
    text = FILEX.replace('\n*CULTIVARS',
        ' 1 5 0 0 Rotation                   3  1  0  0  3  0  0  0  0  0  0  4  3\n'
        ' 1 6 0 0 Rotation                   2  1  0  0  0  0  0  0  0  0  0  5  4\n'
        '\n*CULTIVARS')
    text = text.replace('\n*HARVEST DETAILS',
        ' 3 80325   -99   7.2   7.2     S     R    75     0     5   -99   -99   -99   -99   -99\n'
        '\n*HARVEST DETAILS')
    text = text.replace('\n*SIMULATION CONTROLS',
        ' 4 81060 GS000   -99   -99   -99   -99 -99\n'
        ' 5 81073 GS000   -99   -99   -99   -99 -99\n'
        '\n*SIMULATION CONTROLS')
    path = tmp_path / 'ZZZZ7801.SQX'
    path.write_text(text)
    entry = {'controls': {'years': 1}}
    if explicit:
        entry['rotation'] = {5: {'harvest': [{'date': '1981-03-01'}]},
                             6: {'harvest': [{'date': '1981-03-14'}]}}
    _, problems, _ = _check_rotation_data(entry, 1, path, text, date(1978, 3, 15),
                                          (date(1978, 3, 15), date(1979, 3, 14)))
    assert problems == []
    # Dates inside the simulated component still need weather.
    _, problems, _ = _check_rotation_data(entry, 1, path, text, date(1978, 3, 15),
                                          (date(1978, 3, 15), date(1979, 3, 13)))
    assert len(problems) == 1 and '1979-03-14' in problems[0]


@pytest.mark.parametrize('explicit', [False, True])
def test_sequence_future_planting_year_is_not_required_weather(tmp_path, explicit):
    # DSSAT v4.8.6.0 AUTPLT.for (151-158) shifts this to 1978-03-16.
    # The raw future year does not require weather beyond the stopping boundary.
    text = (FILEX.replace('78074', '79075').replace('78274', '79274')
            .replace('78318', '79318').replace('78325', '79325')
            .replace('79060', '80060').replace('79073', '80073'))
    path = tmp_path / 'ZZZZ7801.SQX'
    path.write_text(text)
    entry = {'controls': {'years': 1}}
    if explicit:
        entry['rotation'] = {1: {'planting': dict(
            date='1979-03-16', method='S', distribution='R',
            population=7, row_spacing=75, depth=5)}}
    _, problems, _ = _check_rotation_data(entry, 1, path, text, date(1978, 3, 15),
                                          (date(1978, 3, 15), date(1979, 3, 14)))
    assert problems == []


@pytest.mark.parametrize('override', [False, True])
def test_template_crop_period_is_reported_once(template, override):
    template[2]['harvest_date'] = '1978-11-16'
    entry = {'rotation': {3: {'harvest': [dict(date='1978-11-16')]}}} if override else {}
    _, problems, _ = _check_rotation_data(
        entry, 1, 'ZZZZ7801.SQX', FILEX, date(1978, 3, 15), None, template)
    problems += _check_template_crop(template[2], None)
    assert len(problems) == 1
    assert '1978-11-16 is not after the planting date 1978-11-21' in problems[0]


@pytest.mark.parametrize('day', ['1978-11-14', '1978-11-15'])
def test_lower_bound_is_exclusive(sim, day):
    edits(sim, {3: {'fertilizer': [fertilizer(day)]}})
    assert (sim.check(False) == []) == (day == '1978-11-15')


@pytest.mark.parametrize('omit_rotation', [False, True])
def test_first_inherited_planting_before_start(sim, omit_rotation):
    if omit_rotation:
        sim.management['treatments'][1].pop('rotation')
    sim.management['treatments'][1]['controls'] = dict(start_date='1978-03-16', years=1)
    assert any('rotation component 1' in p and 'before simulation start date' in p
               for p in sim.check(False))


@pytest.mark.parametrize('section,event', [
    ('residues', dict(date='1978-01-01', material='RE001', amount=1500)),
    ('tillage', dict(date='1978-01-01', implement='TI005', depth=20)),
    ('harvest', dict(date='1978-01-01')),
])
def test_component_operations_use_period_message(sim, section, event):
    edits(sim, {2: {section: [event]}})
    message = (
        f"Management data treatment 1, rotation component 2, {section}, event 1, field 'date': "
        "1978-01-01 is not after rotation component 1's end (1978-03-15). "
        "DSSAT applies a component's events only while it runs and would skip this one "
        "without a warning. Move the date into the component's period.")
    assert message in sim.check(False)


@pytest.mark.parametrize('day,valid', [('1978-11-20', False), ('1978-11-21', True)])
def test_reported_harvest_moves_neighbor_bound(sim, day, valid):
    # Keep the component periods separate while checking the edited event's lower bound.
    if sim.filex is None:
        sim.filex_template['rotation'][2]['planting']['date'] = '1978-11-21'
    else:
        sim.filex.write_text(sim.filex.read_text().replace(' 2 78319', ' 2 78325'))
    edits(sim, {2: {'harvest': [{'date': '1978-11-16'}, {'date': '1978-11-20'}]},
                3: {'fertilizer': [fertilizer(day)]}})
    problems = sim.check(False)
    assert (problems == []) == valid
    if not valid:
        assert len(problems) == 1
        assert "is not after rotation component 2's end (1978-11-20)" in problems[0]


def test_maturity_harvest_ignores_populated_hdate(sim, capsys):
    if sim.filex is None:
        pytest.skip('HARVS M with populated HDATE belongs to a copied FileX')
    text = sim.filex.read_text().replace(' 2 MA              R     R     R     N     R',
                                       ' 2 MA              R     R     R     N     M')
    sim.filex.write_text(text)
    edits(sim, {3: {'fertilizer': [fertilizer('1978-10-01')]}})
    assert sim.check(True) == []
    report = capsys.readouterr().out
    assert ('rotation component 2: period bound check was skipped because HARVS "M" '
            'harvests at maturity and ignores HDATE; the end bound is unknown and not checked.') in report
    assert 'Correct the FileX date' not in report


@pytest.mark.parametrize('section,event,column,field,fix', [
    ('residues', dict(date='1978-11-15', material='RE001', amount=1500), 'RESID', 'residue', '"R"'),
    ('harvest', dict(date='1978-11-15'), 'HARVS', 'harvest_management', '"R" or "M"'),
])
@pytest.mark.parametrize('code', ['G', 'X', '-99', None, 'unreadable_sm'])
def test_component_rejects_unusable_operation_code(sim, section, event, column, field, fix, code):
    if sim.filex is None:
        pytest.skip('Unavailable or unknown SM codes belong to a copied FileX')
    old = ' 3 MA              R     R     R     N     M'
    row = ('' if code is None else
           f' 3 MA              R     R     R{code:>6}     M' if column == 'RESID' else
           f' 3 MA              R     R     R     N{code:>6}')
    text = sim.filex.read_text().replace(old, row)
    if code == 'unreadable_sm':
        text = sim.filex.read_text().replace(' 0  0  0  0  3\n', ' 0  0  0  0  X\n')
    sim.filex.write_text(text)
    edits(sim, {3: {section: [event]}})
    problems = [p for p in sim.check(False) if f'{section}: ' in p and 'events need' in p]
    assert len(problems) == 1
    if code in (None, 'unreadable_sm'):
        assert f'could not be read (checked controls {field} and the FileX SM level column {column})' in problems[0]
        assert '"None"' not in problems[0]
    else:
        assert f'but it is "{code}".' in problems[0]
    assert f'Set the component\'s FileX SM level column {column} to {fix}, or remove the {section} events.' in problems[0]


@pytest.mark.parametrize('day,valid', [('1978-11-14', True), ('1978-11-15', False), ('1978-11-20', False)])
def test_edited_end_rechecks_unchanged_next_planting(sim, day, valid):
    edits(sim, {2: {'harvest': [{'date': '1978-11-01'}, {'date': day}]}})
    problems = sim.check(False)
    expected = (
        "Management data treatment 1, rotation component 2, harvest, event 2, field 'date': "
        f"{day} is not before rotation component 3's planting date (1978-11-15). "
        "DSSAT applies a component's events only while it runs and would skip this one "
        "without a warning. Move the date into the component's period.")
    assert problems == ([] if valid else [expected])


@pytest.mark.parametrize('day,valid', [('1979-03-13', True), ('1979-03-14', False), ('1979-03-20', False)])
def test_edited_end_rechecks_next_fallow_end(sim, day, valid):
    if sim.filex is None:
        sim.filex_template['rotation'][2]['harvest_date'] = '1979-03-01'
    else:
        sim.filex.write_text(sim.filex.read_text().replace(' 3 MA              R     R     R     N     M',
                                                        ' 3 MA              R     R     R     N     R'))
    edits(sim, {3: {'harvest': [{'date': day}]}})
    problems = sim.check(False)
    assert (problems == []) == valid
    if not valid:
        assert len(problems) == 1
        assert f"{day} is not before rotation component 4's end date (1979-03-14)" in problems[0]


@pytest.mark.parametrize('day,valid', [('1978-11-14', True), ('1978-11-15', False), ('1978-11-20', False)])
def test_fallow_end_rechecks_unchanged_next_planting(sim, day, valid):
    if sim.filex is not None:
        pytest.skip('end_date belongs to a FileX template')
    sim.filex_template['rotation'][1]['end_date'] = day
    problems = sim.check(False)
    assert (problems == []) == valid
    if not valid:
        assert any(f"1978-11-15 is not after rotation[2]'s end ({day})" in p
                   for p in problems)
