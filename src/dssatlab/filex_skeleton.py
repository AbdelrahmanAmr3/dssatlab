"""Write a fixed-width FileX from checked weather, soil and a FileX template."""

from datetime import date
from pathlib import Path
import shutil

from .controls import _controls_start_date
from .cultivar import _CROPS, _template_data_dir
from .errors import DSSATCheckError
from .filex_template import (_check_filex_template, _load_filex_template,
                             _template_treatment_fields, _template_treatment_names,
                             _template_crop_entry, _template_genotype_files)
from .filex_write import _columns, _planting_row, _PLANTING_HEADER, _write_management
from .initial_conditions import _HEADERS as _INITIAL_HEADERS
from .runner import _create_dated_folder
from .soil import _write_soil_profiles
from .template_checks import _parse_field_data
from .weather import _dssat_date, write_weather_file


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
    first = data["rotation"][0] if rotation else _template_crop_entry(data, sim.treatment)
    start = (_controls_start_date(experiment_data, sim.treatment)
             or date.fromisoformat(first["start_date"] if first["crop"] == "fallow"
                                   else first["planting"]["date"]))
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
        _write_rotation_controls(filex, experiment_data, start, data['rotation'])
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

    Each crop entry writes its own cultivar, planting and controls levels;
    a single crop uses level 1. Unused operations have level 0 (none).
    Start equals each entry's planting date, with default initial conditions (IC=0).
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
    first = data["crops"][0] if "crops" in data else _template_crop_entry(data, 1)
    crop = _CROPS[first["crop"]][0]
    day = date.fromisoformat(first["planting"]["date"])
    # Four station characters + YY + 01, then .<crop>X: exactly 8.3 characters.
    # One FileX per station/year/crop in a caller-owned simulation directory.
    weather = weather_rows[1] if isinstance(weather_rows, dict) else weather_rows
    stem = f"{weather[0]['station']}{day.year % 100:02d}01"
    text = _skeleton_text(data, weather_rows, soil_rows, stem)
    return f"{stem}.{crop}X", text


def _skeleton_text(data, weather_rows, soil_rows, stem):
    """Layout references: UFGA8201.MZX and KSAS8101.WHX in tests/fixtures/filex_template."""
    entries = data["crops"] if "crops" in data else [_template_crop_entry(data, 1)]
    crop = _CROPS[entries[0]["crop"]][0]
    names = _template_treatment_names(data)
    fields = _template_treatment_fields(data)
    numbers = data.get("treatment_crops", [1] * len(names))
    weather_rows = weather_rows if isinstance(weather_rows, dict) else {1: weather_rows}
    soil_rows = soil_rows if isinstance(soil_rows, dict) else {1: soil_rows}
    name, station = names[0], weather_rows[1][0]["station"]
    cultivars, planting, controls, harvest_rows = [], [], [], []
    harvest_levels = {}
    for number, entry in enumerate(entries, 1):
        entry_crop, model, _, _, symbi = _CROPS[entry["crop"]]
        day = _dssat_date(date.fromisoformat(entry["planting"]["date"]))
        cultivars.append(f"{number:2d} {entry_crop} {entry['cultivar']['code']} -99")
        planting.append(_planting_row(_columns(_PLANTING_HEADER), number, entry["planting"]))
        if "harvest_date" in entry:
            level = len(harvest_rows) + 1
            harvest_levels[number] = level
            harvest_day = _dssat_date(date.fromisoformat(entry["harvest_date"]))
            harvest_rows.append(f"{level:2d} {harvest_day} GS000   -99   -99   -99   -99 -99")
        entry_name = names[numbers.index(number)]
        controls.extend(_control_lines(number, 1, day, entry_name, model, symbi,
                                       number in harvest_levels))
    harvest = []
    if harvest_rows:
        harvest = ["*HARVEST DETAILS", "@H HDATE  HSTG  HCOM HSIZE   HPC  HBPC HNAME",
                   *harvest_rows, ""]
    lines = [
        f"*EXP.DETAILS: {stem}{crop} {name}", "",
        "*GENERAL", "@PEOPLE", " DSSATLab", "@ADDRESS", " -99", "@SITE",
        f" {station}", "",
        "*TREATMENTS                        -------------FACTOR LEVELS------------",
        "@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM",
        *(f"{number:2d} 1 0 0 {treatment_name:<25} "
          f"{numbers[number - 1]:2d} {fields[number - 1]:2d}  0  0 "
          f"{numbers[number - 1]:2d}  0  0  0  0  0  0 "
          f"{harvest_levels.get(numbers[number - 1], 0):2d} {numbers[number - 1]:2d}"
          for number, treatment_name in enumerate(names, 1)), "",
        "*CULTIVARS", "@C CR INGENO CNAME",
        *cultivars, "",
        *_field_lines(weather_rows, soil_rows, max(fields)),
        "*INITIAL CONDITIONS", *_INITIAL_HEADERS, "",
        "*PLANTING DETAILS", _PLANTING_HEADER, *planting, "",
        *harvest, "*SIMULATION CONTROLS",
        *controls,
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
