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
Supplied input that no run treatment uses is a problem, not a warning. The checks read the climate
file narrowly: the `*CLIMATE` header, the `@ INSI` station and twelve monthly averages rows.
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

- A Simulation can run seasonal and sequence analyses on generated weather with replicates.
- The narrow read cannot prove the climate file is complete for WGEN; DSSAT's own errors still
  surface through the run.

## Probe findings

Ticket #293, parent #292; attempted 2026-10-04. **T0 remains blocked; items 1-6 have no
new real-DSSAT result.** The Windows DSSAT executable exists at
`C:/DSSAT48/DSCSM048.EXE`. Its earlier Summary identifies version
`4.8.5.017 -pre-relea`. This session could read the earlier probes but could not write
inside the required probe folder. The actual preparation command

```powershell
Set-Content -LiteralPath 'C:/Users/abdosaleh/Desktop/dssat_lab/.work/probe-v021/t0_probe.py' -Encoding ascii
```

(with the probe script piped into it) failed with `UnauthorizedAccessException`,
"Access to the path ... is denied." The file was not created, and no Windows DSSAT
subprocess was started. The session's writable root covers only the git worktree,
not the main repository's `.work/probe-v021/`. Running DSSAT there would also require
permission to write its output files. No installation files were changed.

The commands below are **rerun instructions, not commands successfully executed in this
session**. Run them in a session with that probe folder writable. Each invocation creates
a fresh folder there, keeps the original `a/` and `b/` evidence, closes DSSAT's stdin,
and records its exit status, console, Summary data rows and errors. It imports no package
code. Seasonal probes use DTCM treatment 1 with NYERS 3; sequence probes retain UFGA's
NYERS 30 and six rotation components. NREPS and RSEED are set on every controls level.
FNAME is set to N so the output is named `Summary.OUT` in every case.

### Common Windows rerun preparation

Save this helper into the probe folder from PowerShell (Python uses only the standard
library). Its Summary hash compares data rows only, excluding the timestamped header.
Equal Summary hashes demonstrate equal Summary rows, not byte-identical output files.

```powershell
$probe = 'C:/Users/abdosaleh/Desktop/dssat_lab/.work/probe-v021'
@'
from pathlib import Path
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent
label, method, seed, reps, drop = sys.argv[1:]
sequence = label.startswith('sequence-')
source = (root.parent / 'dssat_test/2026-05-23/UFGA7874/ref'
          if sequence else root / 'a')
filex = 'UFGA7874.SQX' if sequence else 'DTCM6401.SNX'
station = 'UFGA' if sequence else 'DTCM'
folder = root / (label + '-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
folder.mkdir()
for path in source.iterdir():
    if path.suffix.upper() in {'.SOL', '.CUL', '.ECO', '.SPE'}:
        shutil.copy2(path, folder / path.name)
lines = []
for line in (source / filex).read_text().splitlines():
    if re.match(r'\s*\d+ GE\s', line):
        if not sequence:
            line = line[:15] + f'{3:5}' + line[20:]
        line = line[:21] + f'{int(reps):5}' + line[26:]
        line = line[:39] + f'{int(seed):5}' + line[44:]
    elif re.match(r'\s*\d+ ME\s', line):
        line = line[:15] + f'{method:>5}' + line[20:]
    elif re.match(r'\s*\d+ OU\s', line):
        line = line[:15] + '    N' + line[20:]
    lines.append(line)
(folder / filex).write_text('\n'.join(lines) + '\n', encoding='ascii')
climate = (Path('C:/DSSAT48/Weather/Climate') / (station + '.CLI')).read_text()
if drop != 'none':
    climate = re.sub(r'^\*' + re.escape(drop) + r'[^\n]*\n.*?(?=^\*|\Z)',
                     '', climate, flags=re.M | re.S)
(folder / (station + '.CLI')).write_text(climate, encoding='ascii')
exe = 'C:/DSSAT48/DSCSM048.EXE'
if sequence:
    shutil.copy2(source / 'DSSBatch.v48', folder / 'DSSBatch.v48')
    command = [exe, 'Q', 'DSSBatch.v48']
else:
    command = [exe, 'C', filex, '1']
with (folder / 'console.txt').open('w') as console:
    result = subprocess.run(command, cwd=folder, stdin=subprocess.DEVNULL,
                            stdout=console, stderr=subprocess.STDOUT)
summary = folder / 'Summary.OUT'
rows = [s for s in summary.read_text().splitlines() if re.match(r'^\s*\d+\s', s)] if summary.exists() else []
evidence = {'command': command, 'cwd': str(folder), 'exit': result.returncode,
            'summary_rows': len(rows),
            'summary_data_sha256': hashlib.sha256(('\n'.join(rows) + '\n').encode()).hexdigest()}
for name in ('ERROR.OUT', 'WARNING.OUT'):
    if (folder / name).exists():
        evidence[name] = (folder / name).read_text(errors='replace')
(folder / 'probe.json').write_text(json.dumps(evidence, indent=2))
print(json.dumps(evidence, indent=2))
'@ | Set-Content -LiteralPath "$probe/probe_293.py" -Encoding ascii
```

### 1. WTHER W with and without `*WGEN PARAMETERS`

**Result:** not run because probe-folder writes were denied. Reading the stock
`DTCM.CLI` confirmed that it contains both tables, including twelve WGEN rows with
fourteen values after MTH. That observation does not establish whether WGEN requires
that section, falls back to monthly averages, or fails without it.

**DSSAT command:** `C:/DSSAT48/DSCSM048.EXE C DTCM6401.SNX 1`, from each fresh
case folder. Change WTHER to W; remove only the WGEN section in the second case.
The third case removes monthly averages instead to distinguish the two requirements.

**Rerun:** after the common preparation:

```powershell
python "$probe/probe_293.py" w-full W 2510 1 none
python "$probe/probe_293.py" w-no-wgen W 2510 1 'WGEN PARAMETERS'
python "$probe/probe_293.py" w-no-monthly W 2510 1 'MONTHLY AVERAGES'
```

Inspect each `probe.json`, `console.txt`, `ERROR.OUT`, `WARNING.OUT` and `Summary.OUT`;
an exit code alone is insufficient evidence of usable generated weather.

### 2. WTHER S without `*MONTHLY AVERAGES`

**Result:** not run because probe-folder writes were denied. The failure mode and any
fallback to WGEN parameters remain unverified.

**DSSAT command:** `C:/DSSAT48/DSCSM048.EXE C DTCM6401.SNX 1`, with WTHER S and
identical inputs except for deleting the monthly averages section in the second case.

**Rerun:** compare successful baseline output against the missing-section case:

```powershell
python "$probe/probe_293.py" s-full S 2510 1 none
python "$probe/probe_293.py" s-no-monthly S 2510 1 'MONTHLY AVERAGES'
```

### 3. RSEED 0 versus 2510

**Result:** not run because probe-folder writes were denied. The spec's statement that
0 selects DSSAT's default seed 2510 has not been confirmed by this probe.

**DSSAT command:** `C:/DSSAT48/DSCSM048.EXE C DTCM6401.SNX 1`, changing only RSEED
between each pair, separately for W and S.

**Rerun:** compare the two Summary data hashes per method, then inspect any other
requested output data separately; exclude timestamps and the recorded seed setting.

```powershell
python "$probe/probe_293.py" w-seed-0 W 0 1 none
python "$probe/probe_293.py" w-seed-2510 W 2510 1 none
python "$probe/probe_293.py" s-seed-0 S 0 1 none
python "$probe/probe_293.py" s-seed-2510 S 2510 1 none
```

### 4. Seasonal NREPS 2

**Result:** not run because probe-folder writes were denied. Neither an unchanged
Summary row count nor ignored NREPS has been established by this session.

**DSSAT command:** `C:/DSSAT48/DSCSM048.EXE C DTCM6401.SNX 1`, with NYERS 3 and WTHER S,
changing only NREPS from 1 to 2.

**Rerun:** compare `summary_rows` and Summary data in the two `probe.json` files:

```powershell
python "$probe/probe_293.py" seasonal-reps-1 S 2510 1 none
python "$probe/probe_293.py" seasonal-reps-2 S 2510 2 none
```

### 5. Sequence NREPS 2 and Summary identifiers

**Result:** not run because probe-folder writes were denied. Replicate row counts,
ordering and distinguishing columns remain unknown. The earlier DTCM Summary header
has `RUNNO`, `TRNO`, `R#`, `O#`, `P#`, `WYEAR` and the simulation dates, but those are
seasonal rows; their presence does not prove which column identifies a sequence
replicate. Do not infer that `R#` is a replicate: it names a rotation component.

**DSSAT command:** `C:/DSSAT48/DSCSM048.EXE Q DSSBatch.v48`, from each case folder.
The existing UFGA batch lists treatment 1, RP 1, SQ 1-6, OP 0, CO 0. It stays unchanged
so the comparison isolates the FileX's NREPS, rather than a batch RP edit.

**Rerun:** retain NYERS 30, WTHER W and RSEED 1157; compare NREPS 1 and 2:

```powershell
python "$probe/probe_293.py" sequence-reps-1 W 1157 1 none
python "$probe/probe_293.py" sequence-reps-2 W 1157 2 none
```

Read all Summary rows around the transition between repetitions. Record the ordered
`RUNNO`, `TRNO`, `R#`, `O#`, `P#`, `WYEAR`, `SDAT`, `PDAT`, `HDAT` values for both
blocks and whether dates reset. Report any column that actually changes per replicate;
if only RUNNO and block order distinguish them, say so instead of inventing an ID.

### 6. Linux local CLI precedence over CLD

**Result:** could not run Linux. WSL is present but inaccessible, not proven missing.
Both commands were attempted and returned exit 1:

```powershell
wsl --list --quiet
# Access is denied. Wsl/EnumerateDistros/Service/E_ACCESSDENIED
wsl --exec /bin/true
# Access is denied. Wsl/Service/CreateInstance/E_ACCESSDENIED
```

`.work/scripts/wsl_run.sh` names `$HOME/dssat_verify/dssat/dscsm048`; this session
could not verify that executable, its version, or its current profile. Linux precedence
is therefore unverified. The absence of CLD described in the Context cannot by itself
prove precedence over a populated CLD lookup.

**Rerun command:** first repeat `wsl --exec /bin/true`. Once WSL works, confirm the
managed executable and stage three fresh folders under `.work/probe-v021/`, each
with copied DTCM FileX and sibling soil/genotype files. Use the same Linux profile in
all three, with a CLD entry pointing to a probe-owned folder containing stock
`DTCM.CLI`; do not edit the managed installation. Case `linux-cld` has no local CLI,
`linux-stock` has the stock local CLI, and `linux-changed` has the earlier `b/DTCM.CLI`
(its monthly RTOT values are halved). Keep the Linux profile paths within DSSAT's
supported lengths. Run from WSL, substituting the confirmed executable if necessary:

```bash
probe=/mnt/c/Users/abdosaleh/Desktop/dssat_lab/.work/probe-v021
exe="$HOME/dssat_verify/dssat/dscsm048"
for case in linux-cld linux-stock linux-changed; do
  (cd "$probe/$case" && "$exe" C DTCM6401.SNX 1 </dev/null >console.txt 2>&1)
  printf '%s exit=%s\n' "$case" "$?"
done
```

Require a successful CLD-only baseline, equal Summary data for CLD-only and stock-local
cases, and changed data for the altered local case. Also inspect errors and warnings.
These are the conditions for a future finding, not observed Linux results.

**Earlier Windows evidence, read only:** `a/DTCM6401.OSU` (no local CLI) and
`b/DTCM6401.OSU` (halved local monthly RTOT) each contain 160 rows. SHA-256 of the
LF-joined data rows plus a final LF is respectively
`e3f6fc156e9a72157ffb2d2fcd092a403db9ac42b0c3dbb3bfa430e5f812f7ae` and
`76f2c1cc6eb64a60d0bb91348c705fbec0fe698b46e87c7c60ec7362a5d7e743`.
This corroborates the recorded Windows difference; it is not a new run or Linux proof.

### Effect on the spec

No verified result from this session justifies changing a rule in `specs/SPEC_v0.21.md`.
Its Solution climate-file rule requires monthly averages for S and WGEN parameters for
W; the existing Decision above mentions monthly averages only. Keep that discrepancy
explicitly unresolved until items 1 and 2 run, rather than treating the older ADR
wording as evidence. The default-seed, seasonal NREPS and sequence-identifier claims
also remain awaiting T0 verification. Do not mark #293 complete on this evidence.
