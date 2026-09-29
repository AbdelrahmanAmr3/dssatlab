"""Manual end-to-end check: build DSSAT on Linux, then run one FileX with it.

Skipped in normal test runs. It needs git, cmake, gfortran and network access, and the
build takes several minutes. To run it, point it at a FileX whose weather and soil files
sit beside it (filename at most 12 characters). Use a throwaway cache and config so your
own saved DSSAT is not touched:

    XDG_CACHE_HOME=/tmp/dl/cache XDG_CONFIG_HOME=/tmp/dl/config \\
    DSSATLAB_MANUAL_FILEX=/path/to/UFGA8201.MZX \\
    python -m pytest tests/test_manual_integration.py
"""

import os
import sys

import pytest

import dssatlab as dl

FILEX = os.environ.get("DSSATLAB_MANUAL_FILEX")

pytestmark = pytest.mark.skipif(
    not FILEX or not sys.platform.startswith("linux"),
    reason="manual test: set DSSATLAB_MANUAL_FILEX on Linux to run it",
)


def test_install_then_run():
    executable = dl.install()
    assert executable.name == "dscsm048"

    result = dl.run(FILEX)

    assert result.returncode == 0
    assert (result.run_dir / "Summary.OUT").is_file()
