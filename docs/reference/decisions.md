# Decisions

Architecture Decision Records (ADRs) document architectural and design choices in `dssatlab`, describing the context, options evaluated, and consequences of each decision.

- [0001: The managed install prefix must be short](../adr/0001-short-managed-install-prefix.md): Limits the managed install prefix to 51 characters (`<cache>/dssatlab/<version>`) because DSSAT fails with substring out of bounds errors when reading `DSSATPRO.L48` lines with longer paths.
- [0002: pandas is accepted but never required](../adr/0002-optional-pandas.md): Accepts pandas DataFrames for tabular weather inputs while maintaining zero runtime dependencies and only importing pandas if a DataFrame is passed.
