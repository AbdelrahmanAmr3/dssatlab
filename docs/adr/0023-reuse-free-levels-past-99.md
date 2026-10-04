# 0023: An edit past level 99 reuses a level no treatment references

Status: accepted (2026-10-02). Amends 0005 (an edit appends a new level, highest + 1).

## Context

Experiment data edits append a new FileX level numbered highest + 1 and repoint the treatment to
it. The level columns of TREATMENTS are three characters wide, so 99 is the last usable number.
Rebuilding MSKB8902's 56 harvest events into a copy that keeps its 56 stock harvest levels reaches
level 100. check() reports it cleanly, but a user cannot rebuild a long sequence in its own FileX.

## Decision

Only when highest + 1 would pass 99, the edit takes the lowest-numbered level of that section
that no TREATMENTS row references once the edit is repointed, and replaces its rows. When no level
is free, check() reports the problem as before.

## Alternatives considered

- Reuse a level whose rows are identical. Rejected: does not help when the rebuilt values differ.
- Drop unreferenced levels and renumber every level. Rejected: changes every edited FileX, also
  the ones far below 99.

## Consequences

- Edits below level 99 write byte-identical FileX as before.
- Past 99, a stock level that the edit stopped using is overwritten in the copy; the user's
  original FileX is never changed.
