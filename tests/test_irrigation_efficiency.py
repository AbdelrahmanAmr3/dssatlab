"""Irrigation level efficiency through the copied and template Simulation paths."""

from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from dssatlab import DSSATCheckError, Simulation, write_experiment_template
from dssatlab.filex import _section_row
from test_controls_options import option_sim
from test_filex_template import data, rows
from test_irrigation_days import day_sim
from test_management_file import sim_inputs
from test_rotation_data import sim as rotation_sim
from test_rotation_template import rotation
from test_season_coverage import weather
from test_simulation_run import fake_dssat
from test_simulation_template import installed


def _entry(sim):
    return sim.management['treatments'][1]


@pytest.mark.parametrize('template', [False, True])
@pytest.mark.parametrize('timing', ['date', 'days_after_planting', 'empty'])
def test_dict_writes_level_efficiency(day_sim, data, rows, installed, template, timing):
    sim = day_sim
    if template:
        data['planting']['date'] = '1982-02-25'
        sim = Simulation(filex_template=data, weather=day_sim.weather, soil=rows[1],
                         management=deepcopy(day_sim.management))
    events = ([] if timing == 'empty' else
              [dict(amount=10, method='IR001', **{timing: '1982-02-25' if timing == 'date' else 0})])
    _entry(sim)['irrigation'] = dict(efficiency=0.75, events=events)
    _entry(sim)['controls'] = {'irrigation_management': 'D' if timing == 'days_after_planting' else 'R'}
    original = None if template else sim.filex.read_bytes()
    inputs = deepcopy(sim.management)
    assert sim.check(False) == []
    result = sim.run()
    text = next(result.run_dir.parent.glob('*.MZX')).read_bytes().decode('latin-1')
    level = int(_section_row(text, 'TREATMENTS', 'N', 1, ('MI',))['MI'])
    assert level > 0
    header = _section_row(text, 'IRRIGATION', 'I', level, ('EFIR', 'IDEP'))
    assert header['EFIR'] == '0.75'
    assert header['IDEP'] == '-99'
    written_events = [line.split() for line in text.splitlines()
                      if len(line.split()) == 4 and line.split()[0] == str(level) and 'IR001' in line]
    assert written_events == ([] if timing == 'empty' else
                              [[str(level), '82056' if timing == 'date' else '0', 'IR001', '10']])
    assert sim.management == inputs
    if template:
        defaults = _section_row(text, 'SIMULATION CONTROLS', 'N', 1, ('MANAGEMENT', 'IRRIG', 'PLANT'))
        assert defaults['IRRIG'] == defaults['PLANT'] == 'R'
    if not template:
        assert sim.filex.read_bytes() == original


@pytest.mark.parametrize('value', [0, -0.1, 1.5, True, False, '0.75', None, float('nan'), float('inf')])
def test_bad_efficiency_is_one_problem(day_sim, value):
    _entry(day_sim)['irrigation'] = dict(efficiency=value, events=[])
    expected = ("Management data treatment 1, irrigation, field 'efficiency': "
                f'found {value!r}. Supply a number above 0 and at most 1 (DSSAT EFIR).')
    assert day_sim.check(False) == [expected]
    with pytest.raises(DSSATCheckError) as error:
        day_sim.run()
    assert error.value.problems == [expected]


@pytest.mark.parametrize('value,fragment', [
    ({}, 'expected a list of event dicts'),
    ({'efficiency': 0.75}, "missing required field 'events'"),
    ({'events': []}, "missing required field 'efficiency'"),
    ({'efficiency': 0.75, 'events': None}, "field 'events': found None. Supply a list"),
    ({'efficiency': 0.75, 'events': {}}, "field 'events': found {}. Supply a list"),
    ({'efficiency': 0.75, 'events': 'none'}, "field 'events': found 'none'. Supply a list"),
    ({'efficiency': 0.75, 'events': [], 'extra': 1}, "unknown key 'extra'"),
])
def test_bad_dict_shape_is_one_problem(day_sim, value, fragment):
    _entry(day_sim)['irrigation'] = value
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert problems[0].startswith('Management data treatment 1, irrigation')
    assert fragment in problems[0]
    assert 'Supply' in problems[0] or 'Add' in problems[0] or 'Use only' in problems[0]


@pytest.mark.parametrize('efficiency', [1, 1.0, 0.01])
def test_efficiency_valid_boundaries(day_sim, efficiency):
    _entry(day_sim)['irrigation'] = dict(efficiency=efficiency, events=[])
    assert day_sim.check(False) == []


def test_efficiency_must_fit_efir_without_rounding(day_sim):
    _entry(day_sim)['irrigation'] = dict(efficiency=0.12345, events=[])
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert all(part in problems[0] for part in ['EFIR', '0.12345', 'does not fit', 'without rounding'])


@pytest.mark.parametrize('code', list('AFNDRPW'))
def test_empty_dict_counts_as_given_with_inherited_events(day_sim, code):
    text = day_sim.filex.read_text(encoding='latin-1')
    row = next(line for line in text.splitlines() if line.startswith(' 1 1 0 0'))
    end = next(line for line in text.splitlines() if line.startswith('@N R O C')).index(' MI') + 3
    day_sim.filex.write_text(text.replace(row, row[:end - 3] + '  1' + row[end:]), encoding='latin-1')
    _entry(day_sim)['controls'] = {'irrigation_management': code}
    _entry(day_sim)['irrigation'] = dict(efficiency=0.75, events=[])
    assert day_sim.check(False) == []


@pytest.mark.parametrize('events,fragment', [
    ([dict(days_after_planting=-1, amount=10, method='IR001')], 'integer at least 0'),
    ([dict(days_after_planting=35, amount=10, method='IR001')], 'outside weather range'),
    ([dict(date='1982-02-25', amount=10, method='IR001')], 'irrigation management is "D"'),
    ([dict(days_after_planting=0, amount=0, method='IR001')], 'number above zero'),
    ([dict(days_after_planting=0, amount=10, method='bad')], 'two ASCII letters'),
    ([dict(days_after_planting=d, amount=10, method='IR001') for d in [1, 1]], 'duplicate'),
    ([dict(days_after_planting=d, amount=10, method='IR001') for d in [2, 1]], 'ascending order'),
    ([dict(amount=10, method='IR001')], 'exactly one'),
])
def test_dict_reuses_event_checks(day_sim, events, fragment):
    _entry(day_sim)['irrigation'] = dict(efficiency=0.75, events=events)
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert fragment in problems[0]


@pytest.mark.parametrize('code,timing', [
    *[(c, 'days_after_planting') for c in 'RPW'],
    *[(c, timing) for c in 'AFN' for timing in ['date', 'days_after_planting']],
])
def test_dict_reuses_management_mismatch_checks(day_sim, code, timing):
    _entry(day_sim)['controls'] = {'irrigation_management': code}
    _entry(day_sim)['irrigation'] = dict(efficiency=0.75, events=[dict(
        amount=10, method='IR001', **{timing: '1982-02-25' if timing == 'date' else 0})])
    problems = day_sim.check(False)
    assert len(problems) == 1
    assert f'irrigation management is "{code}"' in problems[0]
    assert 'or set controls' in problems[0]


def test_rotation_components_reject_dict(rotation_sim):
    _entry(rotation_sim)['rotation'] = {1: {'irrigation': dict(efficiency=0.75, events=[])}}
    expected = ('Management data treatment 1, rotation component 1, irrigation: '
                'dict form is not supported per rotation component; irrigation management '
                'belongs to the treatment. Use dated events in a list.')
    assert rotation_sim.check(False) == [expected]


@pytest.mark.parametrize('events', [[], [dict(date='1982-02-25', amount=10, method='IR001')]])
def test_list_output_remains_byte_identical(day_sim, fake_dssat, events):
    del _entry(day_sim)['planting']
    _entry(day_sim)['controls'] = {}
    _entry(day_sim)['irrigation'] = events
    result = day_sim.run()
    written = next(result.run_dir.parent.glob('*.MZX')).read_bytes()
    original = day_sim.filex.read_bytes()
    if not events:
        expected = original.replace(
            b'RAINFED LOW NITROGEN       1  1  0  1  1  1  1',
            b'RAINFED LOW NITROGEN       1  1  0  1  1  0  1')
    else:
        block = (b'*IRRIGATION AND WATER MANAGEMENT\n'
                    b'@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME\n'
                    b' 1     1   -99   -99   -99   -99   -99   -99    -99\n'
                    b'@I IDATE  IROP IRVAL\n'
                    b' 1 82056 IR001    10\n\n')
        newline = b'\r\n' if b'\r\n' in original else b'\n'
        expected = original.replace(b'*SIMULATION CONTROLS',
                                    block.replace(b'\n', newline) + b'*SIMULATION CONTROLS')
    assert written == expected


def test_template_documents_dict_and_loads(day_sim, tmp_path):
    yaml = pytest.importorskip('yaml')
    fixture = Path(__file__).parent / 'fixtures/cultivar/MZCER048.CUL'
    shutil.copyfile(fixture, day_sim.filex.parent / fixture.name)
    path = tmp_path / 'experiment.yaml'
    write_experiment_template(path)
    text = path.read_text(encoding='utf-8')
    assert 'irrigation: {efficiency: 0.75, events: []}' in text
    assert "EFIR applies to the irrigation level's events; IREFF applies to automatic irrigation" in text
    template = yaml.safe_load(text)
    entry = template['treatments'][1]
    day_sim.management = path
    assert day_sim.check(False) == []
    entry['irrigation'] = dict(efficiency=0.75, events=entry['irrigation'])
    path.write_text(yaml.safe_dump(template), encoding='utf-8')
    assert day_sim.check(False) == []
