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
"""


_EXPERIMENT_SECTIONS_TEXT = """
    # Cultivar and initial_conditions currently have shape checks only; they are not yet
    # applied to the FileX. Omit a section to keep the FileX's own level.
    cultivar:
      code: "IB0035"             # Required existing DSSAT cultivar code from the .CUL file

    initial_conditions:
      date: "1982-02-25"          # Required initial-conditions date (quoted "YYYY-MM-DD")
      previous_crop: "MZ"         # Optional previous crop, DSSAT crop code
      residue_mass: 0.0           # Optional surface residue mass, kg/ha
      layers:                    # Required list of layers; all four fields required per layer
        - depth: 15.0            # Bottom of layer, cm; list layers in ascending depth
          water: 0.2             # Volumetric soil water, cm3/cm3
          nh4: 0.5               # Soil ammonium, mg/kg
          no3: 2.0               # Soil nitrate, mg/kg

    # Controls are checked and applied to a new level in a copy of the FileX.
    # Omitted fields keep their base values; omit controls to keep the FileX level.
    # start_date replaces SDATE in weather and management date checks; START stays unchanged.
    controls:                    # All fields optional; an empty dict keeps the FileX level
      start_date: "1982-02-25"    # Simulation start date (quoted "YYYY-MM-DD")
      water: "Y"                 # Water simulation: "Y" or "N" (strings, not booleans)
      nitrogen: "Y"              # Nitrogen simulation: "Y" or "N" (strings, not booleans)
      output_interval: 1          # Output interval (FROPT), positive integer days; must fit the FileX column
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

    Controls are checked and applied to a copy of FileX; cultivar and initial
    conditions have shape checks only. Dates are quoted ISO calendar strings.
    With filex, use its treatment numbers in file order, keeping example values.
    Without filex, write one example treatment numbered 1. No PyYAML is needed.
    Raise DSSATError if the destination exists or FileX treatments cannot be read.
    """
    text = _MANAGEMENT_TEMPLATE_TEXT.replace(
        "# DSSATLab Management Template", "# DSSATLab Experiment Template", 1)
    text = text.replace(
        "# Management operations (planting, irrigation, fertilizer) by treatment number.",
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
            numbers = read_treatment_numbers(filex)
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
