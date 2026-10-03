# 0009: Ten template crops, one model each; listing shows only template crops

Status: accepted (2026-09-30)

## Context

ADR 0006 allowed a FileX written from a fixed template for maize and wheat, adding a crop only
after a real DSSAT run proves it. Users of other common crops still had to find an existing FileX,
and could not see which cultivar codes their installed DSSAT has without opening a `.CUL` file.

## Decision

The FileX template supports ten crops: maize, wheat, rice, soybean, potato, sorghum, pearl millet,
barley, peanut and dry bean, each with one fixed model and its own list of genotype files (rice has
no `.ECO`). Legumes are written with N fixation on. Potato needs a planting material weight, a
sprout length and a harvest date, so the template gains those fields for every crop; only potato
requires them.

`list_crops()` lists the template crops whose genotype files are in the installed DSSAT, and
`list_cultivars(crop)` lists one template crop's cultivar codes and names. Both read only the
installed Genotype folder, never the network or the config.

## Alternatives considered

- List every crop the installed DSSAT has genotype files for. Rejected: most of them cannot be
  written by the template, so the list would not answer "what can I write as `crop:`".
- Leave potato out. Rejected: it is a common crop and needs only three fields and one section.
- Let the user choose the model per crop. Still deferred: each model needs its own proof.

## Consequences

- A new template crop is one table row plus a real-DSSAT run; a crop failing the run is removed.
- Harvest on a date is available to every template crop, not only potato.
