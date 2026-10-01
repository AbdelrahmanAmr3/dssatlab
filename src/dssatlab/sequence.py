"""Read rotation components, check sequences and render DSSAT's batch file."""

from pathlib import Path

from .filex import _section_row
from .filex_write import _columns
from .runner import _run_command


def _rotation_components(source, treatment):
    """Read matching TREATMENTS rows in file order; unreadable inputs give []."""
    if isinstance(treatment, bool) or not isinstance(treatment, (int, str)):
        return []
    try:
        treatment = int(treatment)
        text = Path(source).read_text(encoding="latin-1")
    except (OSError, ValueError, TypeError):
        return []
    components, columns, in_section = [], {}, False
    for line in text.splitlines():
        if line.startswith("*"):
            in_section = line[1:].strip().split(" ")[0] == "TREATMENTS"
            columns = {}
        elif in_section and line.startswith("@"):
            columns = _columns(line)
        elif in_section and "N" in columns and line.strip() and not line.startswith("!"):
            row = {key: line[left:right].strip() for key, (left, right) in columns.items()}
            try:
                if int(row["N"]) != treatment:
                    continue
            except ValueError:
                continue
            component = {key: row.get(key, "?") for key in ("R", "FL", "SM", "CU")}
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
                        f"{' and '.join(fields)}; dssatlab writes one weather file and one soil "
                        "profile, so give every component the same field (FL).")
    try:
        general = _section_row(Path(source).read_text(encoding="latin-1"),
                               "SIMULATION CONTROLS", "N", int(components[0]["SM"]),
                               ("GENERAL",))
        nreps = general.get("NREPS", "1")
    except ValueError:
        nreps = "1"
    if nreps != "1":
        problems.append(f"FileX NREPS {nreps} for sequence treatment {treatment}: with measured "
                        "weather every replicate repeats the same rows. Set NREPS to 1.")
    span = f"{min(numbers)}-{max(numbers)}" if numbers else ", ".join(raw_numbers)
    crops = ", ".join(row["CR"] for row in components)
    report = (f"FileX: treatment {treatment} is a sequence of {len(components)} rotation "
              f"components (R {span}: {crops}); it runs in DSSAT's sequence mode.")
    return problems, [report]


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
