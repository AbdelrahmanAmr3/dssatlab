"""Read DSSAT output files from a run directory using their fixed-width headers."""

from datetime import date, timedelta
from pathlib import Path
import re

from .errors import DSSATError, DSSATOutputError


_SUMMARY_DATES = {"SDAT", "PDAT", "EDAT", "ADAT", "MDAT", "HDAT"}
_SUMMARY_TEXT = {"CR", "MODEL", "EXNAME", "TNAM", "FNAM", "WSTA", "SOIL_ID"}


def to_dataframe(rows: list[dict]):
    """Build a pandas DataFrame in row key order, retaining dates and missing values.

    pandas is imported only when called. Install it with ``pip install pandas``
    if unavailable. An empty list produces an empty DataFrame.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise DSSATError(
            "Cannot create a DataFrame: could not import pandas. "
            "Install it with pip install pandas, then call to_dataframe(rows) again."
        ) from exc
    return pd.DataFrame(rows)


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
    return _numeric_value(name, value)


def _numeric_value(name: str, value: str):
    if re.fullmatch(r"-99(?:\.0+)?", value):
        return None
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


def read_plant_growth(run_dir: str | Path) -> list[dict]:
    """Return one Plant growth row per simulation day from ``PlantGro.OUT``.

    Each *RUN block supplies its own RUNNO, TREATMENT (TRNO), and column header.
    DSSAT column names and YEAR/DOY are retained; DATE is a datetime.date, or
    None if either date component is missing. Numeric -99 values become None.
    Raises DSSATOutputError for missing or malformed output, never returning
    partial rows from a damaged file.
    """
    path = Path(run_dir) / "PlantGro.OUT"
    checked = (f"Checked {path} in the run directory for *RUN and TREATMENT lines, "
               "an @YEAR header in each run block, and complete data rows.")
    next_step = "Check the run directory and output file, or rerun DSSAT to produce a complete PlantGro.OUT."
    try:
        lines = path.read_text(encoding="latin-1").splitlines()
    except OSError as exc:
        raise DSSATOutputError(
            f"PlantGro.OUT is missing or unreadable ({exc}). {checked} {next_step}"
        ) from exc

    starts = [i for i, line in enumerate(lines) if re.match(r"\*RUN\b", line)]
    if not starts:
        raise DSSATOutputError(
            f"Plant growth has no data rows in *RUN blocks; RUNNO not found. {checked} {next_step}"
        )
    rows = []
    for start, end in zip(starts, starts[1:] + [len(lines)]):
        line_number = start + 1
        try:
            run_match = re.match(r"\*RUN\s+(\d+)\b", lines[start])
            if run_match is None:
                raise ValueError("RUNNO not found in *RUN line")
            runno = int(run_match[1])
            header_index = next((i for i in range(start + 1, end)
                                 if lines[i].startswith("@")), None)
            if header_index is None:
                raise ValueError(f"@YEAR header not found in run block {runno}")
            treatment = next((match for line in lines[start + 1:header_index]
                              if (match := re.match(r"\s*TREATMENT\s+(\d+)\s*:", line))), None)
            if treatment is None:
                raise ValueError(f"TREATMENT number (TRNO) not found in run block {runno}")
            trno = int(treatment[1])
            header = lines[header_index]
            names = header[1:].split()
            if (not {"YEAR", "DOY"}.issubset(names) or len(names) != len(set(names))
                    or {"RUNNO", "TRNO", "DATE"}.intersection(names)):
                raise ValueError("invalid @YEAR header: expected unique DSSAT columns including YEAR and DOY")
            for line_number, line in enumerate(lines[header_index + 1:end], header_index + 2):
                if not line.strip() or line.lstrip().startswith("!"):
                    continue
                values = _split_fixed_width(header, line)
                row = {name: _numeric_value(name, value) for name, value in values.items()}
                year, day = row["YEAR"], row["DOY"]
                if year is None or day is None:
                    row["DATE"] = None
                else:
                    if type(year) is not int or type(day) is not int:
                        raise ValueError("DATE requires integer YEAR and DOY columns")
                    row["DATE"] = date(year, 1, 1) + timedelta(days=day - 1)
                    if day < 1 or row["DATE"].year != year:
                        raise ValueError(f"invalid DATE from YEAR {year} and DOY {day}")
                row.update(RUNNO=runno, TRNO=trno)
                rows.append(row)
        except (ValueError, OverflowError) as exc:
            raise DSSATOutputError(
                f"Malformed Plant growth header or data row at line {line_number} "
                f"in run block starting at line {start + 1}: {exc}. {checked} {next_step}"
            ) from exc
    if not rows:
        raise DSSATOutputError(f"Plant growth has no data rows. {checked} {next_step}")
    return rows
