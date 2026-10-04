# 0030: New cultivars written under the user's own code

Status: accepted (2026-10-04). Builds on 0017.

## Context

Course FileXs point at cultivars the installed .CUL does not have (UFGA7801: IB1000-IB1010,
KADO7701: IB0098); DSSAT stops with 99 (IPVAR). ADR 0017 only changes an existing cultivar and
renames it DLnnnn, so a FileX's own missing code can never exist.

## Decision

- The cultivar section takes two more optional fields, `ecotype` and `name`. A `code` missing from
  the crop's .CUL together with `ecotype` and `coefficients` is a new cultivar.
- A new cultivar must give every coefficient column after `ECO#` of the .CUL's first `@VAR#` table,
  with no defaults. The ecotype must exist in the crop's .ECO when the crop has one.
- dssatlab writes one line in the layout of that table's first cultivar line (EXPNO `.`, name
  defaulting to the code) at the end of the table in the simulation folder's .CUL copy, under the
  user's code. The source .CUL, .ECO and .SPE never change.
- DL0001-DL9999 stay reserved for changed cultivars. One new code used twice in a run must be
  defined identically. Rotation components reject new cultivars, as they reject coefficients.

## Alternatives considered

- A user-supplied .CUL file. Rejected: another input file with its own checks, and the user edits
  fixed-width columns by hand.
- `based_on` an existing cultivar plus changes. Rejected: that is ADR 0017's changed cultivar.
- Defaults for omitted coefficients. Rejected: a silent guess at a physiological value.

## Real-DSSAT proof

All four proofs PASS on Windows DSSAT 4.8.5.017 (`C:\DSSAT48\DSCSM048.EXE`).
Local evidence: `.work/e2e29/FINDINGS.md` and `FINDINGS_after_fix.md` in the main checkout.
HWAM is kg/ha; ADAT and MDAT below are raw YYYYDDD.

| Proof | HWAM / ADAT / MDAT | Result |
|---|---|---|
| Maize template NC0001 with IB0035's ecotype and coefficients | Stock and new: 13601 / 1982120 / 1982176 | PASS, identical |
| Same maize definition, P1 increased from 259 to 279 | 13646 / 1982122 / 1982178 | PASS, different |
| Copied UFGA7801.SBX T1, IB1000 defined from stock BRAGG IB0001 / SB0701 | Stock exits 99 without a Summary row; new exits 0: 2806 / 1978210 / 1978280 | PASS after fix |
| Rice template NR0001 with IB0012's coefficients and IB0001 ecotype, no .ECO, name omitted | Stock and new: 7072 / 1982140 / 1982171 | PASS, identical |

Proof 3 first failed on a real FileX writer bug: I3 cultivar levels 1-11 were read through
the narrower header span, so the writer allocated a colliding level 2 and DSSAT selected
IB1001 instead of IB1000 (exit 99/IPVAR). The multi-digit level fix selects the free level 12;
public `check()` returns `[]` and `run()` now gives the result above. The regression also
covers replacing an old I3 row when reusing a free level past 99.

Maize/rice use synthetic daily weather for 1982-1983 (station PROO, 29.63/-82.37/40 m,
SRAD 20, TMAX 30, TMIN 20, RAIN 5), template soil layers at 5/15/30 cm, planting
1982-03-01 and WATER=N/NITRO=N. This proves cultivar writing, not agronomic calibration.
The soybean definition is an approximation of the unavailable course sensitivity values.
Source FileX, course and installation inputs stayed unchanged.

After integrating the fix, rerun from the main checkout in PowerShell (the proof
script requires that checkout's `src`, rather than a worktree's package):

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -B -u .work/e2e29/e2e29.py
```

The script retains definitions in `stock_definitions.json`, API inputs in `inputs.json`,
source paths/hashes in `input_manifest.json`, and commands/results in `results.json`.
The successful proof 3 rerun is retained under
`.work/wt280fix/proof3_after_fix/runs/20261004_082331_707042/results.json`.
