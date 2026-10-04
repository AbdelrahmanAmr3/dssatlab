# 0031: Different crops in different treatments through numbered crop entries

Status: accepted (2026-10-04). Extends 0006, 0009, 0010 and 0011.

## Context

The FileX template writes one crop for every treatment (ADR 0010). DSSAT experiments such as the
course case DTCM6401 run dry bean, maize, soybean and wheat as different treatments of one FileX,
and a DSSAT Shell user builds them in XBuild with one cultivar and planting level per crop.

Measured on Windows DSSAT 4.8.5.017 while planning v0.20.1: DTCM6401.SNX copied as DTCM6401.MZX and
run in mode A gives the same crops and the same HWAM and MDAT in all 76 Summary rows as the
reference. DSSAT takes each treatment's crop from the CULTIVARS `CR` column; the FileX extension
does not choose it.

## Decision

- The FileX template takes `crops`, a list of 1 to 99 crop entries, instead of the top-level
  `crop`, `cultivar`, `planting` and `harvest_date`. Each entry has those four keys with the
  single-crop checks. `treatment_crops` gives one entry number per treatment, values 1..K with
  every entry used, like `treatment_fields` (ADR 0011). `crops` needs `treatments` and cannot be
  combined with `rotation`.
- Entry k writes cultivar, planting and simulation controls level k, the controls with its crop's
  fixed model, legume N fixation and its own planting date as the start. Harvest levels are
  numbered in entry order among entries with a harvest date.
- The FileX is named after the first entry's planting year and crop. All entries' genotype files
  are checked and copied into the simulation folder.
- Experiment data is checked against the treatment's own crop: a cultivar edit must keep it, and
  planting and new-cultivar checks use its .CUL.

## Alternatives considered

- A dict per item of `treatments` with its own crop, cultivar and planting. Rejected: changes the
  type of `treatments` and repeats the crop block for every treatment of the same crop.
- One shared controls level with a blank SMODEL, as DTCM6401 does. Rejected: ADR 0009 writes the
  model per crop (the crop's CR and its SMODEL are separate choices), and the package
  writes SYMBI Y for legumes as its fixed default; DSSAT allows Y or N for legumes and forces N for others.
- A crop per treatment in experiment data. Rejected: experiment data varies a written FileX; it
  does not decide what the FileX holds (ADR 0010).

## Consequences

- DTCM6401 becomes representable but stays blocked in the course check by generated weather,
  replicates and its TMAX 99.9 rows (GAPS F11).
- Mixed crops inside a rotation stay out: each rotation component already has its own crop.
