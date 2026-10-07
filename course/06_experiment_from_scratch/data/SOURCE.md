# Gainesville inputs

The weather and soil CSVs were transcribed from stock DSSAT 4.8 into the exact columns written by `write_weather_template()` and `write_soil_template()`.
They reproduce the inputs planned for lessons 04/05; those lessons were not needed to build this one.
No stock FileX or genotype files are bundled; genotype files come from the installed DSSAT data directory.

| file | origin | what it is |
| --- | --- | --- |
| `station_weather.csv` | DSSAT 4.8 `Weather/UFGA8201.WTH`, transcribed for this lesson | All 365 daily records in 1982; UFGA station metadata and SRAD, TMAX, TMIN, RAIN values unchanged, plus daily PAR; the same file as lesson 04 |
| `gainesville_soil.csv` | DSSAT 4.8 `Soil/SOIL.SOL`, profile `IBMZ910014`, transcribed for this lesson | Millhopper Fine Sand, all eight layers to 180 cm; profile values, layer values and -99 missing markers preserved |
| `filex.yaml` | Written for this lesson | Filled FileX template: two Gainesville maize density treatments, cultivar IB0035, planting 26 February 1982 |
| `experiment.yaml` | Written for this lesson | Experiment data: treatment 2 at 8 plants/m2 and water/nitrogen simulation off for both treatments |
