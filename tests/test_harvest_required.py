"""Reported harvests require a usable event after all experiment edits."""

from copy import deepcopy

import pytest

from dssatlab import Simulation
from test_season_coverage import weather
from test_filex_template import data, rows
from test_rotation_template import rotation
from test_simulation_template import installed
from test_simulation_run import fake_dssat
from test_rotation_data import sim, edits


MESSAGE = ('Treatment 7: harvest management is "R" (reported dates), but there are '
           'no harvest events with a date. Add a harvest event, or set controls '
           'harvest_management to another code.')
COMPONENT_MESSAGE = ('Treatment 7, rotation[2]: harvest management is "R" (reported '
                     'dates), but there are no harvest events with a date. Add a '
                     'harvest event to this component, or change HARVS in the FileX '
                     'simulation controls.')


def simulation(tmp_path, *, code='R', level=0, harvest='82057', sequence=False, fallow=False):
    rows = [f' 7 1 0 0 Harvest                    1  1  0  0  0  0  0  0  0  0  0 {level:2d}  1']
    if sequence:
        # Only component 2 uses the requested code; component 1 uses maturity.
        rows.append(f' 7 2 0 0 Harvest                    {2 if fallow else 1}  1  0  0  0  0  0  0  0  0  0 {level:2d}  2')
    text = '\n'.join([
        '*TREATMENTS',
        '@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM',
        *rows, '', '*CULTIVARS', '@C CR INGENO CNAME',
        ' 1 MZ IB0035 Maize', ' 2 FA IB0001 Fallow', '', '*FIELDS',
        '@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME',
        ' 1 UFGA0002 UFGA       -99     0 DR000     0     0 00000 -99    180  IBMZ910214 Field',
        '', '*HARVEST DETAILS', '@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME',
        f' 1 {harvest:>5} GS000   -99   -99   100     0 -99',
        '', '*SIMULATION CONTROLS',
        '@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL',
        ' 1 GE              1     1     S 82056  2150 Harvest',
        ' 2 GE              1     1     S 82056  2150 Harvest',
        '@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS',
        f' 1 MA              R     R     R     N     {"M" if sequence else code}',
        f' 2 MA              R     R     R     N     {code}', '',
    ])
    path = tmp_path / ('UFGA8201.SQX' if sequence else 'UFGA8201.MZX')
    path.write_text(text, encoding='latin-1')
    return Simulation(path, 7, weather('1982-02-25', '1983-02-24', station='UFGA'))


@pytest.mark.parametrize('entry', [None, {}, {'fertilizer': []}, {'harvest': []}])
def test_reported_harvest_without_events(tmp_path, entry, capsys):
    sim = simulation(tmp_path, level=1 if entry == {'harvest': []} else 0)
    sim.management = None if entry is None else {'treatments': {'07': entry}}
    before = sim.filex.read_bytes(), deepcopy(sim.management)
    assert sim.check(True) == [MESSAGE]
    assert MESSAGE in capsys.readouterr().out
    assert (sim.filex.read_bytes(), sim.management) == before


@pytest.mark.parametrize('harvest', ['', '-99', 'xxxxx', '82000', '82366', '82999'])
def test_referenced_level_needs_usable_hdate(tmp_path, harvest):
    sim = simulation(tmp_path, level=1, harvest=harvest)
    assert sim.check(False) == [MESSAGE]


def test_referenced_level_without_hdate_column(tmp_path):
    sim = simulation(tmp_path, level=1)
    sim.filex.write_text(sim.filex.read_text().replace('HDATE', 'XXXXX'))
    assert sim.check(False) == [MESSAGE]


def test_usable_hdate_in_later_row_of_referenced_level(tmp_path):
    sim = simulation(tmp_path, level=1, harvest='-99')
    text = sim.filex.read_text().replace('*SIMULATION CONTROLS',
        ' 1 82057 GS000   -99   -99   100     0 -99\n\n*SIMULATION CONTROLS')
    # Keep both events in the same header block (a blank line closes it).
    text = text.replace('-99\n\n 1 82057', '-99\n 1 82057')
    sim.filex.write_text(text)
    assert sim.check(False) == []


def test_each_experiment_treatment_is_checked(tmp_path):
    sim = simulation(tmp_path)
    text = sim.filex.read_text()
    row = next(line for line in text.splitlines() if line.startswith(' 7 1'))
    sim.filex.write_text(text.replace(row, row + '\n' + row.replace(' 7 1', ' 8 1', 1)))
    sim.management = {'treatments': {7: {'harvest': [{'date': '1982-02-26'}]}, 8: {}}}
    assert sim.check(False) == [MESSAGE.replace('Treatment 7', 'Treatment 8')]


@pytest.mark.parametrize('code', ['M', 'A'])
@pytest.mark.parametrize('override', [False, True])
def test_maturity_and_automatic_harvest_need_no_events(tmp_path, code, override):
    sim = simulation(tmp_path, code='R' if override else code)
    sim.management = {'treatments': {7: {'harvest': []}}}
    if override:
        sim.management['treatments'][7]['controls'] = {'harvest_management': code}
    assert sim.check(False) == []


def test_controls_override_requires_reported_harvest(tmp_path):
    sim = simulation(tmp_path, code='M')
    sim.management = {'treatments': {7: {'controls': {'harvest_management': 'R'}}}}
    assert sim.check(False) == [MESSAGE]


@pytest.mark.parametrize('edited', [False, True])
def test_usable_event_from_filex_or_edit(tmp_path, edited):
    sim = simulation(tmp_path, level=0 if edited else 1)
    if edited:
        sim.management = {'treatments': {7: {'harvest': [{'date': '1982-02-26'}]}}}
    assert sim.check(False) == []


@pytest.mark.parametrize('entry', [None, {}, {'rotation': {'2': {'harvest': []}}}])
def test_crop_component_requires_event_and_names_filex_fix(tmp_path, entry):
    sim = simulation(tmp_path, sequence=True, level=1 if entry and 'rotation' in entry else 0)
    sim.management = None if entry is None else {'treatments': {7: entry}}
    assert sim.check(False) == [COMPONENT_MESSAGE]


@pytest.mark.parametrize('code', ['M', 'A'])
def test_component_without_reported_harvest_needs_no_events(tmp_path, code):
    assert simulation(tmp_path, sequence=True, code=code).check(False) == []


def test_fallow_without_harvest_is_unaffected(tmp_path):
    assert simulation(tmp_path, sequence=True, fallow=True).check(False) == []


def test_each_crop_component_is_checked_once(tmp_path):
    sim = simulation(tmp_path, sequence=True)
    sim.filex.write_text(sim.filex.read_text().replace(
        ' 1 MA              R     R     R     N     M',
        ' 1 MA              R     R     R     N     R'))
    sim.management = {'treatments': {7: {'rotation': {}}}}
    assert sim.check(False) == [COMPONENT_MESSAGE.replace('rotation[2]', 'rotation[1]'),
                              COMPONENT_MESSAGE]


def test_component_edit_supplies_usable_event(tmp_path):
    sim = simulation(tmp_path, sequence=True, level=1, harvest='-99')
    sim.management = {'treatments': {7: {'rotation': {2: {'harvest': [{'date': '1982-02-26'}]}}}}}
    assert sim.check(False) == []


def test_component_referenced_level_needs_hdate(tmp_path):
    assert simulation(tmp_path, sequence=True, level=1, harvest='-99').check(False) == [COMPONENT_MESSAGE]


def test_single_crop_template_harvest_edit(data, rows, installed):
    data['harvest_date'] = '2021-03-02'
    sim = Simulation(filex_template=data, weather=weather('2021-03-01', '2021-03-02'), soil=rows[1],
                     management={'treatments': {1: {'harvest': []}}})
    assert sim.check(False) == [MESSAGE.replace('Treatment 7', 'Treatment 1')]


def test_rotation_template_harvest_edit(rotation, rows, installed):
    rotation['rotation'][0]['harvest_date'] = '1978-10-01'
    rotation['rotation'][2]['cultivar']['code'] = 'IB0488'
    sim = Simulation(filex_template=rotation, soil=rows[1],
                     weather=weather('1978-03-15', '1979-03-14'),
                     management={'treatments': {1: {'rotation': {1: {'harvest': []}}}}})
    assert sim.check(False) == [COMPONENT_MESSAGE.replace('Treatment 7', 'Treatment 1')
                              .replace('rotation[2]', 'rotation[1]')]


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
        # M accepts harvest details without needing dates; component 3 has its own SM.
        text = sim.filex.read_text().replace(' 1 MA              R     R     R     N     M',
                                           ' 1 MA              R     R     R     R     M')
        if section == 'harvest':
            text = text.replace(' 3 MA              R     R     R     N     M',
                                ' 3 MA              R     R     R     N     D')
        sim.filex.write_text(text)
    edits(sim, {3: {section: [event]}})
    kind = 'residue' if section == 'residues' else 'harvest'
    assert sim.check(False) == [
        f'Management data treatment 1, rotation component 3, {section}: '
        f'{kind} events need the {fix}']


