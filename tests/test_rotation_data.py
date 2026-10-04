"""Experiment data per rotation component, through both Simulation paths."""
from pathlib import Path
import shutil

import pytest

from dssatlab import Simulation
from test_filex_template import data, rows
from test_rotation_template import rotation
from test_simulation_template import installed
from test_simulation_run import fake_dssat, snapshot
from test_season_coverage import weather


@pytest.fixture(params=['copied', 'template'])
def sim(request, rotation, rows, installed, tmp_path):
    rotation['rotation'][2]['cultivar']['code'] = 'IB0488'
    kwargs = dict(weather=weather('1978-03-15', '1981-03-15'),
                  management={'treatments': {1: {'rotation': {}}}})
    if request.param == 'template':
        return Simulation(filex_template=rotation, soil=rows[1], **kwargs)
    path = tmp_path / 'ZZZZ7801.SQX'
    path.write_bytes((Path(__file__).parent / 'fixtures/rotation_writers.SQX').read_bytes())
    for prefix in ('WHCER048', 'MZCER048'):
        shutil.copy2(installed.executable.parent / 'Genotype' / (prefix + '.CUL'), tmp_path)
    return Simulation(path, **kwargs)


def edits(sim, value):
    sim.management['treatments'][1]['rotation'] = value


def fertilizer(day):
    return dict(date=day, material='FE005', application='AP001', depth=5, n=40)


def test_valid_read_only(sim, tmp_path, capsys):
    edits(sim, {'3': {'cultivar': {'crop': 'WH', 'code': 'ZZ0001'},
                      'fertilizer': [fertilizer('1978-11-15')]},
                1: {'irrigation': [dict(date='1978-05-01', amount=25, method='IR001')]}})
    before = snapshot(tmp_path)
    assert sim.check(True) == []
    report = capsys.readouterr().out
    assert 'rotation component 3' in report and 'fertilizer: OK' in report
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('value,match', [
    ({5: {}}, 'Use one of those numbers'),
    ({2: {'fertilizer': []}}, 'is a fallow (FA)'),
    ({3: {'cultivar': {'crop': 'MZ', 'code': 'IB0035'}}}, "component's crop 'WH'"),
    ({1: {}, '1': {}}, 'duplicate rotation component number'),
    ({True: {}}, 'invalid rotation component key'),
    ({'x': {}}, 'invalid rotation component key'),
    ([], 'rotation must be a dict'),
    ({3: []}, 'entry must be a dict'),
    ({3: {'controls': {}}}, 'unknown key'),
])
def test_shape(sim, value, match):
    edits(sim, value)
    assert any(match in p for p in sim.check(False))


@pytest.mark.parametrize('section', ['fertilizer', 'irrigation', 'planting'])
@pytest.mark.parametrize('day,match', [
    ('1978-10-01', "is not after rotation component 2's end (1978-11-14)"),
    ('1979-03-14', "is not before rotation component 4's end date (1979-03-14)"),
    ('1982-03-15', 'outside weather range'),
])
def test_period(sim, section, day, match, capsys):
    value = ([fertilizer(day)] if section == 'fertilizer' else
             [dict(date=day, amount=25, method='IR001')] if section == 'irrigation' else
             dict(date=day, method='S', distribution='R', population=7, row_spacing=75, depth=5))
    edits(sim, {3: {section: value}})
    assert any(match in p for p in sim.check(True))
    assert section + ': REJECTED' in capsys.readouterr().out


def test_first_planting_before_start(sim):
    edits(sim, {1: {'planting': dict(date='1978-03-14', method='S', distribution='R',
                                    population=7, row_spacing=75, depth=5)}})
    assert any('before simulation start date' in p for p in sim.check(False))


def test_component_coefficients_rejected(sim):
    edits(sim, {3: {'cultivar': {'crop': 'WH', 'code': 'ZZ0001',
                                'coefficients': {'P1': 300}}}})
    message = ("Management data treatment 1, rotation component 3, cultivar: coefficients "
               "are supported in a treatment's cultivar section only, not per rotation "
               "component. Remove 'coefficients'.")
    assert message in sim.check(False)
    from dssatlab import DSSATCheckError
    with pytest.raises(DSSATCheckError) as error:
        sim.run()
    assert message in error.value.problems


@pytest.mark.parametrize('field,value', [('ecotype', 'IB0001'), ('name', 'New name')])
def test_component_new_cultivar_fields_rejected(sim, field, value):
    edits(sim, {3: {'cultivar': {'crop': 'WH', 'code': 'ZZ0001', field: value}}})
    assert any(field in p and 'not per rotation component' in p and 'Remove' in p
               for p in sim.check(False))

@pytest.mark.parametrize('value', ['-99', 'XXXXX', '78367'])
def test_unreadable_bound_note(sim, value, capsys):
    if sim.filex is None:
        pytest.skip('Unreadable DSSAT dates belong to a copied FileX')
    sim.filex.write_text(sim.filex.read_text().replace(' 1 78318 GS000', f' 1 {value:>5} GS000'))
    edits(sim, {3: {'fertilizer': [fertilizer('1978-10-01')]}})
    assert sim.check(True) == []
    report = capsys.readouterr().out
    assert 'rotation component 2' in report and 'period bound check was skipped' in report
    assert 'HDATE' in report


@pytest.mark.parametrize('day,valid', [('1978-07-15', True), ('1978-07-16', False)])
def test_explicit_harvest_bound(sim, day, valid):
    if sim.filex is None:
        sim.filex_template['rotation'][0]['harvest_date'] = '1978-07-15'
    else:
        text = sim.filex.read_text().replace(' 0  0  0  0  1\n', ' 0  0  0  3  1\n', 1)
        text = text.replace(' 2 79073 GS000', ' 3 78196 GS000   -99   -99   -99   -99 -99\n 2 79073 GS000')
        text = text.replace(' 1 MA              R     R     R     N     M',
                            ' 1 MA              R     R     R     N     R')
        sim.filex.write_text(text)
    edits(sim, {1: {'fertilizer': [fertilizer(day)]}})
    problems = sim.check(False)
    assert (problems == []) == valid
    if not valid:
        assert any("is after rotation component 1's harvest date (1978-07-15)" in p for p in problems)


@pytest.mark.parametrize('section,value,match', [
    ('planting', {'date': '1978-11-15'}, 'missing'),
    ('fertilizer', [dict(fertilizer('1978-11-15'), n=-1)], 'nonnegative'),
    ('irrigation', [dict(date='1978-11-15', amount=0, method='IR001')], 'above zero'),
    ('cultivar', dict(crop='WH', code='BAD999'), '.CUL'),
])
def test_reuses_checks(sim, section, value, match):
    edits(sim, {3: {section: value}})
    problems = sim.check(False)
    assert any(match in p and 'rotation component 3' in p for p in problems)


def test_controls_and_rotation(sim):
    sim.management['treatments'][1]['controls'] = dict(years=2, start_date='1978-03-15')
    edits(sim, {3: {'fertilizer': []}})
    assert sim.check(False) == []


def test_sequence_other_keys(sim):
    sim.management['treatments'][1]['planting'] = {}
    assert any('controls years, start_date, weather_source, replicates, random_seed and rotation'
               in p for p in sim.check(False))


def test_non_sequence(data, rows, installed):
    sim = Simulation(filex_template=data, weather=rows[0], soil=rows[1],
                     management={'treatments': {1: {'rotation': {}}}})
    assert any('rotation applies only to a sequence' in p and
               'move the sections up to the treatment' in p for p in sim.check(False))


def test_template_example(sim, tmp_path, installed):
    from dssatlab import write_management_template
    yaml = pytest.importorskip('yaml')
    path = tmp_path / 'management.yaml'
    write_management_template(path)
    text = path.read_text()
    example = text[text.index('    # rotation:'):]
    sim.management = yaml.safe_load('treatments:\n  1:\n' + example.replace('    # ', '    '))
    cultivar = (installed.executable.parent / 'Genotype/WHCER048.CUL' if sim.filex is None
                else sim.filex.parent / 'WHCER048.CUL')
    cultivar.write_text(cultivar.read_text() + 'IB1500 Example\n')
    assert sim.check(False) == []


def test_override_dates_bound_neighbor(sim):
    # Remove the intervening fallow's readable end: lower bound for wheat is then absent.
    # A planting override on wheat becomes its preceding component's next known date.
    if sim.filex is not None:
        text = sim.filex.read_text()
        text = text.replace(' 1 2 0 0 Rotation                   2', ' 1 2 0 0 Rotation                   1')
        text = text.replace(' 0  0  0  1  2\n', ' 0  0  0  0  2\n')
        sim.filex.write_text(text)
    else:
        from copy import deepcopy
        sim.filex_template['rotation'][1] = deepcopy(sim.filex_template['rotation'][0])
        sim.filex_template['rotation'][1]['planting']['date'] = '1978-08-01'
    edits(sim, {2: {'fertilizer': [fertilizer('1978-11-15')]},
                3: {'planting': dict(date='1978-11-14', method='S', distribution='R',
                                     population=7, row_spacing=75, depth=5)}})
    assert any("is not before rotation component 3's planting date (1978-11-14)"
               in p for p in sim.check(False))


def test_rejected_check_writes_nothing(sim, tmp_path):
    edits(sim, {3: {'fertilizer': [fertilizer('1978-10-01')]}})
    before = snapshot(tmp_path)
    assert sim.check(False)
    assert snapshot(tmp_path) == before


def test_maturity_is_not_guessed(sim):
    # Probe D: actual maize maturity is in July, but it is unknowable before a run.
    edits(sim, {1: {'fertilizer': [fertilizer('1978-10-01')]}})
    assert sim.check(False) == []


@pytest.mark.parametrize('omit_rotation', [False, True])
def test_all_known_dates_need_weather(sim, omit_rotation):
    if omit_rotation:
        sim.management['treatments'][1].pop('rotation')
    sim.weather = weather('1978-03-15', '1978-12-31')
    assert any('rotation component 4' in p and 'outside weather range' in p
               for p in sim.check(False))


def test_start_override_does_not_change_filex_century(sim):
    if sim.filex is None:
        pytest.skip('Two-digit years belong to a copied FileX')
    sim.weather = weather('2000-03-15', '2004-03-15')
    sim.management['treatments'][1]['controls'] = dict(start_date='2000-03-15')
    edits(sim, {3: {'fertilizer': [fertilizer('2001-11-15')]}})
    problems = sim.check(False)
    assert any("date '1978-03-15' is outside weather range" in p for p in problems)
    assert any("rotation component 4's end date (1979-03-14)" in p for p in problems)
    edits(sim, {3: {'fertilizer': [fertilizer('1978-10-01')]}})
    assert any("rotation component 2's end (1978-11-14)" in p for p in sim.check(False))


def test_loop_renders_all_component_edits(tmp_path):
    from dssatlab.rotation_data import _rotation_text
    from dssatlab.filex import _section_row
    original = (Path(__file__).parent / 'fixtures/rotation_writers.SQX').read_text()
    written = _rotation_text(original, 1, {1: {'fertilizer': [fertilizer('1978-03-15')]},
        '3': {'fertilizer': [fertilizer('1978-11-15')], 'cultivar': dict(crop='WH', code='ZZ0001')}})
    treatments = written.split('*TREATMENTS', 1)[1].split('*CULTIVARS')[0].splitlines()[2:6]
    assert treatments[0][52:55].strip() == '3'
    assert treatments[2][52:55].strip() == '4'
    assert _section_row(written, 'FERTILIZERS (INORGANIC)', 'F', 4, ('FDATE',))['FDATE'] == '78319'
    assert _section_row(written, 'CULTIVARS', 'C', 4, ('INGENO',))['INGENO'] == 'ZZ0001'
    original_rows = original.split('*TREATMENTS', 1)[1].split('*CULTIVARS')[0].splitlines()[2:6]
    assert [treatments[1], treatments[3]] == [original_rows[1], original_rows[3]]


def test_non_sequence_copied(tmp_path):
    source = (Path(__file__).parent / 'fixtures/rotation_writers.SQX').read_text()
    text = '\n'.join(line for line in source.splitlines()
                     if not any(line.startswith(f' 1 {r} 0 0 ') for r in (2, 3, 4)))
    path = tmp_path / 'ZZZZ7801.SQX'
    path.write_text(text)
    sim = Simulation(path, weather=weather('1978-03-15', '1981-03-15'),
                     management={'treatments': {1: {'rotation': {3: {}}}}})
    assert any('rotation applies only to a sequence' in p for p in sim.check(False))


@pytest.mark.parametrize('section,value', [
    ('planting', dict(date='1978-11-15', method='S', distribution='R',
                     population=1000000, row_spacing=75, depth=5)),
    ('fertilizer', [dict(fertilizer('1978-11-15'), n=1000000)]),
    ('irrigation', [dict(date='1978-11-15', amount=1000000, method='IR001')]),
])
def test_render_checks_column_fit(sim, section, value):
    edits(sim, {3: {section: value}})
    assert any('rotation component 3' in p and section in p for p in sim.check(False))


@pytest.mark.parametrize('day,invalid', [
    ('1978-01-01', True), ('1978-03-14', True), ('1978-03-15', False),
])
def test_override_cycle_closure(rotation, rows, installed, day, invalid):
    planting = dict(rotation['rotation'][0]['planting'], date=day)
    sim = Simulation(filex_template=rotation, soil=rows[1],
                     weather=weather('1978-01-01', '1981-03-15'),
                     management={'treatments': {1: {
                         'controls': {'start_date': '1978-01-01'},
                         'rotation': {1: {'planting': planting}},
                     }}})
    problems = sim.check(False)
    closure = [p for p in problems if 'next cycle' in p]
    assert bool(closure) == invalid
    assert all('Management data treatment 1, rotation component 1, planting' in p
               for p in closure)


@pytest.mark.parametrize('component', [1, '1', '01', 3])
@pytest.mark.parametrize('irrigation', [None, [], [
    dict(date='1978-06-02', amount=25, method='IR001'),
]])
def test_component_irrigation_replaces_inherited_guard(sim, component, irrigation):
    if sim.filex is None:
        pytest.skip('Inherited irrigation belongs to a copied FileX')
    entry = sim.management['treatments'][1]
    entry['controls'] = dict(start_date='1978-06-02', years=1)
    entry['rotation'] = {1: {'planting': dict(date='1978-06-02', method='S',
        distribution='R', population=7, row_spacing=75, depth=5)}}
    if irrigation is not None:
        entry['rotation'].setdefault(component, {})['irrigation'] = irrigation
        if isinstance(component, str):
            entry['rotation'][component].update(entry['rotation'].pop(1))
    problems = sim.check(False)
    assert any('IPIRR' in p for p in problems) == (irrigation is None or component == 3)
    if irrigation is not None and component != 3:
        assert problems == []
