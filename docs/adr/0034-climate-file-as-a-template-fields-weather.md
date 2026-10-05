# 0034: A climate file as a FileX template field's weather

Status: accepted (2026-10-04). Extends 0032; reverses its "templates keep measured weather" limit (#300).

## Context

ADR 0032 let a copied FileX run on generated weather (WTHER W or S) from a climate file passed in
`weather=`. A FileX template still required weather data rows for every field, because the template
takes each field's station and coordinates from those rows. A user with only a station's `.CLI` file
could not write a FileX from scratch.

## Decision

Each template field's weather is either weather data rows or exactly one `.CLI` path. For a climate
file, the field's station is the `@ INSI` value (already checked equal to the filename's first four
characters) and its FIELDS coordinates are the INSI row's LAT, LONG and ELEV. The template still
writes WTHER M; the run treatment needs experiment data `controls.weather_source` W or S to use a
climate-file field, and W or S with a data-rows field is a problem. `run()` copies the climate file
unchanged beside the FileX and writes no weather file for that station. This applies to single-crop,
crop-entry and rotation templates; replicates above 1 still need a sequence (a rotation template).

## Alternatives considered

- Switch WTHER to W or S automatically when a field has only a climate file. Rejected: an automatic
  repair, and W versus S is the user's choice.
- A separate `climate=` parameter. Rejected for the same reason as in 0032.

## Consequences

- Daily-weather coverage checks do not apply to a climate-file field; date order checks still do.
- Fields sharing a station must share the same source, as weather rows already must.
