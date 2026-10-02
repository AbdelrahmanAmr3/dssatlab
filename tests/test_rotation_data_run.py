"""Simulation runs with experiment data per rotation component."""
from pathlib import Path
import shutil

import pytest

from dssatlab import Simulation, run_treatments
from dssatlab.filex import _section_row
from test_filex_template import data, rows
from test_rotation_template import rotation
from test_rotation_data import sim, edits
from test_season_coverage import weather
from test_simulation_run import fake_dssat
from test_simulation_template import installed


def fertilizer(day, amount=40):
    return dict(date=day, material="FE005", application="AP001", depth=5, n=amount)


@pytest.fixture
def sequence_copy(installed, tmp_path):
    path = tmp_path / "ZZZZ7801.SQX"
    path.write_bytes((Path(__file__).parent / "fixtures/rotation_writers.SQX").read_bytes())
    for prefix in ("WHCER048", "MZCER048"):
        shutil.copy2(installed.executable.parent / "Genotype" / f"{prefix}.CUL", tmp_path)
    return path


@pytest.mark.parametrize("trt_key,comp_key", [(1, 3), ("1", "3")])
def test_copied_sequence_run(installed, sequence_copy, trt_key, comp_key):
    original = sequence_copy.read_bytes()
    management = {
        "treatments": {
            trt_key: {
                "rotation": {
                    comp_key: {
                        "fertilizer": [fertilizer("1978-11-15", amount=40)],
                        "cultivar": {"crop": "WH", "code": "ZZ0001"},
                    }
                }
            }
        }
    }
    sim = Simulation(
        sequence_copy,
        treatment=1,
        weather=weather("1978-03-15", "1981-03-15"),
        management=management,
    )
    result = sim.run()
    folder = result.run_dir.parent
    command, cwd, _ = installed.calls[0]
    assert command == [str(installed.executable), "Q", "DSSBatch.v48"]
    assert cwd == folder

    written = (folder / sequence_copy.name).read_text(encoding="latin-1")
    fert_row = _section_row(written, "FERTILIZERS (INORGANIC)", "F", 3, ("FDATE", "FAMN"))
    assert fert_row["FDATE"] == "78319" and fert_row["FAMN"] == "40"
    cul_row = _section_row(written, "CULTIVARS", "C", 4, ("CR", "INGENO"))
    assert cul_row["CR"] == "WH" and cul_row["INGENO"] == "ZZ0001"

    orig_rows = original.decode("latin-1").split("*TREATMENTS")[1].split("*CULTIVARS")[0].splitlines()[2:6]
    written_rows = written.split("*TREATMENTS")[1].split("*CULTIVARS")[0].splitlines()[2:6]
    assert written_rows[0] == orig_rows[0]
    assert written_rows[1] == orig_rows[1]
    assert written_rows[3] == orig_rows[3]
    # Row (1, 3): CU (cols 34:37) repointed to 4, MF (cols 52:55) repointed to 3
    assert written_rows[2][34:37].strip() == "4"
    assert written_rows[2][52:55].strip() == "3"
    assert sequence_copy.read_bytes() == original


def test_rotation_template_run(rotation, rows, installed):
    rotation["rotation"][2]["cultivar"]["code"] = "IB0488"
    management = {
        "treatments": {
            1: {
                "controls": {"years": 3},
                "rotation": {
                    1: {
                        "fertilizer": [fertilizer("1978-04-20", amount=60)],
                        "irrigation": [dict(date="1978-05-01", amount=25, method="IR001")],
                    },
                    3: {
                        "fertilizer": [fertilizer("1978-11-15", amount=40)],
                    },
                },
            }
        }
    }
    sim = Simulation(
        filex_template=rotation,
        weather=weather("1978-03-15", "1981-03-15"),
        soil=rows[1],
        management=management,
    )
    result = sim.run()
    folder = result.run_dir.parent
    command, cwd, _ = installed.calls[0]
    assert command == [str(installed.executable), "Q", "DSSBatch.v48"]
    assert cwd == folder

    written = (folder / "UFGA7801.SQX").read_text(encoding="latin-1")
    assert _section_row(written, "SIMULATION CONTROLS", "N", 1, ("NYERS",))["NYERS"] == "3"
    for level in (2, 3, 4):
        assert _section_row(written, "SIMULATION CONTROLS", "N", level, ("NYERS",))["NYERS"] == "1"

    assert _section_row(written, "FERTILIZERS (INORGANIC)", "F", 1, ("FAMN",))["FAMN"] == "60"
    assert _section_row(written, "FERTILIZERS (INORGANIC)", "F", 2, ("FAMN",))["FAMN"] == "40"
    assert _section_row(written, "IRRIGATION AND WATER MANAGEMENT", "I", 1, ("IRVAL",))["IRVAL"] == "25"

    written_rows = written.split("*TREATMENTS")[1].split("*CULTIVARS")[0].splitlines()[2:6]
    # Row (1, 1): MI (49:52) repointed to 1, MF (52:55) repointed to 1
    assert written_rows[0][49:52].strip() == "1"
    assert written_rows[0][52:55].strip() == "1"
    # Row (1, 2): fallow untouched (MI 0, MF 0)
    assert written_rows[1][49:52].strip() == "0"
    assert written_rows[1][52:55].strip() == "0"
    # Row (1, 3): MF repointed to 2 (MI 0)
    assert written_rows[2][49:52].strip() == "0"
    assert written_rows[2][52:55].strip() == "2"
    # Row (1, 4): fallow untouched (MI 0, MF 0)
    assert written_rows[3][49:52].strip() == "0"
    assert written_rows[3][52:55].strip() == "0"


def test_run_treatments_and_scenarios_sequence(installed, sequence_copy):
    original = sequence_copy.read_bytes()
    base_management = {
        "treatments": {
            1: {
                "rotation": {
                    3: {"fertilizer": [fertilizer("1978-11-15", amount=30)]},
                }
            }
        }
    }
    scenarios = {
        "high_nitrogen": {
            "management": {
                "treatments": {
                    1: {
                        "rotation": {
                            3: {"fertilizer": [fertilizer("1978-11-15", amount=75)]},
                        }
                    }
                }
            }
        }
    }
    results = run_treatments(
        filex=sequence_copy,
        weather=weather("1978-03-15", "1981-03-15"),
        management=base_management,
        scenarios=scenarios,
    )
    assert list(results) == [("base", 1), ("high_nitrogen", 1)]
    assert sequence_copy.read_bytes() == original

    for (name, _), expected_n in [(("base", 1), "30"), (("high_nitrogen", 1), "75")]:
        folder = results[name, 1].run_dir.parent
        written = (folder / sequence_copy.name).read_text(encoding="latin-1")
        assert _section_row(written, "FERTILIZERS (INORGANIC)", "F", 3, ("FAMN",))["FAMN"] == expected_n
        rows = written.split("*TREATMENTS")[1].split("*CULTIVARS")[0].splitlines()[2:6]
        assert rows[2][52:55].strip() == "3"
        assert name == "base" or name not in written


@pytest.mark.parametrize('rotation_edits', [None, {}, {'3': {'fertilizer': []}}, {
    '3': {'fertilizer': [fertilizer('1978-11-15')]},
    1: {'fertilizer': [fertilizer('1978-03-15')]},
}])
def test_run_consumes_checked_rotation(sim, installed, rotation_edits):
    from dssatlab.filex import _section_row

    if rotation_edits is None:
        sim.management['treatments'][1].pop('rotation')
    else:
        edits(sim, rotation_edits)
    sim.management['treatments'][1]['controls'] = {'years': 1}
    sim.management['treatments'] = {'1': sim.management['treatments'][1]}
    result = sim.run()
    written = next(result.run_dir.parent.glob('*.SQX')).read_text(encoding='latin-1')
    components = written.split('*TREATMENTS')[1].split('*CULTIVARS')[0].splitlines()[2:6]
    levels = [int(row[52:55]) for row in components]
    if rotation_edits:
        for key, entry in rotation_edits.items():
            level = levels[int(key) - 1]
            if not entry['fertilizer']:
                assert level == 0
            else:
                row = _section_row(written, 'FERTILIZERS (INORGANIC)', 'F', level, ('FDATE',))
                assert row['FDATE'] == ('78074' if int(key) == 1 else '78319')
    else:
        assert levels == (
            [0, 0, 0, 0] if sim.filex is None else [1, 0, 1, 0])
