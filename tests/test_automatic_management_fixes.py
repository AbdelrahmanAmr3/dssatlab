"""Review regressions for inherited automatic-management controls."""

from datetime import date

import pytest

from dssatlab import Simulation
from dssatlab.controls import _check_planting_window
from dssatlab.irrigation import _check_irrigation
from dssatlab.rotation_data import _check_rotation_data
from test_filex_check import SAMPLE
from test_season_coverage import weather
from test_simulation_run import fake_dssat


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


@pytest.mark.parametrize('first,last,start,rejected', [
    ('99365', '00001', date(1999, 1, 1), False),
    ('00001', '99365', date(2000, 1, 1), True),
    ('50001', '00001', date(1950, 1, 1), False),
    ('36001', '40001', date(2035, 1, 1), True),
])
def test_inherited_planting_window_uses_filex_rule(tmp_path, fake_dssat, first, last, start, rejected):
    text = SAMPLE.replace('S 82056', f'S {start.year % 100:02d}001') + f"""
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              A     R     R     N     M
@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          {first} {last}    40   100    30    40    10
"""
    path = tmp_path / 'TEST9901.MZX'
    path.write_text(text, encoding='latin-1')
    sim = Simulation(path, weather=weather(str(start), f'{start.year}-12-31'),
                     executable=fake_dssat.executable,
                     management={'treatments': {1: {'controls': {'planting_management': 'A'}}}})
    problems = sim.check(False)
    assert len(problems) == int(rejected)
    if rejected:
        expected = ("'1936-01-01' is before simulation start date '2035-01-01'" if first == '36001'
                    else "'2000-01-01' is after auto_planting_last '1999-12-31'")
        assert expected in problems[0]


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
