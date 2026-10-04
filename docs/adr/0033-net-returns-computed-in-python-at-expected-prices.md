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
