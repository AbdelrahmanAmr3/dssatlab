"""Read DSSAT output files from a run directory using their fixed-width headers."""

from datetime import date, timedelta
from pathlib import Path
import re

from .errors import DSSATOutputError


_SUMMARY_DATES = {"SDAT", "PDAT", "EDAT", "ADAT", "MDAT", "HDAT"}
_SUMMARY_TEXT = {"CR", "MODEL", "EXNAME", "TNAM", "FNAM", "WSTA", "SOIL_ID"}


def _split_fixed_width(header: str, line: str) -> dict[str, str]:
    """Slice at header token ends; DSSAT dots fill left-aligned text headers.

    Both arguments exclude line endings. Keep header spacing intact: numeric
    fields end at their header's right edge, as do dot-padded text fields.
    Return stripped strings with header padding dots removed from the keys.
    """
    tokens = list(re.finditer(r"[^\s@]+", header))
    if not tokens:
        raise ValueError("header has no columns")
    width = tokens[-1].end()
    if len(line) < width or line[width:].strip():
        raise ValueError(f"row length does not match the header's {width}-character layout")
    values = {}
    start = 0
    for token in tokens:
        name = token.group().rstrip(".")
        if not name or name in values:
            raise ValueError("header has empty or duplicate column names")
        values[name] = line[start:token.end()].strip()
        start = token.end()
    return values


def _summary_value(name: str, value: str, text_columns: set[str]):
    if re.fullmatch(r"-99(?:\.0+)?", value):
        return None
    if name in text_columns:
        return value
    if name in _SUMMARY_DATES:
        if not re.fullmatch(r"\d{7}", value):
            raise ValueError(f"invalid YYYYDDD date in {name}: {value!r}")
        year, day = int(value[:4]), int(value[4:])
        try:
            result = date(year, 1, 1) + timedelta(days=day - 1)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"invalid YYYYDDD date in {name}: {value!r}") from exc
        if day < 1 or result.year != year:
            raise ValueError(f"invalid YYYYDDD date in {name}: {value!r}")
        return result
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"invalid numeric column {name}: {value!r}") from exc


def read_summary(run_dir: str | Path) -> list[dict]:
    """Return one Summary row per simulation from ``run_dir/Summary.OUT``.

    Keys retain DSSAT column names, without header padding dots. Numeric values
    become int or float, text stays text, and the six YYYYDDD date columns become
    datetime.date values. DSSAT's -99 missing values become None.

    Raises DSSATOutputError for a missing, empty or malformed output file;
    malformed rows never produce partial results.
    """
    path = Path(run_dir) / "Summary.OUT"
    checked = f"Checked {path} in the run directory for a Summary @ header and complete data rows."
    next_step = "Check the run directory and output file, or rerun DSSAT to produce a complete Summary.OUT."
    try:
        lines = path.read_text(encoding="latin-1").splitlines()
    except OSError as exc:
        raise DSSATOutputError(
            f"Summary.OUT is missing or unreadable ({exc}). {checked} {next_step}"
        ) from exc

    header_index = next((i for i, line in enumerate(lines) if line.startswith("@")), None)
    if header_index is None:
        raise DSSATOutputError(f"Summary header (@ line) not found. {checked} {next_step}")
    header = lines[header_index]
    names = [token.rstrip(".") for token in header[1:].split()]
    if (not {"RUNNO", "TRNO", "TNAM"}.issubset(names)
            or len(names) != len(set(names)) or "" in names):
        raise DSSATOutputError(
            f"Invalid Summary header: expected unique columns including RUNNO, TRNO and TNAM. "
            f"{checked} {next_step}"
        )
    text_columns = _SUMMARY_TEXT | {
        token.rstrip(".") for token in header[1:].split() if token.endswith(".")
    }
    rows = []
    for line_number, line in enumerate(lines[header_index + 1:], header_index + 2):
        if not line.strip() or line.lstrip().startswith(("!", "*")):
            continue
        try:
            values = _split_fixed_width(header, line)
            row = {name: _summary_value(name, value, text_columns)
                   for name, value in values.items()}
        except ValueError as exc:
            raise DSSATOutputError(
                f"Malformed Summary data row at line {line_number}: {exc}. {checked} {next_step}"
            ) from exc
        rows.append(row)
    if not rows:
        raise DSSATOutputError(f"Summary has no data rows. {checked} {next_step}")
    return rows
