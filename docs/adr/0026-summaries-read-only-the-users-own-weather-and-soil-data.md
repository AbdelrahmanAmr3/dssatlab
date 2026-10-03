# 0026: Weather and soil summaries read only the user's own data

Status: accepted (2026-10-03).

## Context

Users want to check their weather and soil data, and see what is in it, before they have a FileX
or a Simulation. The checks already exist but run only inside `Simulation.check()`. A Simulation
also accepts stock weather and soil files, copied unchanged (ADR 0024): a five-digit stock weather
date needs a century that only the FileX gives, and stock soil files are read only for their soil
profile IDs.

## Decision

`summarize_weather(source)` and `summarize_soil(source)` take the same sources as the weather and
soil templates (a CSV path, rows or a DataFrame). They run the same source checks as
`Simulation.check()`, raise one `DSSATCheckError` with every problem, and otherwise return a plain
dict. A stock `.WTH` or `.SOL` path is rejected with a message naming the template route.

## Alternatives considered

- Also summarise stock files. Rejected: it needs the FileX century rule (still being reworked) and a
  soil layer parser that does not exist; stock files are DSSAT's own and already used as-is.
- Separate `check_*` functions. Rejected: a summary is only meaningful for data that passes the
  checks, so one function per data kind does both.
- One `describe(path)` that detects the kind. Rejected: the templates are never guessed at.

## Consequences

- One small module (`summaries.py`); the templates, checks and writers do not change.
- Summaries of stock files can be added later without changing these two functions' sources.
