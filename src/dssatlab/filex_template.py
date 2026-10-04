"""Numbered fields, named treatments and crop values: FileX template checks."""

from pathlib import Path
import re

from .cultivar import _CROPS, _read_cultivar_codes, _unknown_cultivar
from .experiment import _check_date, _check_fields, _check_number
from .filex_write import _cell, _columns, _PLANTING_HEADER
from .management import _check_planting, _REQUIRED
from .management_file import _load_yaml, _write_template
from .weather import _show_value


_CROP_ENTRY_BOUNDS = (1, 99)


_TEMPLATE = """# DSSATLab FileX template: numbered fields, named treatments.
# Use one crop, crop entries for mixed-crop treatments, or a rotation.
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

# For different crops in different treatments, replace the top-level crop,
# cultivar, planting, harvest_date and treatment_name with the example below.
# crops takes 1-99 entries, each with its own crop, cultivar, planting and optional
# harvest_date. treatment_crops needs treatments: one entry number per treatment,
# 1..K with every entry used. Entries may share a crop. Do not combine with rotation.
# treatment_fields still selects each treatment's field; omitted means all field 1.
# Mixed-crops example:
# treatments: ["Maize control", "Maize fertilized", "Soybean", "Wheat"]
# treatment_crops: [1, 1, 2, 3]
# crops:
#   - crop: "maize"
#     cultivar: {code: "IB0035"}
#     planting:
#       date: "2021-03-01"
#       method: "S"
#       distribution: "R"
#       population: 7.2
#       row_spacing: 75
#       depth: 5
#   - crop: "soybean"
#     cultivar: {code: "IB0011"}
#     planting:
#       date: "2021-04-01"
#       method: "S"
#       distribution: "R"
#       population: 30
#       row_spacing: 50
#       depth: 5
#   - crop: "wheat"
#     cultivar: {code: "IB0488"}
#     planting:
#       date: "2021-03-01"
#       method: "S"
#       distribution: "R"
#       population: 150
#       row_spacing: 20
#       depth: 3
#     harvest_date: "2021-08-01"

# Only a leading fallow takes start_date, before end_date; the simulation starts there.
# For example, prepend {crop: "fallow", start_date: "2021-02-01", end_date: "2021-02-28"}
# and end the last fallow on "2022-01-31", before the start's day of year.
# Rotation example: replace the single-crop form with 2 to 99 components.
# treatment_name: "Maize and fallow"
# rotation:
#   - crop: "maize"
#     cultivar: {code: "IB0035"}
#     planting:
#       date: "2021-03-01"
#       method: "S"
#       distribution: "R"
#       population: 7.2
#       row_spacing: 75
#       depth: 5
#   - crop: "fallow"
#     end_date: "2022-02-28"
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


def _template_crop_entries(data):
    """Return entries in FileX level order; malformed lists give no entries.

    Rotation takes precedence on conflicts so genotype checks keep working.
    """
    entries = data.get("rotation", data.get("crops", [data]))
    return entries if isinstance(entries, list) else []


def _template_crop_entry(data, treatment):
    """Return a treatment's crop entry, or None for a malformed crop mapping."""
    if "crops" not in data:
        return data
    entries, numbers = _template_crop_entries(data), data.get("treatment_crops")
    if (isinstance(treatment, bool) or not isinstance(treatment, (int, str))
            or not str(treatment).isascii() or not str(treatment).isdigit()
            or not isinstance(numbers, list) or not 1 <= int(treatment) <= len(numbers)):
        return None
    number = numbers[int(treatment) - 1]
    if type(number) is int and 1 <= number <= len(entries):
        entry = entries[number - 1]
        return entry if isinstance(entry, dict) else None
    return None


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
    # Import only at dispatch: crop entries use the shared crop value checks.
    from .crop_entries import _check_crop_entries
    crop_problems = _check_crop_entries(data, data_dir)
    if "rotation" in data and "crops" not in data:
        # Import only at dispatch: rotation uses the shared template checks.
        from .rotation import _check_rotation_template
        return crop_problems + _check_rotation_template(data, data_dir)
    required = () if "crops" in data else ("crop", "cultivar", "planting")
    optional = ("treatment_name", "treatments", "treatment_fields", "harvest_date", "treatment_crops")
    if "crops" in data:
        optional += ("crop", "cultivar", "planting", "crops", "rotation")
    problems = _check_fields(data, required, optional, where, "FileX")
    problems.extend(_check_template_treatments(data))
    problems.extend(crop_problems)
    if "crops" not in data:
        problems.extend(_check_template_crop(_template_crop_entry(data, 1), data_dir))
    return problems


def _check_template_treatments(data):
    """Check treatment names and numbered fields shared by crop forms."""
    where, problems = "FileX template", []
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
        elif not isinstance(fields, list):
            problems.append(f"{where}, treatment_fields: found {_show_value(fields)}. "
                            "Supply a list with one field number per treatment.")
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
    return problems


def _check_template_crop(data, data_dir):
    """Shared crop values, cultivar lookup, dates and planting widths."""
    where, problems = "FileX template", []
    crop = data.get("crop")
    supported = isinstance(crop, str) and crop in _CROPS
    if "crop" in data and not supported:
        problems.append(f"{where}: {_show_value(crop)} is not a template crop. "
                        f"Use one of the template crops: {', '.join(_CROPS)}.")
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


def _template_genotype_files(data, data_dir):
    """List each template crop's required genotype files once; fallow needs none."""
    paths = {}
    # Genotype checks need only each entry's crop, even if treatment mapping
    # or other values are malformed. Rotation takes precedence on conflicts.
    for component in _template_crop_entries(data):
        crop = component.get("crop") if isinstance(component, dict) else None
        if isinstance(crop, str) and crop in _CROPS and data_dir is not None:
            _, _, prefix, extensions, _ = _CROPS[crop]
            for suffix in extensions:
                path = data_dir / "Genotype" / f"{prefix}.{suffix}"
                paths.setdefault(path, None)
    return list(paths)


def _shared_field_problems(rows, kind):
    """Reject different checked rows claiming the same station or soil ID."""
    column, label, own = (("station", "station", "station code") if kind == "weather"
                          else ("soil_id", "soil ID", "soil ID"))
    seen, problems = {}, []
    for field, data in rows.items():
        identity = data[0][column]
        if identity in seen and data != rows[seen[identity]]:
            problems.append(f"Fields {seen[identity]} and {field} both use {label} {identity!r} "
                            f"but their {kind} data differs. Give each field's {kind} its own "
                            f"{own}, or the same data.")
        else:
            seen.setdefault(identity, field)
    return problems
