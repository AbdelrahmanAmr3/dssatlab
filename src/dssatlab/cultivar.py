"""Check cultivar identifiers against the sibling .CUL copied into a simulation."""

from difflib import get_close_matches
from pathlib import Path
import re

from . import core
from .errors import DSSATCheckError, DSSATNotFoundError
from .experiment import _check_fields
from .filex import _section_row
from .filex_write import (_append_rows, _event_blocks, _event_row,
                          _insert_section, _new_level, _repoint)
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

def _cultivar_codes(filex, crop):
    """Read only VAR# from one crop's .CUL; never inspect model coefficients."""
    folder = Path(filex).parent
    paths = sorted(path for path in folder.iterdir()
                   if path.is_file() and path.suffix.upper() == ".CUL"
                   and path.name[:2].upper() == crop)
    if not paths:
        raise ValueError(f"no .CUL file for crop {crop!r} beside FileX {filex}. "
                         f"Supply the {crop}*.CUL file to copy into the simulation folder.")
    if len(paths) != 1:
        raise ValueError(f"multiple .CUL files for crop {crop!r}: "
                         f"{', '.join(path.name for path in paths)}. Keep one matching "
                         ".CUL file beside the FileX; model selection is not supported.")
    path = paths[0]
    return path, _read_cultivar_codes(path)


def _read_cultivar_codes(path, *, names: bool = False):
    """Read VAR# and optional names from a .CUL, shared across template checks and listings."""
    path = Path(path)
    cultivars, seen, in_table, has_header = [], set(), False, False
    col_start, col_end = 6, 22
    for line in path.read_text(encoding="latin-1").splitlines():
        if line.startswith("@"):
            parts = line.split()
            in_table = bool(parts and parts[0] == "@VAR#")
            has_header = has_header or in_table
            if in_table:
                tokens = list(re.finditer(r"[^\s@]+", line))
                if len(tokens) > 1:
                    col_start, col_end = tokens[1].start(), tokens[1].end()
        elif line.startswith("*"):
            in_table = False
        elif in_table and line.strip() and not line.lstrip().startswith("!"):
            code = line[:6]
            if re.fullmatch(r"[!-~]{6}", code) and code not in seen:
                seen.add(code)
                cultivars.append({
                    "code": code,
                    "name": line[col_start:col_end].strip(),
                })
    if not has_header:
        raise ValueError(f".CUL file {path} has no @VAR# header. Supply a cultivar table.")
    if not cultivars:
        raise ValueError(f".CUL file {path} has no cultivar codes under @VAR#. "
                         "Supply a table containing six-character cultivar codes.")
    return cultivars if names else [c["code"] for c in cultivars]


def _unknown_cultivar(code, codes, path, crop, where):
    return (f"{where}: code {code!r} is missing from .CUL "
            f"file {path} for crop {crop!r}. Closest codes: "
            f"{', '.join(get_close_matches(code, codes, 5, 0) or codes[:5])}"
            f" ({len(codes)} codes in the file; open it to see all).")


def _check_cultivar(data, where, filex, text, treatment, *, cultivar_path=None, new_cultivars=None):
    """Check fields, local cultivar availability and the edit before any write."""
    where = f"{where}, cultivar"
    if not isinstance(data, dict):
        return [f"{where}: expected a dict. Supply crop and code from the "
                "Experiment template or omit cultivar to keep the FileX level."]
    problems = _check_fields(data, ("crop", "code"), ("coefficients", "ecotype", "name"),
                             where, "Experiment")
    for field, pattern, hint in (
        ("crop", r"[A-Z]{2}", "two uppercase ASCII letters for CR"),
        ("code", r"[!-~]{6}", "six printable ASCII characters without spaces for INGENO"),
    ):
        if field in data and (not isinstance(data[field], str) or
                              not re.fullmatch(pattern, data[field])):
            problems.append(f"{where}, field {field!r}: found {_show_value(data[field])}. "
                            f"Supply a quoted string with {hint}.")
    if problems:
        return problems
    if cultivar_path is not None or isinstance(filex, (str, Path)):
        try:
            if cultivar_path is not None:
                path = Path(cultivar_path)
                if data["crop"] != path.name[:2]:
                    problems.append(f"{where}: crop {data['crop']!r} differs from the "
                                    f"FileX template crop {path.name[:2]!r}. Keep the template "
                                    "crop and choose a cultivar from its fixed model.")
                codes = _read_cultivar_codes(path)
            else:
                path, codes = _cultivar_codes(filex, data["crop"])
            from .cultivar_coefficients import _check_cultivar_definition
            problems.extend(_check_cultivar_definition(path, data, codes, where,
                                                       new_cultivars=new_cultivars))
        except (OSError, ValueError) as error:
            problems.append(f"{where}: cannot check .CUL: {error}")
    if text is not None and treatment is not None:
        try:
            _cultivar_text(text, treatment, data)
        except ValueError as error:
            problems.append(f"{where}: FileX {filex}: {error}")
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


def _cultivar_text(text, treatment, cultivar, *, rotation=None):
    """Add a CULTIVARS level and repoint CU, using the management edit helpers."""
    if rotation is None:
        _section_row(text, "TREATMENTS", "N", treatment, ("CU",))
    lines = text.splitlines(keepends=True)
    header = "@C CR INGENO CNAME"
    blocks, highest = _event_blocks(lines, "CULTIVARS", (header,))
    columns, index, _ = blocks[0]
    level = _new_level(lines, treatment, "CU", highest, "CULTIVARS", rotation=rotation)
    # CNAME is descriptive; -99 avoids retaining the previous cultivar's name.
    row = _event_row(columns, {"C": level, "CR": cultivar["crop"],
                               "INGENO": cultivar["code"], "CNAME": -99}, "CULTIVARS")
    _repoint(lines, treatment, "CU", level, rotation=rotation)
    if index is None:
        lines = _insert_section(lines, "CULTIVARS", [header, row])
    else:
        _append_rows(lines, index, [row])
    return "".join(lines)
