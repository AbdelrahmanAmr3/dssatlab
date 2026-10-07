WARNING.OUT files copied unchanged from real Windows DSSAT runs on 2026-10-06.
DSSAT: C:\DSSAT48\DSCSM048.EXE, version 4.8.5.017 (pre-release).
All runs used a scratch folder outside the worktree, PYTHONPATH set to this
worktree's src, and dssatlab.run(..., executable=C:\DSSAT48\DSCSM048.EXE).

Inputs copied from C:\DSSAT48\Maize\UFGA8201.MZX and
C:\DSSAT48\Weather\UFGA8201.WTH; soil and genotype came from the stock
installation through its DSSATPRO.v48 paths.

single: stock inputs, treatment=1 (mode C); 1 Summary row, 3 warning blocks:
IPSOIL SKS at year/day 0/0, SOILDYN SLPF 0.92 at 1982/56, and IPWTH
SRAD 0.80 at 1982/98. This run's DATA PATH banner contains NUL bytes.

all: stock inputs, treatment=None (mode A); 6 Summary rows, 18 blocks,
3 distinct blocks. Each treatment repeats the same three warnings.

seasonal: treatment=1 (mode C), NYERS changed from 1 to 3 in the FileX's
GENERAL row. Repeat the 365 daily weather rows under years 82, 83 and 84
in UFGA8201.WTH, retaining the stock header and values. Copies of that file
were also placed as UFGA8301.WTH and UFGA8401.WTH. 3 Summary rows,
5 distinct blocks: the initial three, then SRAD at 1983/98 and 1984/98.

missing_weather: treatment=1 (mode C), keep the stock weather header and
only daily rows through 82097. DSSAT exits 0, writes 1 Summary row and
3 warning blocks; the last reports missing weather at 1982/98.
The existing Simulation missing-weather scan must still reject this run.

Unit tests replay these files with a mocked subprocess; CI never runs DSSAT.
