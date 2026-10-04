"""Inherited I3 levels preserve FileX bytes when discovered or reused."""

import pytest

from dssatlab.filex_write import _inherited_level


@pytest.fixture(params=[
    ("ENVIRONMENT MODIFICATIONS", "ME", ("@E ODATE EDAY ENVNAME",), ("ENVNAME",)),
    ("SOIL ANALYSIS", "SA", ("@A SADAT", "@A SABL SASC"), ("SASC",)),
])
def section(request):
    return request.param


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("prefix,expected", [("  9", 10), (" 9 ", 10), (" 10", 11)])
def test_inherited_levels_are_discovered_without_rewriting_rows(section, newline, prefix, expected):
    name, column, headers, optional = section
    # The optional trailing column is absent in the inherited header.
    body = "\n".join(header.replace(" " + optional[0], "") + "\n" + prefix + "82055"
                     for header in headers)
    text = f"*TREATMENTS\n@N {column}\n 1  0\n*{name}\n! keep\n{body}\n\n*OTHER\n 99 untouched\n"
    lines = text.replace("\n", newline).splitlines(keepends=True)
    original = list(lines)

    blocks, level = _inherited_level(lines, 1, column, name, headers, optional_columns=optional)

    assert level == expected
    assert lines == original
    assert [block[1] for block in blocks] == [7 + 2 * index for index in range(len(headers))]


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_reuse_blanks_only_unreferenced_level_rows_without_shifting_indices(section, newline):
    name, column, headers, optional = section
    body = "\n".join(header + "\n  182055\n 1082055\n 9982055" for header in headers)
    text = f"*TREATMENTS\n@N {column}\n 1 99\n 2 10\n*{name}\n! keep\n{body}\n\n*OTHER\n  182055\n"
    lines = text.replace("\n", newline).splitlines(keepends=True)
    original = list(lines)

    blocks, level = _inherited_level(lines, 1, column, name, headers, optional_columns=optional)

    assert level == 1
    assert len(lines) == len(original)
    assert lines == ["" if index in (7, 11)[:len(headers)] else line
                     for index, line in enumerate(original)]
    assert [block[1] for block in blocks] == [10 + 4 * index for index in range(len(headers))]


def test_missing_section_starts_at_level_one_and_leaves_lines_untouched(section):
    name, column, headers, optional = section
    lines = f"*TREATMENTS\n@N {column}\n 1  0\n*OTHER\n 99 untouched\n".splitlines(keepends=True)
    original = list(lines)

    blocks, level = _inherited_level(lines, 1, column, name, headers, optional_columns=optional)

    assert level == 1
    assert lines == original
    assert [block[1] for block in blocks] == [None] * len(headers)
