"""Write a fixed-width FileX from checked weather, soil and a FileX template."""

from datetime import date
from pathlib import Path

from .errors import DSSATCheckError
from .filex_template import _CROPS, _check_filex_template, _load_filex_template
from .filex_write import _columns, _planting_row, _PLANTING_HEADER
from .initial_conditions import _HEADERS as _INITIAL_HEADERS
from .weather import _dssat_date


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
    crop, _, _ = _CROPS[data["crop"]]
    day = date.fromisoformat(data["planting"]["date"])
    # Four station characters + YY + 01, then .<crop>X: exactly 8.3 characters.
    # One FileX per station/year/crop in a caller-owned simulation directory.
    stem = f"{weather_rows[0]['station']}{day.year % 100:02d}01"
    path = Path(directory) / f"{stem}.{crop}X"
    text = _skeleton_text(data, weather_rows[0], soil_rows[-1], stem)
    path.write_bytes(text.encode("ascii"))
    return path


def _skeleton_text(data, weather, soil, stem):
    """Layout references: UFGA8201.MZX and KSAS8101.WHX in tests/fixtures/filex_template."""
    crop, model, _ = _CROPS[data["crop"]]
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
        " 1 OP              Y     Y     N     N     N     N     N     N     M",
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
