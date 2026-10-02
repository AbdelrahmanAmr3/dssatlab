"""Check and write fixed-width cultivar coefficients in a simulation .CUL copy."""

import re

from .experiment import _check_number
from .weather import _show_value


def _coefficient_line(path, code):
    """Locate the first listed cultivar and its own table's header spans."""
    lines = [line.decode("latin-1") for line in path.read_bytes().splitlines(keepends=True)]
    tokens = []
    for index, line in enumerate(lines):
        if line.startswith("@"):
            tokens = list(re.finditer(r"[^\s@]+", line)) if line.split()[0] == "@VAR#" else []
        elif line.startswith("*"):
            tokens = []
        elif tokens and not line.lstrip().startswith("!") and line[:6] == code:
            eco = next((i for i, token in enumerate(tokens) if token.group() == "ECO#"), None)
            spans = None if eco is None else {
                tokens[i].group(): (tokens[i - 1].end(), tokens[i].end())
                for i in range(eco + 1, len(tokens))}
            return lines, index, spans
    raise ValueError(f".CUL file {path} has no cultivar {code!r} under @VAR#.")


def _coefficient_text(value):
    return str(value) if isinstance(value, int) else (f"{value:.1f}" if value.is_integer() else repr(value))


def _check_coefficients(path, code, coefficients, where):
    if not isinstance(coefficients, dict) or not coefficients:
        return [f"{where}, field 'coefficients': found {_show_value(coefficients)}. Supply a "
                "non-empty dict of .CUL coefficient names to numbers, such as {'P1': 300}."]
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
