"""Template fields keep their own weather and soil in both FIELDS tables."""

from copy import deepcopy

import pytest

from dssatlab import write_filex_template
from dssatlab.filex import _section_row
from dssatlab.filex_skeleton import _render_filex, write_filex
from dssatlab.filex_template import _check_filex_template, _load_filex_template
from test_filex_template import CROPS, data, data_dir, rows


def test_fields_need_treatments(data, data_dir):
    data['treatment_fields'] = [1]
    assert _check_filex_template(data, data_dir) == [
        'FileX template, treatment_fields: needs treatments. '
        'Supply treatments with one name per treatment.']


@pytest.mark.parametrize('fields,found', [
    (None, 'None'), ('1', "'1'"), (1, '1'), ({}, '{}'), ((1, 2), '(1, 2)'),
    ([], '0'), ([1], '1'), ([1, 1, 1], '3'),
])
def test_fields_need_one_number_per_treatment(data, data_dir, fields, found):
    data.pop('treatment_name')
    data.update(treatments=['A', 'B'], treatment_fields=fields)
    assert _check_filex_template(data, data_dir) == [
        'FileX template, treatment_fields: supply one field number per treatment '
        f'(found {found} for 2 treatments).']


@pytest.mark.parametrize('bad', ['2', 0, 100, True, False, 1.5, None, [], {}])
@pytest.mark.parametrize('position', [1, 2, 3])
def test_bad_field_number_reports_position(data, data_dir, bad, position):
    data.pop('treatment_name')
    fields = [1, 1, 1]
    fields[position - 1] = bad
    data.update(treatments=['A', 'B', 'C'], treatment_fields=fields)
    assert _check_filex_template(data, data_dir) == [
        f'FileX template, treatment_fields[{position}]: found {bad!r}. '
        'Supply a whole number 1 to 99.']


def test_every_bad_field_is_reported(data, data_dir):
    data.pop('treatment_name')
    data.update(treatments=['A'] * 5, treatment_fields=[1, '2', 0, 100, True])
    assert _check_filex_template(data, data_dir) == [
        f'FileX template, treatment_fields[{i}]: found {value!r}. '
        'Supply a whole number 1 to 99.'
        for i, value in enumerate(['2', 0, 100, True], 2)]


@pytest.mark.parametrize('fields,maximum,missing', [
    ([1, 3], 3, '2'), ([4, 1], 4, '2, 3'), ([2, 2], 2, '1'),
])
def test_field_numbers_have_no_gaps(data, data_dir, fields, maximum, missing):
    data.pop('treatment_name')
    data.update(treatments=['A', 'B'], treatment_fields=fields)
    assert _check_filex_template(data, data_dir) == [
        f'FileX template, treatment_fields: number the fields 1 to {maximum} '
        f'without gaps (missing {missing}).']


@pytest.mark.parametrize('fields', [[1], [1, 2, 2], [3, 1, 2], list(range(1, 100))])
def test_valid_fields_and_default(data, data_dir, fields):
    from dssatlab.filex_template import _template_treatment_fields
    assert _template_treatment_fields(data) == [1]
    data.pop('treatment_name')
    data['treatments'] = ['A'] * len(fields)
    assert _template_treatment_fields(data) == [1] * len(fields)
    data['treatment_fields'] = fields
    before = deepcopy(data)
    assert _check_filex_template(data, data_dir) == []
    assert _template_treatment_fields(data) == fields
    assert data == before


@pytest.mark.parametrize('uncomment', [False, True])
def test_written_template_explains_fields_and_passes(tmp_path, data_dir, uncomment):
    pytest.importorskip('yaml')
    path = tmp_path / 'filex.yaml'
    write_filex_template(path)
    text = path.read_text()
    assert '# treatment_fields: [1, 2]' in text
    if uncomment:
        text = '\n'.join('# ' + line if line.startswith('treatment_name:') else
                         line[2:] if line.startswith(('# treatments:', '# treatment_fields:'))
                         else line for line in text.splitlines())
        path.write_text(text)
    loaded, problems = _load_filex_template(path)
    assert problems == []
    assert _check_filex_template(loaded, data_dir) == []


@pytest.mark.parametrize('fields', [[2, 1, 2], [3, 1, 2, 3]])
@pytest.mark.parametrize('crop,code,crop_code', [row[:3] for row in CROPS])
def test_each_field_renders_its_own_data(
        tmp_path, data, data_dir, rows, fields, crop, code, crop_code):
    data.pop('treatment_name')
    data.update(crop=crop, cultivar={'code': code},
                treatments=[f'Treatment {i}' for i in range(len(fields))],
                treatment_fields=fields)
    if crop == 'potato':
        data['harvest_date'] = '2021-08-01'
        data['planting'].update(planting_material_weight=1500, sprout_length=2)
    count = max(fields)
    weather, soil = {}, {}
    for field in range(count, 0, -1):  # Dict insertion order must not choose field 1.
        station = ['UFGA', 'AMES', 'KSAS'][field - 1]
        weather[field] = [dict(rows[0][0], station=station, longitude=-100 + field,
                               latitude=40 + field, elevation=200 + field)]
        soil[field] = [dict(rows[1][0], soil_id=f'SOIL{field:06d}', slb=depth)
                       for depth in (10, field * 40)]
    before = deepcopy((data, weather, soil))
    path = write_filex(data, weather, soil, tmp_path, data_dir=data_dir)
    text = path.read_text(encoding='ascii')
    assert path.name == f'UFGA2101.{crop_code}X'
    assert text.splitlines()[0] == f'*EXP.DETAILS: UFGA2101{crop_code} Treatment 0'
    assert '@SITE\n UFGA\n' in text
    for treatment, field in enumerate(fields, 1):
        assert _section_row(text, 'TREATMENTS', 'N', treatment, ('FL',))['FL'] == str(field)
    field_lines = text.split('*FIELDS\n')[1].split('\n\n')[0].splitlines()
    assert len(field_lines) == 2 * (count + 1)
    for field in range(1, count + 1):
        station = weather[field][0]['station']
        line = field_lines[field]
        assert line[:2] == f'{field:2d}'
        assert line[3:11] == f'{station}{field:04d}'
        assert line[12:20] == f'{station:<8}'
        assert float(line[61:67]) == field * 40
        assert line[69:79] == f'SOIL{field:06d}'
        coordinates = field_lines[count + 1 + field]
        assert coordinates[:2] == f'{field:2d}'
        assert float(coordinates[2:18]) == -100 + field
        assert float(coordinates[18:34]) == 40 + field
        assert float(coordinates[34:44]) == 200 + field
    assert (data, weather, soil) == before


@pytest.mark.parametrize('explicit', [False, True])
@pytest.mark.parametrize('weather_dict,soil_dict', [(True, False), (False, True), (True, True)])
def test_single_field_dict_matches_original_lists(data, rows, explicit, weather_dict, soil_dict):
    data['treatments'] = [data.pop('treatment_name'), 'Second']
    original = _render_filex(data, *rows)
    if explicit:
        data['treatment_fields'] = [1, 1]
    weather, soil = rows
    assert _render_filex(data, {1: weather} if weather_dict else weather,
                         {1: soil} if soil_dict else soil) == original
