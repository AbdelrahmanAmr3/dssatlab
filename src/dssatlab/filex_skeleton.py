"""Write a fixed-width FileX from checked weather, soil and a FileX template."""

from datetime import date
from pathlib import Path
import shutil

from .controls import _controls_start_date, _season_coverage
from .cultivar import _CROPS, _template_data_dir
from .errors import DSSATCheckError
from .experiment import _check_date
from .filex_template import (_check_filex_template, _load_filex_template,
                             _template_treatment_fields, _template_treatment_names,
                             _shared_field_problems, _template_genotype_files)
from .filex_write import _columns, _identity_text, _planting_row, _PLANTING_HEADER, _write_management
from .initial_conditions import _HEADERS as _INITIAL_HEADERS
from .management import _check_management, _report_lines
from .runner import _create_dated_folder
from .soil import _parse_soil, _write_soil_profiles
from .weather import _dssat_date, _parse_weather, write_weather_file


def _parse_field_data(source, count, kind):
    """Check field keys against fields 1..count (any keys if count is None) and parse each source."""
    label = f"{kind.capitalize()} data"
    parser = _parse_weather if kind == "weather" else _parse_soil
    if source is None and kind == "soil":
        problems = ["Soil data is required with a FileX template. Supply soil=..."]
        return {}, problems, _report_lines(label, problems)
    sources = source if isinstance(source, dict) else {1: source}
    normalized, invalid = {}, []
    for key, value in sources.items():
        if (type(key) is int or isinstance(key, str) and key.isascii() and key.isdigit()):
            number = int(key)
            if number not in normalized:
                normalized[number] = value
                continue
        invalid.append(repr(key))
    if invalid or count is not None and set(normalized) != set(range(1, count + 1)):
        count = count or max(normalized, default=1)
        keys = ", ".join([str(k) for k in sorted(normalized)] + invalid) or "none"
        example = ", ".join(f"{k}: ..." for k in range(1, count + 1))
        problems = [f"FileX template has fields 1 to {count}, but {kind} data has fields {keys}. "
                    f"Supply {kind} data for every field: {kind}={{{example}}}."]
        return {}, problems, _report_lines(label, problems)
    rows, problems, report = {}, [], []
    for number, value in sorted(normalized.items()):
        rows[number], found = parser(value)
        field_label = f"{label}, field {number}" if isinstance(source, dict) else label
        if isinstance(source, dict):
            found = [p.replace(label, field_label, 1) if p.startswith(label)
                     else f"{field_label}: {p}" for p in found]
        problems.extend(found)
        report.extend(_report_lines(field_label, found))
    return rows, problems, report


def _check_template_simulation(sim, experiment_data, load_problems):
    """Check template inputs and the loaded experiment data dict in memory."""
    data, template_problems = _load_filex_template(sim.filex_template)
    data_dir = None
    try:
        data_dir = _template_data_dir(sim.executable)
    except DSSATCheckError as error:
        template_problems.extend(error.problems)
    # Shape/value checks still run when executable discovery fails.
    if data is not None:
        template_problems.extend(_check_filex_template(data, data_dir))
    if isinstance(data, dict) and "rotation" in data:
        # Import only at dispatch: rotation uses the shared skeleton helpers.
        from .rotation import _check_rotation_simulation
        return _check_rotation_simulation(sim, data, data_dir, template_problems,
                                          experiment_data, load_problems)
    fields = _template_treatment_fields(data) if isinstance(data, dict) else [1]
    # Malformed field lists are reported by the template checks, never indexed,
    # and the field keys are then not compared with them (count None).
    count = max(fields) if not any("treatment_fields" in p for p in template_problems) else None
    if (not isinstance(fields, list) or not fields
            or any(type(k) is not int or not 1 <= k <= 99 for k in fields)):
        fields = [1]
    weather_fields, weather_problems, weather_report = _parse_field_data(sim.weather, count, "weather")
    soil_fields, soil_problems, soil_report = _parse_field_data(sim.soil, count, "soil")
    for rows, found, kind in ((weather_fields, weather_problems, "weather"),
                              (soil_fields, soil_problems, "soil")):
        if not found:
            template_problems.extend(_shared_field_problems(rows, kind))
    selected_field = fields[int(sim.treatment) - 1] if (
        str(sim.treatment).isascii() and str(sim.treatment).isdigit()
        and 1 <= int(sim.treatment) <= len(fields)) else 1
    weather, soil = weather_fields.get(selected_field, []), soil_fields.get(selected_field, [])
    count = len(_template_treatment_names(data))
    if (isinstance(sim.treatment, bool) or not isinstance(sim.treatment, (int, str))
            or not str(sim.treatment).isascii() or not str(sim.treatment).isdigit()
            or not 1 <= int(sim.treatment) <= count):
        if count == 1:
            template_problems.append("FileX template has only treatment 1. Supply treatment=1.")
        else:
            template_problems.append(f"FileX template has treatments 1 to {count}. "
                                     f"Supply treatment=<k> with 1 <= k <= {count}.")
    start = _controls_start_date(experiment_data, sim.treatment)
    if start is None and isinstance(data, dict) and isinstance(data.get("planting"), dict):
        planting_date = data["planting"].get("date")
        if not _check_date(planting_date, "planting date"):
            start = date.fromisoformat(planting_date)
    text, cultivar_path = None, None
    if isinstance(data, dict) and isinstance(data.get("crop"), str) and data["crop"] in _CROPS:
        if data_dir is not None:
            cultivar_path = data_dir / "Genotype" / f"{_CROPS[data['crop']][2]}.CUL"
    if not (weather_problems or soil_problems or template_problems):
        _, text = _render_filex(data, weather_fields, soil_fields)
    if cultivar_path is not None:
        for suffix in _CROPS[data["crop"]][3]:
            path = cultivar_path.with_suffix(f".{suffix}")
            if not path.is_file():
                template_problems.append(f"FileX template: missing genotype file {path}. "
                                         "Supply this file in the data directory's Genotype folder.")
    days = [row["date"] for row in weather if "date" in row]
    template_problems.extend(_season_coverage(experiment_data, sim.treatment, start, days))
    if start is not None and days and start not in days:
        template_problems.append(f"Simulation start date {start} is not covered by weather "
                                 f"data ({min(days)} to {max(days)}). Supply weather for that date.")
    if isinstance(data, dict) and "harvest_date" in data:
        harvest = data["harvest_date"]
        if not _check_date(harvest, "harvest_date") and days and date.fromisoformat(harvest) not in days:
            template_problems.append(f"FileX template, harvest_date: {harvest} is not covered by "
                                     f"weather data ({min(days)} to {max(days)}). "
                                     "Supply weather for that date.")
    problems = weather_problems + soil_problems + template_problems
    report = weather_report + soil_report + _report_lines("FileX template", template_problems)
    if sim.management is not None:
        if load_problems:
            problems.extend(load_problems)
            report.extend(_report_lines("Management data", load_problems))
        else:
            found, lines = _check_management(
                experiment_data, None, sim.treatment, weather, start,
                max(row["slb"] for row in soil) if soil and not soil_problems else None,
                text=text, cultivar_path=cultivar_path)
            problems.extend(found)
            report.extend(lines)
    if not problems and text is not None:
        selected = int(sim.treatment)
        has_override = (isinstance(experiment_data, dict)
                        and isinstance(experiment_data.get("treatments"), dict)
                        and any(int(k) == selected and v for k, v in experiment_data["treatments"].items()))
        if has_override or sim.name not in (None, "base"):
            try:
                _identity_text(text, selected, sim.name, weather[0]["station"], soil[0]["soil_id"])
            except ValueError as error:
                problems.append(f"FileX: {error}")
                report.extend(_report_lines("FileX identity", [str(error)]))
    return problems, report


def _write_template_simulation(sim, experiment_data):
    """Write checked template inputs and experiment data dict; return the FileX path."""
    data_dir = _template_data_dir(sim.executable)
    data, _ = _load_filex_template(sim.filex_template)
    rotation = "rotation" in data
    count = 1 if rotation else max(_template_treatment_fields(data))
    weather, _, _ = _parse_field_data(sim.weather, count, "weather")
    soil, _, _ = _parse_field_data(sim.soil, count, "soil")
    parent = (Path(sim.filex_template).resolve().parent
              if isinstance(sim.filex_template, (str, Path)) else Path.cwd())
    folder = _create_dated_folder(parent, "dssat_sim_", "simulation folder")
    filex = write_filex(data, weather, soil, folder, data_dir=data_dir)
    first = data["rotation"][0] if rotation else data
    start = (_controls_start_date(experiment_data, sim.treatment)
             or date.fromisoformat(first["planting"]["date"]))
    stations, profiles = {}, {}
    for rows in weather.values():
        stations.setdefault(rows[0]["station"], rows)
    for station, rows in stations.items():
        write_weather_file(rows, folder / f"{station}{start.year % 100:02d}01.WTH")
    for rows in soil.values():
        profiles.setdefault(rows[0]["soil_id"], rows)
    _write_soil_profiles(list(profiles.values()), folder / "SOIL.SOL")
    for path in _template_genotype_files(data, data_dir):
        shutil.copy2(path, folder / path.name)
    if rotation:
        from .rotation import _write_rotation_controls
        from .rotation_data import _write_rotation_data
        _write_rotation_controls(filex, experiment_data, start)
        _write_rotation_data(filex, sim.treatment, experiment_data)
        return filex
    if isinstance(experiment_data, dict) and isinstance(experiment_data.get("treatments"), dict):
        for key in sorted(experiment_data["treatments"], key=int):
            _write_management(filex, int(key), experiment_data)
    if sim.name not in (None, "base"):
        _write_management(filex, sim.treatment, None, name=sim.name)
    return filex


def write_filex(source, weather_rows: list[dict] | dict[int, list[dict]],
                soil_rows: list[dict] | dict[int, list[dict]],
                directory: str | Path, *, data_dir: str | Path) -> Path:
    """Check a FileX template and write its fields and treatments; return its path.

    source is a template dict or YAML path. weather_rows and soil_rows must be
    nonempty checked rows from _parse_weather/_parse_soil, with no problems:
    a list for field 1, or a dict keyed by every field number in the template.
    data_dir is the DSSAT data directory containing Genotype. The destination
    directory must exist. Existing FileX contents are overwritten, like the
    weather and soil file writers. All template checks and rendering happen
    before opening the file; failures raise DSSATCheckError with all problems.

    Each treatment references required levels 1; unused operations have level 0
    (none). Initial-condition headers allow the v0.6 writer to add a level.
    Start equals planting date, with DSSAT default initial conditions (IC=0).
    """
    data, problems = _load_filex_template(source)
    if not problems:
        problems = _check_filex_template(data, data_dir)
    if problems:
        raise DSSATCheckError(problems)
    filename, text = _render_filex(data, weather_rows, soil_rows)
    path = Path(directory) / filename
    path.write_bytes(text.encode("ascii"))
    return path


def _render_filex(data, weather_rows, soil_rows):
    """Return the filename and skeleton text from checked inputs without writing."""
    if "rotation" in data:
        # Import only at dispatch: rotation uses the shared skeleton helpers.
        from .rotation import _render_rotation
        return _render_rotation(data, weather_rows, soil_rows)
    crop = _CROPS[data["crop"]][0]
    day = date.fromisoformat(data["planting"]["date"])
    # Four station characters + YY + 01, then .<crop>X: exactly 8.3 characters.
    # One FileX per station/year/crop in a caller-owned simulation directory.
    weather = weather_rows[1] if isinstance(weather_rows, dict) else weather_rows
    stem = f"{weather[0]['station']}{day.year % 100:02d}01"
    text = _skeleton_text(data, weather_rows, soil_rows, stem)
    return f"{stem}.{crop}X", text


def _skeleton_text(data, weather_rows, soil_rows, stem):
    """Layout references: UFGA8201.MZX and KSAS8101.WHX in tests/fixtures/filex_template."""
    crop, model, _, _, symbi = _CROPS[data["crop"]]
    names = _template_treatment_names(data)
    fields = _template_treatment_fields(data)
    weather_rows = weather_rows if isinstance(weather_rows, dict) else {1: weather_rows}
    soil_rows = soil_rows if isinstance(soil_rows, dict) else {1: soil_rows}
    name, station = names[0], weather_rows[1][0]["station"]
    day = _dssat_date(date.fromisoformat(data["planting"]["date"]))
    planting = _planting_row(_columns(_PLANTING_HEADER), 1, data["planting"])
    harvest = []
    if "harvest_date" in data:
        harvest_day = _dssat_date(date.fromisoformat(data["harvest_date"]))
        harvest = ["*HARVEST DETAILS", "@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME",
                   f" 1 {harvest_day} GS000   -99   -99   -99   -99 -99", ""]
    lines = [
        f"*EXP.DETAILS: {stem}{crop} {name}", "",
        "*GENERAL", "@PEOPLE", " DSSATLab", "@ADDRESS", " -99", "@SITE",
        f" {station}", "",
        "*TREATMENTS                        -------------FACTOR LEVELS------------",
        "@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM",
        *(f"{number:2d} 1 0 0 {treatment_name:<25}  1 {fields[number - 1]:2d}  0  0  1  0  0  0  0  0  0  {int(bool(harvest))}  1"
          for number, treatment_name in enumerate(names, 1)), "",
        "*CULTIVARS", "@C CR INGENO CNAME",
        f" 1 {crop} {data['cultivar']['code']} -99", "",
        *_field_lines(weather_rows, soil_rows, max(fields)),
        "*INITIAL CONDITIONS", *_INITIAL_HEADERS, "",
        "*PLANTING DETAILS", _PLANTING_HEADER, planting, "",
        *harvest, "*SIMULATION CONTROLS",
        *_control_lines(1, 1, day, name, model, symbi, bool(harvest)),
    ]
    return "\n".join(lines)


def _field_lines(weather_rows, soil_rows, count):
    """Shared field and coordinate columns for single crops and sequences."""
    field_lines, coordinate_lines = [], []
    for number in range(1, count + 1):
        weather = weather_rows[number][0]
        soil = max(soil_rows[number], key=lambda row: row["slb"])
        field_station = weather["station"]
        field_lines.append(
            f"{number:2d} {field_station}{number:04d} {field_station:<8}   -99     0 DR000     0     0 00000 -99 "
            f"{soil['slb']:6.0f}  {soil['soil_id']:<10} -99")
        coordinate_lines.append(
            f"{number:2d}{weather['longitude']:16.5f}{weather['latitude']:16.5f}"
            f"{weather['elevation']:10.1f}{'-99':>18}   -99   -99   -99   -99   -99")
    return [
        "*FIELDS",
        "@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME",
        *field_lines,
        "@L ...........XCRD ...........YCRD .....ELEV .............AREA .SLEN .FLWR .SLAS FLHST FHDUR",
        *coordinate_lines, "",
    ]


def _control_lines(number, years, day, name, model, symbi, harvest):
    """One controls level, including DSSAT automatic-management defaults."""
    return [
        "@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL",
        f"{number:2d} GE          {years:5d}     1     S {day}  2150 {name:<25} {model}",
        "@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2",
        f"{number:2d} OP              Y     Y     {symbi}     N     N     N     N     N     M",
        "@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL",
        f"{number:2d} ME              M     M     E     R     S     C     R     1     G     R     2",
        "@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS",
        f"{number:2d} MA              R     R     R     N     {'R' if harvest else 'M'}",
        "@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT",
        f"{number:2d} OU              N     Y     Y     1     Y     N     Y     Y     N     N     Y     N     Y     A",
        "", "@  AUTOMATIC MANAGEMENT",
        "@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN",
        f"{number:2d} PL          {day} {day}    40   100    30    40    10",
        "@N IRRIGATION  IMDEP ITHRL ITHRU IROFF IMETH IRAMT IREFF",
        f"{number:2d} IR             30    50   100 GS000 IR001    10     1",
        "@N NITROGEN    NMDEP NMTHR NAMNT NCODE NAOFF",
        f"{number:2d} NI             30    50    25 FE001 GS000",
        "@N RESIDUES    RIPCN RTIME RIDEP",
        f"{number:2d} RE            100     1    20",
        "@N HARVEST     HFRST HLAST HPCNP HPCNR",
        f"{number:2d} HA              0   -99   100     0", "",
    ]
