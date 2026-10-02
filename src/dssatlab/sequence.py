"""Read rotation components, check sequences and render DSSAT's batch file."""

from datetime import date, timedelta
from pathlib import Path
import re

from .controls import _selected_controls
from .filex import _section_row, _treatment_rows
from .filex_write import _columns
from .runner import _run_command


def _rotation_components(source, treatment, *, text=None):
    """Read matching TREATMENTS rows in file order; unreadable inputs give []."""
    if isinstance(treatment, bool) or not isinstance(treatment, (int, str)):
        return []
    try:
        treatment = int(treatment)
        if text is None:
            text = Path(source).read_text(encoding="latin-1")
    except (OSError, ValueError, TypeError):
        return []
    treatments = _treatment_rows(text)
    components, columns, in_section = [], {}, False
    for line in text.splitlines():
        if line.startswith("*"):
            in_section = line[1:].strip().split(" ")[0] == "TREATMENTS"
            columns = {}
        elif in_section and line.startswith("@"):
            columns = _columns(line)
        elif in_section and "N" in columns and line.strip() and not line.startswith("!"):
            row = {key: line[left:right].strip() for key, (left, right) in columns.items()}
            row["N"], row["R"] = treatments.get(line, ("", ""))
            try:
                if int(row["N"]) != treatment:
                    continue
            except ValueError:
                continue
            component = {key: row.get(key, "?") for key in ("R", "FL", "SM", "CU", "MP", "MH")}
            try:
                cultivar = _section_row(text, "CULTIVARS", "C", int(component["CU"]), ("CR",))
                component["CR"] = cultivar["CR"] or "?"
            except ValueError:
                component["CR"] = "?"
            components.append(component)
    return components


def _check_sequence(source, treatment, components):
    """Return sequence problems and an informational FileX report line."""
    if len(components) < 2:
        return [], []
    treatment = int(treatment)
    problems = []
    name = Path(source).name
    if len(name) != 12:
        problems.append("A sequence runs in DSSAT's sequence mode, which needs a FileX "
                        "filename of exactly 12 characters (8 plus the extension, like "
                        f"UFGA7804.SQX); {name!r} has {len(name)}. Rename the FileX.")
    raw_numbers = [row["R"] for row in components]
    try:
        numbers = [int(value) for value in raw_numbers]
    except ValueError:
        numbers = []
    if not numbers or min(numbers) <= 0 or len(set(numbers)) != len(numbers):
        problems.append(f"Treatment {treatment} has rotation components R "
                        f"{', '.join(raw_numbers)}: give each row of a sequence its own R number.")
    fields = list(dict.fromkeys(row["FL"] for row in components))
    if len(fields) > 1:
        problems.append(f"Treatment {treatment} is a sequence whose components use fields "
                        f"{', '.join(fields[:-1])} and {fields[-1]}; dssatlab writes one weather "
                        "file and one soil profile, so give every component the same field (FL).")
    try:
        general = _section_row(Path(source).read_text(encoding="latin-1"),
                               "SIMULATION CONTROLS", "N", int(components[0]["SM"]),
                               ("GENERAL",))
        nreps = general.get("NREPS", "1")
    except ValueError:
        nreps = "1"
    if nreps not in ("", "-99") and (not nreps.lstrip("-").isdigit() or int(nreps) != 1):
        problems.append(f"FileX NREPS {nreps} for sequence treatment {treatment}: with measured "
                        "weather every replicate repeats the same rows. Set NREPS to 1.")
    span = f"{min(numbers)}-{max(numbers)}" if numbers else ", ".join(raw_numbers)
    crops = ", ".join(row["CR"] for row in components)
    report = (f"FileX: treatment {treatment} is a sequence of {len(components)} rotation "
              f"components (R {span}: {crops}); it runs in DSSAT's sequence mode.")
    return problems, [report]


def _sequence_coverage(source, treatment, start, days, nyers=None):
    """Check the final day using DSSAT's fixed day-of-year end rule."""
    if start is None or not days:
        return []
    controls = _selected_controls(source, treatment)
    if "years" in controls:
        years, label = controls["years"], "Controls years"
        if type(years) is not int or not 1 <= years <= 99999:
            return []  # Ordinary controls checks report invalid values and column overflow.
    else:
        try:
            years = max(1, int(nyers))
        except (TypeError, ValueError):
            years = 1
        label = "FileX NYERS"
    year, day = start.year + years, start.timetuple().tm_yday
    end = max(days)
    # Subtract one day after locating the start's day of year in the target year.
    last = f"day {day - 1} of {year}" if day > 1 else f"{year - 1}-12-31"
    if year <= date.max.year:
        last = date(year, 1, 1) + timedelta(days=day - 2)
        if last <= end:
            return []
    return [f"{label} {years}: the sequence runs from {start} through {last}, "
            f"after the weather data ends ({end}). "
            f"Supply weather through {last}, or fewer years."]


def _sequence_experiment_data(source, treatment, components):
    """Report unsupported sequence edits once; omit them from ordinary checks."""
    if len(components) < 2 or not isinstance(source, dict):
        return [], source
    treatments = source.get("treatments")
    if not isinstance(treatments, dict):
        return [], source
    checked, problems = dict(treatments), []
    for key, entry in treatments.items():
        if (isinstance(key, bool) or not isinstance(key, (int, str)) or
                not re.fullmatch(r"[0-9]+", str(key)) or int(key) != int(treatment)):
            continue
        if not isinstance(entry, dict):
            continue  # Ordinary experiment checks report malformed entries.
        controls = entry.get("controls", {})
        if entry.keys() - {"controls", "rotation"} or (
                isinstance(controls, dict) and controls.keys() - {"years", "start_date"}):
            if not problems:
                problems.append(f"Treatment {int(treatment)} is a sequence of {len(components)} "
                                "rotation components; experiment data for a sequence takes only "
                                "controls years, start_date and rotation. Edit the components in the FileX "
                                "for other changes.")
            checked[key] = {}
    return problems, dict(source, treatments=checked)


def _batch_text(filex_name, treatment, components):
    """Render the fixed columns accepted by DSSAT's sequence mode."""
    header = "@FILEX                                                                                        TRTNO     RP     SQ     OP     CO"
    lines = ["$BATCH(SEQUENCE)", "", header]
    lines.extend(f"{filex_name:<92}{int(treatment):7d}{1:7d}{int(row['R']):7d}{0:7d}{0:7d}"
                 for row in components)
    return "\r\n".join(lines) + "\r\n"


def _run_sequence(filex, treatment, components, executable):
    """Write the batch file before the runner snapshots the simulation folder."""
    (filex.parent / "DSSBatch.v48").write_bytes(
        _batch_text(filex.name, treatment, components).encode("latin-1"))
    return _run_command(filex.parent, ["Q", "DSSBatch.v48"], executable)


def _parse_sdate(sdate):
    """Parse a FileX SDATE (YYDDD) string into (yy, doy) integers, or None."""
    if isinstance(sdate, str) and re.fullmatch(r"[0-9]{5}", sdate):
        return int(sdate[:2]), int(sdate[2:])
    return None


def _simulation_start_date(sdate, days):
    """Resolve SDATE using weather years, or return the reason it cannot be checked."""
    if sdate is None:
        return None, "START is not S or SDATE is unavailable; check the FileX start controls"
    parsed = _parse_sdate(sdate)
    if parsed is None:
        return None, f"SDATE {sdate!r} is not a DSSAT date (yyddd); correct SDATE"
    if not days:
        return None, "weather unreadable"
    yy, doy = parsed
    years = [y for y in range(min(d.year for d in days), max(d.year for d in days) + 1) if y % 100 == yy]
    if not years:
        return None, f"no weather year matches SDATE year {yy:02d}; supply weather for the start year"
    if len(years) > 1:
        return None, f"ambiguous start year (candidate years: {', '.join(map(str, years))}); supply controls.start_date"
    year = years[0]
    if not 1 <= doy <= date(year, 12, 31).timetuple().tm_yday:
        return None, f"day {doy} does not exist in {year}; correct SDATE"
    return date(year, 1, 1) + timedelta(days=doy - 1), None
