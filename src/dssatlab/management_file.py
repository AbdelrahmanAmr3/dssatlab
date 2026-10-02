"""Management and experiment YAML templates and the strict optional YAML loader."""

from pathlib import Path

from .errors import DSSATError
from .filex import read_treatment_numbers


_MANAGEMENT_TEMPLATE_TEXT = """# DSSATLab Management Template
#
# Management operations (planting, irrigation, fertilizer) by treatment number.
# Every date MUST be quoted in ISO calendar format ("YYYY-MM-DD") to prevent YAML
# from parsing it as a date object, boolean, or number.
# To keep FileX levels unchanged for any section or treatment, omit that section.
# An empty list [] for irrigation or fertilizer means no events for that treatment.

treatments:
  1:
    # Planting details (optional section; omit to keep the FileX planting level)
    planting:
      # Required planting fields:
      date: "1982-02-26"          # Planting date (quoted "YYYY-MM-DD"); on or after simulation start date
      method: "S"                 # Planting method: single ASCII letter DSSAT code (e.g., S=seed, T=transplant)
      distribution: "R"           # Plant distribution: single ASCII letter DSSAT code (e.g., R=rows, H=hills, B=broadcast)
      population: 7.2             # Plant population at seeding, plants/m2 (must be > 0)
      row_spacing: 75.0           # Row spacing, cm (must be > 0)
      depth: 5.0                  # Planting depth, cm (must be >= 0)
      # Optional planting fields:
      emergence_date: "1982-03-05" # Emergence date (quoted "YYYY-MM-DD")
      emergence_population: 7.0   # Emergence population, plants/m2
      row_direction: 0.0          # Row direction, degrees from north
      planting_material_weight: 0.0 # Weight of planting material, kg/ha
      transplant_age: 0.0         # Transplant age, days
      transplant_environment: 0.0 # Transplant environment temperature, degrees C
      plants_per_hill: 1.0        # Plants per hill
      sprout_length: 0.0          # Sprout length, cm

    # Irrigation schedule (optional section; omit to keep the FileX level, or [] for none)
    # Each event uses exactly one of date or days_after_planting (DSSAT IDATE).
    # days_after_planting: integer >= 0, not a boolean; ascending and unique.
    # Use one timing kind per list: IRRIG D needs days; R/P/W need dates; A/F/N need [].
    # Set controls.irrigation_management for day events; rotation components use dates only.
    # Or use exactly efficiency and events: irrigation: {efficiency: 0.75, events: []}
    # efficiency: a number above 0 and at most 1, not a boolean (DSSAT EFIR).
    # events: the same event list as below; [] writes an EFIR level with no events.
    # List form writes EFIR 1; rotation components take dated events in list form only.
    # EFIR applies to the irrigation level's events; IREFF applies to automatic irrigation.
    irrigation:
      - date: "1982-03-15"        # Event date (quoted "YYYY-MM-DD"); must be ascending and unique
        amount: 30.0              # Water applied, mm (must be > 0)
        method: "IR001"           # Irrigation method: 2 ASCII letters + 3 digits (e.g., IR001)

    # Fertilizer schedule (optional section; omit to keep the FileX level, or [] for none)
    fertilizer:
      - date: "1982-03-20"        # Event date (quoted "YYYY-MM-DD"); must be ascending and unique
        material: "FE001"         # Fertilizer material: 2 ASCII letters + 3 digits (e.g., FE001)
        application: "AP001"      # Application method: 2 ASCII letters + 3 digits (e.g., AP001)
        depth: 5.0                # Application depth, cm (must be >= 0)
        n: 50.0                   # Elemental nitrogen applied, kg/ha (must be >= 0)
        # Optional fertilizer fields:
        p: 20.0                   # Elemental phosphorus applied, kg/ha (must be >= 0)
        k: 10.0                   # Elemental potassium applied, kg/ha (must be >= 0)

    # For a sequence, replace the sections above with this rotation example.
    # R1 maize planted 1978-03-15; R2 fallow ends 1978-11-14;
    # R3 wheat planted 1978-11-15; R4 fallow ends 1979-03-14.
    # Events after maturity cannot be checked; leave a margin before the crop ends.
    # rotation:
    #   1:
    #     fertilizer:
    #       - {date: "1978-03-15", material: FE005, application: AP001, depth: 5, n: 60}
    #     irrigation:
    #       - {date: "1978-05-01", amount: 25, method: IR001}
    #   3:
    #     cultivar: {crop: WH, code: IB1500}
    #     fertilizer:
    #       - {date: "1978-11-15", material: FE005, application: AP001, depth: 5, n: 40}
"""


_EXPERIMENT_SECTIONS_TEXT = """
    # Omit a section to keep the FileX's own level.
    # Cultivar adds a new CULTIVARS level in the copy and repoints this treatment.
    cultivar:
      crop: "MZ"                 # Required CR: two uppercase ASCII letters (e.g., MZ=maize)
      code: "IB0035"             # Required INGENO: six printable ASCII characters, no spaces; case-sensitive
      # Code must exist in the one crop-matching .CUL beside the FileX (e.g., MZCER048.CUL).
      # coefficients: {P1: 300}  # Optional: exact .CUL header names to numbers.
      # Writes a changed cultivar in the simulation folder's .CUL copy only.

    # Or replace the whole dict with initial_conditions: "off" (must be quoted).
    # "off" sets IC to 0 in the copy; DSSAT supplies initial soil water and nitrogen.
    initial_conditions:          # Checked and written as a new level in the FileX copy
      date: "1982-02-25"          # Required initial-conditions date (quoted "YYYY-MM-DD")
      previous_crop: "MZ"         # Optional two-letter DSSAT crop code; omitted writes -99
      residue_mass: 0.0           # Optional surface residue mass, kg/ha (>= 0); omitted writes -99
      # Optional surface details; omitted fields write -99. Numbers, not booleans.
      # root_mass: 0             # ICRT, kg/ha (>= 0)
      # nodule_mass: 0           # ICND, kg/ha (>= 0)
      # rhizobia_number: 1       # ICRN (0 to 1 inclusive)
      # rhizobia_effectiveness: 1 # ICRE (0 to 1 inclusive)
      # residue_n: 0             # ICREN, % (0 to 100 inclusive)
      # residue_p: 0             # ICREP, % (0 to 100 inclusive)
      # residue_incorporation: 0 # ICRIP, % (0 to 100 inclusive)
      # residue_depth: 0         # ICRID, cm (>= 0)
      layers:                    # Required non-empty list; all four fields required per layer
        - depth: 15.0            # Bottom of layer, cm (> 0); strictly ascending; within soil= depth
          water: 0.2             # Volumetric soil water, cm3/cm3 (0 to 1 inclusive)
          nh4: 0.5               # Soil ammonium, mg/kg (>= 0, no upper limit)
          no3: 2.0               # Soil nitrate, mg/kg (>= 0, no upper limit)

    # Controls are checked and applied to a new level in a copy of the FileX.
    # Omitted fields keep their base values; omit controls to keep the FileX level.
    # start_date replaces SDATE in weather and management date checks; START stays unchanged.
    controls:                    # All fields optional; an empty dict keeps the FileX level
      start_date: "1982-02-25"    # Simulation start date (quoted "YYYY-MM-DD")
      water: "Y"                 # Water simulation: "Y" or "N" (strings, not booleans)
      nitrogen: "Y"              # Nitrogen simulation: "Y" or "N" (strings, not booleans)
      output_interval: 1          # Output interval (FROPT), positive integer days; must fit the FileX column
      # years: 9                 # Number of seasons (DSSAT NYERS), positive integer
      # Simulation options: quoted, case-sensitive letter codes; soil_layers is an integer.
      # photosynthesis: "C"       # DSSAT PHOTO: "C", "R", "L", "V"
      # co2: "M"                  # DSSAT CO2: "M", "W", "D", "R"
      # symbiosis: "N"            # DSSAT SYMBI: "Y", "N", "U"
      # phosphorus: "N"           # DSSAT PHOSP: "Y", "N"
      # potassium: "N"            # DSSAT POTAS: "Y", "N"
      # tillage: "N"              # DSSAT TILL: "Y", "N"
      # evapotranspiration: "R"    # DSSAT EVAPO: "F", "R", "S", "T"
      # infiltration: "S"         # DSSAT INFIL: "R", "S", "N"
      # soil_organic_matter: "G"   # DSSAT MESOM: "G", "P"
      # soil_evaporation: "R"      # DSSAT MESEV: "R", "S"
      # soil_layers: 2            # DSSAT MESOL: 1, 2, 3 (not a string or boolean)
      # residue: "N"              # DSSAT RESID: "N", "R", "D"
      # Management codes are quoted, case-sensitive strings, not booleans or numbers.
      # irrigation_management: "R" # DSSAT IRRIG: "A", "N", "F", "R", "D", "P", "W"
      # planting_management: "R"   # DSSAT PLANT: "A", "F", "R"
      # Automatic irrigation numbers are finite, not booleans; omitted values stay unchanged.
      # auto_irrigation_depth: 30       # DSSAT IMDEP, cm: a number above 0
      # auto_irrigation_threshold: 50   # DSSAT ITHRL, %: a number from 0 to 100 inclusive
      # auto_irrigation_refill: 100     # DSSAT ITHRU, %: a number from 0 to 100 inclusive
      # auto_irrigation_method: "IR001" # DSSAT IMETH: two ASCII letters followed by three digits for the DSSAT code
      # auto_irrigation_amount: 10      # DSSAT IRAMT, mm: a number above 0
      # auto_irrigation_efficiency: 1   # DSSAT IREFF: a number above 0 and at most 1
      # EFIR applies to the irrigation level's events; IREFF applies to automatic irrigation.
      # Automatic planting: omitted values stay unchanged; numbers are finite, not booleans.
      # auto_planting_first: "1982-02-25" # DSSAT PFRST: a valid ISO calendar date as a quoted YYYY-MM-DD string
      # auto_planting_last: "1982-03-10"  # DSSAT PLAST: a valid ISO calendar date as a quoted YYYY-MM-DD string
      # auto_planting_soil_water_low: 40   # DSSAT PH2OL, %: a number from 0 to 100 inclusive
      # auto_planting_soil_water_high: 100 # DSSAT PH2OU, %: a number from 0 to 100 inclusive
      # auto_planting_soil_water_depth: 30 # DSSAT PH2OD, cm: a number above 0
      # auto_planting_max_temperature: 40 # DSSAT PSTMX, degrees C: a finite number
      # auto_planting_min_temperature: 10 # DSSAT PSTMN, degrees C: a finite number
      # With PLANT A/F, first <= last and first >= start_date; given dates need weather coverage.
"""


def write_management_template(path: str | Path, filex: str | Path | None = None) -> None:
    """Write a UTF-8 YAML management template with commented examples.

    Documents every planting, irrigation, and fertilizer field and its unit.
    Dates must be quoted ISO calendar strings ("YYYY-MM-DD").
    An existing destination raises DSSATError, preserving the user's data.

    Args:
        path: File destination path where the YAML management template will be created.
        filex: Optional FileX whose treatment numbers replace the example number.
            Only numbers are read; all example values stay unchanged.

    Raises:
        DSSATError: If the destination exists or FileX treatments cannot be read.
    """
    _write_template(path, _MANAGEMENT_TEMPLATE_TEXT, "Management", filex)


def write_experiment_template(path: str | Path, filex: str | Path | None = None) -> None:
    """Write commented YAML for management, cultivar, initial conditions and controls.

    Cultivar, initial conditions and controls are checked and applied to the FileX copy.
    EFIR applies to the irrigation level's events; controls auto_irrigation_efficiency
    (IREFF) applies to automatic irrigation.
    Dates are quoted ISO calendar strings; units and codes are DSSAT's.
    With filex, use its treatment numbers in file order, keeping example values.
    Without filex, write one example treatment numbered 1. No PyYAML is needed.
    Raise DSSATError if the destination exists or FileX treatments cannot be read.
    """
    title = "# DSSATLab Management Template"
    intro = "# Management operations (planting, irrigation, fertilizer) by treatment number."
    assert title in _MANAGEMENT_TEMPLATE_TEXT and intro in _MANAGEMENT_TEMPLATE_TEXT, (
        "management template wording changed; update write_experiment_template")
    text = _MANAGEMENT_TEMPLATE_TEXT.replace(title, "# DSSATLab Experiment Template", 1)
    text = text.replace(
        intro,
        "# Experiment data by treatment number: planting, irrigation, fertilizer,\n"
        "# cultivar, initial_conditions and controls.", 1)
    _write_template(path, text + _EXPERIMENT_SECTIONS_TEXT, "Experiment", filex)


def _write_template(path, text, label, filex):
    """Share exclusive creation and treatment-number pre-fill for both templates."""
    path = Path(path)
    message = f"{label} template path {path} already exists. Choose another path."
    if path.exists():
        raise DSSATError(message)
    if filex is not None:
        try:
            numbers = list(dict.fromkeys(read_treatment_numbers(filex)))
        except ValueError as error:
            raise DSSATError(str(error)) from error
        header, example = text.split("  1:\n", 1)
        text = header + "\n".join(f"  {number}:\n{example}" for number in numbers)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as error:
        raise DSSATError(message) from error


def _load_management(source):
    """Load management data from a YAML path or pass through a dict.

    Returns:
        tuple[Any, list[str]]: (loaded_dict_or_source, list_of_problems).
    """
    return _load_yaml(source, "Management", "a 'treatments' key")


def _load_yaml(source, label, mapping_hint):
    """Shared optional, strict YAML loading; dict inputs pass through unchanged."""
    if source is None:
        return None, []
    if isinstance(source, (str, Path)):
        path = Path(source)
        try:
            import yaml
        except ImportError:
            return None, [
                f"{label} file {path}: PyYAML is not installed. "
                f"Install PyYAML with 'pip install pyyaml' to load {label.lower()} YAML files."
            ]
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            return None, [
                f"{label} file {path}: cannot read file: {error}. "
                "Check that the path exists and is readable."
            ]
        except UnicodeDecodeError as error:
            return None, [
                f"{label} file {path}: cannot read file: {error}. "
                "Supply a UTF-8 encoded YAML file."
            ]

        class _StrictSafeLoader(yaml.SafeLoader):
            pass

        def _construct_mapping(loader, node, deep=False):
            loader.flatten_mapping(node)
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key {key!r}",
                        key_node.start_mark,
                    )
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        _StrictSafeLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            _construct_mapping,
        )

        try:
            data = yaml.load(text, Loader=_StrictSafeLoader)
        except yaml.constructor.ConstructorError as error:
            if "found duplicate key" in str(error):
                return None, [f"{label} file {path}: duplicate key: {error}"]
            return None, [f"{label} file {path}: invalid YAML: {error}"]
        except yaml.YAMLError as error:
            return None, [f"{label} file {path}: invalid YAML: {error}"]

        if not isinstance(data, dict):
            return None, [
                f"{label} file {path}: expected a YAML mapping document. "
                f"Supply a YAML mapping with {mapping_hint}."
            ]
        return data, []

    return source, []
