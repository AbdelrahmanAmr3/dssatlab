"""Review regressions for inherited automatic-management controls."""

from datetime import date

import pytest

from dssatlab.controls import _check_planting_window
from dssatlab.irrigation import _check_irrigation
from dssatlab.rotation_data import _check_rotation_data


@pytest.mark.parametrize('code,events,rejected', [
    ('D', True, True), ('A', True, True), ('F', True, True), ('N', True, True),
    ('R', True, False), ('P', True, False), ('W', True, False), ('A', False, False),
])
def test_component_irrigation_checks_its_own_sm(tmp_path, code, events, rejected):
    text = f"""*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 Rotation                   1  1  0  0  0  0  0  0  0  0  0  0  1
 1 2 0 0 Rotation                   1  1  0  0  0  0  0  0  0  0  0  0  2
*CULTIVARS
@C CR INGENO CNAME
 1 MZ IB0035 -99
*SIMULATION CONTROLS
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              R     R     R     N     M
 2 MA              R     {code}     R     N     M
"""
    path = tmp_path / 'TEST8201.SQX'
    path.write_text(text, encoding='latin-1')
    irrigation = [dict(date='1982-02-25', amount=10, method='IR001')] if events else []
    entry = {'rotation': {2: {'irrigation': irrigation}}}
    _, problems, _ = _check_rotation_data(
        entry, 1, path, text, date(1982, 1, 1), (date(1982, 1, 1), date(1982, 12, 31)))
    assert len(problems) == int(rejected)
    if rejected:
        assert all(part in problems[0] for part in [
            'rotation component 2, irrigation, event 1', f'irrigation management is "{code}"',
            "FileX component's IRRIG", 'Remove the events',
        ])
        assert 'set controls' not in problems[0]
        assert 'Use days_after_planting' not in problems[0]


@pytest.mark.parametrize('first,last,start,rejected,first_date,last_date', [
    ('99365', '00001', date(1999, 1, 1), False, '1999-12-31', '2000-01-01'),
    ('00001', '99365', date(2000, 1, 1), False, '2000-01-01', '2099-12-31'),
    ('50001', '00001', date(1950, 1, 1), False, '1950-01-01', '2000-01-01'),
])
def test_inherited_planting_window_uses_weather_century(
        tmp_path, first, last, start, rejected, first_date, last_date):
    text = f"""*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 Window                     1  1  0  0  0  0  0  0  0  0  0  0  1
*SIMULATION CONTROLS
@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          {first} {last}    40   100    30    40    10
"""
    path = tmp_path / 'TEST9901.MZX'
    path.write_text(text, encoding='latin-1')
    problems = _check_planting_window(
        path.read_text(encoding='latin-1'), 1, {'planting_management': 'A'},
        'Management data treatment 1', start, (start, date(start.year, 12, 31)),
        weather_dates=[start])
    assert len(problems) == int(rejected)
    if rejected:
        assert f"'{first_date}' is after auto_planting_last '{last_date}'" in problems[0]


def test_legacy_planting_window_crosses_century_without_weather_hint():
    text = """*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 Window                     1  1  0  0  0  0  0  0  0  0  0  0  1
*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     S 99364  2150 WINDOW
@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          99365 00001    40   100    30    40    10
"""
    assert _check_planting_window(
        text, 1, {'planting_management': 'A'}, 'Management data treatment 1',
        weather_range=(date(1999, 12, 30), date(2000, 1, 1))) == []


def test_irrigation_code_change_rejects_noninteger_inherited_mi(tmp_path):
    text = """*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 Irrigation                 1  1  0  0  0  X  0  0  0  0  0  0  1
*SIMULATION CONTROLS
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              R     R     R     N     M
"""
    path = tmp_path / 'TEST8201.MZX'
    path.write_text(text, encoding='latin-1')
    problems, _ = _check_irrigation(
        {'controls': {'irrigation_management': 'A'}}, 1, 'Management data treatment 1',
        path.read_text(encoding='latin-1'), None)
    assert len(problems) == 1
    assert all(part in problems[0] for part in [
        'Management data treatment 1, irrigation', "MI 'X'", 'integer',
        'FileX MI column', 'Supply the irrigation section',
    ])


@pytest.mark.parametrize('start,rejected', [('P', False), ('S', True)])
def test_inherited_sdate_bounds_planting_window_only_when_start_is_s(tmp_path, start, rejected):
    text = f"""*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 Window                     1  1  0  0  0  0  0  0  0  0  0  0  1
*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              1     1     {start} 82100  2150 WINDOW
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              A     R     R     N     M
@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          82056 82070    40   100    30    40    10
"""
    problems = _check_planting_window(
        text, 1, {'auto_planting_first': '1982-02-25'}, 'Management data treatment 1',
        None, (date(1982, 1, 1), date(1982, 12, 31)))
    assert len(problems) == int(rejected)
    if rejected:
        assert "before simulation start date '1982-04-10'" in problems[0]
