"""Stock weather retains the effective-start and identity checks from ticket A."""

from datetime import date

import pytest

import dssatlab as lab
from dssatlab.filex import _read_filex
from dssatlab.sequence import _rotation_components
from dssatlab.stock import _simulation_weather
from test_harvest_required import simulation as harvest_simulation
from test_simulation_run import inputs, SAMPLE
from test_simulation_stock_weather import stock_file


@pytest.mark.parametrize('start,override', [
    ('P', False), ('P', True), ('S', False),
])
def test_stock_weather_uses_effective_start_date(tmp_path, start, override):
    sim = harvest_simulation(tmp_path, level=1, harvest='84057')
    text = sim.filex.read_text().replace('UFGA       -99', 'UFGA8401   -99')
    text = text.replace('     S 82056', f'     {start} {"84056" if start == "S" else "82056"}')
    text = text.replace('  1  1  0  0  0  0  0  0  0  0  0  1  1',
                        '  1  1  0  0  1  0  0  0  0  0  0  1  1')
    text += ('\n*PLANTING DETAILS\n'
             '@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE'
             '  PENV  PLPH  SPRL\n'
             f' 1 {"82056" if override else "84056"}   -99    10    10     S     R'
             '    75     0     5   -99   -99   -99   -99   -99\n')
    sim.filex.write_text(text, encoding='ascii')
    if override:
        sim.management = {'treatments': {'07': {'planting': {
            'date': '1984-02-25', 'method': 'S', 'distribution': 'R',
            'population': 10, 'depth': 5, 'row_spacing': 75}}}}
    sim.weather = stock_file(tmp_path, 'UFGA8401.WTH',
                             days=[date(1984, 2, 25), date(1984, 2, 26)])
    assert sim.check(False) == []
    if start == 'P' and not override:
        # This override changes SDATE only; START P still uses planting.
        values, problems = _read_filex(sim.filex, sim.treatment)
        assert problems == []
        rows, problems = _simulation_weather(sim, values, {'treatments': {
            7: {'controls': {'start_date': '1982-02-25'}}}},
            _rotation_components(sim.filex, sim.treatment))
        assert problems == []
        assert [row['date'] for row in rows] == [date(1984, 2, 25), date(1984, 2, 26)]


@pytest.mark.parametrize('start', ['E', 'P'])
@pytest.mark.parametrize('override', [False, True])
def test_stock_weather_unknown_start_keeps_station_mismatch(tmp_path, start, override):
    filex = tmp_path / 'UFGA8201.MZX'
    filex.write_text(SAMPLE.replace('     S 82056', f'     {start} 82056'), encoding='ascii')
    management = {'treatments': {2: {'fertilizer': []}}} if override else None
    sim = lab.Simulation(filex, 2, 'missing.WTH', management=management)
    problems = sim.check(False)
    assert len(problems) == (1 if override else 2)
    assert all(part in problems[0] for part in (
        'Stock weather missing.WTH', 'simulation start is unknown',
        'START and SDATE/PDATE', 'treatment 2', 'Use START S or P', 'weather as rows'))
    if start == 'E':
        assert 'emergence date' in problems[0]
    if not override:
        assert problems[1] == (
            "FileX WSTA 'UFGA' expects station 'UFGA', but stock weather file missing.WTH "
            "has station 'MISS'. Make the station codes exactly equal; "
            "filenames are case-sensitive on Linux.")
    with pytest.raises(lab.DSSATCheckError) as error:
        sim.run()
    assert error.value.problems == problems


def test_stock_weather_missing_station_needs_a_reported_filex_problem(inputs):
    sim = lab.Simulation(inputs.filex, 2, 'missing.WTH')
    values, problems = _read_filex(sim.filex, sim.treatment)
    assert problems == []
    del values['WSTA']
    rows, problems = _simulation_weather(sim, values, {}, [])
    assert rows == [] and len(problems) == 1
    assert 'WSTA' in problems[0] and 'Supply' in problems[0]
    inputs.filex.write_text(inputs.filex.read_text().replace('WSTA....', 'STATION.'))
    _, filex_problems = _read_filex(sim.filex, sim.treatment)
    assert filex_problems
    assert sim.check(False) == filex_problems


def test_identity_check_skips_station_edit_without_weather_rows(inputs, monkeypatch):
    monkeypatch.setattr(lab.simulation, '_simulation_weather', lambda *args: ([], []))
    sim = lab.Simulation(inputs.filex, 2, 'missing.WTH',
                         management={'treatments': {2: {'fertilizer': []}}})
    assert sim.check(False) == []
