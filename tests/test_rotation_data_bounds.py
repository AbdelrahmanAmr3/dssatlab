"""Effective rotation bounds from inherited FileX dates and component edits."""

from datetime import date

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


@pytest.mark.parametrize('override', [False, True])
def test_template_crop_period_is_reported_once(template, override):
    template[2]['harvest_date'] = '1978-11-16'
    entry = {'rotation': {3: {'harvest': [dict(date='1978-11-16')]}}} if override else {}
    _, problems, _ = _check_rotation_data(
        entry, 1, 'ZZZZ7801.SQX', FILEX, date(1978, 3, 15), None, template)
    problems += _check_template_crop(template[2], None)
    assert len(problems) == 1
    assert '1978-11-16 is not after the planting date 1978-11-21' in problems[0]
