# 0031: Different crops in different treatments through numbered crop entries

Status: accepted (2026-10-04). Extends 0006, 0009, 0010 and 0011.

## Context

The FileX template writes one crop for every treatment (ADR 0010). DSSAT experiments such as the
course case DTCM6401 run dry bean, maize, soybean and wheat as different treatments of one FileX,
and a DSSAT Shell user builds them in XBuild with one cultivar and planting level per crop.

Measured on Windows DSSAT 4.8.5.017 while planning v0.20.1: DTCM6401.SNX copied as DTCM6401.MZX and
run in mode A gives the same crops and the same HWAM and MDAT in all 96 Summary rows as the
corresponding reference rows (the planning note's 76 was a counting error; see the proof below).
DSSAT takes each treatment's crop from the CULTIVARS `CR` column; the FileX extension
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

## Real-DSSAT proof

Ticket #287 / T4 PASS on 2026-10-04 with Windows DSSAT **4.8.5.017**
(`C:\DSSAT48\DSCSM048.EXE`, executable SHA256
`7b75b4df50f61733b04b70922c1c26dc048108cae9e934535b5af94ccd9cec60`).
The proof loads `wt287/src/dssatlab`, not the main checkout's package.
No T2/T3 mismatch was found and no package fix was needed.

A four-entry template (maize, soybean, wheat, dry bean) has five treatments;
treatments 1 and 2 share maize entry 1. Every treatment was run through
`run_treatments(filex_template=...)`, separately through `Simulation(treatment=k)`,
and through its own single-crop template. All 15 runs exited 0, produced exactly
one Summary row for NYERS=1, and matched exactly on HWAM, ADAT, MDAT and HDAT.
HWAM, ADAT and MDAT were present and nonmissing in the public parsed Summary
(`None` is the parsed missing marker). Each mixed-crop row retained its TRNO and
the expected CR/MODEL despite the common `PROO8201.MZX` filename.

HWAM is kg/ha; dates below are raw YYYYDDD. Each row gives the identical values
from all three runs for that treatment.

| Treatment | Crop / cultivar | CR / MODEL | HWAM | ADAT | MDAT | HDAT |
|---|---|---|---:|---:|---:|---:|
| 1 | Maize / IB0035 | MZ / MZCER048 | 597 | 1982120 | 1982176 | 1982176 |
| 2 | Maize / IB0035, fertilizer | MZ / MZCER048 | 7699 | 1982120 | 1982176 | 1982176 |
| 3 | Soybean / IB0001 | SB / CRGRO048 | 893 | 1982123 | 1982239 | 1982251 |
| 4 | Wheat / CI0001 | WH / CSCER048 | 539 | 1982129 | 1982159 | 1982213 |
| 5 | Dry bean / IB0001 | BN / CRGRO048 | 605 | 1982159 | 1982190 | 1982199 |

Inputs: synthetic daily weather for 1982-01-01 through 1983-12-31, station PROO,
29.63/-82.37/40 m, SRAD 20 MJ/m2/day, TMAX 30 C, TMIN 20 C, RAIN 5 mm;
the unmodified `write_soil_template()` profile IBMZ910214, layers at 5/15/30 cm.
Planting method S, distribution R, spacing 75 cm and depth 5 cm for every entry;
maize plants on 1982-03-01 at 7.2 plants/m2, soybean on 1982-04-01 at 30,
wheat on 1982-03-01 at 200, and dry bean on 1982-05-01 at 30.
Only wheat has `harvest_date`, 1982-08-01 (HDAT 1982213).
Experiment data sets WATER=Y/NITRO=Y for every treatment; treatment 2 alone
adds FE001/AP001 on 1982-03-01, depth 5 cm, N 100 kg/ha (Summary NICM=100;
treatment 1 NICM=0). Soybean's selected controls retain SYMBI=Y and its Summary
NFXM=71 kg/ha in all three runs; dry bean NFXM=22 kg/ha.
All four crops' stock genotype files were copied. Installation inputs and the
executable were verified unchanged by SHA256 before and after the proof.

Two preliminary input trials are retained: WATER=N yielded missing nitrogen
totals and zero soybean fixation despite NITRO=Y; enabling WATER=Y exercised
nitrogen. Winter wheat IB0488 did not reach anthesis/maturity in constant warm
weather, so the final proof uses stock CI0001. No missing dates were accepted
and no proof assertion was skipped. These synthetic runs prove template
equivalence, not course L2 equivalence or agronomic calibration.

The plan probe was rerun in a fresh folder with the retained `DTCM6401.MZX`,
`DTCM6401.PRI`, `SBGRO048.CUL`, `SOIL.SOL` and `UFAC9925.WTH`, in mode A.
Its **96/96** rows equal the corresponding rows of the **160-row** reference
`.work/dssat_test/2026-05-23/DTCM6401/ref/DTCM6401.OSU`, keyed uniquely by
(TRNO, SDAT), on CR, MODEL, HWAM, ADAT, MDAT and HDAT. They also equal the
retained probe output. Controls levels 1-2 have NYERS=2, while levels 3-4 retain
NYERS=10: treatments 1/2/5/6/9/10/13/14 have two rows each and
3/4/7/8/11/12/15/16 have ten each, giving 8*2 + 8*10 = 96.
The remaining 64 reference rows are outside the shortened probe's seasons.
The earlier ADR/grill count of 76 does not describe the retained input or output.

Local script: `.work/wt287/.work/scripts/proof287.py` relative to the main
checkout, deliberately uncommitted. Successful evidence:
`.work/wt287/.work/proof287/20261004_104828_851054/results.json`.
The script retains API input dicts, soil CSV, generated FileXs and their hashes,
all DSSAT commands and console output, parsed and raw Summary numbers, and the
probe comparison counts and reference hash. Every invocation uses fresh folders.

Rerun from the main checkout in PowerShell:

```powershell
.venv/Scripts/python.exe -B -u .work/wt287/.work/scripts/proof287.py
```

That command also reruns and compares the probe; its underlying DSSAT invocation
is `C:\DSSAT48\DSCSM048.EXE A DTCM6401.MZX` in the new evidence folder's `probe`
directory, with stdin closed. The 15 API runs use mode C with the generated
bare FileX filename and selected treatment number.

GAPS F10 is representable for DTCM6401 through numbered crop entries. Full
course L2 remains blocked by **F11** (generated weather, replicates/NREPS and
economics from `.PRI`) and rejected **TMAX 99.9** weather rows; this proof does
not claim an L2 course match.
