"""START E harvest bounds use the first component's effective emergence date."""

import pytest

from test_filex_dates import dated_simulation
from test_season_coverage import weather
from test_simulation_stock_weather import stock_file


def emergence_simulation(tmp_path, harvest, *, sequence=False):
    sim = dated_simulation(tmp_path, '82056', '82069', harvest,
                           '1982-02-25', sequence=sequence)
    text = sim.filex.read_text().replace('     S 82056', '     E 82056')
    text = text.replace('@P PDATE\n 1 82069',
                        '@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  '
                        'PLDP  PLWT  PAGE  PENV  PLPH  SPRL\n'
                        ' 1 82069 82079     8     8     S     R    75     0     3'
                        '   -99   -99   -99   -99   -99')
    sim.filex.write_text(text, encoding='latin-1')
    return sim


@pytest.mark.parametrize('override,harvest,bound', [
    (False, '82074', '1982-03-20'),
    (True, '82074', '1982-03-25'),
    (True, '82080', '1982-03-25'),
])
def test_harvest_before_effective_emergence_reported_once(tmp_path, override, harvest, bound):
    sim = emergence_simulation(tmp_path, harvest)
    if override:
        sim.management = {'treatments': {'07': {
            'controls': {'start_date': '1982-02-25'},
            'planting': dict(date='1982-03-10', emergence_date=bound, method='S',
                             distribution='R', population=8, row_spacing=75, depth=3)}}}
    before = sim.filex.read_bytes()
    problems = sim.check(False)
    assert len(problems) == 1
    assert all(value in problems[0] for value in
               ('Treatment 7', f"FileX HDATE '{harvest}'", 'harvest level 1',
                f'simulation start date ({bound})', 'Move HDATE on or after'))
    assert 'planting date (' not in problems[0]
    assert sim.filex.read_bytes() == before


@pytest.mark.parametrize('harvest', ['82079', '82080'])
def test_harvest_on_or_after_emergence_passes(tmp_path, harvest):
    assert emergence_simulation(tmp_path, harvest).check(False) == []


@pytest.mark.parametrize('sequence', [False, True])
def test_stock_weather_century_rejects_harvest_before_emergence(tmp_path, sequence):
    sim = emergence_simulation(tmp_path, '82074', sequence=sequence)
    text = sim.filex.read_text().replace('820', '400')
    if sequence:
        text = text.replace(' 1 MA              R     R     R     N     M',
                            ' 1 MA              R     R     R     N     R')
    sim.filex.write_text(text)
    sim.weather = stock_file(tmp_path, 'UFGA4001.WTH', wide=True,
                             days=[row['date'] for row in weather('1940-01-01', '1941-12-31')])
    problems = sim.check(False)
    harvest = [problem for problem in problems if 'FileX HDATE' in problem]
    assert len(harvest) == 1
    assert "HDATE '40074' (1940-03-14)" in harvest[0]
    assert 'simulation start date (1940-03-19)' in harvest[0]
    assert 'planting date (' not in harvest[0]


@pytest.mark.parametrize('start', ['S', 'P', 'E'])
def test_start_date_override_replaces_sdate_only_under_start_s(tmp_path, start):
    sim = emergence_simulation(tmp_path, '82080')
    sim.filex.write_text(sim.filex.read_text().replace('     E 82056', f'     {start} 82056'))
    sim.management = {'treatments': {7: {'controls': {'start_date': '1982-03-22'}}}}
    problems = sim.check(False)
    if start == 'S':
        assert len(problems) == 1
        assert 'simulation start date (1982-03-22)' in problems[0]
    else:
        assert problems == []


@pytest.mark.parametrize('first_reported', [False, True])
def test_sequence_emergence_bounds_only_first_component(tmp_path, first_reported):
    sim = emergence_simulation(tmp_path, '82074', sequence=True)
    text = sim.filex.read_text()
    row = next(line for line in text.splitlines() if line.startswith(' 7 2'))
    text = text.replace(row, row[:46] + '  1' + row[49:])
    if first_reported:
        text = text.replace(' 1 MA              R     R     R     N     M',
                            ' 1 MA              R     R     R     N     R')
    sim.filex.write_text(text, encoding='latin-1')
    sim.weather = weather('1982-02-25', '1984-03-20')
    problems = sim.check(False)
    if first_reported:
        assert len(problems) == 1
        assert 'rotation[1]' in problems[0]
        assert 'simulation start date (1982-03-20)' in problems[0]
    else:
        assert problems == []
