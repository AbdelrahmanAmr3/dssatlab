"""Manual end-to-end check: build DSSAT on Linux, then run one FileX with it.

Skipped in normal test runs. It needs git, cmake, gfortran and network access, and the
build takes several minutes. To run it, point it at a FileX whose weather and soil files
sit beside it (filename at most 12 characters). Use a throwaway cache and config so your
own saved DSSAT is not touched:

    XDG_CACHE_HOME=/tmp/dl/cache XDG_CONFIG_HOME=/tmp/dl/config \\
    DSSATLAB_MANUAL_FILEX=/path/to/UFGA8201.MZX \\
    python -m pytest tests/test_manual_integration.py

Generated-weather checks use an available DSSAT executable on Windows or Linux.
Set DSSATLAB_MANUAL_DTCM6401 to the course folder containing DTCM6401.SNX and
its SOL/CUL/ECO/SPE files, and DSSATLAB_MANUAL_CLIMATE to the stock DTCM.CLI path.
"""

import os
import shutil
import sys

import pytest

import dssatlab as dl

FILEX = os.environ.get("DSSATLAB_MANUAL_FILEX")

INSTALL_REQUIRED = pytest.mark.skipif(
    not FILEX or not sys.platform.startswith("linux"),
    reason="manual test: set DSSATLAB_MANUAL_FILEX on Linux to run it",
)


@INSTALL_REQUIRED
def test_install_then_run():
    executable = dl.install()
    assert executable.name == "dscsm048"

    result = dl.run(FILEX)

    assert result.returncode == 0
    assert (result.run_dir / "Summary.OUT").is_file()


WEATHER = os.environ.get("DSSATLAB_MANUAL_WEATHER")


@INSTALL_REQUIRED
@pytest.mark.skipif(not WEATHER, reason="also set DSSATLAB_MANUAL_WEATHER (a weather template CSV)")
def test_simulation_from_the_weather_template():
    """A Simulation from your own template CSV: FileX treatment 1, station and dates must match it."""
    sim = dl.Simulation(FILEX, 1, WEATHER)

    assert sim.check() == []
    result = sim.run()

    assert result.returncode == 0
    assert (result.run_dir / "Summary.OUT").is_file()


DTCM6401 = os.environ.get("DSSATLAB_MANUAL_DTCM6401")
CLIMATE = os.environ.get("DSSATLAB_MANUAL_CLIMATE")
CLIMATE_REQUIRED = pytest.mark.skipif(
    not DTCM6401 or not CLIMATE,
    reason="manual test: set DSSATLAB_MANUAL_DTCM6401 and DSSATLAB_MANUAL_CLIMATE",
)


@CLIMATE_REQUIRED
def test_course_generated_weather(tmp_path):
    """ADR 0032 proof (a): treatment 1 keeps the course's ten seasons."""
    course = shutil.copytree(DTCM6401, tmp_path / "course")
    sim = dl.Simulation(course / "DTCM6401.SNX", 1, weather=[CLIMATE])
    result = sim.run()

    assert result.returncode == 0
    rows = dl.read_summary(result.run_dir)
    assert len(rows) == 10
    assert all(row["TRNO"] == 1 and row["HWAM"] is not None for row in rows)


@CLIMATE_REQUIRED
@pytest.mark.parametrize("weather_source", ["W", "S"])
def test_generated_weather_seed_repeats(tmp_path, weather_source):
    """ADR 0032 proofs (b)-(c): a fixed seed repeats, a changed seed differs."""
    course = shutil.copytree(DTCM6401, tmp_path / "course")

    def yields(seed):
        controls = {"weather_source": weather_source, "years": 3, "random_seed": seed}
        sim = dl.Simulation(
            course / "DTCM6401.SNX", 1, weather=[CLIMATE],
            management={"treatments": {1: {"controls": controls}}},
        )
        assert sim.check() == []
        result = sim.run()
        assert result.returncode == 0
        rows = dl.read_summary(result.run_dir)
        assert len(rows) == 3
        assert all(row["TRNO"] == 1 and row["HWAM"] is not None for row in rows)
        return [row["HWAM"] for row in rows]

    first = yields(1234)
    assert yields(1234) == first
    assert yields(4321) != first
