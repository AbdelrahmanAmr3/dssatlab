"""Experiment harvest dates use the inherited HDATE bounds and corrections."""

import pytest

from test_harvest_emergence import BOUND, emergence_simulation, planting_edit
from test_simulation_run import fake_dssat, snapshot


@pytest.mark.parametrize('start,sequence', [('E', False), ('S', False), ('E', True)])
def test_edited_harvest_before_start_matches_inherited_bounds(
        tmp_path, fake_dssat, capsys, start, sequence):
    sim = emergence_simulation(tmp_path, fake_dssat, sequence=sequence)
    if start == 'S':
        sim.filex.write_text(sim.filex.read_text().replace('     E 82056', '     S 82079'))
    inherited = sim.check(False)
    assert len(inherited) == 1
    entry = {'harvest': [{'date': '1982-03-15'}]}
    sim.management = {'treatments': {7: {'rotation': {'1': entry}} if sequence else entry}}
    before = snapshot(tmp_path)
    problems = sim.check(True)
    where = 'Treatment 7, rotation[1]' if sequence else 'Treatment 7'
    assert problems == [
        f"{where}, harvest, event 1: date '1982-03-15' (1982-03-15) "
        'is before ' + inherited[0].split('is before ', 1)[1]]
    assert problems[0] in capsys.readouterr().out
    assert snapshot(tmp_path) == before
    assert fake_dssat.calls == []


@pytest.mark.parametrize('start_date,rejected', [('1982-03-14', False), ('1982-03-20', True)])
def test_edited_harvest_uses_controls_start_date(tmp_path, fake_dssat, start_date, rejected):
    sim = emergence_simulation(tmp_path, fake_dssat, harvest='82090')
    sim.filex.write_text(sim.filex.read_text().replace('     E 82056', '     S 82056'))
    sim.management = {'treatments': {7: {
        'controls': {'start_date': start_date}, 'harvest': [{'date': '1982-03-15'}]}}}
    problems = sim.check(False)
    if rejected:
        assert len(problems) == 1
        assert f'is before simulation start date ({start_date})' in problems[0]
    else:
        assert problems == []


@pytest.mark.parametrize('edited_planting', [False, True])
def test_edited_harvest_before_effective_planting(tmp_path, fake_dssat, edited_planting):
    sim = emergence_simulation(tmp_path, fake_dssat, harvest='82090')
    sim.filex.write_text(sim.filex.read_text().replace('     E 82056', '     S 82056'))
    entry = {'harvest': [{'date': '1982-03-05'}]}
    if edited_planting:
        entry['planting'] = dict(planting_edit(), date='1982-03-12')
    sim.management = {'treatments': {7: entry}}
    planting = '1982-03-12' if edited_planting else '1982-03-10'
    assert sim.check(False) == [
        "Treatment 7, harvest, event 1: date '1982-03-05' (1982-03-05) "
        f'is before planting date ({planting}). Move HDATE on or after '
        'these bounds, or change the start or planting date.']


@pytest.mark.parametrize('start,sequence', [('E', False), ('S', False), ('E', True)])
@pytest.mark.parametrize('harvest', ['1982-03-20', '1982-03-21'])
def test_edited_harvest_on_or_after_bounds(tmp_path, fake_dssat, start, sequence, harvest):
    sim = emergence_simulation(tmp_path, fake_dssat, sequence=sequence)
    if start == 'S':
        sim.filex.write_text(sim.filex.read_text().replace('     E 82056', '     S 82079'))
    entry = {'harvest': [{'date': harvest}]}
    sim.management = {'treatments': {7: {'rotation': {1: entry}} if sequence else entry}}
    assert sim.check(False) == []


@pytest.mark.parametrize('code', ['M', 'A', 'D'])
@pytest.mark.parametrize('override', [False, True])
def test_edited_harvest_other_management_adds_no_bounds_problem(
        tmp_path, fake_dssat, code, override):
    sim = emergence_simulation(tmp_path, fake_dssat)
    entry = {'harvest': [{'date': '1982-03-15'}]}
    if override:
        entry['controls'] = {'harvest_management': code}
    else:
        sim.filex.write_text(sim.filex.read_text().replace(
            ' 1 MA              R     R     R     N     R',
            f' 1 MA              R     R     R     N     {code}'))
    sim.management = {'treatments': {7: entry}}
    problems = sim.check(False)
    if code == 'M':
        assert problems == []
    else:
        assert len(problems) == 1
        assert 'harvest events need the harvest management "R" or "M"' in problems[0]
    assert not any('is before' in problem or 'Move HDATE' in problem for problem in problems)


def test_each_edited_harvest_event_is_bounded(tmp_path, fake_dssat):
    sim = emergence_simulation(tmp_path, fake_dssat, harvest='82090')
    sim.management = {'treatments': {7: {'harvest': [
        {'date': '1982-03-14'}, {'date': '1982-03-15'}, {'date': '1982-03-20'}]}}}
    problems = sim.check(False)
    assert len(problems) == 2
    for number, problem in enumerate(problems, 1):
        assert f'harvest, event {number}:' in problem
        assert f'{BOUND} (1982-03-20)' in problem
