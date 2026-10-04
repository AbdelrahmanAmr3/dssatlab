"""Guide experiment examples pass the public checks without running DSSAT."""

import ast
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import re

import pytest

from dssatlab import Simulation, write_management_template
from test_experiment_template import sim_inputs, cultivar_table
from test_management_file import sim_inputs as management_inputs
from test_filex_template import data, rows
from test_simulation_template import installed
from test_simulation_run import fake_dssat


ROOT = Path(__file__).resolve().parent.parent
PAGES = [ROOT / 'README.md', *sorted((ROOT / 'docs' / 'guide').glob('*.md'))]


def _experiment_dicts(value):
    if isinstance(value, dict):
        if isinstance(value.get('treatments'), dict):
            yield value
        else:
            for child in value.values():
                yield from _experiment_dicts(child)


def _examples():
    yaml = pytest.importorskip('yaml')
    for page in PAGES:
        text = page.read_text(encoding='utf-8')
        for number, block in enumerate(re.findall(r'```yaml\n(.*?)```', text, re.S)):
            for data in _experiment_dicts(yaml.safe_load(block)):
                yield f'{page.name}:yaml:{number}', data
        for number, block in enumerate(re.findall(r'```python\n(.*?)```', text, re.S)):
            tree = ast.parse(block)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                if not any(isinstance(key, ast.Constant) and key.value == 'treatments'
                           for key in node.keys):
                    continue
                # The management guide's nitrogen loop has one dynamic value.
                # Check every documented rate without executing the code block.
                rates = next((ast.literal_eval(item.value) for item in tree.body
                              if isinstance(item, ast.Assign) and
                              any(isinstance(t, ast.Name) and t.id == 'n_rates'
                                  for t in item.targets)), [None])
                for rate in rates:
                    candidate = node if rate is None else ast.parse(
                        ast.unparse(node).replace(': rate', f': {rate}'), mode='eval').body
                    for data in _experiment_dicts(ast.literal_eval(candidate)):
                        yield f'{page.name}:python:{number}:{rate}', data


EXAMPLES = list(_examples())


def _filex_templates():
    yaml = pytest.importorskip('yaml')
    for page in PAGES:
        text = page.read_text(encoding='utf-8')
        for number, block in enumerate(re.findall(r'```yaml\n(.*?)```', text, re.S)):
            template = yaml.safe_load(block)
            if isinstance(template, dict) and (
                    'crop' in template or isinstance(template.get('rotation'), list) or
                    'treatment_name' in template or isinstance(template.get('treatments'), list)):
                yield f'{page.name}:yaml:{number}', template


TEMPLATES = list(_filex_templates())


def test_new_guide_sections_match_management_template_comments(tmp_path):
    yaml = pytest.importorskip('yaml')
    path = tmp_path / 'management.yaml'
    write_management_template(path)
    lines, active = [], False
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith(('    # soil_analysis:', '    # environment:')):
            active = True
        elif active and not line.startswith('    #   '):
            active = False
        lines.append(line.replace('    # ', '    ', 1) if active else line)
    entry = yaml.safe_load('\n'.join(lines))['treatments'][1]
    for section in ('soil_analysis', 'environment'):
        examples = [data['treatments'][1][section] for label, data in EXAMPLES
                    if label.startswith('experiment.md:') and section in data['treatments'][1]]
        assert examples == [entry[section]]


@pytest.mark.parametrize('label,template', TEMPLATES, ids=[label for label, _ in TEMPLATES])
def test_guide_filex_templates(label, template, data, rows, installed):
    genotype = installed.executable.parent / 'Genotype' / 'WHCER048.CUL'
    genotype.write_bytes(genotype.read_bytes() + b'IB1500 Wheat\n')
    if 'rotation' in template:
        first, last = date(1977, 1, 1), date(1982, 1, 1)
    else:
        # Short name-only examples use the preceding single-crop template's fields.
        complete = deepcopy(data)
        if 'treatments' in template:
            complete.pop('treatment_name')
        complete.update(template)
        template = complete
        first, last = date(2021, 1, 1), date(2022, 1, 1)
    weather = [dict(rows[0][0], date=(first + timedelta(days=i)).isoformat())
               for i in range((last - first).days)]
    fields = set(template.get('treatment_fields', [1]))
    soil = rows[1]
    if len(fields) > 1:
        weather, soil = ({field: weather for field in fields},
                         {field: soil for field in fields})
    assert Simulation(filex_template=template, weather=weather,
                      soil=soil).check(False) == [], label


@pytest.mark.parametrize('label,experiment', EXAMPLES, ids=[label for label, _ in EXAMPLES])
def test_guide_experiment_examples(label, experiment, sim_inputs, cultivar_table,
                                  data, rows, installed):
    filex, weather = sim_inputs
    # The narrow cultivar fixture omits the stock code used by the guide's scenario.
    cultivar = filex.parent / 'MZCER048.CUL'
    source = cultivar.read_bytes()
    line = next(line for line in source.splitlines() if line.startswith(b'IB0035'))
    cultivar.write_bytes(source + b'999991' + line[6:] + b'\n')
    first = date(1978, 1, 1)
    weather = [dict(weather[0], date=(first + timedelta(days=i)).isoformat())
               for i in range((date(1996, 1, 1) - first).days)]
    if any('rotation' in entry for entry in experiment['treatments'].values()):
        yaml = pytest.importorskip('yaml')
        page = (ROOT / 'docs/guide/sequence.md').read_text(encoding='utf-8')
        template = next(yaml.safe_load(block) for block in
                        re.findall(r'```yaml\n(.*?)```', page, re.S)
                        if '# rotation.yaml' in block)
        genotype = installed.executable.parent / 'Genotype' / 'WHCER048.CUL'
        genotype.write_bytes(genotype.read_bytes() + b'IB1500 Wheat\n')
        kwargs = dict(filex_template=template, soil=rows[1])
    elif label.startswith('simulation.md:'):
        # This example belongs to the preceding three-treatment FileX template.
        data.pop('treatment_name')
        data['treatments'] = ['Control', 'Nitrogen 120', 'Irrigated']
        (installed.executable.parent / 'Genotype' / 'MZCER048.CUL').write_bytes(source)
        first = date(2021, 1, 1)
        weather = [dict(weather[0], date=(first + timedelta(days=i)).isoformat())
                   for i in range(365)]
        kwargs = dict(filex_template=data, soil=rows[1])
    else:
        kwargs = dict(filex=filex)
    assert Simulation(weather=weather, management=experiment, **kwargs).check(False) == [], label
