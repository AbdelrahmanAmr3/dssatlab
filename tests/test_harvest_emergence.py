"""START E bounds the first reported harvest by effective emergence only."""

import pytest

from test_harvest_required import simulation
from test_simulation_run import fake_dssat, snapshot


BOUND = 'simulation start date (START E emergence date)'
PLANTING_HEADER = ('@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  '
                   'PLDP  PLWT  PAGE  PENV  PLPH  SPRL')


def planting_edit(emergence=None):
    planting = dict(date='1982-03-10', population=5, row_spacing=75, depth=5,
                    method='S', distribution='R')
    if emergence is not None:
        planting['emergence_date'] = emergence
    return planting


def emergence_simulation(tmp_path, fake_dssat, *, emergence='82079', harvest='82074',
                         sequence=False):
    sim = simulation(tmp_path, level=1, harvest=harvest, sequence=sequence)
    sim.executable = fake_dssat.executable
    text = sim.filex.read_text().replace('     S 82056', '     E 82056')
    text = text.replace(' 1 MA              R     R     R     N     M',
                        ' 1 MA              R     R     R     N     R')
    for index in range(1, 3 if sequence else 2):
        row = next(line for line in text.splitlines() if line.startswith(f' 7 {index}'))
        changed = (f' 7 {index} 0 0 {"Emergence sequence":<25}'
                   f'  1  1  0  0 {index:2d}  0  0  0  0  0  0 {index:2d} {index:2d}')
        text = text.replace(row, changed)
    planting = (f' 1 82069 {emergence:>5}     5     5     S     R    75     0     5'
                '   -99   -99   -99   -99   -99')
    if sequence:
        planting += ('\n 2 82150 82200     5     5     S     R    75     0     5'
                     '   -99   -99   -99   -99   -99')
        text = text.replace('*SIMULATION CONTROLS',
                            ' 2 82151 GS000   -99   -99   100     0 -99\n\n'
                            '*SIMULATION CONTROLS')
        text = text.replace('-99\n\n 2 82151', '-99\n 2 82151')
        sim.management = {'treatments': {7: {'rotation': {}}}}
    text = text.replace('*HARVEST DETAILS',
                        f'*PLANTING DETAILS\n{PLANTING_HEADER}\n{planting}\n\n'
                        '*HARVEST DETAILS')
    text += ('@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN\n'
             ' 1 PL          82060 82070    40   100    30    40    10\n')
    sim.filex.write_text(text, encoding='latin-1')
    return sim


def test_start_e_harvest_between_planting_and_emergence(tmp_path, fake_dssat, capsys):
    sim = emergence_simulation(tmp_path, fake_dssat)
    before = snapshot(tmp_path)
    problems = sim.check(True)
    assert len(problems) == 1
    assert all(part in problems[0] for part in (
        'Treatment 7', "FileX HDATE '82074' (1982-03-15)",
        'harvest level 1', f'{BOUND} (1982-03-20)', 'Move HDATE on or after'))
    assert problems[0] in capsys.readouterr().out
    assert snapshot(tmp_path) == before
    assert fake_dssat.calls == []


@pytest.mark.parametrize('emergence,harvest,rejected', [
    ('1982-03-14', '82074', False),
    ('1982-03-21', '82079', True),
])
def test_start_e_emergence_edit_replaces_filex_bound(
        tmp_path, fake_dssat, emergence, harvest, rejected):
    sim = emergence_simulation(tmp_path, fake_dssat, harvest=harvest)
    sim.management = {'treatments': {7: {'planting': planting_edit(emergence)}}}
    problems = sim.check(False)
    if rejected:
        assert len(problems) == 1
        assert f'{BOUND} ({emergence})' in problems[0]
    else:
        assert problems == []


def test_start_e_planting_edit_without_emergence_has_no_bound(tmp_path, fake_dssat):
    sim = emergence_simulation(tmp_path, fake_dssat)
    sim.management = {'treatments': {7: {'planting': planting_edit()}}}
    assert sim.check(False) == []


@pytest.mark.parametrize('emergence', ['-99', '', 'xxxxx', '82000', '82366'])
def test_start_e_unreadable_emergence_has_no_bound(tmp_path, fake_dssat, emergence):
    sim = emergence_simulation(tmp_path, fake_dssat, emergence=emergence)
    assert sim.check(False) == []


def test_start_e_missing_emergence_column_has_no_bound(tmp_path, fake_dssat):
    sim = emergence_simulation(tmp_path, fake_dssat)
    sim.filex.write_text(sim.filex.read_text().replace('EDATE', 'XXXXX'))
    assert sim.check(False) == []


@pytest.mark.parametrize('code', ['A', 'F'])
@pytest.mark.parametrize('edited', [False, True])
def test_start_e_automatic_planting_keeps_emergence_bound(tmp_path, fake_dssat, code, edited):
    sim = emergence_simulation(tmp_path, fake_dssat)
    if edited:
        sim.management = {'treatments': {7: {'controls': {'planting_management': code}}}}
    else:
        sim.filex.write_text(sim.filex.read_text().replace(' 1 MA              R',
                                                         f' 1 MA              {code}'))
    problems = sim.check(False)
    assert len(problems) == 1
    assert f'{BOUND} (1982-03-20)' in problems[0]
    assert 'planting date (' not in problems[0]


@pytest.mark.parametrize('harvest', ['82079', '82080'])
def test_start_e_harvest_on_or_after_emergence(tmp_path, fake_dssat, harvest):
    sim = emergence_simulation(tmp_path, fake_dssat, harvest=harvest)
    assert sim.check(False) == []


@pytest.mark.parametrize('edited', [False, True])
def test_start_e_named_sequence_planting_before_emergence(tmp_path, fake_dssat, edited):
    sim = emergence_simulation(tmp_path, fake_dssat, harvest='82080', sequence=True)
    if edited:
        sim.management['treatments'][7]['rotation'][1] = {
            'planting': planting_edit('1982-03-20')}
    assert sim.check(False) == []


def test_start_e_sequence_first_harvest_keeps_emergence_bound(tmp_path, fake_dssat):
    sim = emergence_simulation(tmp_path, fake_dssat, sequence=True)
    problems = sim.check(False)
    assert len(problems) == 1
    assert 'rotation[1]' in problems[0]
    assert f'{BOUND} (1982-03-20)' in problems[0]


def test_start_e_sequence_later_harvest_not_bounded_by_emergence(tmp_path, fake_dssat):
    sim = emergence_simulation(tmp_path, fake_dssat, harvest='82080', sequence=True)
    assert sim.check(False) == []


def test_start_e_ignores_pdate_as_harvest_bound(tmp_path, fake_dssat):
    # DSSAT IPEXP sets the planting date to EDATE under START E.
    sim = emergence_simulation(tmp_path, fake_dssat, harvest='82090')
    text = sim.filex.read_text(encoding='latin-1').replace(' 1 82069 82079', ' 1 82100 82079')
    sim.filex.write_text(text, encoding='latin-1')
    assert sim.check(False) == []
