"""Inherited harvest and rotation bounds use DSSAT's FileX calendar dates."""

import pytest

from test_harvest_required import simulation
from test_season_coverage import weather


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
    problems = sim.check(False)
    assert len(problems) == 1
    assert first in problems[0] and first[:4] + '-01-02' in problems[0]
