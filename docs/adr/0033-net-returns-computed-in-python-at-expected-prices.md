# 0033: Net returns are computed in Python from a price file, at expected prices

Status: accepted (2026-10-04). Follows 0007.

## Context

Seasonal course cases such as DTCM6401 come with a DSSAT price file (`*.PRI`) for an economic
analysis. DSSAT-CSM never reads that file: the analysis lived in DSSAT's Seasonal Analysis tool,
which combines each Summary row with prices and costs (Thornton et al. 1994, Agron. J. 86:860,
Table 4) and samples price distributions (IDIS 1-3) at a few percentiles before a mean-variance or
stochastic-dominance comparison.

## Decision

`net_returns(rows, price_file)` reads the price file and adds one `net_return` ($/ha) to a copy of
each Summary row, matched by crop (`CR`) and treatment (`TRNO`):

    GRAN*HWAH/1000 + BYPR*BWAH/1000 - BASE - NFER*NICM - NCOS*NI#M - IRRI*IRCM - IRCO*IR#M
    - SCOS*DWAP - RESM*RECM/1000 - PCOS*PICM - PFER*PI#M - KCOS*KICM - KFER*KI#M

Every price and cost is replaced by its expected value: fixed PAR1, uniform and triangular means,
normal mean; IDIS -1 leaves the component out. Season statistics come from `summarize_seasons()`.

## Alternatives considered

- Sample the distributions as the Seasonal Analysis tool did. Rejected: needs a seed and a
  percentile rule the tool never documented, and gives results that are no easier to check.
- Reject IDIS 1-3. Rejected: DTCM6401 uses a normal grain price, and net return is linear in each
  price, so the expected value gives the exact mean net return over seasons.
- Stochastic dominance and risk plots. Rejected for now: no course case needs more than the mean.

## Consequences

- No DSSAT output to compare against; the proof recomputes every DTCM6401 row independently.
- Price spread (risk) is not modelled: two price files with the same means give the same results.
- Every Summary row needs a section for its crop and treatment, fallow rows included.
