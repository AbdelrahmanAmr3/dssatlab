"""One field, one treatment and one crop: the fixed FileX template and checks."""

from pathlib import Path
import re

from .cultivar import _read_cultivar_codes, _unknown_cultivar
from .experiment import _check_date, _check_fields, _check_number
from .filex_write import _cell, _columns, _PLANTING_HEADER
from .management import _check_planting, _REQUIRED
from .management_file import _load_yaml, _write_template
from .weather import _show_value


# Crop code, fixed model, genotype prefix, required extensions, SYMBI.
_CROPS = {
    "maize": ("MZ", "MZCER048", "MZCER048", ("CUL", "ECO", "SPE"), "N"),
    "wheat": ("WH", "CSCER048", "WHCER048", ("CUL", "ECO", "SPE"), "N"),
    "rice": ("RI", "RICER048", "RICER048", ("CUL", "SPE"), "N"),
    "soybean": ("SB", "CRGRO048", "SBGRO048", ("CUL", "ECO", "SPE"), "Y"),
    "potato": ("PT", "PTSUB048", "PTSUB048", ("CUL", "ECO", "SPE"), "N"),
    "sorghum": ("SG", "SGCER048", "SGCER048", ("CUL", "ECO", "SPE"), "N"),
    "pearl millet": ("ML", "MLCER048", "MLCER048", ("CUL", "ECO", "SPE"), "N"),
    "barley": ("BA", "CSCER048", "BACER048", ("CUL", "ECO", "SPE"), "N"),
    "peanut": ("PN", "CRGRO048", "PNGRO048", ("CUL", "ECO", "SPE"), "Y"),
    "dry bean": ("BN", "CRGRO048", "BNGRO048", ("CUL", "ECO", "SPE"), "Y"),
}

_TEMPLATE = """# DSSATLab FileX template: one field, one treatment, one crop.
# Station, latitude, longitude and elevation come from checked weather data.
# The soil profile ID comes from checked soil data. Do not add them here.
# The simulation starts on the planting date. Use experiment data to add
# irrigation, fertilizer, initial conditions or control overrides later.
# Uncommented fields are required. Dates and cultivar codes must be quoted.

# Template crops: maize, wheat, rice, soybean, potato, sorghum, pearl millet,
# barley, peanut, dry bean; model is fixed per crop.
crop: "maize"
treatment_name: "My treatment" # 1-25 printable ASCII characters; not just spaces
cultivar:
  code: "IB0035"              # Six ASCII characters, no spaces; case-sensitive
  # Must exist in data directory/Genotype/<prefix>.CUL for the crop,
  # e.g. MZCER048.CUL for maize.
planting:
  date: "2021-03-01"          # Quoted ISO calendar date, YYYY-MM-DD
  method: "S"                 # One ASCII letter: DSSAT planting code (S=seed)
  distribution: "R"           # One ASCII letter: DSSAT distribution code (R=rows)
  population: 7.2             # Plants/m2, above zero; also used at emergence
  row_spacing: 75             # cm, above zero
  depth: 5                    # cm, nonnegative
  # planting_material_weight: 1500 # Optional PLWT, kg/ha; potato needs it
  # sprout_length: 2               # Optional SPRL, cm; potato needs it
# harvest_date: "2021-08-01"  # Optional; potato needs it. After planting,
# within weather data; omit to harvest at maturity.
# Values must fit DSSAT's fixed-width columns without rounding or truncation.
"""


def write_filex_template(path: str | Path) -> None:
    """Write commented FileX YAML without requiring PyYAML; preserve existing paths.

    The maize example uses IB0035 from the DSSAT data directory. Loading YAML
    uses the same optional PyYAML loader as experiment data; dicts need no extra
    dependency. Raise DSSATError if the destination already exists.
    """
    _write_template(path, _TEMPLATE, "FileX", None)


def _load_filex_template(source):
    """Return (data, problems) from a YAML path or dict, without writing."""
    return _load_yaml(source, "FileX template", "crop, treatment_name, cultivar and planting keys")


def _check_filex_template(data, data_dir) -> list[str]:
    """Return every template problem; data_dir is the DSSAT data directory.

    Accept loaded data only. No discovery, writes or DSSAT run is performed.
    Station and soil checks belong to weather/soil; this checks template values
    and planting column widths before the skeleton writer opens a destination.
    """
    where = "FileX template"
    if not isinstance(data, dict):
        return [f"{where}: expected a dict. Supply crop, treatment_name, cultivar and planting."]
    problems = _check_fields(data, ("crop", "treatment_name", "cultivar", "planting"),
                             ("harvest_date",), where, "FileX")
    crop = data.get("crop")
    supported = isinstance(crop, str) and crop in _CROPS
    if "crop" in data and not supported:
        problems.append(f"{where}: unsupported crop {_show_value(crop)}. "
                        f"Supported crops: {', '.join(_CROPS)}.")
    if "treatment_name" in data:
        name = data["treatment_name"]
        if not isinstance(name, str) or not re.fullmatch(r"[ -~]{1,25}", name) or not name.strip():
            problems.append(f"{where}, treatment_name: found {_show_value(name)}. "
                            "Supply 1-25 printable ASCII characters, not just spaces.")
    if "cultivar" in data:
        problems.extend(_check_template_cultivar(data["cultivar"], crop if supported else None,
                                                 data_dir))
    planting = data.get("planting")
    if crop == "potato":
        for field in ("planting_material_weight", "sprout_length", "harvest_date"):
            source = data if field == "harvest_date" else planting
            if not isinstance(source, dict) or field not in source:
                problems.append(f"{where}: missing {field!r}; potato needs it.")
    if "harvest_date" in data:
        found = _check_date(data["harvest_date"], f"{where}, harvest_date")
        problems.extend(found)
        if (not found and isinstance(planting, dict)
                and not _check_date(planting.get("date"), "planting date")
                and data["harvest_date"] <= planting["date"]):
            problems.append(f"{where}, harvest_date: must be after the planting date.")
    if "planting" in data:
        planting = data["planting"]
        found = _check_planting(planting, f"{where}, planting")
        if isinstance(planting, dict):
            allowed = _REQUIRED + ("planting_material_weight", "sprout_length")
            found.extend(f"{where}, planting: unknown key {_show_value(key)}. "
                         f"Use only {', '.join(allowed)} from the FileX template."
                         for key in planting if key not in allowed
                         and not any(f"unknown key {_show_value(key)}" in p for p in found))
            # Dates/codes have bounded lengths after the value checks. Check
            # each numeric cell separately so all overflows are reported.
            columns = _columns(_PLANTING_HEADER)
            for field, column in (("population", "PPOP"), ("row_spacing", "PLRS"),
                                  ("depth", "PLDP"), ("planting_material_weight", "PLWT"),
                                  ("sprout_length", "SPRL")):
                if field not in planting or _check_number(planting[field], field):
                    continue
                left, right = columns[column]
                try:
                    _cell(planting[field], right - left, "PLANTING DETAILS", column)
                except ValueError as error:
                    found.append(f"{where}, planting: {error}")
        problems.extend(found)
    return problems


def _check_template_cultivar(data, crop, data_dir):
    where = "FileX template, cultivar"
    if not isinstance(data, dict):
        return [f"{where}: expected a dict. Supply a quoted six-character code."]
    problems = _check_fields(data, ("code",), (), where, "FileX")
    code = data.get("code")
    if "code" not in data:
        return problems
    if not isinstance(code, str) or not re.fullmatch(r"[!-~]{6}", code):
        return problems + [f"{where}, code: found {_show_value(code)}. "
                           "Supply six printable ASCII characters without spaces as a quoted string."]
    if crop is not None:
        crop_code, _, prefix, _, _ = _CROPS[crop]
        try:
            path = Path(data_dir) / "Genotype" / f"{prefix}.CUL"
            codes = _read_cultivar_codes(path)
            if code not in codes:
                problems.append(_unknown_cultivar(code, codes, path, crop_code, where))
        except (OSError, ValueError, TypeError) as error:
            problems.append(f"{where}: cannot check .CUL: {error}. "
                            f"Supply a DSSAT data directory containing Genotype/{prefix}.CUL.")
    return problems
