"""Guide experiment examples pass the public checks without running DSSAT."""

import ast
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import re

import pytest

from dssatlab import Simulation
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
                    candidate = deepcopy(node)
                    if rate is not None:
                        class Rate(ast.NodeTransformer):
                            def visit_Name(self, name):
                                assert name.id == 'rate', (page, name.id)
                                return ast.Constant(value=rate)
                        candidate = Rate().visit(candidate)
                    for data in _experiment_dicts(ast.literal_eval(candidate)):
                        yield f'{page.name}:python:{number}:{rate}', data


EXAMPLES = list(_examples())


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
