"""YAML management template writer and strict YAML loader."""

from pathlib import Path

from .errors import DSSATError


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


def write_management_template(path: str | Path) -> None:
    """Write a UTF-8 YAML management template with commented examples.

    Documents every planting, irrigation, and fertilizer field and its unit.
    Dates must be quoted ISO calendar strings ("YYYY-MM-DD").
    An existing destination raises DSSATError, preserving the user's data.

    Args:
        path: File destination path where the YAML management template will be created.

    Raises:
        DSSATError: If the destination path already exists.
    """
    path = Path(path)
    message = f"Management template path {path} already exists. Choose another path."
    if path.exists():
        raise DSSATError(message)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_MANAGEMENT_TEMPLATE_TEXT)
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
