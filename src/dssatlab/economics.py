"""Net returns from Summary quantities and a DSSAT Price file."""

import math
from pathlib import Path
import re

from .errors import DSSATCheckError


# Component: (Summary quantity, divisor, sign). BASE has no quantity.
_TERMS = {
    "GRAN": ("HWAH", 1000, 1), "BYPR": ("BWAH", 1000, 1),
    "BASE": (None, 1, -1), "NFER": ("NICM", 1, -1),
    "NCOS": ("NI#M", 1, -1), "IRRI": ("IRCM", 1, -1),
    "IRCO": ("IR#M", 1, -1), "SCOS": ("DWAP", 1, -1),
    "RESM": ("RECM", 1000, -1), "PCOS": ("PICM", 1, -1),
    "PFER": ("PI#M", 1, -1), "KCOS": ("KICM", 1, -1),
    "KFER": ("KI#M", 1, -1),
}
_PARAMETERS = ("IDIS", "PAR1", "PAR2", "PAR3")


def _expected_prices(table, where, problems):
    """Check one section and return its valid components' expected prices."""
    for name in ("@PRAM", *_PARAMETERS):
        if name not in table:
            problems.append(f"{where}: missing {name} row. Add the {name} row to this section.")
    if "@PRAM" not in table:
        return {}
    columns = table["@PRAM"]
    missing = [name for name in _TERMS if name not in columns]
    extra = [name for name in columns if name not in _TERMS]
    if missing:
        problems.append(f"{where}: missing columns: {', '.join(missing)}. "
                        "Use all 13 required price columns in @PRAM.")
    if extra:
        problems.append(f"{where}: extra columns: {', '.join(extra)}. "
                        "Use only the 13 required price columns in @PRAM.")
    if len(set(columns)) != len(columns):
        problems.append(f"{where}: duplicate @PRAM columns {columns!r}. "
                        "Use each required price column once.")
    values = {}
    for parameter in _PARAMETERS:
        if parameter not in table:
            continue
        cells = table[parameter]
        if len(cells) != len(columns):
            problems.append(f"{where}: {parameter} has {len(cells)} values for "
                            f"{len(columns)} @PRAM columns. Supply one value per column.")
        for column, cell in zip(columns, cells):
            try:
                value = float(cell)
            except ValueError:
                value = math.nan
            if not math.isfinite(value):
                problems.append(f"{where}: {column} {parameter} value {cell!r} is not a "
                                "finite number. Set a finite numeric price-file value.")
            else:
                values[column, parameter] = value
    prices = {}
    for column in _TERMS:
        idis = values.get((column, "IDIS"))
        if idis is None:
            continue
        if idis not in (-1, 0, 1, 2, 3):
            problems.append(f"{where}: {column} has unknown IDIS {idis}. "
                            "Use IDIS -1, 0, 1, 2 or 3.")
            continue
        if not all((column, parameter) in values for parameter in _PARAMETERS):
            continue
        p1, p2, p3 = (values[column, name] for name in _PARAMETERS[1:])
        rule = None
        if idis == 1 and p1 > p2:
            rule = "PAR1 <= PAR2"
        elif idis == 2 and not p1 <= p2 <= p3:
            rule = "PAR1 <= PAR2 <= PAR3"
        elif idis == 3 and p2 < 0:
            rule = "PAR2 >= 0"
        if rule:
            problems.append(f"{where}: {column} IDIS {idis} has inconsistent parameters "
                            f"{(p1, p2, p3)}. Set {rule}.")
            continue
        if idis == -1:
            prices[column] = None
        elif idis == 1:
            prices[column] = p1 / 2 + p2 / 2
        elif idis == 2:
            prices[column] = p1 / 3 + p2 / 3 + p3 / 3
        else:
            prices[column] = p1
    return prices


def _read_prices(price_file, problems):
    """Read every crop/treatment section, retaining the current crop heading."""
    try:
        text = Path(price_file).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, TypeError, ValueError) as error:
        problems.append(f"Price file {price_file!s}: could not read the path as UTF-8 "
                        f"({error}). Supply an existing, readable DSSAT .PRI file.")
        return None
    sections = []
    crop = None
    table = None
    where = f"Price file {price_file}"
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("*"):
            heading = line[1:].strip()
            if heading.startswith("PRICE-COST_FILE"):
                continue
            treatment = re.fullmatch(r"TREATMENT\s*(\d+)", heading)
            if treatment:
                n = int(treatment[1])
                where = f"Price file {price_file}, crop {crop!r}, treatment {n}"
                table = {}
                if crop is None:
                    problems.append(f"{where}: treatment at line {number} has no crop heading. "
                                    "Add a '* <CR>' heading before the treatment.")
                else:
                    sections.append(((crop, n), table, where))
            else:
                crop = heading
                table = None
            continue
        fields = line.split()
        if table is None:
            problems.append(f"Price file {price_file}, line {number}: found {fields[0]!r} "
                            "outside a treatment section. Add crop and treatment headings.")
        elif fields[0] not in ("@PRAM", *_PARAMETERS):
            problems.append(f"{where}, line {number}: unknown row {fields[0]!r}. "
                            "Use @PRAM, IDIS, PAR1, PAR2 and PAR3 rows.")
        elif fields[0] in table:
            problems.append(f"{where}, line {number}: duplicate {fields[0]} row. "
                            "Remove the duplicate row.")
        else:
            table[fields[0]] = fields[1:]
    if not sections:
        problems.append(f"Price file {price_file}: no crop/treatment sections found. "
                        "Add a crop heading, a treatment heading and its price rows.")
    prices = {}
    for key, table, where in sections:
        expected = _expected_prices(table, where, problems)
        if key in prices:
            problems.append(f"{where}: duplicate crop/treatment section. "
                            "Remove the duplicate section.")
        else:
            prices[key] = expected
    return prices


def net_returns(rows: list[dict], price_file: str | Path) -> list[dict]:
    """Return copies of Summary rows with net_return ($/ha) at expected prices.

    Match the Price file's crop and treatment to CR and TRNO, including fallow.
    IDIS -1 omits a component; fixed, uniform, triangular and normal prices use
    their expected values. Price risk is not modelled. A used quantity of None
    makes net_return None; absent or invalid quantities are check problems.
    All file and row problems are raised together as DSSATCheckError. Results
    can be passed to summarize_seasons(..., variables=['net_return']).
    """
    problems = []
    prices = _read_prices(price_file, problems)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        problems.append("Summary rows: expected a list of dicts. Supply the rows from "
                        "result.summary() or combine_summaries().")
        rows = []
    out = []
    for number, row in enumerate(rows, 1):
        missing = [name for name in ("CR", "TRNO") if row.get(name) is None]
        if missing:
            problems.append(f"Summary row {number}: missing {' and '.join(missing)}. "
                            "Supply CR and TRNO from the Summary rows.")
            continue
        key = (row["CR"], row["TRNO"])
        if prices is None:
            continue
        try:
            if isinstance(key[0], bool) or isinstance(key[1], bool):
                raise TypeError("bool is not a crop code or treatment number")
            section = prices.get(key)
        except TypeError:
            problems.append(f"Summary row {number}: invalid CR/TRNO values {key!r}. "
                            "Supply a crop code and treatment number from the Summary rows.")
            continue
        if section is None:
            problems.append(f"Summary row {number}: no Price file section for crop "
                            f"{key[0]!r}, treatment {key[1]!r}; available sections: "
                            f"{list(prices)}. Add a section for this crop and TRNO.")
            continue
        total = 0.0
        has_missing = False
        for component, price in section.items():
            if price is None:
                continue
            quantity, divisor, sign = _TERMS[component]
            value = 1
            if quantity is not None:
                if quantity not in row:
                    problems.append(f"Summary row {number}: missing quantity column {quantity} "
                                    f"used by {component}. Supply this column from Summary.OUT.")
                    continue
                value = row[quantity]
                if value is None:
                    has_missing = True
                    continue
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value)):
                    problems.append(f"Summary row {number}: {quantity} value {value!r} is not a "
                                    "finite number. Supply a numeric Summary quantity or None.")
                    continue
            total += sign * price * value / divisor
        out.append(dict(row, net_return=None if has_missing else total))
    if problems:
        raise DSSATCheckError(problems)
    return out
