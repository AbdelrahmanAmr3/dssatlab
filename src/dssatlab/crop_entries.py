"""Check numbered crop entries and the treatments that use them."""

from .experiment import _check_fields
from .filex_template import _check_template_crop, _CROP_ENTRY_BOUNDS
from .weather import _show_value


def _check_crop_entries(data, data_dir):
    """Return crop-form, entry and treatment_crops problems without rendering."""
    where, problems = "FileX template", []
    minimum, maximum = _CROP_ENTRY_BOUNDS
    forms = [key for key in ("crop", "rotation", "crops") if key in data]
    if len(forms) != 1:
        problems.append(f"{where}: supply exactly one of crop, rotation or crops "
                        f"(found {', '.join(forms) or 'none'}). "
                        "crops replaces top-level crop, cultivar, planting and harvest_date.")
    if "crops" in data:
        for key in ("cultivar", "planting", "harvest_date"):
            if key in data:
                problems.append(f"{where}, crops: cannot be mixed with top-level {key}. "
                                "Each crop entry has its own crop values. "
                                f"Move {key} into its crop entry.")
        if "rotation" in data:
            problems.append(f"{where}, crops: cannot be mixed with rotation; "
                            "rotations already take a crop per component. "
                            "Supply crops for different treatments or rotation for one sequence.")
        if "treatments" not in data:
            problems.append(f"{where}, crops: needs treatments. "
                            "Checked the top-level treatment names. "
                            "Supply treatments with one name per treatment.")
        if "treatment_crops" not in data:
            problems.append(f"{where}, crops: needs treatment_crops. "
                            "Checked the top-level crop entry numbers. "
                            "Supply treatment_crops with one crop entry number per treatment.")
        entries = data["crops"]
        if not isinstance(entries, list) or not minimum <= len(entries) <= maximum:
            problems.append(f"{where}, crops: found {_show_value(entries)}. "
                            f"Supply a list of {minimum} to {maximum} crop entries.")
        if isinstance(entries, list):
            for number, entry in enumerate(entries, 1):
                location = f"{where}, crops[{number}]"
                if not isinstance(entry, dict):
                    problems.append(f"{location}: expected a dict; found {_show_value(entry)}. "
                                    "Supply crop, cultivar, planting and optional harvest_date.")
                    continue
                problems.extend(_check_fields(entry, ("crop", "cultivar", "planting"),
                                              ("harvest_date",), location, "FileX"))
                problems.extend(p.replace(where, location, 1)
                                for p in _check_template_crop(entry, data_dir))
    if "treatment_crops" not in data:
        return problems
    if "crops" not in data:
        problems.append(f"{where}, treatment_crops: needs crops. "
                        "Checked the top-level crop form. "
                        "Supply crops with numbered crop entries, or remove treatment_crops.")
    if "treatments" not in data or "treatment_name" in data:
        problems.append(f"{where}, treatment_crops: needs treatments. "
                        "Checked the top-level treatment names. "
                        "Supply treatments instead of treatment_name.")
    numbers = data["treatment_crops"]
    treatments = data.get("treatments")
    if isinstance(treatments, list):
        count = len(treatments)
        if not isinstance(numbers, list) or len(numbers) != count:
            found = len(numbers) if isinstance(numbers, list) else _show_value(numbers)
            problems.append(f"{where}, treatment_crops: supply one crop entry number per "
                            f"treatment (found {found} for {count} treatments). "
                            "Set treatment_crops to a list with that many whole numbers.")
    elif not isinstance(numbers, list):
        problems.append(f"{where}, treatment_crops: found {_show_value(numbers)}. "
                        "Checked the crop entry numbers. Supply a list of whole numbers.")
    entries = data.get("crops")
    valid_entries = isinstance(entries, list) and minimum <= len(entries) <= maximum
    # Malformed crops must not hide independent whole-number problems. Entry
    # numbers cannot exceed 99 even when the actual entry count is unavailable.
    limit = len(entries) if valid_entries else maximum
    if isinstance(numbers, list):
        used = set()
        for number, value in enumerate(numbers, 1):
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= limit:
                problems.append(f"{where}, treatment_crops[{number}]: found {_show_value(value)}. "
                                f"Supply a whole number {minimum} to {limit}.")
            else:
                used.add(value)
    if valid_entries and isinstance(numbers, list):
        for number in range(1, len(entries) + 1):
            if number not in used:
                problems.append(f"{where}, treatment_crops: crop entry {number} is not used "
                                "by any treatment. Checked the treatment crop entry numbers. "
                                f"Number crop entries 1 to {len(entries)} and use each.")
    return problems
