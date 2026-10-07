"""Weather must reach a sequence component's scheduled end, beyond NYERS."""

import pytest

from dssatlab import DSSATCheckError, DSSATRunError, Simulation, run_treatments
from test_season_coverage import weather
from test_simulation_run import fake_dssat, snapshot


@pytest.fixture
def fixed_sequence(tmp_path):
    # MSKB8921-style period weather, SDATE 89060, NYERS 9, final fallow.
    # Each crop starts May 4, and the following fallow ends May 6 next year.
    path = tmp_path / 'MSKB8921.SQX'
    path.write_text('''*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 Crop                       1  1  0  0  1  0  0  0  0  0  0  1  1
 1 2 0 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  2  2

*CULTIVARS
@C CR INGENO CNAME
 1 MZ IB0035 Maize
 2 FA IB0001 Fallow

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 MSKB0001 MSKB       -99     0 DR000     0     0 00000 -99    180  MSKB890006 -99

*PLANTING DETAILS
@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP
 1 89124   -99   7.2   7.2     S     R    75     0     5

*HARVEST DETAILS
@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME
 1 89266 GS000   -99   -99   100     0 -99
 2 90126 GS000   -99   -99   100     0 -99

*SIMULATION CONTROLS
@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL
 1 GE              9     1     S 89060  2150 Sequence
@N METHODS     WTHER
 1 ME              M
@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS
 1 MA              R     N     R     N     R
 2 MA              R     N     R     N     R
''', encoding='latin-1')
    return Simulation(path, weather=weather('1989-03-01', '1998-05-06', 'MSKB'))


@pytest.mark.parametrize('override', [False, True])
@pytest.mark.parametrize('last', ['1998-02-28', '1998-05-05', '1998-05-06'])
def test_period_weather_reaches_final_fallow(fixed_sequence, fake_dssat, last, override):
    sim = fixed_sequence
    sim.weather = weather('1989-03-01', last, 'MSKB')
    if override:
        sim.filex.write_text(sim.filex.read_text().replace('GE              9', 'GE              1'))
        sim.management = {'treatments': {1: {'controls': {'years': 9}}}}
    before = snapshot(sim.filex.parent)
    prefix = 'Controls years' if override else 'FileX NYERS'
    expected = ([] if last == '1998-05-06' else [
        f'{prefix} 9: the sequence runs from 1989-03-01 through 1998-05-06, '
        f'after the weather data ends ({last}). Supply weather through 1998-05-06, '
        'or fewer years.'])
    assert sim.check(False) == expected
    assert snapshot(sim.filex.parent) == before
    if expected:
        with pytest.raises(DSSATCheckError) as error:
            sim.run()
        assert error.value.problems == expected
        assert snapshot(sim.filex.parent) == before
        assert fake_dssat.calls == []
    else:
        result = sim.run()
        assert fake_dssat.calls[0][0][1:] == ['Q', 'DSSBatch.v48']
        assert (result.run_dir.parent / 'MSKB8901.WTH').is_file()


def test_scenario_sequence_uses_component_end(fixed_sequence, fake_dssat):
    sim = fixed_sequence
    with pytest.raises(DSSATCheckError) as error:
        run_treatments(sim.filex, sim.weather, treatments=[1], scenarios={
            'short': {'weather': weather('1989-03-01', '1998-02-28', 'MSKB')}})
    assert len(error.value.problems) == 1
    assert error.value.problems[0].startswith("Scenario 'short', treatment 1: FileX NYERS 9:")
    assert 'through 1998-05-06' in error.value.problems[0]
    assert fake_dssat.calls == []


def test_maturity_end_stays_with_warning_scan(fixed_sequence, fake_dssat):
    sim = fixed_sequence
    # Crop maturity determines whether a subsequent fallow is reached at all.
    sim.filex.write_text(sim.filex.read_text().replace(
        ' 1 MA              R     N     R     N     R',
        ' 1 MA              R     N     R     N     M'))
    sim.weather = weather('1989-03-01', '1998-02-28', 'MSKB')
    assert sim.check(False) == []
    fake_dssat.outputs['WARNING.OUT'] = b'Weather record not found for YR DOY: 1998 060'
    with pytest.raises(DSSATRunError, match='1998-03-01'):
        sim.run()


@pytest.mark.parametrize('explicit', [False, True])
def test_fallow_then_maturity_checks_planting_after_boundary(fixed_sequence, explicit):
    from datetime import date
    from dssatlab.sequence import _sequence_end, _sequence_stop

    sim = fixed_sequence
    text = sim.filex.read_text().replace(
        ' 1 1 0 0 Crop                       1  1  0  0  1  0  0  0  0  0  0  1  1\n'
        ' 1 2 0 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  2  2',
        ' 1 1 0 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  2  2\n'
        ' 1 2 0 0 Crop                       1  1  0  0  1  0  0  0  0  0  0  0  1')
    text = (text.replace('89124', '79075').replace('90126', '79072')
            .replace(' 1 GE              9     1     S 89060  2150 Sequence',
                     ' 1 GE              9     1     S 89060  2150 Sequence\n'
                     ' 2 GE              9     1     S 89060  2150 Sequence')
            .replace(' 1 MA              R     N     R     N     R',
                     ' 1 MA              R     N     R     N     M'))
    sim.filex.write_text(text)
    entry = {'controls': {'start_date': '1978-03-15', 'years': 1}}
    if explicit:
        entry['rotation'] = {2: {'planting': dict(
            date='1979-03-16', method='S', distribution='R',
            population=7.2, row_spacing=75, depth=5)}}
    sim.management = {'treatments': {1: entry}}
    sim.weather = weather('1978-03-15', '1979-03-14', 'MSKB')
    start = date(1978, 3, 15)
    stop = _sequence_stop(start, 1)
    assert _sequence_end(sim.management, 1, start, stop, sim.filex, None) == stop
    assert _sequence_end(sim.management, 1, start, stop, sim.filex, None,
                         proven_only=True) is None
    problems = sim.check(False)
    assert len(problems) == 1
    assert 'rotation component 2' in problems[0] and '1979-03-16' in problems[0]
    assert 'outside weather range' in problems[0]


@pytest.mark.parametrize('later_maturity', [False, True])
@pytest.mark.parametrize('last', ['1989-09-22', '1989-09-23'])
def test_fixed_crop_can_end_sequence_before_final_fallow(fixed_sequence, last, later_maturity):
    sim = fixed_sequence
    # One year from a September start crosses the next crop's fixed harvest,
    # so CSM never reaches the following fallow in this run.
    text = sim.filex.read_text().replace('S 89060', 'S 88266').replace(
        'GE              9', 'GE              1')
    if later_maturity:
        text = text.replace(' 2 MA              R     N     R     N     R',
                            ' 2 MA              R     N     R     N     M')
    sim.filex.write_text(text)
    sim.weather = weather('1988-09-22', last, 'MSKB')
    expected = ([] if last == '1989-09-23' else [
        'FileX NYERS 1: the sequence runs from 1988-09-22 through 1989-09-23, '
        'after the weather data ends (1989-09-22). Supply weather through 1989-09-23, '
        'or fewer years.'])
    assert sim.check(False) == expected


def test_component_harvest_override_sets_sequence_end(fixed_sequence):
    sim = fixed_sequence
    sim.management = {'treatments': {'01': {'rotation': {'02': {
        'harvest': [{'date': '1990-05-10'}]}}}}}
    assert sim.check(False) == [
        'FileX NYERS 9: the sequence runs from 1989-03-01 through 1998-05-10, '
        'after the weather data ends (1998-05-06). Supply weather through 1998-05-10, '
        'or fewer years.']
    sim.weather = weather('1989-03-01', '1998-05-10', 'MSKB')
    assert sim.check(False) == []


@pytest.mark.parametrize('start,end', [('1997-01-01', '1997-12-31'),
                                      ('1996-02-29', '1997-02-28')])
def test_fixed_end_at_stopping_boundary(fixed_sequence, start, end):
    from datetime import date

    sim = fixed_sequence
    # Match HDATE to the fixed day-of-year boundary (leap SDATE keeps day 60).
    # Only the first crop runs: its end equals, rather than exceeds, YRDOY_END.
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    sim.filex.write_text(sim.filex.read_text().replace('89266', last.strftime('%y%j'))
                        .replace('89124', first.strftime('%y%j')))
    sim.management = {'treatments': {1: {'controls': {'start_date': start, 'years': 1}}}}
    sim.weather = weather(start, end, 'MSKB')
    # Ignore inherited component dates outside this intentionally moved period.
    assert not any('sequence runs from' in p for p in sim.check(False))
    sim.weather.pop()
    assert any(f'through {end}' in p and 'sequence runs from' in p for p in sim.check(False))


def test_multirow_fallow_shifts_from_first_harvest_to_last(fixed_sequence):
    sim = fixed_sequence
    # MGMTOPS anchors the fallow on the first harvest; AUTHAR finishes on the
    # last. This two-year fallow changes which component crosses NYERS.
    sim.filex.write_text(sim.filex.read_text().replace(
        ' 2 90126 GS000   -99   -99   100     0 -99',
        ' 2 90126 GS000   -99   -99   100     0 -99\n'
        ' 2 91125 GS000   -99   -99   100     0 -99'))
    sim.weather = weather('1989-03-01', '1998-09-22', 'MSKB')
    assert sim.check(False) == [
        'FileX NYERS 9: the sequence runs from 1989-03-01 through 1998-09-23, '
        'after the weather data ends (1998-09-22). Supply weather through 1998-09-23, '
        'or fewer years.']
    sim.weather = weather('1989-03-01', '1998-09-23', 'MSKB')
    assert sim.check(False) == []


def test_filex_year_zero_fallow_end_is_leap_day(fixed_sequence):
    sim = fixed_sequence
    text = sim.filex.read_text().replace('GE              9', 'GE              1')
    for old, new in [('89060', '99060'), ('89124', '99124'),
                     ('89266', '99266'), ('90126', '00060')]:
        text = text.replace(old, new)
    sim.filex.write_text(text)
    sim.weather = weather('1999-03-01', '2000-02-28', 'MSKB')
    assert sim.check(False) == [
        'FileX NYERS 1: the sequence runs from 1999-03-01 through 2000-02-29, '
        'after the weather data ends (2000-02-28). Supply weather through 2000-02-29, '
        'or fewer years.']
    sim.weather = weather('1999-03-01', '2000-02-29', 'MSKB')
    assert sim.check(False) == []
