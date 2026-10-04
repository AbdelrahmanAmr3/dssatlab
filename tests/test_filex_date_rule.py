"""Every inherited FileX date follows DSSAT's rule, independent of weather."""

import pytest

from dssatlab import Simulation
from test_filex_check import filex, SAMPLE
from test_filex_dates import dated_simulation
from test_season_coverage import weather
from test_simulation_run import fake_dssat
from test_stock_weather import weather_file


def test_sdate_wrong_century_names_rule_and_remedies(filex, fake_dssat):
    sim = Simulation(filex(sdate='35001'), weather=weather('1935-01-01', '1935-12-31'),
                     executable=fake_dssat.executable)
    assert sim.check(False) == [
        "FileX SDATE '35001' is 2035-01-01 (DSSAT reads two-digit years 00-35 as "
        "2000-2035 and 36-99 as 1936-1999), not covered by weather data "
        "(1935-01-01 to 1935-12-31). Supply weather for 2035-01-01, "
        "or set controls.start_date."]
    assert fake_dssat.calls == []


@pytest.mark.parametrize('year', [1936, 1940, 1941, 1982, 2035])
def test_sdate_uses_dssat_century(filex, fake_dssat, year):
    sim = Simulation(filex(sdate=f'{year % 100:02d}001'),
                     weather=weather(f'{year}-01-01', f'{year}-12-31'),
                     executable=fake_dssat.executable)
    assert sim.check(False) == []


def test_long_weather_resolves_start_in_2025(filex, fake_dssat):
    sim = Simulation(filex(sdate='25001'), weather=weather('1920-01-01', '2030-12-31'),
                     executable=fake_dssat.executable)
    assert sim.check(False) == []
    sim.management = {'treatments': {1: {'planting': dict(
        date='1925-01-01', method='S', distribution='R', population=8,
        row_spacing=75, depth=5)}}}
    problems = sim.check(False)
    assert len(problems) == 1
    assert "before simulation start date '2025-01-01'" in problems[0]
    assert 'ambiguous start year' not in problems[0]


@pytest.mark.parametrize('sdate', ['35001', 'bad!!', '35366'])
def test_controls_start_date_wins_over_sdate(filex, fake_dssat, sdate):
    sim = Simulation(filex(sdate=sdate), weather=weather('1935-01-01', '1935-12-31'),
                     executable=fake_dssat.executable,
                     management={'treatments': {1: {'controls': {'start_date': '1935-01-01'}}}})
    assert sim.check(False) == []


@pytest.mark.parametrize('sdate,reason', [
    ('bad!!', "SDATE 'bad!!' is not a DSSAT date (yyddd); correct SDATE"),
    ('35366', 'day 366 does not exist in 2035; correct SDATE'),
])
def test_invalid_sdate_keeps_message(filex, fake_dssat, capsys, sdate, reason):
    path = filex(sdate=sdate)
    sim = Simulation(path, weather=weather('2035-01-01', '2035-12-31'),
                     executable=fake_dssat.executable,
                     management={'treatments': {1: {'planting': dict(
                         date='2035-01-01', method='S', distribution='R',
                         population=8, row_spacing=75, depth=5)}}})
    problems = sim.check(True)
    expected = ("is invalid: day 366 does not exist in 2035 (DSSAT reads years 00-35 as "
                "2000-2035 and 36-99 as 1936-1999). Supply a day of year from 1 to 365."
                if sdate == '35366' else
                "is invalid. Supply five digits: two-digit year followed by three-digit day of year.")
    assert problems == [f"FileX {path}: SDATE {sdate!r} {expected}"]
    assert f'check was skipped ({reason}).' in capsys.readouterr().out
    assert not any('not covered by weather data' in p for p in problems)


@pytest.mark.parametrize('stock', [False, True])
@pytest.mark.parametrize('sdate,year,day,last', [('00000', 2000, 0, 366),
                                             ('36999', 1936, 999, 366)])
def test_out_of_range_sdate_names_year_and_valid_days(filex, fake_dssat, stock,
                                                    sdate, year, day, last):
    path = filex(sdate=sdate)
    source = (weather_file(path.parent, "UFGA0001.WTH", ("00001",)) if stock else
              weather('2000-01-01', '2000-01-02'))
    sim = Simulation(path, weather=source, executable=fake_dssat.executable)
    assert sim.check(False) == [
        f"FileX {path}: SDATE {sdate!r} is invalid: day {day} does not exist in {year} "
        "(DSSAT reads years 00-35 as 2000-2035 and 36-99 as 1936-1999). "
        f"Supply a day of year from 1 to {last}."
    ]


def test_inherited_irrigation_uses_filex_century(filex, fake_dssat):
    text = SAMPLE + '\n*IRRIGATION AND WATER MANAGEMENT\n@I IDATE  IROP IRVAL\n 1 40001 IR001    10\n'
    sim = Simulation(filex(sdate='40001', text=text),
                     weather=weather('1940-01-01', '2040-01-02'),
                     executable=fake_dssat.executable,
                     management={'treatments': {1: {'controls': {'start_date': '2040-01-01'}}}})
    assert sim.check(False) == [
        "Controls start_date '2040-01-01' is after the FileX's first irrigation date "
        "1940-01-01; DSSAT stops with error IPIRR. Start on or before that date, "
        "or give irrigation in the management data."]


def test_inherited_planting_window_uses_rule_and_only_edited_coverage(filex, fake_dssat):
    text = SAMPLE + '''
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              A     R     R     N     M
@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN
 1 PL          36001 40001    40   100    30    40    10
'''
    sim = Simulation(filex(sdate='35001', text=text),
                     weather=weather('2035-01-01', '2035-12-31'),
                     executable=fake_dssat.executable,
                     management={'treatments': {1: {'controls': {'planting_management': 'A'}}}})
    assert sim.check(False) == [
        "Management data treatment 1, controls, field 'auto_planting_first': date "
        "'1936-01-01' is before simulation start date '2035-01-01'. Supply an automatic "
        "planting first date on or after the simulation start date, or an earlier controls start_date."]
    sim.management['treatments'][1]['controls']['auto_planting_first'] = '2035-01-01'
    assert sim.check(False) == [
        "Management data treatment 1, controls, field 'auto_planting_first': date "
        "'2035-01-01' is after auto_planting_last '1940-01-01'. Supply an automatic "
        "planting first date on or before the last date (DSSAT PFRST/PLAST)."]


@pytest.mark.parametrize('irrigation,harvest', [('99365', '00001'), ('00001', '00366')])
def test_inherited_hdate_idate_across_1999_2000(tmp_path, fake_dssat, irrigation, harvest):
    sim = dated_simulation(tmp_path, '99365', '99365', harvest, '1999-12-31')
    text = sim.filex.read_text()
    row = next(line for line in text.splitlines() if line.startswith(' 7 1'))
    text = text.replace(row, row[:49] + '  1' + row[52:])
    text += f'\n*IRRIGATION AND WATER MANAGEMENT\n@I IDATE  IROP IRVAL\n 1 {irrigation} IR001    10\n'
    sim.filex.write_text(text, encoding='latin-1')
    sim.executable = fake_dssat.executable
    sim.weather = weather('1999-12-31', '2000-12-31')
    sim.management = {'treatments': {7: {'controls': {'start_date': '1999-12-31'}}}}
    assert sim.check(False) == []
    sim.management['treatments'][7]['controls']['start_date'] = '2000-01-02'
    problems = sim.check(False)
    assert any(f'first irrigation date {"1999-12-31" if irrigation == "99365" else "2000-01-01"}'
               in p for p in problems)
    if harvest == '00001':
        assert any("HDATE '00001' (2000-01-01)" in p for p in problems)


def test_named_rotation_inherits_1936_through_1940(tmp_path, fake_dssat):
    sim = dated_simulation(tmp_path, '36001', '36001', '36366', '1936-01-01', sequence=True)
    text = sim.filex.read_text()
    start, tail = text.split('*CULTIVARS', 1)
    header = '\n'.join(start.splitlines()[:2])
    treatments = '\n'.join(
        f' 7 {r} 0 0 Dates                      1  1  0  0 {r:2d}  0  0  0  0  0  0 {r:2d}  1'
        for r in range(1, 6))
    text = header + '\n' + treatments + '\n\n*CULTIVARS' + tail
    text = text.replace('@P PDATE\n 1 36001', '@P PDATE\n' + '\n'.join(
        f' {r} {year}001' for r, year in enumerate(range(36, 41), 1)))
    harvest_row = next(line for line in text.splitlines() if line.startswith(' 1 36366'))
    text = text.replace(harvest_row, '\n'.join(
        f' {r} {year}{366 if year in (36, 40) else 365} GS000   -99   -99   100     0 -99'
        for r, year in enumerate(range(36, 41), 1)))
    text = text.replace(' 1 GE              1', ' 1 GE              5')
    text = text.replace(' 1 MA              R     R     R     N     M',
                        ' 1 MA              R     R     R     N     R')
    sim.filex.write_text(text, encoding='latin-1')
    sim.weather = weather('1936-01-01', '1940-12-31')
    sim.executable = fake_dssat.executable
    sim.name = 'Dates'
    sim.management = {'treatments': {'07': {'rotation': {}}}}
    assert sim.check(False) == []
    sim.weather = weather('1936-01-01', '1940-12-30')
    problems = sim.check(False)
    assert any('sequence runs from 1936-01-01 through 1940-12-31' in p for p in problems)
    assert any('rotation component 5, harvest/end date' in p and '1940-12-31' in p
               for p in problems)
