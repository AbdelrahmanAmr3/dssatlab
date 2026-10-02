# 0018: Treatment rows read with DSSAT's own fixed columns

Status: accepted (2026-10-02). Amends how 0013's sequences and every FileX treatment are read.

## Context

dssatlab found a treatment's TREATMENTS row in two ways: most readers sliced the N and R columns at
the ends of the header tokens (`@N R`, so N is columns 1-2), and the treatment number list took the
first whitespace-separated word. DSSAT does neither. Its FileX reader (`ipexp.for`, 4.8.5) reads
every row with a fixed Fortran format: `I3,I1` (N in columns 1-3, R in column 4) in every run mode
except sequence mode Q, and `2I2` (N in columns 1-2, R in columns 3-4) in mode Q.

The DSSAT_Test course cases showed both readings going wrong on real files: the DSSAT sensitivity
tool writes rows like `  11 0 0` (treatment 1, R 1; DSSAT's Summary says TRNO 1), which dssatlab read
as a blank treatment or as treatment 11; the stock `MSKB8902.SQX` writes components 10-39 as
` 110 1 0` (treatment 1, R 10 in mode Q), which the number list read as treatments 110-139.

## Decision

- N and R of a TREATMENTS row are read with DSSAT's fixed columns. The rest of the row (the factor
  levels) keeps the header-token columns, which equal DSSAT's for every DSSAT-written header.
- A FileX is read with the sequence columns (`2I2`) only when every TREATMENTS row,
  read with those columns, has a digit N and a positive R written as Fortran I2
  (` 1`..` 9` or `10`..`99`, never blank, 0 or a leading zero), and some N has two
  or more rows; otherwise with the normal columns (`I3,I1`). Ordinary treatments
  100 and 101 share sequence-column N 10, so repetition alone cannot select a sequence.
  Even in a sequence FileX, a treatment with one row runs in a normal mode, so its row keeps
  the normal columns (` 210` is treatment 21, as DSSAT reads it there).
- Every reader of a treatment row uses this one rule, so check(), run(), the scenario runner and the
  templates always agree with each other and with DSSAT's Summary TRNO.

## Alternatives considered

- Header-token columns everywhere: simple, but wrong for `  11 0 0` rows in normal mode.
- First word of the row: wrong for both course files.
- Choosing the columns by file extension (`.SQX`): a sequence is defined by its rows, not by the
  extension, and a `.SQX` with one row per treatment runs normally.
- "Any row with R of 2 or more under the normal columns": misses sparse components (only R 1 and
  R 10, where R 10 reads as treatment 11).

- "Some N has two or more rows" alone: reads treatments 100 and 101 as one sequence.
