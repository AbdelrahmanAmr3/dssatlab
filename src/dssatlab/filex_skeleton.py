"""Write a fixed-width FileX from checked weather, soil and a FileX template."""

from datetime import date
from pathlib import Path
import shutil

from . import core
from .controls import _controls_start_date
from .errors import DSSATCheckError
from .experiment import _check_date
from .filex_template import _CROPS, _check_filex_template, _load_filex_template
from .filex_write import _columns, _identity_text, _planting_row, _PLANTING_HEADER, _write_management
from .initial_conditions import _HEADERS as _INITIAL_HEADERS
from .management import _check_management, _report_lines
from .runner import _create_dated_folder
from .soil import _parse_soil, write_soil_file
from .weather import _dssat_date, _parse_weather, write_weather_file


def _template_data_dir(executable):
    """Locate Genotype beside the executable, without connect()'s config write."""
    found = (core._discover(core._os_name()) if executable is None
             else core.find_dssat_path(Path(executable)))
    if found is None:
        raise DSSATCheckError(["FileX template: cannot find the DSSAT data directory. "
                               "Supply executable pointing to DSSAT beside its Genotype folder."])
    return found.parent


def _check_template_simulation(sim, experiment_data, load_problems):
    """Check template inputs and the loaded experiment data dict in memory."""
    weather, weather_problems = _parse_weather(sim.weather)
    soil, soil_problems = (_parse_soil(sim.soil) if sim.soil is not None else
                          ([], ["Soil data is required with a FileX template. Supply soil=..."]))
    data, template_problems = _load_filex_template(sim.filex_template)
    data_dir = None
    try:
        data_dir = _template_data_dir(sim.executable)
    except DSSATCheckError as error:
        template_problems.extend(error.problems)
    # Shape/value checks still run when executable discovery fails.
    if data is not None:
        template_problems.extend(_check_filex_template(data, data_dir))
    if (isinstance(sim.treatment, bool) or not isinstance(sim.treatment, (int, str))
            or not str(sim.treatment).isascii() or not str(sim.treatment).isdigit()
            or int(sim.treatment) != 1):
        template_problems.append("FileX template has only treatment 1. Supply treatment=1.")
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
        _, text = _render_filex(data, weather, soil)
    if cultivar_path is not None:
        for suffix in _CROPS[data["crop"]][3]:
            path = cultivar_path.with_suffix(f".{suffix}")
            if not path.is_file():
                template_problems.append(f"FileX template: missing genotype file {path}. "
                                         "Supply this file in the data directory's Genotype folder.")
    days = [row["date"] for row in weather if "date" in row]
    if start is not None and days and start not in days:
        template_problems.append(f"Simulation start date {start} is not covered by weather "
                                 f"data ({min(days)} to {max(days)}). Supply weather for that date.")
    problems = weather_problems + soil_problems + template_problems
    report = (_report_lines("Weather data", weather_problems)
              + _report_lines("Soil data", soil_problems)
              + _report_lines("FileX template", template_problems))
    if sim.management is not None:
        if load_problems:
            problems.extend(load_problems)
            report.extend(_report_lines("Management data", load_problems))
        else:
            found, lines = _check_management(
                experiment_data, None, sim.treatment, weather, start,
                max(row["slb"] for row in soil) if not soil_problems else None,
                text=text, cultivar_path=cultivar_path)
            problems.extend(found)
            report.extend(lines)
            if not problems and any(int(k) == 1 and v for k, v in experiment_data["treatments"].items()):
                try:
                    _identity_text(text, 1, sim.name, weather[0]["station"], soil[0]["soil_id"])
                except ValueError as error:
                    problems.append(f"FileX: {error}")
                    report.extend(_report_lines("FileX identity", [str(error)]))
    return problems, report


def _write_template_simulation(sim, experiment_data):
    """Write checked template inputs and experiment data dict; return the FileX path."""
    data_dir = _template_data_dir(sim.executable)
    data, _ = _load_filex_template(sim.filex_template)
    weather, _ = _parse_weather(sim.weather)
    soil, _ = _parse_soil(sim.soil)
    parent = (Path(sim.filex_template).resolve().parent
              if isinstance(sim.filex_template, (str, Path)) else Path.cwd())
    folder = _create_dated_folder(parent, "dssat_sim_", "simulation folder")
    filex = write_filex(data, weather, soil, folder, data_dir=data_dir)
    start = _controls_start_date(experiment_data, sim.treatment) or date.fromisoformat(data["planting"]["date"])
    write_weather_file(weather, folder / f"{weather[0]['station']}{start.year % 100:02d}01.WTH")
    write_soil_file(soil, folder / "SOIL.SOL")
    _, _, prefix, extensions, _ = _CROPS[data["crop"]]
    for suffix in extensions:
        name = f"{prefix}.{suffix}"
        shutil.copy2(data_dir / "Genotype" / name, folder / name)
    _write_management(filex, sim.treatment, experiment_data, name=sim.name,
                      station=weather[0]["station"], soil_id=soil[0]["soil_id"])
    return filex


def write_filex(source, weather_rows: list[dict], soil_rows: list[dict],
                directory: str | Path, *, data_dir: str | Path) -> Path:
    """Check a FileX template and write one field and treatment; return its path.

    source is a template dict or YAML path. weather_rows and soil_rows must be
    nonempty checked rows from _parse_weather/_parse_soil, with no problems.
    data_dir is the DSSAT data directory containing Genotype. The destination
    directory must exist. Existing FileX contents are overwritten, like the
    weather and soil file writers. All template checks and rendering happen
    before opening the file; failures raise DSSATCheckError with all problems.

    Treatment 1 references required levels 1; unused operations have level 0
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
    crop = _CROPS[data["crop"]][0]
    day = date.fromisoformat(data["planting"]["date"])
    # Four station characters + YY + 01, then .<crop>X: exactly 8.3 characters.
    # One FileX per station/year/crop in a caller-owned simulation directory.
    stem = f"{weather_rows[0]['station']}{day.year % 100:02d}01"
    text = _skeleton_text(data, weather_rows[0], soil_rows[-1], stem)
    return f"{stem}.{crop}X", text


def _skeleton_text(data, weather, soil, stem):
    """Layout references: UFGA8201.MZX and KSAS8101.WHX in tests/fixtures/filex_template."""
    crop, model, _, _, symbi = _CROPS[data["crop"]]
    name, station = data["treatment_name"], weather["station"]
    day = _dssat_date(date.fromisoformat(data["planting"]["date"]))
    planting = _planting_row(_columns(_PLANTING_HEADER), 1, data["planting"])
    # SMODEL occupies eight characters starting at column 72, past its header.
    # ID_SOIL likewise occupies ten characters, starting at column 70.
    lines = [
        f"*EXP.DETAILS: {stem}{crop} {name}", "",
        "*GENERAL", "@PEOPLE", " DSSATLab", "@ADDRESS", " -99", "@SITE",
        f" {station}", "",
        "*TREATMENTS                        -------------FACTOR LEVELS------------",
        "@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM",
        f" 1 1 0 0 {name:<25}  1  1  0  0  1  0  0  0  0  0  0  0  1", "",
        "*CULTIVARS", "@C CR INGENO CNAME",
        f" 1 {crop} {data['cultivar']['code']} -99", "",
        "*FIELDS",
        "@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME",
        f" 1 {station}0001 {station:<8}   -99     0 DR000     0     0 00000 -99 "
        f"{soil['slb']:6.0f}  {soil['soil_id']:<10} -99",
        "@L ...........XCRD ...........YCRD .....ELEV .............AREA .SLEN .FLWR .SLAS FLHST FHDUR",
        f" 1{weather['longitude']:16.5f}{weather['latitude']:16.5f}"
        f"{weather['elevation']:10.1f}{'-99':>18}   -99   -99   -99   -99   -99", "",
        "*INITIAL CONDITIONS", *_INITIAL_HEADERS, "",
        "*PLANTING DETAILS", _PLANTING_HEADER, planting, "",
        "*SIMULATION CONTROLS",
        "@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL",
        f" 1 GE              1     1     S {day}  2150 {name:<25} {model}",
        "@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2",
        f" 1 OP              Y     Y     {symbi}     N     N     N     N     N     M",
        "@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL",
        " 1 ME              M     M     E     R     S     C     R     1     G     R     2",
        "@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS",
        " 1 MA              R     R     R     N     M",
        "@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT",
        " 1 OU              N     Y     Y     1     Y     N     Y     Y     N     N     Y     N     Y     A",
        "", "@  AUTOMATIC MANAGEMENT",
        "@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN",
        f" 1 PL          {day} {day}    40   100    30    40    10",
        "@N IRRIGATION  IMDEP ITHRL ITHRU IROFF IMETH IRAMT IREFF",
        " 1 IR             30    50   100 GS000 IR001    10     1",
        "@N NITROGEN    NMDEP NMTHR NAMNT NCODE NAOFF",
        " 1 NI             30    50    25 FE001 GS000",
        "@N RESIDUES    RIPCN RTIME RIDEP",
        " 1 RE            100     1    20",
        "@N HARVEST     HFRST HLAST HPCNP HPCNR",
        " 1 HA              0   -99   100     0", "",
    ]
    return "\n".join(lines)
