"""Numbered fields, named treatments and one crop: the FileX template and checks."""

from pathlib import Path
import re

from . import core
from .cultivar import _read_cultivar_codes, _unknown_cultivar
from .errors import DSSATCheckError, DSSATNotFoundError
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

_TEMPLATE = """# DSSATLab FileX template: numbered fields, named treatments, one crop.
# Station, latitude, longitude and elevation come from checked weather data.
# The soil profile ID comes from checked soil data. Do not add them here.
# The simulation starts on the planting date. Use experiment data to add
# irrigation, fertilizer, initial conditions or control overrides later.
# Uncommented fields are required. Dates and cultivar codes must be quoted.

# Template crops: maize, wheat, rice, soybean, potato, sorghum, pearl millet,
# barley, peanut, dry bean; model is fixed per crop.
crop: "maize"
treatment_name: "My treatment" # 1-25 printable ASCII characters; not just spaces
# treatments: ["Control", "Variant"] # Instead of treatment_name; 1-99 names, same rule
# treatment_fields: [1, 2] # With treatments: one field per treatment, 1..K without gaps; default all 1
cultivar:
  code: "IB0035"              # Six ASCII characters, no spaces; case-sensitive
  # Must exist in the crop's .CUL in data directory/Genotype: maize MZCER048,
  # wheat WHCER048, rice RICER048, soybean SBGRO048, potato PTSUB048,
  # sorghum SGCER048, pearl millet MLCER048, barley BACER048, peanut
  # PNGRO048, dry bean BNGRO048. list_cultivars(crop) lists the codes.
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
    return _load_yaml(source, "FileX template",
                      "crop, cultivar, planting and either treatment_name or treatments keys")


def _template_treatment_names(data):
    """Return the template's treatment names, treatment 1 first.

    A treatments list of 1 to 99 entries gives N names; anything else gives one
    entry, so the checks report a malformed template for treatment 1 only.
    """
    if isinstance(data, dict) and "treatments" in data and "treatment_name" not in data:
        names = data["treatments"]
        if isinstance(names, list) and 1 <= len(names) <= 99:
            return names
    return [data.get("treatment_name") if isinstance(data, dict) else None]


def _template_treatment_fields(data):
    """Return checked treatment field numbers, defaulting every treatment to field 1."""
    return data.get("treatment_fields", [1] * len(_template_treatment_names(data)))


def _check_filex_template(data, data_dir) -> list[str]:
    """Return every template problem; data_dir is the DSSAT data directory.

    Accept loaded data only. No discovery, writes or DSSAT run is performed.
    Station and soil checks belong to weather/soil; this checks template values
    and planting column widths before the skeleton writer opens a destination.
    """
    where = "FileX template"
    if not isinstance(data, dict):
        return [f"{where}: expected a dict. Supply crop, cultivar, planting "
                "and either treatment_name or treatments."]
    problems = _check_fields(data, ("crop", "cultivar", "planting"),
                             ("treatment_name", "treatments", "treatment_fields", "harvest_date"), where, "FileX")
    crop = data.get("crop")
    supported = isinstance(crop, str) and crop in _CROPS
    if "crop" in data and not supported:
        problems.append(f"{where}: {_show_value(crop)} is not a template crop. "
                        f"Use one of the template crops: {', '.join(_CROPS)}.")
    names = []
    if ("treatment_name" in data) == ("treatments" in data):
        problems.append(f"{where}: supply exactly one of treatment_name or treatments.")
    elif "treatment_name" in data:
        names = [("treatment_name", data["treatment_name"])]
    else:
        treatments = data["treatments"]
        if not isinstance(treatments, list) or not 1 <= len(treatments) <= 99:
            problems.append(f"{where}, treatments: found {_show_value(treatments)}. "
                            "Supply a list of 1 to 99 treatment names.")
        if isinstance(treatments, list):
            names = [(f"treatments[{i}]", name) for i, name in enumerate(treatments, 1)]
    for field, name in names:
        if not isinstance(name, str) or not re.fullmatch(r"[ -~]{1,25}", name) or not name.strip():
            problems.append(f"{where}, {field}: found {_show_value(name)}. "
                            "Supply 1-25 printable ASCII characters, not just spaces.")
    if "treatment_fields" in data:
        fields = data["treatment_fields"]
        if "treatments" not in data or "treatment_name" in data:
            problems.append(f"{where}, treatment_fields: needs treatments. "
                            "Supply treatments with one name per treatment.")
        elif isinstance(data["treatments"], list):
            count = len(data["treatments"])
            if not isinstance(fields, list) or len(fields) != count:
                found = len(fields) if isinstance(fields, list) else _show_value(fields)
                problems.append(f"{where}, treatment_fields: supply one field number per "
                                f"treatment (found {found} for {count} treatments).")
            if isinstance(fields, list):
                bad = [i for i, value in enumerate(fields, 1)
                       if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 99]
                problems.extend(f"{where}, treatment_fields[{i}]: found {_show_value(fields[i - 1])}. "
                                "Supply a whole number 1 to 99." for i in bad)
                if fields and not bad:
                    missing = sorted(set(range(1, max(fields) + 1)) - set(fields))
                    if missing:
                        problems.append(f"{where}, treatment_fields: number the fields 1 to {max(fields)} "
                                        f"without gaps (missing {', '.join(map(str, missing))}).")
    if "cultivar" in data:
        problems.extend(_check_template_cultivar(data["cultivar"], crop if supported else None,
                                                 data_dir))
    planting = data.get("planting")
    if crop == "potato":
        for field in ("planting_material_weight", "sprout_length"):
            if not isinstance(planting, dict) or field not in planting:
                problems.append(f"{where}, planting: missing {field!r}; potato needs it. "
                                f"Supply planting.{field}.")
        if "harvest_date" not in data:
            problems.append(f"{where}: missing 'harvest_date'; potato needs it. "
                            "Supply a quoted harvest_date after the planting date.")
    if "harvest_date" in data:
        found = _check_date(data["harvest_date"], f"{where}, harvest_date")
        problems.extend(found)
        if (not found and isinstance(planting, dict)
                and not _check_date(planting.get("date"), "planting date")
                and data["harvest_date"] <= planting["date"]):
            problems.append(f"{where}, harvest_date: {data['harvest_date']} is not after the "
                            f"planting date {planting['date']}. Supply a later harvest_date.")
    if "planting" in data:
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


def _template_data_dir(executable=None):
    """Locate Genotype beside the executable, without connect()'s config write."""
    found = (core.detect()["dssat_path"] if executable is None
             else core.find_dssat_path(Path(executable)))
    if found is None:
        raise DSSATCheckError(["FileX template: cannot find the DSSAT data directory. "
                               "Supply executable pointing to DSSAT beside its Genotype folder."])
    return found.parent


def _listing_data_dir(executable):
    """Data directory for the listings; a missing DSSAT is DSSATNotFoundError."""
    try:
        return _template_data_dir(executable)
    except DSSATCheckError:
        checked = (f"Checked {executable}." if executable is not None
                   else "Checked saved configuration, DSSAT_HOME, and PATH/platform defaults "
                        "(including the managed cache on Linux).")
        raise DSSATNotFoundError(f"DSSAT was not found. {checked} "
                                 "Supply executable= pointing to the DSSAT executable or directory.") from None


def _listed_cultivars(path, crop):
    """Cultivar rows of a .CUL; an unreadable table is DSSATCheckError."""
    try:
        return _read_cultivar_codes(path, names=True)
    except ValueError as error:
        raise DSSATCheckError([f"Cannot list cultivars for {crop!r}: {error}"]) from None


def list_crops(executable: str | Path | None = None) -> list[dict]:
    """List template crops whose genotype files exist in the installed DSSAT.

    Parameters:
        executable: Optional path to the DSSAT executable or its directory.
            If None, discovery finds DSSAT without prompting or saving config.

    Returns:
        list[dict]: Rows with keys "crop", "code", "model", and "cultivars"
        in table order. Rows can be passed to to_dataframe().

    Examples:
        >>> import dssatlab as dl
        >>> crops = dl.list_crops()
        >>> crops[0]["crop"]
        'maize'
    """
    genotype_dir = _listing_data_dir(executable) / "Genotype"
    rows = []
    for crop, (code, model, prefix, extensions, _) in _CROPS.items():
        if not all((genotype_dir / f"{prefix}.{ext}").is_file() for ext in extensions):
            continue
        cultivars = _listed_cultivars(genotype_dir / f"{prefix}.CUL", crop)
        rows.append({"crop": crop, "code": code, "model": model, "cultivars": len(cultivars)})
    return rows


def list_cultivars(crop: str, executable: str | Path | None = None) -> list[dict]:
    """List cultivar codes and names for a template crop in file order.

    Parameters:
        crop: Template crop name (e.g. "maize", "wheat", "rice").
        executable: Optional path to the DSSAT executable or its directory.
            If None, discovery finds DSSAT without prompting or saving config.

    Returns:
        list[dict]: Rows with keys "code" and "name" in .CUL order, listing
        the first occurrence of each distinct code. Rows can be passed to
        to_dataframe().

    Raises:
        DSSATCheckError: If crop is not a template crop, or if the crop's .CUL
            file is missing or has no cultivar table.
        DSSATNotFoundError: If DSSAT executable or data directory cannot be found.

    Examples:
        >>> import dssatlab as dl
        >>> cultivars = dl.list_cultivars("maize")
        >>> cultivars[0]["code"]
        '999991'
    """
    if not isinstance(crop, str) or crop not in _CROPS:
        raise DSSATCheckError([
            f"{_show_value(crop)} is not a template crop. "
            f"Use one of the template crops: {', '.join(_CROPS)}."
        ])

    prefix = _CROPS[crop][2]
    cul_path = _listing_data_dir(executable) / "Genotype" / f"{prefix}.CUL"
    if not cul_path.is_file():
        raise DSSATCheckError([
            f"Missing .CUL file for crop {crop!r} at {cul_path}. "
            "Supply this file in the data directory's Genotype folder."
        ])

    return _listed_cultivars(cul_path, crop)
