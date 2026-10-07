# Gainesville case inputs

The FileX is copied byte-for-byte from stock DSSAT 4.8. The two UTF-8 CSVs transcribe stock values into the exact columns written by the public template writers, without changing their units.
Genotype files come from the installed DSSAT data directory; no stock soil file is needed because the lesson supplies soil data.

| file | origin | what it is |
| --- | --- | --- |
| `UFGA8201.MZX` | DSSAT 4.8 `Maize/UFGA8201.MZX` | Gainesville maize FileX; the lesson runs treatment 1 |
| `gainesville_1982_weather.csv` | DSSAT 4.8 `Weather/UFGA8201.WTH`, transcribed into `write_weather_template()` columns | All 365 days of 1982, with station UFGA, latitude 29.630°, longitude -82.370°, elevation 10 m and the four optional station values; optional daily PAR is omitted because the writer's example does not include it |
| `gainesville_soil.csv` | DSSAT 4.8 `Soil/SOIL.SOL`, profile `IBMZ910014`, transcribed into `write_soil_template()` columns | Eight layers of Millhopper Fine Sand to 180 cm, with all template profile and layer values preserved, including optional `-99` markers |

The weather CSV is created here independently while lesson 04 is being built; these same inputs can be aligned with lessons 04 and 06 during review.
