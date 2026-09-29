"""Fixed-width soil files match the real DSSAT profile layout."""

from copy import deepcopy
import os
from pathlib import Path
import re
import shutil

import pytest

from dssatlab.runner import run
from dssatlab.soil import _parse_soil, write_soil_file, write_soil_template


SAMPLE_PROFILE = (
    "*SOILS: IBMZ910014 (written by dssatlab)\n"
    "*IBMZ910014  DSSATLAB    -99     180 Written by dssatlab\n"
    "@SITE        COUNTRY          LAT     LONG SCS FAMILY\n"
    " -99         -99              -99      -99 -99\n"
    "@ SCOM  SALB  SLU1  SLDR  SLRO  SLNF  SLPF  SMHB  SMPX  SMKE\n"
    "   -99  0.18   2.0  0.65  60.0  1.00  0.92   -99   -99   -99\n"
    "@  SLB  SLMH  SLLL  SDUL  SSAT  SRGF  SSKS  SBDM  SLOC  SLCL  SLSI  SLCF  SLNI  SLHW  SLHB  SCEC  SADC\n"
    "     5   -99 0.026 0.096 0.230 1.000   -99  1.30  2.00   -99   -99   -99   -99   -99   -99  20.0   -99\n"
    "    15   -99 0.025 0.086 0.230 1.000   -99  1.30  1.00   -99   -99   -99   -99   -99   -99   -99   -99\n"
    "   180   -99 0.070 0.258 0.360 0.000   -99  1.20  0.24   -99   -99   -99   -99   -99   -99   -99   -99\n"
)


@pytest.fixture
def sample_rows():
    profile = dict(soil_id="IBMZ910014", salb=0.18, slu1=2.0, sldr=0.65,
                   slro=60.0, slnf=1.0, slpf=0.92)
    return [
        dict(profile, slb=5.0, slll=0.026, sdul=0.096, ssat=0.230,
             srgf=1.000, sbdm=1.30, sloc=2.00, scec=20.0),
        dict(profile, slb=15.0, slll=0.025, sdul=0.086, ssat=0.230,
             srgf=1.000, sbdm=1.30, sloc=1.00),
        dict(profile, slb=180.0, slll=0.070, sdul=0.258, ssat=0.360,
             srgf=0.000, sbdm=1.20, sloc=0.24),
    ]


@pytest.mark.parametrize("as_string", [False, True])
def test_exact_sample_and_returned_path(tmp_path, sample_rows, as_string):
    path = tmp_path / "caller-chosen-soil.SOL"
    rows = deepcopy(sample_rows)
    before = deepcopy(rows)
    result = write_soil_file(rows, str(path) if as_string else path)

    assert path.read_text(encoding="ascii") == SAMPLE_PROFILE
    assert path.read_bytes() == SAMPLE_PROFILE.encode("ascii")
    assert isinstance(result, Path)
    assert result == path
    assert list(tmp_path.iterdir()) == [path]
    assert rows == before


def test_existing_file_overwritten(tmp_path, sample_rows):
    path = tmp_path / "SOIL.SOL"
    path.write_text("old content\n", encoding="ascii")
    write_soil_file(sample_rows, path)
    assert path.read_text(encoding="ascii") == SAMPLE_PROFILE


def test_column_widths_and_headers(tmp_path, sample_rows):
    path = tmp_path / "SOIL.SOL"
    write_soil_file(sample_rows, path)
    lines = path.read_text(encoding="ascii").splitlines()

    assert lines[0] == "*SOILS: IBMZ910014 (written by dssatlab)"
    assert lines[1] == "*IBMZ910014  DSSATLAB    -99     180 Written by dssatlab"
    assert lines[2] == "@SITE        COUNTRY          LAT     LONG SCS FAMILY"
    assert lines[3] == " -99         -99              -99      -99 -99"
    assert lines[4] == "@ SCOM  SALB  SLU1  SLDR  SLRO  SLNF  SLPF  SMHB  SMPX  SMKE"
    assert len(lines[4]) == 60
    assert len(lines[5]) == 60
    assert lines[6] == "@  SLB  SLMH  SLLL  SDUL  SSAT  SRGF  SSKS  SBDM  SLOC  SLCL  SLSI  SLCF  SLNI  SLHW  SLHB  SCEC  SADC"
    assert len(lines[6]) == 102
    for layer_line in lines[7:]:
        assert len(layer_line) == 102


@pytest.mark.parametrize("small_negative", [False, True])
def test_negative_zero_handling(tmp_path, sample_rows, small_negative):
    eps = -0.0001 if small_negative else -0.0
    for r in sample_rows:
        r.update(salb=eps, slu1=eps, sldr=eps, slro=eps, slnf=eps, slpf=eps,
                 sloc=eps, sbdm=eps, scec=eps)
    path = tmp_path / "SOIL.SOL"
    write_soil_file(sample_rows, path)
    content = path.read_text(encoding="ascii")
    assert "-0.0" not in content
    assert "-0.00" not in content
    assert "-0.000" not in content


def test_parsed_optional_minus_99_written_as_minus_99(tmp_path):
    raw = [
        {"soil_id": "IBMZ910214", "salb": 0.18, "slro": 60.0, "sldr": 0.65, "slpf": 0.92,
         "slb": 5, "slll": 0.026, "sdul": 0.096, "ssat": 0.230, "srgf": 1.0},
        {"soil_id": "IBMZ910214", "salb": 0.18, "slro": 60.0, "sldr": 0.65, "slpf": 0.92,
         "slb": 15, "slll": 0.025, "sdul": 0.086, "ssat": 0.230, "srgf": 1.0},
    ]
    rows, problems = _parse_soil(raw)
    assert not problems

    path = tmp_path / "SOIL.SOL"
    write_soil_file(rows, path)
    lines = path.read_text(encoding="ascii").splitlines()

    assert lines[5] == "   -99  0.18   -99  0.65  60.0   -99  0.92   -99   -99   -99"
    assert lines[7] == "     5   -99 0.026 0.096 0.230 1.000   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99"
    assert lines[8] == "    15   -99 0.025 0.086 0.230 1.000   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99"
    # Ensure -99 is written as -99 without decimal point
    assert "-99." not in path.read_text(encoding="ascii")


def test_one_profile_only(tmp_path, sample_rows):
    path = tmp_path / "SOIL.SOL"
    write_soil_file(sample_rows, path)
    lines = path.read_text(encoding="ascii").splitlines()
    assert sum(1 for line in lines if line.startswith("*SOILS:")) == 1
    assert sum(1 for line in lines if line.startswith("*") and not line.startswith("*SOILS:")) == 1
    assert sum(1 for line in lines if line.startswith("@SITE")) == 1
    assert sum(1 for line in lines if line.startswith("@ SCOM")) == 1
    assert sum(1 for line in lines if line.startswith("@  SLB")) == 1


def test_template_example_roundtrip(tmp_path):
    csv_path = tmp_path / "template.csv"
    write_soil_template(csv_path)
    rows, problems = _parse_soil(csv_path)
    assert not problems

    sol_path = tmp_path / "SOIL.SOL"
    write_soil_file(rows, sol_path)

    expected = (
        "*SOILS: IBMZ910214 (written by dssatlab)\n"
        "*IBMZ910214  DSSATLAB    -99      30 Written by dssatlab\n"
        "@SITE        COUNTRY          LAT     LONG SCS FAMILY\n"
        " -99         -99              -99      -99 -99\n"
        "@ SCOM  SALB  SLU1  SLDR  SLRO  SLNF  SLPF  SMHB  SMPX  SMKE\n"
        "   -99  0.13   -99  0.50  60.0  1.00  1.00   -99   -99   -99\n"
        "@  SLB  SLMH  SLLL  SDUL  SSAT  SRGF  SSKS  SBDM  SLOC  SLCL  SLSI  SLCF  SLNI  SLHW  SLHB  SCEC  SADC\n"
        "     5   -99 0.100 0.240 0.450 1.000  6.00  1.30  1.50   -99   -99   -99   -99   -99   -99   -99   -99\n"
        "    15   -99 0.120 0.260 0.430 0.800  4.00  1.40  1.10   -99   -99   -99   -99   -99   -99   -99   -99\n"
        "    30   -99 0.130 0.270 0.400 0.600  3.00  1.50  0.80   -99   -99   -99   -99   -99   -99   -99   -99\n"
    )
    assert sol_path.read_text(encoding="ascii") == expected


SOIL_FILEX = os.environ.get("DSSATLAB_MANUAL_SOIL_FILEX")


@pytest.mark.skipif(
    not SOIL_FILEX,
    reason="manual test: set DSSATLAB_MANUAL_SOIL_FILEX pointing at a FileX to run it",
)
def test_manual_soil_file_with_real_dssat(tmp_path):
    filex_src = Path(SOIL_FILEX).resolve()
    assert filex_src.is_file(), f"FileX not found: {filex_src}"

    # Setup isolated folder in tmp_path
    filex_copy = tmp_path / filex_src.name
    content = filex_src.read_text(encoding="utf-8", errors="replace")
    content = re.sub(r"IBMZ\d{6}", "IBMZ910214", content)
    filex_copy.write_text(content, encoding="utf-8")

    # Copy sibling files (.CUL, .ECO, .SPE, .WTH)
    for sibling in filex_src.parent.iterdir():
        if sibling.is_file() and sibling.suffix.upper() in (".CUL", ".ECO", ".SPE", ".WTH"):
            shutil.copy2(sibling, tmp_path / sibling.name)

    # If weather or genotype not beside FileX, check parent/Weather/Genotype
    dssat_root = filex_src.parent.parent
    if (dssat_root / "Weather").is_dir():
        for wth in (dssat_root / "Weather").glob("*.WTH"):
            if not (tmp_path / wth.name).exists():
                shutil.copy2(wth, tmp_path / wth.name)
    if (dssat_root / "Genotype").is_dir():
        for geno in (dssat_root / "Genotype").glob("MZCER048.*"):
            if not (tmp_path / geno.name).exists():
                shutil.copy2(geno, tmp_path / geno.name)

    # Generate SOIL.SOL using write_soil_template & write_soil_file
    csv_path = tmp_path / "soil_template.csv"
    write_soil_template(csv_path)
    rows, problems = _parse_soil(csv_path)
    assert not problems, f"Soil parsing problems: {problems}"

    soil_path = tmp_path / "SOIL.SOL"
    write_soil_file(rows, soil_path)
    assert soil_path.is_file()

    # Run real DSSAT through existing run()
    result = run(filex_copy, treatment=1)
    assert result.returncode == 0
    assert (result.run_dir / "Summary.OUT").is_file()
    assert not (result.run_dir / "ERROR.OUT").exists()


def test_fractional_layer_depth_is_not_rounded(tmp_path):
    rows = [dict(soil_id="IBMZ910214", salb=0.13, slro=60, sldr=0.5, slnf=1, slpf=1,
                 slb=7.5, slll=0.1, sdul=0.24, ssat=0.45, srgf=1, ssks=-99, sbdm=-99,
                 sloc=-99)]
    text = write_soil_file(rows, tmp_path / "SOIL.SOL").read_text()
    assert "   7.5   -99 0.100" in text
