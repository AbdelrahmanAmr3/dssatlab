# 0033: Net returns are computed in Python from a price file, at expected prices

Status: accepted (2026-10-04). Follows 0007.

## Context

Seasonal course cases such as DTCM6401 come with a DSSAT price file (`*.PRI`) for an economic
analysis. DSSAT-CSM never reads that file: the analysis lived in DSSAT's Seasonal Analysis tool,
which combines each Summary row with prices and costs (Thornton et al. 1994, Agron. J. 86:860,
Table 4) and evaluates five percentiles of each price distribution (IDIS 1-3) against every yield,
then sorts and interpolates them for a mean-variance or stochastic-dominance comparison (Table 5).

## Decision

`net_returns(rows, price_file)` reads the price file and adds one `net_return` ($/ha) to a copy of
each Summary row, matched by crop (`CR`) and treatment (`TRNO`):

    GRAN*HWAH/1000 + BYPR*BWAH/1000 - BASE - NFER*NICM - NCOS*NI#M - IRRI*IRCM - IRCO*IR#M
    - SCOS*DWAP - RESM*RECM/1000 - PCOS*PICM - PFER*PI#M - KCOS*KICM - KFER*KI#M

Every price and cost is replaced by its expected value: fixed PAR1, uniform and triangular means,
normal mean; IDIS -1 leaves the component out. Season statistics come from `summarize_seasons()`.

## Alternatives considered

- Reproduce the tool's five-percentile price procedure. Rejected as scope: no course case needs more
  than the mean, and a deterministic expected-price result is the easiest to check.
- Reject IDIS 1-3. Rejected: DTCM6401 uses a normal grain price, and net return is linear in each
  price, so at expected prices the mean over seasons is the expected mean net return, conditional on
  the simulated quantities (not a reproduction of the historical risk analysis).
- Stochastic dominance and risk plots. Rejected for now: no course case needs more than the mean.

## Consequences

- No DSSAT output to compare against; the proof recomputes every row of DTCM6401 and of UFGA8201
  (nonzero N and irrigation) independently.
- Summary alone cannot give complete economics for DTCM6401: missing N quantities and maize DWAP make
  most of its rows None.
- Price spread (risk) is not modelled: two price files with the same means give the same results.
- Every Summary row needs a section for its crop and treatment, fallow rows included.

## Proof

Ticket #307 (T2 of spec #303), run on 2026-10-04 in worktree
`.worktrees/v0211-307`, using `C:/DSSAT48/DSCSM048.EXE`. The real output banner
identifies DSSAT-CSM 4.8.5.017. Executable SHA-256:
`7b75b4df50f61733b04b70922c1c26dc048108cae9e934535b5af94ccd9cec60`.
The package imported is this worktree's `src/dssatlab`, with no source changes.

The local scripts are `.work/probe-v0211/run_probe.py` and
`.work/probe-v0211/independent.py`. Evidence from this run is under
`.work/probe-v0211/runs/20261004_174012_987883/`: `manifest.json` records input
paths/hashes, each DSSAT command, working directory, exit status and raw Summary
path/hash; `library.json` retains every `net_returns` row; `independent.json`
retains every independently sliced raw row, source line, missing quantity and
computed term; `comparison.json` records the comparison and stock parse results.
The owner-approved follow-up recomputes the seed-cost-disabled UFGA8201 variant
from the same six recorded treatment outputs in that evidence directory;
it adds a probe-local price copy and updates the JSON evidence for all three cases.
The scripts and run artifacts are local, ignored `.work` files.

Each FileX is copied unchanged into the worktree. DTCM6401 uses the stock
`C:/Users/abdosaleh/Desktop/dssat_lab/DSSAT_Test/2026-05-23/DTCM6401.SNX` and
its sibling `DTCM6401.PRI`, with the archived course `SOIL.SOL` and
`SBGRO048.CUL` inputs from `.work/dssat_test/2026-05-23/DTCM6401/ref`.
Its 16 treatments use `Simulation(filex, treatment, weather, executable)` with
stock `C:/DSSAT48/Weather/Climate/DTCM.CLI`, retaining the FileX's WTHER S
controls (the v0.21 generated-weather path). UFGA8201's stock seasonal FileX
is at `C:/DSSAT48/Seasonal/UFGA8201.SNX`; its six treatments use stock
`C:/DSSAT48/Weather/Climate/UFGA.CLI` and retain WTHER W, with
`C:/DSSAT48/Economic/UFGA8201.PRI`. The copied FileXs and climate files were
checked byte-for-byte against their sources. All 22 DSSAT runs exited 0.
The actual commands were `C:/DSSAT48/DSCSM048.EXE C DTCM6401.SNX <1..16>`
and `C:/DSSAT48/DSCSM048.EXE C UFGA8201.SNX <1..6>`, each executed in its
isolated simulation folder inside this worktree, with stdin closed.

Stock FNAME Y makes DSSAT name its Summary text `DTCM6401.OSU` or
`UFGA8201.OSU`, rather than `Summary.OUT`. Both are the raw `*SUMMARY` output
accepted by `read_summary`; no output values or FileX controls were edited.
The independent script reads that raw text directly, locates its own column
boundaries, reads prices with its own parser, and uses Decimal expected-price
arithmetic. It imports no DSSATLab module and never reads the library results.
The comparison checks row identities, all 12 economics quantities, exact None
row positions, and every numeric net return with absolute tolerance `1e-6`.

| Case | Rows | Numeric (both) | None (both) | None positions | Numeric comparison |
| --- | ---: | ---: | ---: | --- | --- |
| DTCM6401 | 160 (10 per treatment) | 30 | 130 | Identical | All 30 pass; maximum absolute difference `8.526512829121202e-14` $/ha |
| UFGA8201 | 180 (30 per treatment) | 0 | 180 | Identical | No numeric rows to compare |
| UFGA8201, SCOS IDIS -1 variant | 180 (same recorded rows) | 180 | 0 | Identical (empty) | All 180 pass; maximum absolute difference `2.2737367544323206e-13` $/ha |

DTCM6401 passes the requested comparison. BN, SB and WH each have 10 numeric
and 30 None rows; MZ has 0 numeric and 40 None rows. Of the 130 None rows,
90 lack used `NICM` and `NI#M`, 10 lack used `DWAP`, and 30 lack all three.
These quantities are raw `-99`, so Summary alone cannot give complete
economics for this case. Missing quantities for ignored price components do
not invalidate a row.

**Stock-price UFGA8201 returns None for all 180 rows, with agreement.**
All 180 raw rows have `DWAP=-99`, and all six stock price sections use seed
cost `SCOS` with `IDIS=0`, `PAR1=0.46`. Both calculations consequently return
None for every row. All 180 rows have nonzero `NICM` and `IRCM`, but none has
a numeric net return. For example, treatment 1's first row (SDAT `1982056`,
raw output line 5) has `HWAH=2543`, `BWAH=0`, `NICM=116`, `NI#M=3`,
`IRCM=13`, `IR#M=1`, and `DWAP=-99`. Its known terms are grain revenue
`406.88`, by-product revenue `0`, base cost `240`, N costs `52.20 + 36`,
and irrigation costs `6.50 + 12.50` $/ha; the required seed cost cannot be
calculated. Neither a zero seed quantity nor a partial return was substituted.
There is no disagreement between `net_returns` and the independent script;
the stock price file requires seed cost from the missing `DWAP` quantity.

**The numeric N-and-irrigation criterion is met via the UFGA8201 variant.**
The owner-approved probe-local copy is
`.work/probe-v0211/runs/20261004_174012_987883/UFGA8201_no_seed_cost/UFGA8201.PRI`.
Only `SCOS`'s `IDIS` changes from `0` to `-1` in each of the six treatment
sections, applying the decision's "leaves the component out" rule. Every other
price, including `SCOS PAR1=0.46`, remains unchanged; the stock file is untouched.
Both calculations reuse the exact same 180 Summary rows and return 180 numeric
values and 0 None values. All 180 numeric rows have nonzero `NICM` and `IRCM`;
all agree within `1e-6`, with maximum absolute difference
`2.2737367544323206e-13` $/ha. Treatment 1's first row above now has net return
`59.68` $/ha, with `NICM=116` and `IRCM=13`; `DWAP` remains missing but is unused.
The probe requires identical None positions and numeric agreement for both
UFGA8201 cases, all-None for the stock case, and at least one numeric row with
nonzero N and irrigation for the variant. These revised criteria and DTCM6401's
comparison all pass; the probe exits **0**. No `src/` or `tests/` changes were made.

The bare price-read check `net_returns([], price_file)` passed for **7/7**
stock files in `C:/DSSAT48/Economic`: `DEFAULT.PRI`, `ITHY7501.PRI`,
`UAFD7465.PRI`, `UFGA7805.PRI`, `UFGA7812.PRI`, `UFGA8201.PRI`, and
`UFGA9701.PRI`, including UFGA7805's single crop heading over nine treatments.

Rerun from this worktree in PowerShell (the runner selects this worktree's
`src` itself and writes a new evidence directory):

```powershell
$probePython = 'C:/Users/abdosaleh/Desktop/dssat_lab/.venv/Scripts/python.exe'
& $probePython -B -u .work/probe-v0211/run_probe.py
# Recompute independently from the recorded raw output, without rerunning DSSAT:
& $probePython -B .work/probe-v0211/independent.py .work/probe-v0211/runs/20261004_174012_987883
# Add/recompute the local variant and recheck every row (exits 0 when all criteria pass):
& $probePython -B -u .work/probe-v0211/run_probe.py --compare .work/probe-v0211/runs/20261004_174012_987883
```
