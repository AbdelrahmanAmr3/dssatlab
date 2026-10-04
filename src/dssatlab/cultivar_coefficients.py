"""Check and write fixed-width cultivar coefficients in a simulation .CUL copy."""

import re
from difflib import get_close_matches

from .experiment import _check_number
from .weather import _show_value


def _coefficient_line(path, code=None):
    """Locate a cultivar's spans, or the first row of the first @VAR# table."""
    lines = [line.decode("latin-1") for line in path.read_bytes().splitlines(keepends=True)]
    tokens = []
    for index, line in enumerate(lines):
        if line.startswith("@"):
            if code is None and tokens:
                break
            tokens = list(re.finditer(r"[^\s@]+", line)) if line.split()[0] == "@VAR#" else []
        elif line.startswith("*"):
            if code is None and tokens:
                break
            tokens = []
        elif tokens and not line.lstrip().startswith(("!", "$")) and (
                line[:6] == code if code is not None else re.fullmatch(r"[!-~]{6}", line[:6])):
            eco = next((i for i, token in enumerate(tokens) if token.group() == "ECO#"), None)
            spans = None if eco is None else {
                tokens[i].group(): (tokens[i - 1].end(), tokens[i].end())
                for i in range(eco + 1, len(tokens))}
            return lines, index, spans
    if code is None:
        raise ValueError(f".CUL file {path} has no cultivar row in its first @VAR# table. "
                         "Supply a standard .CUL table with a cultivar line.")
    raise ValueError(f".CUL file {path} has no cultivar {code!r} under @VAR#.")


def _coefficient_text(value):
    return str(value) if isinstance(value, int) else (f"{value:.1f}" if value.is_integer() else repr(value))


def _check_coefficients(path, code, coefficients, where, *, spans=None):
    if not isinstance(coefficients, dict) or not coefficients:
        return [f"{where}, field 'coefficients': found {_show_value(coefficients)}. Supply a "
                "non-empty dict of .CUL coefficient names to numbers, such as {'P1': 300}."]
    if spans is None:
        _, _, spans = _coefficient_line(path, code)
    if spans is None:
        return [f"{where}: .CUL file {path} has no ECO# column, so coefficients cannot be "
                "located. Remove 'coefficients' or supply a standard .CUL file."]
    problems = []
    for name, value in coefficients.items():
        location = f"{where}, coefficient {name!r}"
        if name not in spans:
            problems.append(f"{location}: not a coefficient in {path}. Use one of: {', '.join(spans)}.")
            continue
        found = _check_number(value, location)
        problems.extend(found)
        if not found:
            text = _coefficient_text(value)
            start, end = spans[name]
            if "e" in text.lower():
                problems.append(f"{location}: {text} is written in exponent notation, which the "
                                f"{name} column in {path.name} cannot hold. "
                                "Supply a plain decimal value.")
            elif len(text) > end - start - 1:
                problems.append(f"{location}: {text} needs {len(text)} characters; the {name} "
                                f"column in {path.name} holds {end - start - 1}. "
                                "Supply a value with fewer digits.")
    return problems


def _check_cultivar_definition(path, data, codes, where, *, new_cultivars=None):
    """Check an existing or new cultivar without changing the genotype files."""
    from .cultivar import _unknown_cultivar

    # DSSAT scans readable rows across the whole file, including later tables.
    for line in path.read_text(encoding="latin-1").splitlines():
        code = line[:6]
        if (not line.lstrip().startswith(("!", "@", "*", "$"))
                and re.fullmatch(r"[!-~]{6}", code) and code not in codes):
            codes.append(code)
    code = data["code"]
    if code in codes:
        fields = [field for field in ("ecotype", "name") if field in data]
        problems = ([f"{where}: code {code!r} is an existing cultivar in {path}. "
                     f"Remove {', '.join(repr(field) for field in fields)} to use or change it, "
                     "or choose a new code."] if fields else [])
        if "coefficients" in data and not fields:
            problems.extend(_check_coefficients(path, code, data["coefficients"], where))
        return problems

    complete = "ecotype" in data and "coefficients" in data
    problems = [] if complete else [_unknown_cultivar(code, codes, path, data["crop"], where)]
    lines, index, spans = _coefficient_line(path)
    header = next(line for line in lines[:index] if line.split() and line.split()[0] == "@VAR#")
    if header[30:36] != "  ECO#" or spans is None:
        problems.append(f"{where}: .CUL file {path} has an unsupported layout: ECO# must be "
                        "in columns 31-36 of the first @VAR# header. Supply a standard .CUL file.")
        return problems
    if not complete:
        problems.append(f"{where}: to define a new cultivar, supply ecotype and coefficients "
                        f"with every required coefficient: {', '.join(spans)}.")
        return problems

    if code.startswith(("!", "@", "*", "$")):
        problems.append(f"{where}, field 'code': found {code!r}. Supply a code not starting with "
                        "!, @, * or $ so DSSAT reads the cultivar line.")
    if re.fullmatch(r"DL[0-9]{4}", code) and code != "DL0000":
        problems.append(f"{where}, field 'code': {code!r} is reserved for changed cultivars "
                        "(DL0001-DL9999). Choose a different new cultivar code.")
    coefficients = data["coefficients"]
    if isinstance(coefficients, dict):
        missing = [name for name in spans if name not in coefficients]
        if missing:
            problems.append(f"{where}, field 'coefficients': missing required coefficients: "
                            f"{', '.join(missing)}. Supply every coefficient from the first @VAR# table.")
    problems.extend(_check_coefficients(path, None, coefficients, where, spans=spans))
    if "name" in data and (not isinstance(data["name"], str)
                           or not re.fullmatch(r"[ -~]{0,16}", data["name"])):
        problems.append(f"{where}, field 'name': found {_show_value(data['name'])}. Supply a "
                        "quoted string of at most 16 printable ASCII characters for columns 8-23.")
    ecotype = data["ecotype"]
    if not isinstance(ecotype, str) or not re.fullmatch(r"[!-~]{6}", ecotype):
        problems.append(f"{where}, field 'ecotype': found {_show_value(ecotype)}. Supply a "
                        "quoted string with six printable ASCII characters without spaces.")
    else:
        problems.extend(_check_ecotype(path, ecotype, where))
    if new_cultivars is not None:
        key = (path, code)
        if key in new_cultivars:
            previous, previous_where = new_cultivars[key]
            if (data["crop"] != previous["crop"]
                    or ecotype != previous["ecotype"]
                    or data.get("name", code) != previous.get("name", code)
                    or coefficients != previous["coefficients"]):
                problems.append(f"{where}: new cultivar code {code!r} has conflicting definitions "
                                f"here and in {previous_where}. Checked crop, ecotype, name and "
                                "coefficients across template treatments sharing the .CUL copy. "
                                "Use identical definitions for this code or choose different codes.")
        else:
            new_cultivars[key] = data, where
    return problems


def _check_ecotype(cul_path, ecotype, where):
    from .cultivar import _CROPS

    path = cul_path.with_suffix(".ECO")
    if not path.exists():
        if any(cul_path.stem.upper() == prefix and "ECO" in extensions
               for _, _, prefix, extensions, _ in _CROPS.values()):
            return [f"{where}, field 'ecotype': required .ECO file {path} is missing. "
                    "Supply it beside the .CUL file to check the ecotype."]
        return []
    try:
        codes = list(dict.fromkeys(line[:6] for line in path.read_text(encoding="latin-1").splitlines()
                    if not line.lstrip().startswith(("!", "@", "*", "$"))
                    and re.fullmatch(r"[!-~]{6}", line[:6])))
    except OSError as error:
        return [f"{where}, field 'ecotype': cannot read .ECO file {path}: {error}. "
                "Supply a readable .ECO file beside the .CUL file."]
    if ecotype not in codes:
        return [f"{where}, field 'ecotype': code {ecotype!r} is missing from .ECO file {path}. "
                f"Closest codes: {', '.join(get_close_matches(ecotype, codes, 5, 0))} "
                f"({len(codes)} codes in the file). Choose an ecotype listed in that file."]
    return []


def _new_cultivar(filex, cultivar):
    """Append a checked new cultivar to the first table in the folder copy."""
    from .cultivar import _cultivar_codes

    path, codes = _cultivar_codes(filex, cultivar["crop"])
    if cultivar["code"] in codes:
        return cultivar  # Identical definitions across template treatments share one line.
    lines, index, spans = _coefficient_line(path)
    ending = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    insert_at = index + 1
    for i in range(index + 1, len(lines)):
        line = lines[i]
        if line.startswith(("@", "*")):
            break
        if (not line.lstrip().startswith(("!", "$"))
                and re.fullmatch(r"[!-~]{6}", line[:6])):
            insert_at = i + 1
    line = (cultivar["code"] + " " + cultivar.get("name", cultivar["code"]).ljust(16)
            + ".".rjust(7) + cultivar["ecotype"])
    for name, (start, end) in spans.items():
        line = line.ljust(end)
        line = line[:start] + _coefficient_text(cultivar["coefficients"][name]).rjust(end - start) + line[end:]
    if not lines[insert_at - 1].endswith(("\r", "\n")):
        lines[insert_at - 1] += ending
    lines.insert(insert_at, line + ending)
    path.write_bytes("".join(lines).encode("latin-1"))
    return cultivar


def _changed_cultivar(filex, cultivar):
    """Insert a changed cultivar in the folder copy, returning its FileX identifiers."""
    if "coefficients" not in cultivar:
        return cultivar
    from .cultivar import _cultivar_codes
    path, codes = _cultivar_codes(filex, cultivar["crop"])
    lines, index, spans = _coefficient_line(path, cultivar["code"])
    code = next(f"DL{i:04d}" for i in range(1, 10000) if f"DL{i:04d}" not in codes)
    source = lines[index]
    ending = source[len(source.rstrip("\r\n")):]
    line = code + source.rstrip("\r\n")[6:]
    for name, value in cultivar["coefficients"].items():
        start, end = spans[name]
        line = line.ljust(end)
        line = line[:start] + _coefficient_text(value).rjust(end - start) + line[end:]
    if not ending:
        ending = "\r\n" if any(s.endswith("\r\n") for s in lines) else "\n"
        lines[index] += ending
    lines.insert(index + 1, line + ending)
    path.write_bytes("".join(lines).encode("latin-1"))
    return {**cultivar, "code": code}
