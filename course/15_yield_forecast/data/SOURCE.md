# Input sources

| file | origin | what it is |
| --- | --- | --- |
| `CAPE2002.FCX` | Stock DSSAT 4.8 `YieldForecast/CAPE2002.FCX`, copied unchanged | Hypothetical 2020 wheat forecast FileX near Petropavl, Kazakhstan; three forecast-date treatments, cultivar North KAZAK1 (`KZ0001`) |
| `CAPE8437.WTH` | Stock DSSAT 4.8 `Weather/CAPE8437.WTH`, copied unchanged | NASA POWER weather identified by the stock header; daily dates 84001 through 20229 (1 January 1984 to 16 August 2020) |
| `KZ.SOL` | Stock DSSAT 4.8 `Soil/KZ.SOL`, copied unchanged | Stock Kazakhstan soil profiles; this FileX selects loam profile `KZ01826030`, 200 cm deep |

Only these three stock files are bundled. Unmodified wheat genotype files come from the installed DSSAT data directory. Inputs are read from the fresh `runs/` copy.

The parent course spec calls this a South African case, but the ticket's FileX and weather header identify Petropavl, Kazakhstan; the lesson follows those visible inputs.
