# 0003: PyYAML is accepted for management files but never required

Status: accepted (2026-09-29)

## Context

Management (planting, irrigation, fertilizer) is a list of events of different kinds, each
with its own fields. The flat CSV template that fits weather (one row per day) and soil
(one row per layer) fits this badly. A YAML file is easy to read and edit and can carry
comments, so users prefer it for this data.

Python has no YAML parser in its standard library, and the package has zero runtime
dependencies (ADR 0002 made the same call for pandas). YAML also has quirks that clash with
strict checks: `no` parses as `False`, and a bare `2024-05-10` becomes a date object in
some parsers and a string in others.

## Decision

The plain Python dict is the real interface: `management=` takes a dict, and the checks run
on that dict, so they behave the same whatever the source. A path to a YAML file is accepted
as a convenience. PyYAML is imported only when the user passes a YAML path, and it is never
listed as a required dependency. If it is missing, the error says how to install it.

Loading is strict: the safe loader only, duplicate keys rejected, and dates must be quoted
ISO strings, so `no` and bare dates cannot slip through. A commented YAML template is
written by a `write_management_template(path)` function, like the weather and soil
templates.

## Alternatives considered

- TOML. Rejected: `tomllib` is in the standard library only from Python 3.11, and the
  package supports 3.10. Repeated events (`[[irrigation]]`) are also less pleasant to write.
- JSON. Rejected: no comments, which hurts hand-edited files.
- PyYAML as a required dependency. Rejected: it adds an install to every user, including
  those who only call `connect()` or `run()`.
- Supporting several file formats. Rejected: one file format is enough.

## Consequences

- Reading a YAML file must not import PyYAML unless the user passes a YAML path.
- Both input forms (dict and YAML path) need tests. A PyYAML-specific test may be skipped
  when PyYAML is absent.
- The docs site and README must say that YAML support needs `pip install pyyaml`.
- If PyYAML ever becomes required, or the file format changes, that is a new decision that
  supersedes this one.
