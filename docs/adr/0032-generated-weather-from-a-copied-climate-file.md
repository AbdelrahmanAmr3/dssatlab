# 0032: Generated weather from a climate file copied beside the FileX

Status: accepted (2026-10-04). Extends 0019 and 0024.

## Context

Simulation rejected every WTHER other than M, so seasonal course cases such as DTCM6401 (WTHER S,
ten seasons) and UFGA7874 (WTHER W, NREPS 10) could not run. Measured on Windows DSSAT 4.8.5.017 while
planning v0.21 (`.work/probe-v021/`): DTCM6401.SNX run in mode A with no `.WTH` and no `.CLI` in its
folder reads `DTCM.CLI` from DSSAT's climate folder (DSSATPRO `CLD`) and gives the course reference
Summary exactly. A changed `DTCM.CLI` placed beside the FileX changes the results: DSSAT prefers the
copy in the FileX folder. A Linux managed install has no `CLD` entry.

## Decision

`weather=` also accepts a `.CLI` path, alone or with `.WTH` paths. `run()` copies it unchanged,
under its upper-case name, into the simulation folder, as ADR 0024 does for stock weather files.
Each run treatment's controls level decides what it needs: WTHER M needs weather data as before;
W or S needs a climate file named after the FileX WSTA's first four characters, and no weather data.
W needs the `*WGEN PARAMETERS` table, S needs `*MONTHLY AVERAGES` (probes 1 and 2 below).
Supplied input that no run treatment uses is a problem, not a warning. The checks read the climate
file narrowly: the `*CLIMATE` header, the `@ INSI` station and the twelve rows of the table the method needs.
Controls gain `weather_source` (WTHER), `replicates` (NREPS) and `random_seed` (RSEED); replicates
above 1 need generated weather.

## Alternatives considered

- A new `climate=` parameter. Rejected: a second way to pass a copied input file; `weather=`
  already takes files by path.
- Look up the climate file in DSSAT's installation. Rejected: not portable to Linux managed installs
  and hides which file the run used.
- Generate the climate file from weather data. Rejected: that is computing climate statistics, a
  later WeatherMan-style feature.

## Consequences

- A Simulation can run seasonal and sequence analyses on generated weather; replicates apply to sequences only.
- The narrow read cannot prove the climate file is complete for WGEN; DSSAT's own errors still
  surface through the run.

## Probe findings

Ticket #293, parent #292; run 2026-10-04 on Windows DSSAT 4.8.5.017 (`C:/DSSAT48/DSCSM048.EXE`),
mode `C DTCM6401.SNX 1` (seasonal, NYERS 3) and `Q DSSBatch.v48` (UFGA7874 sequence, NYERS 30). Each
case ran in a fresh folder with the stock `DTCM.CLI` or `UFGA.CLI` beside the FileX. Summary hashes cover
data rows only (the header is timestamped). Evidence: `.work/probe-v021/<case>-<timestamp>/probe.json`.

1. **WTHER W needs `*WGEN PARAMETERS`; it does not need monthly averages.** Full file: exit 0, 3 rows.
   Without WGEN: exit 99, `ERROR.OUT`, no Summary. Without monthly averages: exit 0, same Summary hash
   as the full file.
2. **WTHER S needs `*MONTHLY AVERAGES`; it does not need WGEN.** Without monthly averages: exit 99,
   `ERROR.OUT`. Without WGEN: exit 0, same Summary hash as the full file. This matches the climate-file
   rule in the code: S checks monthly averages, W checks WGEN.
3. **RSEED 0 is not DSSAT's default seed 2510.** Seed 0 and 2510 give different Summary hashes for both
   W and S, and two seed-0 runs repeat each other. So a fixed seed repeats, and 0 is just another value.
   The spec's "0 means 2510" was wrong; code comments and docs now say 0 is passed as is.
4. **Seasonal NREPS is ignored.** NREPS 1 and 2 with WTHER S: 3 rows each, identical hash. The problem
   for `replicates` above 1 outside a sequence stands.
5. **Sequence NREPS 2 doubles the rows.** UFGA7874 with WTHER W: NREPS 1 gives 91 Summary rows, NREPS 2
   gives 182. Replicates are consecutive blocks of 91; `RUNNO` and `WYEAR` restart in each block (RUNNO
   1 to 91, WYEAR from 1978). The `P#` column is 1 in the first block and 2 in the second, so `P#` tells
   replicates apart; `R#` is the rotation component and is not a replicate number.
6. **Linux precedence is not proven.** WSL has only an aarch64 PDI-instrumented DSSAT build from another
   project, which aborts without its paraconf file, and no stock managed install. The Windows result
   (a climate file beside the FileX wins over DSSAT's climate folder, earlier `a/` and `b/` runs) is the
   evidence; a Linux managed install has no `CLD` entry, so the copied file is the only source there.

## Real-DSSAT proofs

Ticket #298, run 2026-10-04 on Windows DSSAT 4.8.5.017 with the public API from the feature branch
(`Simulation`, `read_summary`). Local script, deliberately uncommitted: `.work/scripts/proof298.py`;
evidence in `.work/proof298/<timestamp>/results.json` and each run directory. Every case uses a fresh
copy of the course folder (`.work/dssat_test/2026-05-23/<case>/ref`) and the stock climate file
`C:/DSSAT48/Weather/Climate/<STATION>.CLI`, passed as `weather=[path]`. Rerun from the main checkout:

```powershell
.venv/Scripts/python.exe -B -u .work/scripts/proof298.py        # all of (a)-(e)
.venv/Scripts/python.exe -B -u .work/scripts/proof298.py b c    # chosen proofs
```

| | Proof | Result |
|---|---|---|
| a | Copied `DTCM6401.SNX` (WTHER S, NYERS 10, 16 treatments run one by one in mode C) with stock `DTCM.CLI` and no weather data | 160 rows; TRNO, CR, MODEL, SDAT, HWAM, ADAT, MDAT, HDAT equal the 160-row course reference `DTCM6401.OSU` (equal digests of the sorted rows) |
| b | Treatment 1 switched with controls `weather_source: W`, `years: 3`, `random_seed: 1234` | `check()` reports no problems; 3 rows (HWAM 1357, 1340, 1077); a rerun is identical; seed 4321 differs (HWAM 1205, 1122, 1194) |
| c | The same with `weather_source: S` | 3 rows (HWAM 683, 1205, 189); rerun identical; seed 4321 differs (HWAM 860, 789, 920) |
| d | Treatment 1 with a locally altered `DTCM.CLI` (monthly RTOT halved) beside the FileX | The ten HWAM values change from 1387, 1250, 847, 877, 1114, 1510, 1222, 740, 216, 677 to 740, 754, 643, 456, 1085, 499, 391, 976, 653, 568 |
| e | Copied `UFGA7874.SQX` (sequence, WTHER W, NREPS 10, NYERS 30, six components) with stock `UFGA.CLI` | `check()` reports no problems; 910 rows; RUNNO, TRNO, R#, P#, CR, MODEL, SDAT, HWAM, ADAT, MDAT, HDAT equal the 910-row Q reference `UFGA7874.OSU` |

Linux managed install: not run. This machine has no stock Linux DSSAT (probe 6), so the Windows
runs are the only real-DSSAT evidence; the Linux file lookup is the same relative-to-FileX rule.
GAPS F11's WTHER/NREPS part is done; economics from a `.PRI` file stays open.
