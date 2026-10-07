"""Stock forecasts follow the historical file lookup and shared gap check."""

from datetime import date

import pytest

from dssatlab import DSSATCheckError, DSSATRunError
from test_forecast_check import forecast, filex, edit, experiment
from test_season_coverage import weather
from test_simulation_run import fake_dssat
from test_simulation_stock_weather import stock_file, assert_copied


@pytest.fixture(autouse=True)
def isolated_weather_directory(monkeypatch):
    monkeypatch.setattr('dssatlab.stock._weather_directory', lambda executable: None)


@pytest.mark.parametrize('annual', [False, True])
@pytest.mark.parametrize('override', [False, True])
def test_stock_forecast_history_and_observations(forecast, tmp_path, fake_dssat, annual, override):
    if override:
        forecast.management = experiment(controls={'years': 2})
    else:
        edit(forecast, 'GE              1', 'GE              2')
    days = [row['date'] for row in weather('1980-02-25', '1982-02-25')]
    if annual:
        paths = [stock_file(tmp_path, f'UFGA{year % 100:02d}01.WTH',
                            days=[day for day in days if day.year == year])
                 for year in (1980, 1981, 1982)]
    else:
        edit(forecast, 'UFGA       -99', 'UFGA8201   -99')
        paths = [stock_file(tmp_path, days=days)]
    forecast.weather = list(reversed(paths))
    before = {path: path.read_bytes() for path in paths}
    assert forecast.check(False) == []
    result = forecast.run()
    assert fake_dssat.calls[0][0][1] == 'Y'
    assert_copied(result, paths)
    assert {path: path.read_bytes() for path in paths} == before

    if annual:
        forecast.weather.remove(paths[1])
    else:
        lines = before[paths[0]].splitlines(keepends=True)
        paths[0].write_bytes(b''.join(line for line in lines if not line.startswith(b'81')))
    problems = forecast.check(False)
    assert len(problems) == 1
    if annual:
        assert 'UFGA8101.WTH' in problems[0] and '1981-01-01' in problems[0]
    else:
        assert 'Stock weather: missing dates 1981-01-01 to 1981-12-31.' in problems[0]
    assert 'Checked' in problems[0] and 'Supply' in problems[0]
    with pytest.raises(DSSATCheckError) as error:
        forecast.run()
    assert error.value.problems == problems
    assert len(fake_dssat.calls) == 1


@pytest.mark.parametrize('first,last,missing', [
    ('1981-02-26', '1982-02-25', '1981-02-25'),
    ('1981-02-25', '1982-02-24', '1982-02-25'),
])
def test_stock_forecast_missing_range_bounds(forecast, tmp_path, first, last, missing):
    edit(forecast, 'UFGA       -99', 'UFGA8201   -99')
    forecast.weather = stock_file(tmp_path, days=[row['date'] for row in weather(first, last)], wide=True)
    problems = forecast.check(False)
    assert len(problems) == 1
    assert missing in problems[0] and 'Checked' in problems[0] and 'Supply' in problems[0]


@pytest.mark.parametrize('override', [False, True])
def test_stock_forecast_date_after_2035(forecast, tmp_path, override):
    edit(forecast, '82056', '35001')
    edit(forecast, 'UFGA       -99', 'UFGA3501   -99')
    if override:
        forecast.management = experiment(controls={'forecast_date': '2040-01-01'})
        last = '2039-12-31'
    else:
        edit(forecast, '1982057', '2036001')
        last = '2035-12-31'
    days = [row['date'] for row in weather('2034-01-01', last)]
    forecast.weather = stock_file(tmp_path, 'UFGA3501.WTH', days=days, wide=True)
    assert forecast.check(False) == []
    days.remove(date(2034, 7, 1))
    stock_file(tmp_path, 'UFGA3501.WTH', days=days, wide=True)
    assert any('Stock weather: missing date 2034-07-01.' in problem
               for problem in forecast.check(False))


def test_stock_forecast_history_before_calendar(forecast, tmp_path):
    forecast.management = experiment(controls={'years': 99999})
    forecast.weather = stock_file(tmp_path)
    problems = forecast.check(False)
    assert len(problems) == 1
    assert 'year -98017' in problems[0] and 'Checked' in problems[0] and 'Supply' in problems[0]


def test_stock_gap_bounds_at_calendar_limits():
    from dssatlab.weather_files import _stock_weather_gaps

    problems = _stock_weather_gaps([{'date': date(1, 1, 2)}, {'date': date(9999, 12, 30)}],
                                   date.min, date.max, check_bounds=True)
    assert 'missing date 0001-01-01.' in problems[0]
    assert 'missing date 9999-12-31.' in problems[-1]


def test_annual_forecast_with_eight_character_station(forecast, tmp_path):
    edit(forecast, 'UFGA       -99', 'UFGA8201   -99')
    forecast.weather = [
        stock_file(tmp_path, f'UFGA{year % 100:02d}01.WTH',
                   days=[row['date'] for row in weather(f'{year}-01-01', f'{year}-12-31')])
        for year in (1981, 1982)]
    assert forecast.check(False) == []


@pytest.mark.parametrize('literal', [False, True])
def test_mixed_forecast_layout_skips_missing_observations(forecast, tmp_path, literal):
    if literal:
        edit(forecast, 'UFGA       -99', 'UFGA8201   -99')
    forecast.weather = [
        stock_file(tmp_path, 'UFGA8101.WTH',
                   days=[row['date'] for row in weather('1981-01-01', '1982-12-31')]),
        stock_file(tmp_path, 'UFGA8201.WTH',
                   days=[row['date'] for row in weather('1982-01-01', '1982-02-24')])]
    assert forecast.check(False) == []


def test_mixed_forecast_ensemble_layout_is_skipped(forecast, tmp_path, fake_dssat, monkeypatch):
    def unexpected_walk(*args, **kwargs):
        pytest.fail('Mixed forecast layouts must skip the coverage walk')

    monkeypatch.setattr('dssatlab.stock._walk_weather_files', unexpected_walk)
    edit(forecast, 'GE              1', 'GE              2')
    forecast.weather = [
        stock_file(tmp_path, 'UFGA8001.WTH',
                   days=[row['date'] for row in weather('1980-01-01', '1982-12-31')]),
        stock_file(tmp_path, 'UFGA8201.WTH',
                   days=[row['date'] for row in weather('1982-01-01', '1982-12-31')])]
    assert forecast.check(False) == []
    fake_dssat.outputs['WARNING.OUT'] = b'Weather record not found for YR DOY: 1981 056'
    with pytest.raises(DSSATRunError, match='1981-02-25'):
        forecast.run()


def test_installed_station_file_counts_toward_forecast_layout(
        forecast, tmp_path, monkeypatch):
    installed = tmp_path / 'installed'
    installed.mkdir()
    stock_file(installed, 'UFGA8101.WTH',
               days=[row['date'] for row in weather('1981-01-01', '1982-12-31')])
    forecast.weather = stock_file(tmp_path, 'UFGA8201.WTH')
    monkeypatch.setattr('dssatlab.stock._weather_directory', lambda executable: installed)
    assert forecast.check(False) == []


def test_forecast_four_character_station_keeps_multi_year_observed_file(forecast, tmp_path):
    forecast.weather = stock_file(tmp_path, 'UFGA8201.WTH',
        days=[row['date'] for row in weather('1981-01-01', '1982-12-31')])
    assert forecast.check(False) == []
