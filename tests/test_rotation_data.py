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
    assert any('controls years, start_date and rotation' in p for p in sim.check(False))


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


def test_century_resolution(sim):
    if sim.filex is None:
        pytest.skip('Two-digit years belong to a copied FileX')
    sim.weather = weather('2077-03-15', '2081-03-15')
    sim.management['treatments'][1]['controls'] = dict(start_date='2077-03-15')
    edits(sim, {3: {'fertilizer': [fertilizer('2078-11-15')]}})
    assert sim.check(False) == []
    edits(sim, {3: {'fertilizer': [fertilizer('2078-10-01')]}})
    assert any("rotation component 2's end (2078-11-14)" in p for p in sim.check(False))


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


@pytest.mark.parametrize('day', ['1978-11-14', '1978-11-15'])
def test_lower_bound_is_exclusive(sim, day):
    edits(sim, {3: {'fertilizer': [fertilizer(day)]}})
    assert (sim.check(False) == []) == (day == '1978-11-15')


@pytest.mark.parametrize('omit_rotation', [False, True])
def test_first_inherited_planting_before_start(sim, omit_rotation):
    if omit_rotation:
        sim.management['treatments'][1].pop('rotation')
    sim.management['treatments'][1]['controls'] = dict(start_date='1978-03-16', years=1)
    assert any('rotation component 1' in p and 'before simulation start date' in p
               for p in sim.check(False))


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


@pytest.mark.parametrize('section', ['planting', 'cultivar', 'fertilizer', 'irrigation'])
def test_fallow_takes_only_field_operations(sim, section):
    edits(sim, {2: {section: []}})
    assert sim.check(False) == [
        'Management data treatment 1, rotation component 2: is a fallow (FA). '
        'Supply only residues, tillage and harvest sections; remove other sections.']


def test_fallow_needs_scheduled_end(sim):
    edits(sim, {2: {'harvest': []}})
    assert sim.check(False) == [
        'Management data treatment 1, rotation component 2, harvest: a fallow needs '
        'its scheduled end. Supply harvest events, or omit harvest to keep the FileX Level.']


@pytest.mark.parametrize('section,event,code,fix', [
    ('residues', dict(date='1978-11-15', material='RE001', amount=1500), 'N',
     'residue management "R" (reported dates), but it is "N". '
     'Set the component\'s FileX SM level column RESID to "R", or remove the residues events.'),
    ('harvest', dict(date='1978-11-15'), 'D',
     'harvest management "R" or "M", but it is "D". '
     'Set the component\'s FileX SM level column HARVS to "R" or "M", or remove the harvest events.'),
])
def test_component_operation_code_from_own_sm(sim, section, event, code, fix):
    if sim.filex is None:
        if section == 'harvest':
            pytest.skip('HARVS D belongs to a copied FileX')
    else:
        # Component 1 accepts both operations; component 3 has a different SM level.
        text = sim.filex.read_text().replace(' 1 MA              R     R     R     N     M',
                                           ' 1 MA              R     R     R     R     R')
        if section == 'harvest':
            text = text.replace(' 3 MA              R     R     R     N     M',
                                ' 3 MA              R     R     R     N     D')
        sim.filex.write_text(text)
    edits(sim, {3: {section: [event]}})
    kind = 'residue' if section == 'residues' else 'harvest'
    assert sim.check(False) == [
        f'Management data treatment 1, rotation component 3, {section}: '
        f'{kind} events need the {fix}']


@pytest.mark.parametrize('section,event', [
    ('residues', dict(date='1978-01-01', material='RE001', amount=1500)),
    ('tillage', dict(date='1978-01-01', implement='TI005', depth=20)),
    ('harvest', dict(date='1978-01-01')),
])
def test_component_operations_use_period_message(sim, section, event):
    edits(sim, {2: {section: [event]}})
    message = (
        f"Management data treatment 1, rotation component 2, {section}, event 1, field 'date': "
        "1978-01-01 is not after rotation component 1's end (1978-03-15). "
        "DSSAT applies a component's events only while it runs and would skip this one "
        "without a warning. Move the date into the component's period.")
    assert message in sim.check(False)


@pytest.mark.parametrize('day,valid', [('1978-11-20', False), ('1978-11-21', True)])
def test_reported_harvest_moves_neighbor_bound(sim, day, valid):
    # Keep the component periods separate while checking the edited event's lower bound.
    if sim.filex is None:
        sim.filex_template['rotation'][2]['planting']['date'] = '1978-11-21'
    else:
        sim.filex.write_text(sim.filex.read_text().replace(' 2 78319', ' 2 78325'))
    edits(sim, {2: {'harvest': [{'date': '1978-11-16'}, {'date': '1978-11-20'}]},
                3: {'fertilizer': [fertilizer(day)]}})
    problems = sim.check(False)
    assert (problems == []) == valid
    if not valid:
        assert len(problems) == 1
        assert "is not after rotation component 2's end (1978-11-20)" in problems[0]


def test_maturity_harvest_ignores_populated_hdate(sim, capsys):
    if sim.filex is None:
        pytest.skip('HARVS M with populated HDATE belongs to a copied FileX')
    text = sim.filex.read_text().replace(' 2 MA              R     R     R     N     R',
                                       ' 2 MA              R     R     R     N     M')
    sim.filex.write_text(text)
    edits(sim, {3: {'fertilizer': [fertilizer('1978-10-01')]}})
    assert sim.check(True) == []
    report = capsys.readouterr().out
    assert ('rotation component 2: period bound check was skipped because HARVS "M" '
            'harvests at maturity and ignores HDATE; the end bound is unknown and not checked.') in report
    assert 'Correct the FileX date' not in report


@pytest.mark.parametrize('section,event,column,field,fix', [
    ('residues', dict(date='1978-11-15', material='RE001', amount=1500), 'RESID', 'residue', '"R"'),
    ('harvest', dict(date='1978-11-15'), 'HARVS', 'harvest_management', '"R" or "M"'),
])
@pytest.mark.parametrize('code', ['G', 'X', '-99', None, 'unreadable_sm'])
def test_component_rejects_unusable_operation_code(sim, section, event, column, field, fix, code):
    if sim.filex is None:
        pytest.skip('Unavailable or unknown SM codes belong to a copied FileX')
    old = ' 3 MA              R     R     R     N     M'
    row = ('' if code is None else
           f' 3 MA              R     R     R{code:>6}     M' if column == 'RESID' else
           f' 3 MA              R     R     R     N{code:>6}')
    text = sim.filex.read_text().replace(old, row)
    if code == 'unreadable_sm':
        text = sim.filex.read_text().replace(' 0  0  0  0  3\n', ' 0  0  0  0  X\n')
    sim.filex.write_text(text)
    edits(sim, {3: {section: [event]}})
    problems = [p for p in sim.check(False) if f'{section}: ' in p and 'events need' in p]
    assert len(problems) == 1
    if code in (None, 'unreadable_sm'):
        assert f'could not be read (checked controls {field} and the FileX SM level column {column})' in problems[0]
        assert '"None"' not in problems[0]
    else:
        assert f'but it is "{code}".' in problems[0]
    assert f'Set the component\'s FileX SM level column {column} to {fix}, or remove the {section} events.' in problems[0]


@pytest.mark.parametrize('day,valid', [('1978-11-14', True), ('1978-11-15', False), ('1978-11-20', False)])
def test_edited_end_rechecks_unchanged_next_planting(sim, day, valid):
    edits(sim, {2: {'harvest': [{'date': '1978-11-01'}, {'date': day}]}})
    problems = sim.check(False)
    expected = (
        "Management data treatment 1, rotation component 2, harvest, event 2, field 'date': "
        f"{day} is not before rotation component 3's planting date (1978-11-15). "
        "DSSAT applies a component's events only while it runs and would skip this one "
        "without a warning. Move the date into the component's period.")
    assert problems == ([] if valid else [expected])


@pytest.mark.parametrize('day,valid', [('1979-03-13', True), ('1979-03-14', False), ('1979-03-20', False)])
def test_edited_end_rechecks_next_fallow_end(sim, day, valid):
    if sim.filex is None:
        sim.filex_template['rotation'][2]['harvest_date'] = '1979-03-01'
    else:
        sim.filex.write_text(sim.filex.read_text().replace(' 3 MA              R     R     R     N     M',
                                                        ' 3 MA              R     R     R     N     R'))
    edits(sim, {3: {'harvest': [{'date': day}]}})
    problems = sim.check(False)
    assert (problems == []) == valid
    if not valid:
        assert len(problems) == 1
        assert f"{day} is not before rotation component 4's end date (1979-03-14)" in problems[0]


@pytest.mark.parametrize('day,valid', [('1978-11-14', True), ('1978-11-15', False), ('1978-11-20', False)])
def test_fallow_end_rechecks_unchanged_next_planting(sim, day, valid):
    if sim.filex is not None:
        pytest.skip('end_date belongs to a FileX template')
    sim.filex_template['rotation'][1]['end_date'] = day
    problems = sim.check(False)
    assert (problems == []) == valid
    if not valid:
        assert any(f"1978-11-15 is not after rotation[2]'s end ({day})" in p
                   for p in problems)
