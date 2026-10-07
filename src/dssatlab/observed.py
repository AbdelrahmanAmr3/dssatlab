"""Read, check and write templates for observed measurements (ADR 0007)."""

from datetime import date
from difflib import get_close_matches
import math
from pathlib import Path
import re

from .errors import DSSATCheckError, DSSATError
from .outputs import _SUMMARY_DATES
from .weather import _read_table


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
# Units from DSSAT DATA.CDE: HWAM/CWAM/CWAD: kg[dm]/ha; LAID: m2/m2.
# ADAT/MDAT: yyyy-mm-dd dates (also SDAT/PDAT/EDAT/HDAT).
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


def _load_observed(source, *, check_measurements=True):
    """Return checked rows and problems, retaining dates for matching/statistics.

    Only unreadable sources, empty tables and missing key headers stop early.
    Invalid cells are omitted so valid keys/measurements can still be matched.
    Evaluation defers measurement checks until it knows whether a row is excluded.
    """
    rows, columns, issues = _read_table(source, "Observed data", comments=True)
    problems = [message for _, message in issues]
    if any(kind == "source" for kind, _ in issues):
        raise DSSATCheckError(problems)
    if not rows:
        raise DSSATCheckError(problems + ["Cannot read observed data: no rows. Supply measurement rows."])
    if columns is None:
        columns = list(dict.fromkeys(name for _, row in rows if isinstance(row, dict) for name in row))
    missing = [f"Observed data: missing {name!r} column. Add it to the table."
               for name in ("scenario", "treatment") if name not in columns]
    if missing:
        raise DSSATCheckError(problems + missing)
    for name in dict.fromkeys(columns):
        if columns.count(name) > 1:
            problems.append(f"Observed data: repeated column {name!r}. Keep one column per name.")
        if check_measurements and name not in _KEYS | _SUMMARY_COLUMNS | _PLANT_COLUMNS:
            problems.append(_unknown(name))
    if not isinstance(source, (str, Path, list)):
        import pandas as pd

        rows = [(number, {name: None if pd.api.types.is_scalar(value) and pd.isna(value) else value
                          for name, value in row.items()}) for number, row in rows]
    parsed, found = _check_rows(rows, check_measurements=check_measurements)
    return parsed, problems + found


def _blank(value):
    return value is None or isinstance(value, str) and not value.strip()


def _observed_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Use yyyy-mm-dd")
    return date.fromisoformat(value)


def _unknown(name):
    closest = get_close_matches(str(name), sorted(_SUMMARY_COLUMNS | _PLANT_COLUMNS), n=5)
    return (f"Observed data: unknown variable {name!r}. Closest valid names: {', '.join(closest) or 'none'}. "
            f"Summary columns: {', '.join(sorted(_SUMMARY_COLUMNS))}. "
            f"Plant growth columns: {', '.join(sorted(_PLANT_COLUMNS))}. Use DSSAT's exact names.")


def _check_measurements(row, daily, where, problems):
    result = {}
    valid = _PLANT_COLUMNS if daily else _SUMMARY_COLUMNS
    for name, value in row.items():
        if name in _KEYS or name not in _SUMMARY_COLUMNS | _PLANT_COLUMNS or _blank(value):
            continue
        if name not in valid:
            output = "Plant growth" if daily else "Summary"
            problems.append(f"{where}: variable {name!r} is not a {output} column. "
                            f"Valid names: {', '.join(sorted(valid))}. Use the appropriate date row.")
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            numeric = None
        if numeric == -99:
            problems.append(f"{where}, {name!r}: -99 is a missing measurement. "
                            "Supply a measured value or leave an unmeasured cell empty.")
        elif name in _SUMMARY_DATES:
            try:
                result[name] = _observed_date(value)
            except ValueError:
                problems.append(f"{where}, {name!r}: bad date {value!r}. Use yyyy-mm-dd.")
        elif numeric is None or isinstance(value, bool) or not math.isfinite(numeric):
            problems.append(f"{where}, {name!r}: non-numeric value {value!r}. "
                            "Supply a finite number in DSSAT's units.")
        else:
            result[name] = numeric
    if not any(name not in _KEYS and not _blank(value) for name, value in row.items()):
        problems.append(f"{where}: no measurements. Supply at least one measured value.")
    return result


def _check_rows(rows, *, check_measurements=True):
    parsed, problems, seen = [], [], {}
    for number, row in rows:
        where = f"Observed data row {number}"
        if not isinstance(row, dict):
            problems.append(f"{where}: expected a dict. Supply named measurement columns.")
            continue
        result = {"date": None}
        scenario, treatment = row.get("scenario"), row.get("treatment")
        if isinstance(scenario, str) and scenario.strip():
            result["scenario"] = scenario
        else:
            problems.append(f"{where}: missing or invalid scenario. "
                            "Supply 'base' or a non-empty scenario name.")
        if (not isinstance(treatment, bool)
                and re.fullmatch(r"[0-9]+(?:\.0+)?", str(treatment))
                and float(treatment) > 0 and math.isfinite(float(treatment))):
            result["treatment"] = int(str(treatment).split(".")[0])
        else:
            problems.append(f"{where}: missing or invalid treatment {treatment!r}. "
                            "Supply a positive integer treatment number.")
        daily = not _blank(row.get("date"))
        if daily:
            try:
                result["date"] = _observed_date(row["date"])
            except ValueError:
                result.pop("date")
                problems.append(f"{where}: bad date {row['date']!r}. Use yyyy-mm-dd.")
        if check_measurements or not _KEYS.issubset(result):
            result.update(_check_measurements(row, daily, where, problems))
        else:
            result.update({name: value for name, value in row.items() if name not in _KEYS})
        if not _KEYS.issubset(result):
            continue
        key = (result["scenario"], result["treatment"], result["date"])
        if key in seen:
            problems.append(f"{where}: duplicate scenario+treatment+date {key!r} "
                            f"from row {seen[key]}. Combine measurements in one row.")
        else:
            seen[key] = number
            parsed.append(result)
    return parsed, problems
