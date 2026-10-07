# Gainesville case inputs

The FileX is copied byte-for-byte from stock DSSAT 4.8. The soil CSV transcribes stock values into the columns written by `write_soil_template()`, without changing their units.
`station_weather.csv` contains the weather-template columns plus optional daily `par`, transcribed from stock `UFGA8201.WTH`.

Genotype files come from the installed DSSAT data directory; no stock soil file is needed because the lesson supplies soil data.

| file | origin | what it is |
| --- | --- | --- |
| `UFGA8201.MZX` | DSSAT 4.8 `Maize/UFGA8201.MZX` | Gainesville maize FileX; the lesson runs treatment 1 |
| `station_weather.csv` | DSSAT 4.8 `Weather/UFGA8201.WTH`, transcribed into `write_weather_template()` columns plus optional daily `par` | All 365 days of 1982, with station UFGA, latitude 29.630°, longitude -82.370°, elevation 10 m and the four optional station values and daily PAR; the same file as lesson 04 |
| `gainesville_soil.csv` | DSSAT 4.8 `Soil/SOIL.SOL`, profile `IBMZ910014`, transcribed into `write_soil_template()` columns | Eight layers of Millhopper Fine Sand to 180 cm, with all template profile and layer values preserved, including optional `-99` markers |
