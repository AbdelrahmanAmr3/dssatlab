# Stock Wa case inputs

All four files are copied byte-for-byte from stock DSSAT 4.8.
The notebook reads the copies in `runs/`; unmodified genotype files come from the installed DSSAT data directory.
The FileX selects soil profile `GHWA040001` and cultivar OBATANPA (`GH0010`).

| file | origin | what it is |
| --- | --- | --- |
| `GHWA0401.MZX` | DSSAT 4.8 `Maize/GHWA0401.MZX` | Wa, Ghana maize FileX with N × P treatments and estimated starting soil-analysis P |
| `GHWA0301.WTH` | DSSAT 4.8 `Weather/GHWA0301.WTH` | Daily Wa weather for 2003, including the pre-planting simulation period |
| `GHWA0401.WTH` | DSSAT 4.8 `Weather/GHWA0401.WTH` | Daily Wa weather for the 2004 maize season |
| `GH.SOL` | DSSAT 4.8 `Soil/GH.SOL` | Stock soil file containing profile `GHWA040001`, a 90 cm profile at Wa |
