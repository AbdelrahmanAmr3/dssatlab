"""Inherited harvest and rotation bounds use DSSAT's FileX calendar dates."""

import pytest

from test_harvest_required import simulation
from test_season_coverage import weather
from test_stock_weather import weather_file


def dated_simulation(tmp_path, start, planting, harvest, first, *, sequence=False):
    sim = simulation(tmp_path, level=1, harvest=harvest, sequence=sequence)
    text = sim.filex.read_text().replace('82056', start)
    row = next(line for line in text.splitlines() if line.startswith(' 7 1'))
    text = text.replace(row, row[:46] + '  1' + row[49:])
    text = text.replace('*HARVEST DETAILS',
                        '*PLANTING DETAILS\n@P PDATE\n'
                        f' 1 {planting}\n\n*HARVEST DETAILS')
    sim.filex.write_text(text, encoding='latin-1')
    sim.weather = weather(first, first[:4] + '-12-31')
    return sim


@pytest.mark.parametrize('start,planting,harvest,day,bound', [
    ('82074', '82074', '82060', '1982-03-01', 'simulation start date (1982-03-15)'),
    ('82060', '82074', '82069', '1982-03-10', 'planting date (1982-03-15)'),
])
def test_inherited_reported_harvest_before_bound(
        tmp_path, capsys, start, planting, harvest, day, bound):
    sim = dated_simulation(tmp_path, start, planting, harvest, '1982-02-25')
    before = sim.filex.read_bytes()
    problems = sim.check(True)
    assert len(problems) == 1
    assert all(value in problems[0] for value in ('Treatment 7', 'HDATE', 'level 1', day, bound))
    assert 'Supply' in problems[0] or 'Move' in problems[0]
    assert problems[0] in capsys.readouterr().out
    assert sim.filex.read_bytes() == before


@pytest.mark.parametrize('harvest', ['82074', '82075'])
def test_inherited_reported_harvest_on_or_after_bounds(tmp_path, harvest):
    sim = dated_simulation(tmp_path, '82074', '82074', harvest, '1982-02-25')
    assert sim.check(False) == []


@pytest.mark.parametrize('code,override,bound', [
    ('P', '1989-05-01', None),
    ('E', '1989-05-01', None),
    ('S', '1989-05-01', '1989-05-01'),
    ('S', None, '1989-05-02'),
])
def test_inherited_harvest_start_bound_only_for_start_s(tmp_path, code, override, bound):
    sim = dated_simulation(tmp_path, '89122', '89080', '89120', '1989-03-01')
    sim.filex.write_text(sim.filex.read_text().replace('     S 89122', f'     {code} 89122'))
    if override is not None:
        sim.management = {'treatments': {7: {'controls': {'start_date': override}}}}
    problems = sim.check(False)
    if bound is None:
        assert problems == []
    else:
        assert len(problems) == 1
        assert 'FileX HDATE' in problems[0]
        assert f'simulation start date ({bound})' in problems[0]


def test_sequence_inherited_harvest_before_planting_reported_once(tmp_path):
    sim = dated_simulation(tmp_path, '82060', '82074', '82069', '1982-02-25', sequence=True)
    row = next(line for line in sim.filex.read_text().splitlines() if line.startswith(' 7 2'))
    sim.filex.write_text(sim.filex.read_text().replace(row, row[:46] + '  1' + row[49:]))
    sim.weather = weather('1982-02-25', '1983-03-01')
    sim.management = {'treatments': {7: {}}}
    problems = sim.check(False)
    assert len(problems) == 1
    assert all(value in problems[0] for value in
               ('rotation[2]', 'HDATE', 'level 1', '1982-03-10', 'planting date (1982-03-15)'))


@pytest.mark.parametrize('later_start', ['91126', '89060'])
@pytest.mark.parametrize('override', [False, True])
def test_sequence_harvest_ignores_later_sdate(tmp_path, later_start, override):
    sim = dated_simulation(tmp_path, '89060', '89080', '90126', '1989-03-01', sequence=True)
    text = sim.filex.read_text().replace(' 2 GE              1     1     S 89060',
                                       f' 2 GE              1     1     S {later_start}')
    row = next(line for line in text.splitlines() if line.startswith(' 7 2'))
    text = text.replace(row, row[:46] + '  2' + row[49:])
    text = text.replace('@P PDATE\n 1 89080', '@P PDATE\n 1 89080\n 2 90080')
    sim.filex.write_text(text, encoding='ascii')
    sim.weather = weather('1989-03-01', '1990-05-06')
    if override:
        sim.management = {'treatments': {7: {'controls': {'start_date': '1989-03-01'}}}}
    assert sim.check(False) == []


@pytest.mark.parametrize('override', [False, True])
def test_sequence_first_harvest_keeps_start_bound(tmp_path, override):
    sim = dated_simulation(tmp_path, '89060', '89055', '89056', '1989-02-24', sequence=True)
    text = sim.filex.read_text().replace(' 1 MA              R     R     R     N     M',
                                       ' 1 MA              R     R     R     N     R')
    sim.filex.write_text(text, encoding='ascii')
    sim.weather = weather('1989-02-24', '1990-03-01')
    if override:
        sim.management = {'treatments': {7: {'controls': {'start_date': '1989-03-02'}}}}
    problems = sim.check(False)
    harvest = [problem for problem in problems if 'HDATE' in problem]
    assert len(harvest) == 1
    assert 'rotation[1]' in harvest[0]
    assert f'simulation start date (1989-03-0{2 if override else 1})' in harvest[0]


def test_filex_year_zero_leap_day_through_harvest(tmp_path):
    sim = dated_simulation(tmp_path, '00061', '00061', '00060', '2000-02-27')
    problems = sim.check(False)
    assert len(problems) == 1
    assert 'HDATE' in problems[0] and '2000-02-29' in problems[0]
    assert 'simulation start date (2000-03-01)' in problems[0]


def test_filex_year_zero_leap_day_through_rotation(tmp_path):
    sim = dated_simulation(tmp_path, '01001', '01001', '00060', '2001-01-01', sequence=True)
    sim.weather = weather('2000-02-27', '2001-12-31')
    sim.management = {'treatments': {7: {'rotation': {
        2: {'tillage': [dict(date='2001-03-01', implement='TI005', depth=20)]}}}}}
    # Both components inherit the same harvest level; only component 2 uses HARVS R.
    problems = sim.check(False)
    assert any('rotation component 2' in p and '2000-02-29' in p for p in problems)
    assert not any('2100' in p for p in problems)


@pytest.mark.parametrize('year,first', [('40', '2040-01-01'), ('41', '1941-01-01')])
def test_filex_cutoff_year_in_inherited_harvest(tmp_path, year, first):
    sim = dated_simulation(tmp_path, year + '002', year + '002', year + '001', first)
    # Keep this harvest-bound test in its intended century with explicit weather.
    sim.weather = weather_file(tmp_path, f'UFGA{year}01.WTH',
                               [first[:4] + f'{doy:03d}' for doy in (1, 2, 3)], wide=True)
    problems = sim.check(False)
    assert len(problems) == 1
    assert first in problems[0] and first[:4] + '-01-02' in problems[0]


@pytest.mark.parametrize('code', ['A', 'F', 'R'])
@pytest.mark.parametrize('override', [False, True])
@pytest.mark.parametrize('planting_override', [False, True])
def test_harvest_bound_uses_effective_planting_management(
        tmp_path, code, override, planting_override):
    sim = dated_simulation(tmp_path, '82056', '82200', '82180', '1982-02-25')
    text = sim.filex.read_text().replace(
        ' 1 MA              R', f' 1 MA              {"R" if override else code}')
    if planting_override:
        text = text.replace('@P PDATE\n 1 82200',
                            '@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  '
                            'PLDP  PLWT  PAGE  PENV  PLPH  SPRL\n'
                            ' 1 82200   -99     5     5     S     R    75     0     5'
                            '   -99   -99   -99   -99   -99')
    text += ('\n@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN\n'
             ' 1 PL          82060 82070    40   100    30    40    10\n')
    sim.filex.write_text(text, encoding='latin-1')
    entry = {}
    if override:
        entry['controls'] = {'planting_management': code}
    if planting_override:
        entry['planting'] = {'date': '1982-07-19', 'population': 5,
                             'row_spacing': 75, 'depth': 5, 'method': 'S', 'distribution': 'R'}
    sim.management = {'treatments': {7: entry}} if entry else None
    problems = sim.check(False)
    if code == 'R':
        assert len(problems) == 1
        assert 'HDATE' in problems[0] and 'planting date (1982-07-19)' in problems[0]
    else:
        assert problems == []


@pytest.mark.parametrize('code', ['A', 'F'])
def test_automatic_planting_keeps_simulation_start_harvest_bound(tmp_path, code):
    sim = dated_simulation(tmp_path, '82056', '82200', '82055', '1982-02-24')
    sim.filex.write_text(sim.filex.read_text().replace(' 1 MA              R', f' 1 MA              {code}'))
    problems = sim.check(False)
    assert len(problems) == 1
    assert 'simulation start date (1982-02-25)' in problems[0]
    assert 'planting date (' not in problems[0]


def test_identity_edits_three_column_fields_level():
    from pathlib import Path
    from dssatlab.filex_write import _identity_text
    text = (Path(__file__).parent / 'fixtures/filex_template/UFGA8201.MZX').read_text()
    text = text.replace(' 1 UFGA0002 UFGA ', '  1UFGA0002 UFGA ')
    row = next(line for line in _identity_text(text, 1, None, 'ABCD', 'XYZW000001').splitlines()
               if 'UFGA0002' in line)
    assert ' ABCD ' in row and 'XYZW000001' in row
