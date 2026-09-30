"""Observed data template, loader and checks (v0.8, ticket #94; ADR 0007)."""

import csv
from datetime import date
import math
from pathlib import Path
import re

from .errors import DSSATCheckError, DSSATError
from .outputs import _SUMMARY_DATES, _date_value


# Fixed numeric column names from tests/fixtures/output_files/{summary,
# plant_growth}/{maize,wheat}. Text Summary metadata is not a measurement.
# outputs.py reads headers dynamically; it defines the six Summary date names
# and adds RUNNO/TRNO to Plant growth rows from each run block.
_SUMMARY_COLUMNS = set("""
RUNNO TRNO R# O# P# WYEAR XLAT LONG ELEV SDAT PDAT EDAT ADAT MDAT HDAT HYEAR
DWAP CWAM HWAM HWAH BWAH PWAM HWUM H#AM H#UM HIAM LAIX EYLDH FCWAM FHWAM
HWAHF FBWAH FPWAM IR#M IRCM PRCM ETCM EPCM ESCM ROCM DRCM SWXM NI#M NICM
NFXM NUCM NLCM NIAM NMINC CNAM GNAM N2OEM PI#M PICM PUPC SPAM KI#M KICM
KUPC SKAM RECM ONTAM ONAM OPTAM OPAM OCTAM OCAM CO2EM CH4EM DMPPM DMPEM
DMPTM DMPIM YPPM YPEM YPTM YPIM DPNAM DPNUM YPNAM YPNUM NDCH TMAXA TMINA
SRADA DAYLA CO2A PRCP ETCP ESCP EPCP CRST
""".split())
_PLANT_COLUMNS = set("""
RUNNO TRNO YEAR DOY DAS DAP L#SD GSTD LAID LWAD SWAD GWAD RWAD VWAD CWAD G#AD GWGD HIAD
PWAD P#AD WSPD WSGD NSTD EWSD PST1A PST2A KSTD LN%D SH%D HIPD PWDD PWTD SLAD
CHTD CWID RDPD RL1D RL2D RL3D RL4D RL5D RL6D RL7D RL8D RL9D CDAD LDAD SDAD
SNW0C SNW1C DTTD TMEAN TKILL PARID PARUD AWAD SAID CAID TWAD SDWAD HWAD
CHWAD EWAD RSWAD SNWPD SNWLD SNWSD RS%D H#AD HWUD T#AD PTFD SWXD WAVRD
WUPRD WFTD WFPD WFGD NFTD NFPD NFGD NUPRD TFPD TFGD VRNFD DYLFD
""".split())
_KEYS = {"scenario", "treatment", "date"}
_TEMPLATE = """# DSSATLab observed data template
# One row per scenario+treatment for Summary; one per scenario+treatment+date
# for Plant growth. Combine measurements for the same key in one row.
# scenario is "base" for a single Simulation run, or the scenario name.
# Leave date empty for an end-of-season Summary value (HWAM, ADAT, MDAT, CWAM...).
# Fill date as yyyy-mm-dd for a Plant growth value on that day (LAID, CWAD...).
# Use DSSAT's own column names and units; no conversion is performed.
# Dates in ADAT/MDAT and SDAT/PDAT/EDAT/HDAT may also be written yyyy-mm-dd.
# Add measurement columns as needed; leave unmeasured cells empty.
# -99 is a missing measurement and fails the checks. Replace example values.
scenario,treatment,date,HWAM,ADAT,MDAT,CWAM,LAID,CWAD
base,1,,6000,2021-07-01,2021-09-01,12000,,
base,1,2021-06-01,,,,,2.5,3000
"""


def write_observed_template(path: str | Path) -> None:
    """Write a commented measurement CSV with example rows (ticket #94).

    Refuse an existing destination with DSSATError, as other template writers do.
    """
    path = Path(path)
    message = f"Observed template path {path} already exists. Choose another path."
    if path.exists():
        raise DSSATError(message)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_TEMPLATE)
    except FileExistsError as error:
        raise DSSATError(message) from error


def load_observed(source) -> list[dict]:
    """Load and check a CSV path or pandas DataFrame (ticket #94).

    Return plain dicts with scenario strings, integer treatments, date=None
    for Summary or YYYYDDD integers for Plant growth, numeric measurements,
    and YYYYDDD integers for Summary date measurements. Blank measurements
    are omitted; explicit -99 is a check problem, never a measured number.
    DataFrame nulls count as blanks. Inputs are not modified. All readable
    problems raise one DSSATCheckError, with no partial results returned.
    pandas is imported only when passed a DataFrame.
    """
    problems, rows, columns = [], [], []
    try:
        if isinstance(source, (str, Path)):
            with Path(source).open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader((line for line in stream
                                     if not line.startswith("#")), strict=True)
                columns = next(reader, [])
                for number, values in enumerate(reader, 1):
                    if not values:
                        continue
                    if len(values) != len(columns):
                        problems.append(f"Observed data row {number}: {len(values)} values "
                                        f"for {len(columns)} columns. Supply one cell per column.")
                    rows.append(dict(zip(columns, values)))
        elif any(cls.__name__ == "DataFrame" and cls.__module__.split(".")[0] == "pandas"
                 for cls in type(source).__mro__):
            import pandas as pd

            if not isinstance(source, pd.DataFrame):
                raise ValueError("expected a pandas DataFrame")
            columns = list(source.columns)
            rows = source.astype(object).where(source.notna(), None).to_dict("records")
        else:
            raise ValueError("expected a CSV path or pandas DataFrame")
    except (OSError, UnicodeError, csv.Error, TypeError, ValueError) as error:
        problems.append(f"Cannot read observed data: {error}. "
                        "Supply a readable UTF-8 CSV path or pandas DataFrame.")
    for name in ("scenario", "treatment"):
        if name not in columns:
            problems.append(f"Observed data: missing {name!r} column. Add it to the table.")
    for name in dict.fromkeys(columns):
        if columns.count(name) > 1:
            problems.append(f"Observed data: repeated column {name!r}. Keep one column per name.")
        if name not in _KEYS | _SUMMARY_COLUMNS | _PLANT_COLUMNS:
            problems.append(_unknown(name, "header", _SUMMARY_COLUMNS | _PLANT_COLUMNS))
    parsed, found = _check_rows(rows)
    if problems or found:
        raise DSSATCheckError(problems + found)
    return parsed


def check_observed(observed: list[dict]) -> None:
    """Check plain observed rows without mutation; raise all problems (ticket #94).

    Accept the normalized rows from load_observed, or dicts with CSV cell values.
    Return None on success; raise one DSSATCheckError on failure. Dates accept
    strict yyyy-mm-dd strings or valid YYYYDDD codes, including leap-day checks.
    Unknown names list valid Summary or Plant growth columns for that row.
    """
    _, problems = _check_rows(observed)
    if problems:
        raise DSSATCheckError(problems)


def _blank(value):
    return value is None or isinstance(value, str) and not value.strip()


def _observed_date(value):
    text = str(value)
    # A numeric date column with blanks can become floats in a DataFrame/CSV.
    if re.fullmatch(r"[0-9]{7}\.0+", text):
        text = text.split(".")[0]
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        day = date.fromisoformat(text)
    else:
        day = _date_value("observed date", text)
        if day is None:
            raise ValueError("missing date")
    return day.year * 1000 + day.timetuple().tm_yday


def _unknown(name, where, valid):
    return (f"Observed data {where}: unknown variable {name!r}. "
            f"Valid names: {', '.join(sorted(valid))}. Use DSSAT's exact names.")


def _check_rows(observed):
    parsed, problems, seen = [], [], {}
    if not isinstance(observed, list) or not observed:
        return [], ["Observed data needs a non-empty list of dicts. Supply measurement rows."]
    for number, row in enumerate(observed, 1):
        where = f"Observed data row {number}"
        if not isinstance(row, dict):
            problems.append(f"{where}: expected a dict. Supply named measurement columns.")
            continue
        result = {"date": None}
        scenario = row.get("scenario")
        if not isinstance(scenario, str) or not scenario.strip():
            problems.append(f"{where}: missing or invalid scenario. "
                            "Supply 'base' or a non-empty scenario name.")
        else:
            result["scenario"] = scenario
        treatment = row.get("treatment")
        try:
            if isinstance(treatment, bool) or not re.fullmatch(r"[0-9]+(?:\.0+)?", str(treatment)):
                raise ValueError
            result["treatment"] = int(str(treatment).split(".")[0])
            if result["treatment"] < 1:
                raise ValueError
        except (ValueError, OverflowError):
            result.pop("treatment", None)
            problems.append(f"{where}: missing or invalid treatment {treatment!r}. "
                            "Supply a positive integer treatment number.")
        daily = not _blank(row.get("date"))
        if daily:
            try:
                result["date"] = _observed_date(row["date"])
            except (TypeError, ValueError, OverflowError):
                result.pop("date")
                problems.append(f"{where}: bad date {row['date']!r}. "
                                "Use yyyy-mm-dd or a valid YYYYDDD date.")
        valid = _PLANT_COLUMNS if daily else _SUMMARY_COLUMNS
        for name, value in row.items():
            if name in _KEYS:
                continue
            # Mixed tables have blanks in columns belonging to the other output.
            if name not in valid and (not _blank(value) or
                                     name not in _SUMMARY_COLUMNS | _PLANT_COLUMNS):
                problems.append(_unknown(name, f"row {number} ({'Plant growth' if daily else 'Summary'})", valid))
            if _blank(value):
                continue
            try:
                numeric = float(value)
                if numeric == -99:
                    problems.append(f"{where}, {name!r}: -99 is a missing measurement. "
                                    "Supply a measured value or leave an unmeasured cell empty.")
                    continue
            except (TypeError, ValueError, OverflowError):
                numeric = None
            if name in _SUMMARY_DATES:
                try:
                    result[name] = _observed_date(value)
                except (TypeError, ValueError, OverflowError):
                    problems.append(f"{where}, {name!r}: bad date {value!r}. "
                                    "Use yyyy-mm-dd or a valid YYYYDDD date.")
            elif numeric is None or isinstance(value, bool) or not math.isfinite(numeric):
                problems.append(f"{where}, {name!r}: non-numeric value {value!r}. "
                                "Supply a finite number in DSSAT's units.")
            else:
                result[name] = numeric
        if not any(name not in _KEYS and not _blank(value) for name, value in row.items()):
            problems.append(f"{where}: no measurements. Supply at least one measured value.")
        if _KEYS.issubset(result):
            key = (result["scenario"], result["treatment"], result["date"])
            if key in seen:
                problems.append(f"{where}: duplicate scenario+treatment+date {key!r} "
                                f"from row {seen[key]}. Combine measurements in one row.")
            else:
                seen[key] = number
        parsed.append(result)
    return parsed, problems
