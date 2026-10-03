"""Check initial conditions and render a new level in a copied FileX."""

from datetime import date
import re

from .experiment import _check_date, _check_fields, _check_number
from .filex import _section_row
from .filex_write import (_append_rows, _event_blocks, _event_row,
                          _insert_section, _new_level, _repoint)
from .weather import _dssat_date, _show_value


# DSSAT 4.8 Input Files help and UFGA8201.MZX: surface row then layer rows.
_HEADERS = (
    "@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME",
    "@C  ICBL  SH2O  SNH4  SNO3",
)
_DETAIL_FIELDS = {
    "root_mass": ("ICRT", None, "kg/ha"),
    "nodule_mass": ("ICND", None, "kg/ha"),
    "rhizobia_number": ("ICRN", 1, ""),
    "rhizobia_effectiveness": ("ICRE", 1, ""),
    "residue_n": ("ICREN", 100, "%"),
    "residue_p": ("ICREP", 100, "%"),
    "residue_incorporation": ("ICRIP", 100, "%"),
    "residue_depth": ("ICRID", None, "cm"),
}


def _check_layers(layers, where):
    if not isinstance(layers, list) or not layers:
        return [f"{where}: expected a non-empty list of layer dicts. Supply layers "
                "with depth, water, nh4 and no3 following the Experiment template."]
    problems, depths = [], []
    for number, layer in enumerate(layers, 1):
        location = f"{where}, layer {number}"
        if not isinstance(layer, dict):
            problems.append(f"{location}: expected a dict. Supply depth, water, nh4 and no3.")
            continue
        fields = ("depth", "water", "nh4", "no3")
        problems.extend(_check_fields(layer, fields, (), location, "Experiment"))
        for field in fields:
            if field not in layer:
                continue
            value, field_location = layer[field], f"{location}, field {field!r}"
            numeric_problems = _check_number(value, field_location)
            problems.extend(numeric_problems)
            if numeric_problems:
                continue
            if field == "depth":
                if value <= 0:
                    problems.append(f"{field_location}: found {_show_value(value)}. "
                                    "Supply a positive bottom-of-layer depth in cm.")
                if depths and value <= depths[-1]:
                    problems.append(f"{field_location}: depth {value} cm follows {depths[-1]} cm. "
                                    "Supply layer bottom depths in strictly ascending order.")
                depths.append(value)
            elif field == "water" and not 0 <= value <= 1:
                problems.append(f"{field_location}: found {_show_value(value)}; allowed range "
                                "is 0 to 1 cm3/cm3 inclusive. Supply volumetric soil water.")
            elif field in ("nh4", "no3") and value < 0:
                problems.append(f"{field_location}: found {_show_value(value)}; allowed range "
                                "is 0 or greater mg/kg (no upper limit). Supply nonnegative "
                                "soil nitrogen in DSSAT's units.")
    return problems


def _check_initial_conditions(data, where):
    where = f"{where}, initial_conditions"
    if isinstance(data, str) and data == "off":
        return []
    if not isinstance(data, dict):
        return [f'{where}: expected a dict or the quoted string "off". Supply fields from the Experiment '
                "template or omit the section to keep the FileX level."]
    problems = _check_fields(data, ("date", "layers"), ("previous_crop", "residue_mass", *_DETAIL_FIELDS),
                             where, "Experiment")
    if "date" in data:
        problems.extend(_check_date(data["date"], f"{where}, field 'date'"))
    if "previous_crop" in data:
        value = data["previous_crop"]
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2}", value):
            problems.append(f"{where}, field 'previous_crop': found {_show_value(value)}. "
                            "Supply a quoted two-ASCII-letter DSSAT crop code.")
    if "residue_mass" in data:
        location, value = f"{where}, field 'residue_mass'", data["residue_mass"]
        numeric_problems = _check_number(value, location)
        problems.extend(numeric_problems)
        if not numeric_problems and value < 0:
            problems.append(f"{location}: found {_show_value(value)}. "
                            "Supply a nonnegative surface residue mass in kg/ha.")
    for field, (_, upper, unit) in _DETAIL_FIELDS.items():
        if field not in data:
            continue
        location, value = f"{where}, field {field!r}", data[field]
        unit = f" {unit}" if unit else ""
        span = (f"0 or greater{unit} (no upper limit)" if upper is None
                else f"0 to {upper}{unit} inclusive")
        numeric_problems = _check_number(value, location)
        if numeric_problems:
            problems.extend(f"{problem} Allowed range is {span}." for problem in numeric_problems)
        elif value < 0 or (upper is not None and value > upper):
            problems.append(f"{location}: found {_show_value(value)}. "
                            f"Supply a number in the allowed range: {span}.")
    if "layers" in data:
        problems.extend(_check_layers(data["layers"], f"{where}, layers"))
    return problems


def _initial_conditions_text(text, treatment, data):
    """Dry-run during checks; apply only to the selected treatment's copy at run."""
    name = "INITIAL CONDITIONS"
    _section_row(text, "TREATMENTS", "N", treatment, ("IC",))
    lines = text.splitlines(keepends=True)
    if isinstance(data, str) and data == "off":
        _repoint(lines, treatment, "IC", 0)
        return "".join(lines)
    optional = {column for field, (column, _, _) in _DETAIL_FIELDS.items() if field not in data}
    blocks, highest = _event_blocks(lines, name, _HEADERS, optional_columns=optional)
    level = _new_level(lines, treatment, "IC", highest, name)
    day = date.fromisoformat(data["date"])
    values = {"C": level, "PCR": data.get("previous_crop", -99),
              "ICDAT": _dssat_date(day),
              "ICRES": data.get("residue_mass", -99)}
    values.update({column: data.get(field, -99) for field, (column, _, _) in _DETAIL_FIELDS.items()})
    body = [blocks[0][2], _event_row(blocks[0][0], values, name), blocks[1][2]]
    for layer in data["layers"]:
        values = {"C": level, "ICBL": layer["depth"], "SH2O": layer["water"],
                  "SNH4": layer["nh4"], "SNO3": layer["no3"]}
        body.append(_event_row(blocks[1][0], values, name))
    _repoint(lines, treatment, "IC", level)
    if blocks[0][1] is None:
        lines = _insert_section(lines, name, body)
    else:
        # Keep each surface row and its layers together, including repeated headers.
        _append_rows(lines, max(block[1] for block in blocks), body)
    return "".join(lines)
