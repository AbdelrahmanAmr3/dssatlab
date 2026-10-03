"""START E harvest bounds use the first component's effective emergence date."""

import pytest

from test_filex_dates import dated_simulation
from test_season_coverage import weather


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
