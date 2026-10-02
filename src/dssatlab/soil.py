"""The fixed soil template and strict checks for one soil profile."""

import csv
import math
from pathlib import Path
import re

from .errors import DSSATError
from .weather import _read_table, _show_value

# Required: DSSAT stops with an error when one of these is missing or -99
# (verified on real DSSAT 4.8.5.017). The optional ones get a default or an
# estimate from DSSAT itself; they are written as -99 when not given.
REQUIRED = ("soil_id", "salb", "slro", "sldr", "slpf", "slb",
            "slll", "sdul", "ssat", "srgf")
OPTIONAL = ("slnf", "ssks", "sbdm", "sloc", "slmh", "slcl", "slsi", "slcf",
            "slni", "slhw", "slhb", "scec", "sadc", "slu1", "smhb", "smpx", "smke", "scom")
PROFILE_COLUMNS = ("soil_id", "salb", "slro", "sldr", "slnf", "slpf",
                   "slu1", "smhb", "smpx", "smke", "scom")
_CODE_COLUMNS = ("slmh", "smhb", "smpx", "smke", "scom")
SOIL_ID_MAX_LENGTH = 10  # DSSAT truncates longer soil profile IDs, characters.
WATER_RANGE = (0, 1)  # Soil water content, cm3/cm3; both limits excluded.
SBDM_RANGE = (0.5, 2.5)  # Bulk density, g/cm3.
SLOC_RANGE = (0, 100)  # Organic carbon, %.
SRGF_RANGE = (0, 1)  # Root growth factor, fraction.
SSKS_RANGE = (0, 500)  # Saturated hydraulic conductivity, cm/h.
SALB_RANGE = (0, 1)  # Soil albedo, fraction.
SLRO_RANGE = (0, 100)  # Runoff curve number, dimensionless.
SLDR_RANGE = (0, 1)  # Drainage rate, fraction/day.
SLNF_RANGE = (0, 1)  # Mineralization factor, dimensionless factor.
SLPF_RANGE = (0, 1)  # Soil fertility factor, dimensionless factor.


def write_soil_template(path: str | Path) -> None:
    """Write a UTF-8 soil template with one valid three-layer soil profile.

    Units are DSSAT's own: slb in cm; slll/sdul/ssat in cm3/cm3; ssks in
    cm/h; sbdm in g/cm3; sloc in %. Profile and other layer values use
    DSSAT's units without conversion. slmh/smhb/smpx/smke/scom are codes:
    1-5 ASCII letters, digits or _ . + -. Optional values default to -99.
    An existing destination raises DSSATError, preserving the user's data.
    """
    path = Path(path)
    message = f"Soil template path {path} already exists. Choose another path."
    if path.exists():
        raise DSSATError(message)
    profile = dict(soil_id="IBMZ910214", salb=0.13, slro=60, sldr=0.5, slpf=1, slnf=1)
    layers = ((5, 0.10, 0.24, 0.45, 1.0, 6, 1.3, 1.5),
              (15, 0.12, 0.26, 0.43, 0.8, 4, 1.4, 1.1),
              (30, 0.13, 0.27, 0.40, 0.6, 3, 1.5, 0.8))
    try:
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(REQUIRED + OPTIONAL)
            for slb, slll, sdul, ssat, srgf, ssks, sbdm, sloc in layers:
                row = dict(profile, slb=slb, slll=slll, sdul=sdul, ssat=ssat,
                           srgf=srgf, ssks=ssks, sbdm=sbdm, sloc=sloc)
                writer.writerow([row.get(name, -99) for name in REQUIRED + OPTIONAL])
    except FileExistsError as error:
        raise DSSATError(message) from error


_PROFILE_FIELDS = (("scom", None), ("salb", 2), ("slu1", 1), ("sldr", 2), ("slro", 1),
                  ("slnf", 2), ("slpf", 2), ("smhb", None), ("smpx", None), ("smke", None))
_LAYER_FIELDS = (("slb", None), ("slmh", None), ("slll", 3), ("sdul", 3),
                ("ssat", 3), ("srgf", 3), ("ssks", 2), ("sbdm", 2),
                ("sloc", 2), ("slcl", 1), ("slsi", 1), ("slcf", 1),
                ("slni", 3), ("slhw", 1), ("slhb", 1), ("scec", 1), ("sadc", 1))


def _cell(value, decimals, code=False):
    if code:
        return f"{_code_text(value):>6}"
    if value is None or value == -99 or value == "-99":
        return "   -99"
    if decimals is None:  # Depths are written as given, not rounded.
        return f"{float(value) + 0.0:>6g}"
    num = round(float(value), decimals) + 0.0
    if round(num) == -99:
        return "   -99"
    return f"{num:>6.{decimals}f}"


def _profile_text(rows: list[dict]) -> str:
    first = rows[0]
    depth = int(round(rows[-1]["slb"]))
    out = [
        f"*{first['soil_id']:<10}  DSSATLAB    -99  {depth:>6} Written by dssatlab",
        "@SITE        COUNTRY          LAT     LONG SCS FAMILY",
        " -99         -99              -99      -99 -99",
        "@ SCOM  SALB  SLU1  SLDR  SLRO  SLNF  SLPF  SMHB  SMPX  SMKE",
        "".join(_cell(first.get(n, -99), d, n in _CODE_COLUMNS) for n, d in _PROFILE_FIELDS),
        "@  SLB  SLMH  SLLL  SDUL  SSAT  SRGF  SSKS  SBDM  SLOC  SLCL  SLSI  SLCF  SLNI  SLHW  SLHB  SCEC  SADC",
    ]
    for row in rows:
        out.append("".join(_cell(row.get(n, -99), d, n in _CODE_COLUMNS) for n, d in _LAYER_FIELDS))
    return "\n".join(out) + "\n"


def _write_soil_profiles(profiles: list[list[dict]], path: str | Path) -> Path:
    """Write several soil profiles into one SOIL.SOL file."""
    path = Path(path)
    header = f"*SOILS: {profiles[0][0]['soil_id']} (written by dssatlab)\n"
    content = header + "\n".join(_profile_text(p) for p in profiles)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(content)
    return path


def write_soil_file(rows: list[dict], path: str | Path) -> Path:
    """Write one soil profile from valid parsed soil rows to the chosen path.

    Require nonempty rows from _parse_soil with no problems. Profile values
    come from the first row, including -99 for unset optional values. The parent
    folder must exist; an existing file is overwritten.
    """
    return _write_soil_profiles([rows], path)


def _check_columns(columns, where, problems):
    for name in REQUIRED:
        if name not in columns:
            problems.append(f"Soil data {where}: missing column {name!r}. "
                            f"Add the required column {name!r}.")
    for name in columns:
        if name not in REQUIRED + OPTIONAL:
            problems.append(f"Soil data {where}: unknown column {_show_value(name)}. "
                            "Use exact lower-case names; valid columns are "
                            f"{', '.join(REQUIRED + OPTIONAL)}.")


def _dataframe_cell(value):
    """Match CSV cell text, including blanks for None and numeric NaN."""
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            if math.isnan(value):
                return ""
        except (TypeError, ValueError, OverflowError):
            pass
    try:
        return str(value)
    except (ValueError, OverflowError):
        return value  # Let the checks report even unrepresentable numbers.


def _code_text(value):
    if isinstance(value, str) and not value.isascii():
        return value
    if value is None or isinstance(value, str) and not value.strip():
        return "-99"
    if isinstance(value, str) and not re.fullmatch(r"\s*([+-]?([\d.]+|inf|infinity)|nan)\s*", value, re.I):
        return value  # Text such as "1E2" or "1_0" stays a code, not a number.
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if math.isnan(number) or number == -99:
        return "-99"
    if not math.isfinite(number):
        return None
    return f"{number + 0.0:g}"


def _parse_soil(source) -> tuple[list[dict], list[str]]:
    """Read soil data and return parsed rows and all problems without writing.

    DataFrame cells use CSV text and blank-cell semantics, keeping IDs as text.
    Numeric columns become floats; code columns become text; missing values become -99.
    Invalid fields are omitted. Consumers must require no problems before
    using parsed rows. The source is never mutated, sorted or repaired.
    """
    rows, columns, read_problems = _read_table(source, "Soil data")
    problems = [message for _, message in read_problems]
    if read_problems and read_problems[0][0] == "source":
        return [], problems
    # The shared reader supplies columns only for CSV paths and DataFrames.
    is_dataframe = columns is not None and not isinstance(source, (str, Path))
    if columns is not None:
        for column in dict.fromkeys(columns):
            if columns.count(column) > 1:
                problems.append(f"Soil template column {column!r} is repeated in "
                                "line 1. Keep one column per name.")
        _check_columns(columns, "line 1", problems)
    if not rows:
        problems.append("Soil data has no layer rows. Supply at least one row "
                        "following the soil template.")
    ranges = {"sbdm": (*SBDM_RANGE, "g/cm3"), "sloc": (*SLOC_RANGE, "%"),
              "srgf": (*SRGF_RANGE, "fraction"), "ssks": (*SSKS_RANGE, "cm/h"),
              "salb": (*SALB_RANGE, "fraction"), "slro": (*SLRO_RANGE, "dimensionless"),
              "sldr": (*SLDR_RANGE, "fraction/day"), "slnf": (*SLNF_RANGE, "factor"),
              "slpf": (*SLPF_RANGE, "factor")}
    parsed, profile_values, depths = [], {}, {}
    previous_depth = None
    for line, row in rows:
        if not isinstance(row, dict):
            problems.append(f"Soil data row {line} is not a dict. "
                            "Supply a dict of soil template column values.")
            continue
        if columns is None:
            _check_columns(row, f"row {line}", problems)
        result = {}
        for name in REQUIRED + OPTIONAL:
            if name not in row and name not in OPTIONAL:
                if columns is not None and name in columns:
                    problems.append(f"Soil data row {line}: missing value for "
                                    f"{name!r}. Supply a value.")
                continue
            value = row.get(name)
            if is_dataframe:
                value = _dataframe_cell(value)
            where = f"Soil data row {line}, column {name!r}"
            if name in _CODE_COLUMNS:
                try:
                    code = _code_text(value)
                except (ValueError, OverflowError):
                    code = None
                if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]{1,5}", code):
                    problems.append(f"{where}: found {_show_value(value)}. Use 1-5 ASCII "
                                    "letters, digits or _ . + -; DSSAT reads it into a "
                                    "5-character code.")
                    continue
                result[name] = code
                continue
            if name == "soil_id":
                if not isinstance(value, str) or not re.fullmatch(
                        rf"[A-Za-z0-9]{{1,{SOIL_ID_MAX_LENGTH}}}", value):
                    problems.append(f"{where}: found {_show_value(value)}. "
                                    f"Use 1 to {SOIL_ID_MAX_LENGTH} ASCII letters or digits.")
                    continue
                result[name] = value
                continue
            if name in OPTIONAL and (value is None or
                                     isinstance(value, str) and not value.strip()):
                value = -99
            try:
                number = float(value)
                if not math.isfinite(number):
                    value = number
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                problems.append(f"{where}: found {_show_value(value)}. "
                                "Supply a non-empty finite number in DSSAT's units.")
                continue
            result[name] = number
            if name in ranges and not (name in OPTIONAL and number == -99):
                low, high, unit = ranges[name]
                if not low <= number <= high:
                    problems.append(f"{where}: found {_show_value(value)}; allowed "
                                    f"range is {low} to {high} {unit}. "
                                    "Correct the value using DSSAT's units.")
            if name in ("slll", "sdul", "ssat"):
                low, high = WATER_RANGE
                if not low < number < high:
                    problems.append(f"{where}: found {_show_value(value)}. Supply a "
                                    f"fraction strictly between {low} and {high} cm3/cm3.")
        if all(name in result for name in ("slll", "sdul", "ssat")):
            if not result["slll"] < result["sdul"] < result["ssat"]:
                problems.append(f"Soil data row {line}: slll {result['slll']}, "
                                f"sdul {result['sdul']}, ssat {result['ssat']} are "
                                "not in strict order. Correct the fractions so "
                                "slll < sdul < ssat (equal values leave no plant-"
                                "available water or no pore space).")
        for name in PROFILE_COLUMNS:
            if name not in result:
                continue
            if name not in profile_values:
                profile_values[name] = (line, result[name])
            first_line, first_value = profile_values[name]
            if result[name] != first_value:
                problems.append(f"Soil data row {line}, column {name!r}: found "
                                f"{result[name]!r}, but row {first_line} has "
                                f"{first_value!r}. Use identical {name} values "
                                "on every row for one soil profile.")
        if "slb" in result:
            depth = result["slb"]
            where = f"Soil data row {line}, column 'slb'"
            if depth <= 0:
                problems.append(f"{where}: found {depth}. Supply a positive layer "
                                "bottom depth in cm.")
            if depth in depths:
                problems.append(f"{where}: duplicate depth {depth} cm from row "
                                f"{depths[depth]}. Keep one row per layer bottom depth.")
            else:
                depths[depth] = line
            if previous_depth is not None and depth <= previous_depth:
                problems.append(f"{where}: depth {depth} cm follows {previous_depth} cm. "
                                "Supply layer bottom depths in strictly increasing order.")
            previous_depth = depth
        parsed.append(result)
    return parsed, problems
