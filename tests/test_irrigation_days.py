"""Days after planting and effective management checked through Simulation."""

from copy import deepcopy

import pytest

from dssatlab import DSSATCheckError, Simulation, write_experiment_template
from dssatlab.filex import _section_row
from test_controls_options import option_sim
from test_filex_template import data, rows
from test_management_file import sim_inputs
from test_rotation_data import sim as rotation_sim
from test_rotation_template import rotation
from test_season_coverage import weather
from test_simulation_run import fake_dssat
from test_simulation_template import installed


@pytest.fixture
def day_sim(option_sim):
    option_sim.management['treatments'][1] = {
        'planting': dict(date='1982-02-25', method='S', distribution='R',
                         population=7, row_spacing=75, depth=5),
        'irrigation': [dict(days_after_planting=0, amount=10, method='IR001')],
        'controls': {'irrigation_management': 'D'},
    }
    return option_sim


def _entry(sim):
    return sim.management['treatments'][1]


def _code(sim, column, value):
    text = sim.filex.read_text(encoding='latin-1')
    lines = text.splitlines(keepends=True)
    header = next(i for i, line in enumerate(lines) if line.startswith('@N MANAGEMENT'))
    end = lines[header].index(column) + len(column)
    lines[header + 1] = lines[header + 1][:end - 6] + value.rjust(6) + lines[header + 1][end:]
    sim.filex.write_text(''.join(lines), encoding='latin-1')


@pytest.mark.parametrize('template', [False, True])
def test_day_idate_written_without_mutating_source(day_sim, fake_dssat, data, rows,
                                                   installed, template):
    sim = day_sim
    if template:
        data['planting']['date'] = '1982-02-25'
        sim = Simulation(filex_template=data, weather=day_sim.weather, soil=rows[1],
                         management=deepcopy(day_sim.management))
    _entry(sim)['irrigation'] += [dict(days_after_planting=34, amount=20, method='IR003')]
    original = None if template else sim.filex.read_bytes()
    inputs = deepcopy(sim.management)
    assert sim.check(False) == []
    result = sim.run()
    path = next(result.run_dir.parent.glob('*.MZX'))
    text = path.read_text(encoding='latin-1')
    level = int(_section_row(text, 'TREATMENTS', 'N', 1, ('MI',))['MI'])
    events = [line.split() for line in text.splitlines() if 'IR00' in line]
    assert [row for row in events if row[0] == str(level) and len(row) == 4] == [
        [str(level), '0', 'IR001', '10'], [str(level), '34', 'IR003', '20']]
    assert sim.management == inputs
    if not template:
        assert sim.filex.read_bytes() == original


@pytest.mark.parametrize('bad', [-1, True, False, 1.0, '1', None, [], {}])
def test_day_count_is_nonnegative_integer(day_sim, fake_dssat, bad):
    _entry(day_sim)['irrigation'][0]['days_after_planting'] = bad
    expected = (f"Management data treatment 1, irrigation, event 1, field 'days_after_planting': "
                f'found {bad!r}. Supply an integer at least 0 (DSSAT IDATE).')
    assert day_sim.check(False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        day_sim.run()
    assert error.value.problems == [expected]
    assert not fake_dssat.calls


@pytest.mark.parametrize('days,fragment', [([2, 1], 'not in ascending order'),
                                         ([2, 2], 'duplicate days after planting')])
def test_order_and_duplicates(day_sim, days, fragment):
    _entry(day_sim)['irrigation'] = [dict(days_after_planting=d, amount=10, method='IR001')
                                    for d in days]
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert fragment in problems[0]
    assert 'event 2' in problems[0]


@pytest.mark.parametrize('timing', [{}, {'date': '1982-02-25', 'days_after_planting': 0}])
def test_exactly_one_timing_field(day_sim, timing):
    _entry(day_sim)['irrigation'] = [dict(amount=10, method='IR001', **timing)]
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert 'date' in problems[0] and 'days_after_planting' in problems[0]
    assert 'exactly one' in problems[0]


def test_mixed_list_is_rejected(day_sim):
    _entry(day_sim)['irrigation'].append(dict(date='1982-02-26', amount=10, method='IR001'))
    problems = day_sim.check(False)
    assert any('mixes' in p and 'date' in p and 'days_after_planting' in p for p in problems)


@pytest.mark.parametrize('code,timing,instruction', [
    ('D', {'date': '1982-02-25'}, 'uses a date but the irrigation management is "D" '
     '(days after planting). Use days_after_planting, or set controls irrigation_management to "R".'),
    *[(code, {'days_after_planting': 0}, f'uses days after planting but the irrigation management '
       f'is "{code}" (dates). Use date, or set controls irrigation_management to "D".')
      for code in 'RPW'],
    *[(code, timing, f'has an event but the irrigation management is "{code}" (no events). '
       f'Remove the events (irrigation: []), or set controls irrigation_management to "{fix}".')
      for code in 'AFN' for timing, fix in [({'date': '1982-02-25'}, 'R'),
                                            ({'days_after_planting': 0}, 'D')]],
])
def test_management_mismatch_is_one_actionable_problem(day_sim, code, timing, instruction):
    _entry(day_sim)['controls'] = {'irrigation_management': code}
    _entry(day_sim)['irrigation'] = [dict(amount=10, method='IR001', **timing)]
    assert day_sim.check(False) == [f'Management data treatment 1, irrigation, event 1: {instruction}']


@pytest.mark.parametrize('code,timing', [('D', {'days_after_planting': 0}),
                                        *[(c, {'date': '1982-02-25'}) for c in 'RPW']])
def test_matching_events_accepted(day_sim, code, timing):
    _entry(day_sim)['controls'] = {'irrigation_management': code}
    _entry(day_sim)['irrigation'] = [dict(amount=10, method='IR001', **timing)]
    assert day_sim.check(False) == []


@pytest.mark.parametrize('code', list('AFN'))
def test_no_event_codes_accept_empty_list(day_sim, code):
    _entry(day_sim)['controls'] = {'irrigation_management': code}
    _entry(day_sim)['irrigation'] = []
    assert day_sim.check(False) == []


def test_effective_irrig_reads_selected_filex_level_and_override_wins(day_sim):
    _code(day_sim, 'IRRIG', 'D')
    _entry(day_sim)['controls'] = {}
    assert day_sim.check(False) == []
    _entry(day_sim)['irrigation'] = [dict(date='1982-02-25', amount=10, method='IR001')]
    assert 'irrigation management is "D"' in day_sim.check(False)[0]
    _entry(day_sim)['controls'] = {'irrigation_management': 'R'}
    assert day_sim.check(False) == []


def test_l2_day_event_uses_templates_default_irrig(data, rows, installed):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={'treatments': {1: {'irrigation': [
                         dict(days_after_planting=0, amount=10, method='IR001')]}}})
    assert sim.check(False) == [
        'Management data treatment 1, irrigation, event 1: uses days after planting but the '
        'irrigation management is "R" (dates). Use date, or set controls irrigation_management to "D".']


def test_effective_irrig_uses_treatments_sm_not_first_level(day_sim):
    text = day_sim.filex.read_text(encoding='latin-1')
    text += ('@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL\n'
             ' 2 GE              1     1     S 82056  2150 N X IRRIGATION\n')
    header = '@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS\n'
    text += header + ' 2 MA              R     D     R     N     M\n'
    row = next(line for line in text.splitlines() if line.startswith(' 1 1 0 0'))
    text = text.replace(row, row[:-1] + '2')
    day_sim.filex.write_text(text, encoding='latin-1')
    _entry(day_sim)['controls'] = {}
    assert day_sim.check(False) == []


def test_day_after_weather_end_rejected(day_sim):
    _entry(day_sim)['irrigation'][0]['days_after_planting'] = 35
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert all(part in problems[0] for part in ['days_after_planting', '1982-04-01',
                                              'outside weather range', 'Supply weather'])


def test_invalid_day_is_skipped_for_order_and_duplicates(day_sim):
    _entry(day_sim)['irrigation'] = [dict(days_after_planting=d, amount=10, method='IR001')
                                    for d in [2, 'bad', 2]]
    problems = day_sim.check(False)
    assert len(problems) == 2
    assert 'integer at least 0' in problems[0]
    assert 'events 1 and 3' in problems[1]


def test_oversized_idate_is_a_column_width_problem(day_sim):
    del _entry(day_sim)['planting']
    _entry(day_sim)['irrigation'][0]['days_after_planting'] = 100000
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert 'IDATE' in problems[0] and 'does not fit' in problems[0]


@pytest.mark.parametrize('plant', [None, 'A', 'F'])
@pytest.mark.parametrize('in_filex', [False, True])
def test_unknown_planting_prints_skip_note_without_problem(day_sim, capsys, plant, in_filex):
    if plant is None:
        del _entry(day_sim)['planting']
    elif in_filex:
        _code(day_sim, 'PLANT', plant)
    else:
        _entry(day_sim)['controls']['planting_management'] = plant
    _entry(day_sim)['irrigation'][0]['days_after_planting'] = 35
    assert day_sim.check(True) == []
    report = capsys.readouterr().out
    assert 'Note: day-event-weather-range check was skipped (' in report
    assert ('planting section is omitted' if plant is None else f'planting management is "{plant}"') in report
    assert day_sim.check(False) == []
    assert capsys.readouterr().out == ''


def test_given_planting_management_overrides_filex_for_weather_check(day_sim):
    _code(day_sim, 'PLANT', 'A')
    _entry(day_sim)['controls']['planting_management'] = 'R'
    _entry(day_sim)['irrigation'][0]['days_after_planting'] = 35
    assert 'outside weather range' in day_sim.check(False)[0]


@pytest.mark.parametrize('mi', [0, 1])
@pytest.mark.parametrize('code', list('ADRPWFN'))
def test_code_change_requires_explicit_irrigation_for_inherited_level(day_sim, mi, code):
    del _entry(day_sim)['irrigation']
    _entry(day_sim)['controls'] = {'irrigation_management': code}
    text = day_sim.filex.read_text(encoding='latin-1')
    row = next(line for line in text.splitlines() if line.startswith(' 1 1 0 0'))
    end = next(line for line in text.splitlines() if line.startswith('@N R O C')).index(' MI') + 3
    text = text.replace(row, row[:end - 3] + str(mi).rjust(3) + row[end:])
    day_sim.filex.write_text(text, encoding='latin-1')
    problems = day_sim.check(False)
    assert len(problems) == mi
    if mi:
        assert all(part in problems[0] for part in ['irrigation_management', 'irrigation',
                                                  'MI 1', 'Supply', '[]'])


def test_rotation_components_reject_day_events(rotation_sim):
    rotation_sim.management['treatments'][1]['rotation'] = {
        1: {'irrigation': [dict(days_after_planting=0, amount=10, method='IR001')]}}
    problems = rotation_sim.check(False)
    assert len(problems) == 1
    assert all(part in problems[0] for part in ['rotation component 1', 'days_after_planting',
                                              'irrigation management', 'Use date'])


def test_template_documents_days_and_still_loads(day_sim, tmp_path):
    yaml = pytest.importorskip('yaml')
    path = tmp_path / 'experiment.yaml'
    write_experiment_template(path)
    text = path.read_text(encoding='utf-8')
    assert 'days_after_planting' in text and 'IDATE' in text
    template = yaml.safe_load(text)
    entry = template['treatments'][1]
    for section in ('cultivar', 'initial_conditions'):
        entry.pop(section)
    day_sim.management = template
    assert day_sim.check(False) == []
