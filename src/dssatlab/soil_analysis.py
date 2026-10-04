"""Check soil analysis and render one new level in a copied FileX."""

from datetime import date
import re

from .experiment import _check_date, _check_fields, _check_number
from .filex import _section_row
from .filex_write import (_append_rows, _cell, _event_blocks, _insert_section,
                          _new_level, _repoint, _section_bounds)
from .weather import _dssat_date, _show_value


# DSSAT-CSM v4.8.6.0 InputModule/IPSLIN.for, IPSLAN formats 55 and 60:
# (I3,I5,3(1X,A5)) and (I3,F5.0,8(1X,F5.0)); SASC also reads (51X,F6.0).
_HEADERS = (
    "@A SADAT  SMHB  SMPX  SMKE  SANAME",
    "@A  SABL  SADM  SAOC  SANI SAPHW SAPHB  SAPX  SAKE  SASC",
)
_METHODS = {"ph_buffer_method": "SMHB", "p_method": "SMPX", "k_method": "SMKE"}
_FIELDS = {
    "bulk_density": ("SADM", 0, 10, True, "g/cm3"),
    "organic_carbon": ("SAOC", 0, 100, False, "%"),
    "total_nitrogen": ("SANI", 0, 10, False, "%"),
    "ph_water": ("SAPHW", 0, 14, True, ""),
    "ph_buffer": ("SAPHB", 0, 14, True, ""),
    "extractable_p": ("SAPX", 0, None, False, "mg/kg"),
    "exchangeable_k": ("SAKE", 0, None, False, "cmol/kg"),
    "stable_carbon": ("SASC", 0, 100, False, "%"),
}


def _check_soil_analysis(data, where):
    where = f"{where}, soil_analysis"
    if isinstance(data, str) and data == "off":
        return []
    if not isinstance(data, dict):
        return [f'{where}: expected a dict or the quoted string "off". Supply fields from the '
                "Experiment template or omit the section to keep the FileX level."]
    problems = _check_fields(data, ("date", "layers"), tuple(_METHODS), where, "Experiment")
    if "date" in data:
        problems.extend(_check_date(data["date"], f"{where}, field 'date'"))
    for field in _METHODS:
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2}[0-9]{3}", value):
                problems.append(f"{where}, field {field!r}: found {_show_value(value)}. Supply two "
                                "ASCII letters followed by three digits for the DSSAT code.")
    if "layers" not in data:
        return problems
    layers = data["layers"]
    if not isinstance(layers, list) or not layers:
        return problems + [f"{where}, layers: expected a non-empty list of layer dicts. "
                           "Supply layers with depth and optional soil analysis values."]
    previous = None
    for number, layer in enumerate(layers, 1):
        location = f"{where}, layer {number}"
        if not isinstance(layer, dict):
            problems.append(f"{location}: expected a dict. Supply depth and optional soil analysis values.")
            continue
        problems.extend(_check_fields(layer, ("depth",), tuple(_FIELDS), location, "Experiment"))
        for field in ("depth", *_FIELDS):
            if field not in layer:
                continue
            value, field_location = layer[field], f"{location}, field {field!r}"
            if field != "depth" and number > 1 and isinstance(layers[0], dict) and field not in layers[0]:
                problems.append(f"{field_location}: DSSAT reads a soil analysis column only when the "
                                f"first layer has a value. Add {field} to layer 1 or remove it "
                                "from the deeper layers.")
            numeric_problems = _check_number(value, field_location)
            problems.extend(numeric_problems)
            if numeric_problems:
                continue
            if field == "depth":
                column = "SABL"
                if value <= 0:
                    problems.append(f"{field_location}: found {_show_value(value)}. "
                                    "Supply a positive bottom-of-layer depth in cm.")
                if previous is not None and value <= previous:
                    problems.append(f"{field_location}: depth {value} cm follows {previous} cm. "
                                    "Supply layer bottom depths in strictly ascending order.")
                previous = value
            else:
                column, lower, upper, exclusive, unit = _FIELDS[field]
                span = ("0 or greater (no upper limit)" if upper is None else
                        f"above {lower} and at most {upper}" if exclusive else
                        f"{lower} to {upper} inclusive")
                if value < lower or (exclusive and value == lower) or (upper is not None and value > upper):
                    problems.append(f"{field_location}: found {_show_value(value)}. "
                                    f"Supply a number in the allowed range: {span}{' ' + unit if unit else ''}.")
            try:
                _cell(value, 5 if field == "depth" else 6, "SOIL ANALYSIS", column,
                      first_column=field == "depth")
            except ValueError as error:
                problems.append(f"{field_location}: {error}")
    return problems


def _soil_analysis_text(text, treatment, data):
    """Dry-run during checks; apply only to the selected treatment's copy at run."""
    name = "SOIL ANALYSIS"
    _section_row(text, "TREATMENTS", "N", treatment, ("SA",))
    lines = text.splitlines(keepends=True)
    if isinstance(data, str) and data == "off":
        _repoint(lines, treatment, "SA", 0)
        return "".join(lines)
    # IPSLAN reads inherited levels as I3. Give the header-based helpers an I2
    # view for discovery and reuse, while preserving the original rows' bytes.
    level_lines = list(lines)
    bounds = _section_bounds(lines, name)
    if bounds is not None:
        for index in range(bounds[0] + 1, bounds[1]):
            try:
                inherited = int(lines[index][:3])
            except ValueError:
                continue
            level_lines[index] = f"{inherited:2d} " + lines[index][3:]
    blocks, highest = _event_blocks(level_lines, name, _HEADERS, optional_columns=("SASC",))
    level = _new_level(level_lines, treatment, "SA", highest, name)
    if bounds is not None:
        for index in range(bounds[0] + 1, bounds[1]):
            if not level_lines[index]:
                lines[index] = ""  # Remove only rows of a reused, unreferenced level.
    # Two-character level plus blank also works with DSSAT's I2 level selection.
    prefix = _cell(level, 2, name, "A", first_column=True) + " "
    surface = prefix + _dssat_date(date.fromisoformat(data["date"]))
    surface += "".join(_cell(data.get(field, -99), 6, name, column)
                       for field, column in _METHODS.items())
    body = [_HEADERS[0], surface + "   -99", _HEADERS[1]]
    for layer in data["layers"]:
        row = prefix + _cell(layer["depth"], 5, name, "SABL", first_column=True)
        row += "".join(_cell(layer.get(field, -99), 6, name, column)
                       for field, (column, _, _, _, _) in _FIELDS.items())
        body.append(row)
    _repoint(lines, treatment, "SA", level)
    if blocks[0][1] is None:
        lines = _insert_section(lines, name, body)
    else:
        # Keep each analysis date and its layers together under a fresh header pair.
        _append_rows(lines, max(block[1] for block in blocks), body)
    return "".join(lines)
