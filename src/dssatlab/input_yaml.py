"""Strict optional YAML loading for experiment data and named inputs."""

from pathlib import Path


def _load_management(source):
    """Return (loaded data, problems) from a YAML path or a passed-through dict."""
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
