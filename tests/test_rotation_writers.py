"""Row-targeted edits of a four-component Sequence preserve shared levels."""

from functools import partial
from pathlib import Path

import pytest

from dssatlab.cultivar import _cultivar_text
from dssatlab.filex_write import _event_text, _planting_text, _repoint


FIXTURE = Path(__file__).parent / "fixtures" / "rotation_writers.SQX"
WRITERS = [
    pytest.param(_planting_text, dict(date="1978-11-16", population=8, method="S",
                 distribution="R", row_spacing=75, depth=4),
                 "PLANTING DETAILS", 46, 3, 1, id="planting"),
    pytest.param(partial(_event_text, section="fertilizer"),
                 [dict(date="1978-11-16", material="FE005", application="AP001",
                       depth=5, n=40)], "FERTILIZERS (INORGANIC)", 52, 3, 1,
                 id="fertilizer"),
    pytest.param(_event_text, [dict(date="1978-11-16", amount=25, method="IR001")],
                 "IRRIGATION AND WATER MANAGEMENT", 49, 2, 2, id="irrigation"),
    pytest.param(_cultivar_text, dict(crop="WH", code="IB1501"),
                 "CULTIVARS", 34, 4, 1, id="cultivar"),
]


@pytest.fixture(params=[b"\n", b"\r\n", b"\r"], ids=["lf", "crlf", "cr"])
def original(request):
    return b"\n".join(FIXTURE.read_bytes().splitlines()).replace(b"\n", request.param)


def section_lines(text, section):
    return text.split(b"*" + section.encode(), 1)[1].split(b"*", 1)[0].splitlines(keepends=True)


@pytest.mark.parametrize("writer,data,section,column,level,row_count", WRITERS)
@pytest.mark.parametrize("rotation", [3, None])
def test_adds_one_level_and_changes_only_selected_row(
        original, writer, data, section, column, level, row_count, rotation):
    text = original.decode("latin-1")
    options = {} if rotation is None else {"rotation": rotation}
    written = writer(text, 1, data, **options).encode("latin-1")
    selected = rotation or 1
    old_rows = section_lines(original, "TREATMENTS")
    new_rows = section_lines(written, "TREATMENTS")
    target = next(row for row in old_rows if row.startswith(f" 1 {selected} ".encode()))
    changed = target[:column] + f"{level:3d}".encode() + target[column + 3:]
    assert new_rows == [changed if row == target else row for row in old_rows]

    before = section_lines(original, section)
    after = section_lines(written, section)
    added = [row for row in after if row[:2].strip() == str(level).encode()]
    assert len(added) == row_count
    old_levels = {int(row[:2]) for row in before if row[:2].strip().isdigit()}
    new_levels = {int(row[:2]) for row in after if row[:2].strip().isdigit()}
    assert new_levels == old_levels | {level}
    if section.startswith("IRRIGATION"):
        headers = [row for row in after if row.startswith(b"@")]
        block = headers[-2] + added[0] + headers[-1] + added[1]
    else:
        block = b"".join(added)
    # Restoring only the new level and target cell recovers every original byte,
    # including the fertilizer level shared by components 1 and 3.
    assert written.replace(block, b"", 1).replace(changed, target, 1) == original
    assert text.encode("latin-1") == original
    assert writer(text, 1, data, rotation=None) == writer(text, 1, data)


@pytest.mark.parametrize("writer,data,section,column,level,row_count", WRITERS)
@pytest.mark.parametrize("treatment,rotation", [(1, 9), (2, 3)])
def test_missing_rotation_keeps_text(
        original, writer, data, section, column, level, row_count, treatment, rotation):
    text = original.decode("latin-1")
    with pytest.raises(ValueError, match=fr"treatment {treatment}.*R {rotation}"):
        writer(text, treatment, data, rotation=rotation)
    assert text.encode("latin-1") == original


@pytest.mark.parametrize("rotation", [3, 9])
def test_repoint_missing_pair_does_not_mutate_lines(original, rotation):
    lines = original.decode("latin-1").splitlines(keepends=True)
    # R 3 exists, but only for N 1: both columns must match.
    treatment = 2 if rotation == 3 else 1
    with pytest.raises(ValueError, match=fr"treatment {treatment}.*R {rotation}"):
        _repoint(lines, treatment, "MF", 3, rotation=rotation)
    assert "".join(lines).encode("latin-1") == original


@pytest.mark.parametrize("section,column", [("fertilizer", 52), ("irrigation", 49)])
def test_empty_events_repoint_only_component_to_zero(original, section, column):
    text = original.decode("latin-1")
    target = next(row for row in section_lines(original, "TREATMENTS")
                  if row.startswith(b" 1 3 "))
    expected = original.replace(target, target[:column] + b"  0" + target[column + 3:])
    assert _event_text(text, 1, [], section, rotation=3).encode("latin-1") == expected
