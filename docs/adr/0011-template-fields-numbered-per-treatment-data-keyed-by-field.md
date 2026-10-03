# 0011: Template fields are numbered per treatment, and weather and soil are keyed by field

Status: accepted (2026-10-01)

## Context

ADR 0010 kept the FileX template to one field. A DSSAT shell user compares sites or soils in one
experiment: XBuild gives each treatment a field (FL), and each field names its own weather station
and soil profile. A plan probe on real DSSAT showed a template FileX with two fields, two weather
files and two profiles in one SOIL.SOL runs clean, all at once and one treatment at a time.

## Decision

The template takes an optional `treatment_fields` list beside `treatments`: one field number per
treatment, fields numbered 1..K without gaps. Absent, every treatment is on field 1. A template
Simulation and `run_treatments` take `weather=` and `soil=` as a dict keyed by field number, each
value what they accept today. Station, soil ID and coordinates still come from the checked data,
never the template (ADR 0006). Fields may share a station or soil ID only with equal data; each
station's weather file and each soil profile is written once.

## Alternatives considered

- Treatment entries as dicts `{name, field}`. Rejected: list items with two shapes.
- A `field` section in experiment data. Rejected: it would only work for templates, and a field is
  not a level dssatlab adds to a copy.
- New keywords `field_weather=` and `field_soil=`. Rejected: two names for the same input.
- Weather and soil paths inside the template. Rejected by ADR 0006.

## Consequences

- A copied FileX still takes one weather source and one soil source.
- A dict is not valid weather or soil data on its own, so the per-field form cannot be confused
  with a single source.
