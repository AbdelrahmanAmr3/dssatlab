"""Read rotation components, check sequences and render DSSAT's batch file."""

from datetime import date, timedelta
from pathlib import Path
import re

from .controls import _controls_start_date, _selected_controls
from .filex import _filex_date, _section_row, _section_rows, _treatment_rows
from .filex_write import _columns
from .runner import _batch_text, _run_command, _run_mode


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
    collision_problems = []
    treatments = dict(_treatment_rows(text, collision_problems))
    # Keep a colliding normal row out of the selected sequence's components.
    sequence_rows = {line for line, (number, _) in treatments.items()
                     if collision_problems and number and int(number) == treatment
                     and line[:2].strip().isdigit() and int(line[:2]) == treatment}
    components, columns, in_section = [], {}, False
    for line in text.splitlines():
        if line.startswith("*"):
            in_section = line[1:].strip().split(" ")[0] == "TREATMENTS"
            columns = {}
        elif in_section and line.startswith("@"):
            columns = _columns(line)
        elif in_section and "N" in columns and line.strip() and not line.startswith("!"):
            if len(sequence_rows) > 1 and line not in sequence_rows:
                continue
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


def _sequence_stop(start, years):
    """Return CSM's stopping boundary, or None beyond Python's date range."""
    # DSSAT-CSM v4.8.6.0, CSM_Main/CSM.for, PROGRAM CSM: YRDOY_END.
    year = start.year + years
    if year <= date.max.year:
        return date(year, 1, 1) + timedelta(days=start.timetuple().tm_yday - 2)
    return None


def _sequence_shift(day, year):
    """Keep DSSAT's day of year when moving a scheduled date to another year."""
    return date(year, 1, 1) + timedelta(days=day.timetuple().tm_yday - 1)


def _sequence_end(source, treatment, start, stop, filex, template):
    """Follow scheduled components; an unknown end keeps the boundary check."""
    from .operations import _component_management
    from .rotation_data import _calendar_date, _known_dates, _rotation_keys

    try:
        text = Path(filex).read_text(encoding='latin-1') if filex is not None else None
        components = (_rotation_components(filex, treatment, text=text) if template is None else
                      [dict(R=str(i), SM=str(i), CR='FA' if c['crop'] == 'fallow' else '?')
                       for i, c in enumerate(template, 1)])
        if len(components) < 2 or any(not row['R'].isdigit() for row in components):
            return stop
        entries = source.get('treatments', {}) if isinstance(source, dict) else {}
        entry = next((value for key, value in entries.items()
                      if str(key).isascii() and str(key).isdigit() and int(key) == int(treatment)
                      and isinstance(value, dict)), {}) if isinstance(entries, dict) else {}
        edits, _ = _rotation_keys(entry.get('rotation', {}), components, '')
        known, _ = _known_dates(components, template, text, edits, '')
        first_ends = []
        for row, (_, planting, end, crop) in zip(components, known):
            code = _component_management(text, row, 'HARVS', 'R' if end else 'M')
            if (code not in ('R', 'W', 'X', 'Y', 'Z') or
                    crop != 'FA' and _component_management(text, row, 'PLANT', 'R') != 'R'):
                first_ends.append(None)  # Unknown until run time, if this component is reached.
                continue
            override = edits.get(int(row['R']), {})
            events = override.get('harvest') if isinstance(override, dict) else None
            if isinstance(events, list):
                first = next((_calendar_date(event.get('date')) for event in events
                              if isinstance(event, dict) and _calendar_date(event.get('date'))), None)
            elif text is not None and end is not None:
                harvests = _section_rows(text, 'HARVEST DETAILS', 'H', int(row['MH']), ('HDATE',))
                first = next((_filex_date(h['HDATE']) for h in harvests if _filex_date(h['HDATE'])), None)
            else:
                first = end
            first_ends.append(first)
        current, run = start, 0
        # CSM_Main/CSM.for, PROGRAM CSM tests YRDOY >= YRDOY_END only
        # AFTER DAY_LOOP/SEAS_LOOP: the crossing component finishes in full.
        # Management/MgmtOps.for (MGMTOPS), AUTPLT.for (AUTPLT), AUTHAR.for
        # (AUTHAR) move planting/fallow anchors and then the harvest schedule.
        while current <= stop:
            for (_, planting, end, crop), first in zip(known, first_ends):
                if end is None or first is None or crop != 'FA' and planting is None:
                    return stop
                shift = 0
                if crop != 'FA' or run:
                    anchor = first if crop == 'FA' else planting
                    moved = _sequence_shift(anchor, current.year)
                    if moved < current:
                        moved = _sequence_shift(anchor, current.year + 1)
                    shift = moved.year - anchor.year
                actual_end = _sequence_shift(end, end.year + shift) if first < current else end
                if actual_end < current:
                    return stop  # Invalid schedules are reported by the ordinary checks.
                if actual_end >= stop:
                    return actual_end
                current = actual_end + timedelta(days=1)
                run += 1
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        pass  # Unreadable dates/levels cannot establish a scheduled end.
    return stop


def _sequence_coverage(source, treatment, start, days, nyers=None, *, filex=None, template=None):
    """Require weather through the scheduled component that crosses NYERS."""
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
    stop = _sequence_stop(start, years)
    if stop is not None:
        last = _sequence_end(source, treatment, start, stop, filex, template)
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


def _run_sequence(filex, treatment, components, executable):
    """Run the sequence through the runner's batch file lifecycle."""
    rows = [(int(treatment), row["R"]) for row in components]
    mode = _run_mode(filex, treatment, rows)
    return _run_command(filex.parent, [mode, "DSSBatch.v48"], executable,
                        _batch_text(filex.name, mode, rows))


def _parse_sdate(sdate):
    """Parse a FileX SDATE (YYDDD) string into (yy, doy) integers, or None."""
    if isinstance(sdate, str) and re.fullmatch(r"[0-9]{5}", sdate):
        return int(sdate[:2]), int(sdate[2:])
    return None


def _simulation_start_date(sdate):
    """Read SDATE as a FileX date, or explain why it cannot be checked."""
    if sdate is None:
        return None, "START is not S or SDATE is unavailable; check the FileX start controls"
    parsed = _parse_sdate(sdate)
    if parsed is None:
        return None, f"SDATE {sdate!r} is not a DSSAT date (yyddd); correct SDATE"
    day = _filex_date(sdate)
    if day is None:
        year = _filex_date(sdate[:2] + "001").year
        return None, f"day {parsed[1]} does not exist in {year}; correct SDATE"
    return day, None


def _simulation_start(text, treatment, experiment_data) -> date | None:
    """Return the effective S/P start of the first component."""
    from .experiment import _check_date

    try:
        row = _section_row(text, "TREATMENTS", "N", int(treatment), ("SM",))
        general = _section_row(text, "SIMULATION CONTROLS", "N", int(row["SM"]),
                               ("GENERAL", "START", "SDATE"))
        if general["START"] == "S":
            return (_controls_start_date(experiment_data, treatment)
                    or _filex_date(general["SDATE"]))
        if general["START"] != "P":
            return None
        entries = experiment_data.get("treatments", {}) if isinstance(experiment_data, dict) else {}
        entry = next((v for k, v in entries.items() if str(k).isascii() and str(k).isdigit()
                      and int(k) == int(treatment) and isinstance(v, dict)), {}) if isinstance(entries, dict) else {}
        components = _rotation_components(None, treatment, text=text)
        if len(components) > 1:
            edits = entry.get("rotation", {})
            entry = next((v for k, v in edits.items() if str(k).isascii() and str(k).isdigit()
                          and int(k) == int(row["R"]) and isinstance(v, dict)), {}) if isinstance(edits, dict) else {}
        planting = entry.get("planting")
        if isinstance(planting, dict):
            value = planting.get("date")
            return None if _check_date(value, "date") else date.fromisoformat(value)
        details = _section_row(text, "PLANTING DETAILS", "P", int(row["MP"]), ("PDATE",))
        return _filex_date(details["PDATE"])
    except (ValueError, TypeError, KeyError):
        return None  # Ordinary FileX/experiment checks explain unreadable inputs.
