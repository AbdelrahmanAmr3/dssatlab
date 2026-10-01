"""Check cultivar identifiers against the sibling .CUL copied into a simulation."""

from difflib import get_close_matches
from pathlib import Path
import re

from .experiment import _check_fields
from .filex_write import _cultivar_text
from .weather import _show_value


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


def _check_cultivar(data, where, filex, text, treatment, *, cultivar_path=None):
    """Check fields, local cultivar availability and the edit before any write."""
    where = f"{where}, cultivar"
    if not isinstance(data, dict):
        return [f"{where}: expected a dict. Supply crop and code from the "
                "Experiment template or omit cultivar to keep the FileX level."]
    problems = _check_fields(data, ("crop", "code"), (), where, "Experiment")
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
            if data["code"] not in codes:
                problems.append(_unknown_cultivar(data["code"], codes, path, data["crop"], where))
        except (OSError, ValueError) as error:
            problems.append(f"{where}: cannot check .CUL: {error}")
    if text is not None and treatment is not None:
        try:
            _cultivar_text(text, treatment, data)
        except ValueError as error:
            problems.append(f"{where}: FileX {filex}: {error}")
    return problems
