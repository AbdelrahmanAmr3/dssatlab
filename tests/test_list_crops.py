"""Tests for list_crops and list_cultivars functions."""

from pathlib import Path
import pytest

from dssatlab import DSSATCheckError, DSSATNotFoundError, list_crops, list_cultivars, to_dataframe
from dssatlab import core
from dssatlab.cultivar import _CROPS


@pytest.fixture
def fake_dssat_env(tmp_path, monkeypatch):
    """Create a fake DSSAT installation with Genotype directory and files."""
    dssat_dir = tmp_path / "dssat"
    dssat_dir.mkdir()
    executable = dssat_dir / "dscsm048.exe"
    executable.write_text("fake executable")
    executable.chmod(0o755)

    genotype_dir = dssat_dir / "Genotype"
    genotype_dir.mkdir()

    # Maize: uses VRNAME.......... header spelling with CUL, ECO, SPE
    mz_cul = (
        "*MAIZE CULTIVAR COEFFICIENTS: MZCER048 MODEL\n"
        "! Comment line\n"
        "@VAR#  VRNAME.......... EXPNO   ECO#    P1    P2    P5    G2    G3 PHINT\n"
        "!Calibration                             P     P     P     G     G     N\n"
        "IB0001 CORNL281             . IB0001 110.0 0.300 685.0 907.9  6.60 38.90\n"
        "IB0002 CP170                . IB0001 120.0 0.000 685.0 907.9 10.00 38.90\n"
    )
    (genotype_dir / "MZCER048.CUL").write_text(mz_cul)
    (genotype_dir / "MZCER048.ECO").write_text("fake eco")
    (genotype_dir / "MZCER048.SPE").write_text("fake spe")

    # Rice: uses CUL and SPE only (no ECO)
    ri_cul = (
        "*RICE CULTIVAR COEFFICIENTS: RICER048 MODEL\n"
        "@VAR#  VRNAME.......... EXPNO   ECO#    P1    P2    P5\n"
        "RI0001 IR64                 . IB0001 100.0 0.200 600.0\n"
    )
    (genotype_dir / "RICER048.CUL").write_text(ri_cul)
    (genotype_dir / "RICER048.SPE").write_text("fake spe")

    # Soybean: uses VAR-NAME........ header spelling with duplicate code
    sb_cul = (
        "*SOYBEAN CULTIVAR COEFFICIENTS: CRGRO048 MODEL\n"
        "@VAR#  VAR-NAME........ EXPNO   ECO#  CSDL\n"
        "990011 M GROUP 000          . SB0001 14.60\n"
        "990011 M GROUP 000 DUP      . SB0001 14.60\n"
        "990012 M GROUP  00          . SB0001 14.35\n"
    )
    (genotype_dir / "SBGRO048.CUL").write_text(sb_cul)
    (genotype_dir / "SBGRO048.ECO").write_text("fake eco")
    (genotype_dir / "SBGRO048.SPE").write_text("fake spe")

    monkeypatch.setattr(core, "detect", lambda: {
        "os_name": "windows",
        "architecture": "x86_64",
        "dssat_path": executable,
    })
    return executable, genotype_dir


def test_list_crops_discovers_dssat_and_returns_rows(fake_dssat_env):
    executable, _ = fake_dssat_env
    rows = list_crops()
    # Exactly maize, rice, soybean have all required genotype files
    crops_listed = [r["crop"] for r in rows]
    assert crops_listed == ["maize", "rice", "soybean"]

    # Check table order matches _CROPS table order
    expected_order = [c for c in _CROPS if c in ("maize", "rice", "soybean")]
    assert crops_listed == expected_order

    # Check maize row structure
    maize = next(r for r in rows if r["crop"] == "maize")
    assert maize == {
        "crop": "maize",
        "code": "MZ",
        "model": "MZCER048",
        "cultivars": 2,
    }

    # Check soybean row: distinct count is 2 (duplicate 990011 not double counted)
    soybean = next(r for r in rows if r["crop"] == "soybean")
    assert soybean == {
        "crop": "soybean",
        "code": "SB",
        "model": "CRGRO048",
        "cultivars": 2,
    }

    # Explicit executable path works the same
    assert list_crops(executable=executable) == rows
    assert list_crops(executable=executable.parent) == rows


def test_rice_listed_with_only_cul_and_spe(fake_dssat_env):
    _, genotype_dir = fake_dssat_env
    assert not (genotype_dir / "RICER048.ECO").exists()
    assert (genotype_dir / "RICER048.CUL").exists()
    assert (genotype_dir / "RICER048.SPE").exists()

    rows = list_crops()
    rice = next((r for r in rows if r["crop"] == "rice"), None)
    assert rice is not None
    assert rice == {
        "crop": "rice",
        "code": "RI",
        "model": "RICER048",
        "cultivars": 1,
    }


def test_missing_eco_or_spe_omitted_from_list_crops(fake_dssat_env):
    _, genotype_dir = fake_dssat_env
    # Removing maize ECO leaves it out of list_crops
    (genotype_dir / "MZCER048.ECO").unlink()
    rows = list_crops()
    assert "maize" not in [r["crop"] for r in rows]


def test_missing_spe_omitted_from_list_crops(fake_dssat_env):
    _, genotype_dir = fake_dssat_env
    (genotype_dir / "RICER048.SPE").unlink()
    rows = list_crops()
    assert "rice" not in [r["crop"] for r in rows]


def test_list_cultivars_both_header_spellings_order_and_duplicates(fake_dssat_env):
    # VRNAME.......... spelling (maize)
    mz_cultivars = list_cultivars("maize")
    assert mz_cultivars == [
        {"code": "IB0001", "name": "CORNL281"},
        {"code": "IB0002", "name": "CP170"},
    ]

    # VAR-NAME........ spelling (soybean) with duplicate code
    # Order kept, first occurrence kept
    sb_cultivars = list_cultivars("soybean")
    assert sb_cultivars == [
        {"code": "990011", "name": "M GROUP 000"},
        {"code": "990012", "name": "M GROUP  00"},
    ]


def test_list_cultivars_unsupported_crop(fake_dssat_env):
    with pytest.raises(DSSATCheckError) as exc_info:
        list_cultivars("cotton")
    message = str(exc_info.value)
    assert "is not a template crop" in message
    assert "cotton" in message
    for crop in _CROPS:
        assert crop in message

    # Non-string input
    with pytest.raises(DSSATCheckError):
        list_cultivars(None)


def test_list_cultivars_missing_cul(fake_dssat_env):
    _, genotype_dir = fake_dssat_env
    (genotype_dir / "MZCER048.CUL").unlink()

    with pytest.raises(DSSATCheckError) as exc_info:
        list_cultivars("maize")
    message = str(exc_info.value)
    assert "Missing .CUL file" in message
    assert "MZCER048.CUL" in message
    assert str(genotype_dir / "MZCER048.CUL") in message


@pytest.mark.parametrize("listing", [list_crops, lambda: list_cultivars("maize")])
def test_cul_without_cultivar_table_is_check_error(fake_dssat_env, listing):
    _, genotype_dir = fake_dssat_env
    (genotype_dir / "MZCER048.CUL").write_text("*MAIZE CULTIVAR COEFFICIENTS\n")

    with pytest.raises(DSSATCheckError, match="no @VAR# header"):
        listing()


def test_dssat_not_found_with_discovery_monkeypatched(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "detect", lambda: {
        "os_name": "windows",
        "architecture": "x86_64",
        "dssat_path": None,
    })

    with pytest.raises(DSSATNotFoundError) as exc_crops:
        list_crops()
    msg = str(exc_crops.value)
    assert "DSSAT was not found" in msg
    assert "Checked saved configuration" in msg
    assert "executable=" in msg

    with pytest.raises(DSSATNotFoundError) as exc_cul:
        list_cultivars("maize")
    msg = str(exc_cul.value)
    assert "DSSAT was not found" in msg
    assert "Checked saved configuration" in msg
    assert "executable=" in msg

    # Explicit invalid executable
    bad_exe = tmp_path / "nonexistent" / "dscsm048"
    with pytest.raises(DSSATNotFoundError) as exc_bad:
        list_crops(executable=bad_exe)
    msg = str(exc_bad.value)
    assert "DSSAT was not found" in msg
    assert str(bad_exe) in msg
    assert "executable=" in msg

    with pytest.raises(DSSATNotFoundError) as exc_bad_cul:
        list_cultivars("maize", executable=bad_exe)
    msg = str(exc_bad_cul.value)
    assert "DSSAT was not found" in msg
    assert str(bad_exe) in msg
    assert "executable=" in msg


def test_rows_through_to_dataframe(fake_dssat_env):
    pytest.importorskip("pandas")
    crops_rows = list_crops()
    crops_df = to_dataframe(crops_rows)
    assert list(crops_df.columns) == ["crop", "code", "model", "cultivars"]
    assert len(crops_df) == len(crops_rows)

    cultivar_rows = list_cultivars("maize")
    cultivars_df = to_dataframe(cultivar_rows)
    assert list(cultivars_df.columns) == ["code", "name"]
    assert len(cultivars_df) == len(cultivar_rows)
