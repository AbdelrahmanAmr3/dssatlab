# Gainesville inputs

The weather and soil CSVs are copied byte-for-byte from the committed lesson 04/05 inputs listed below, originally transcribed from stock DSSAT 4.8 into the columns written by `write_weather_template()` and `write_soil_template()`.
The earlier independent stock-data transcriptions were compared with these predecessor CSVs: all columns and row values already matched; these copies now also match the committed bytes.
No stock FileX or genotype files are bundled; genotype files come from the installed DSSAT data directory.

| file | origin | what it is |
| --- | --- | --- |
| `station_weather.csv` | Copied from lesson 04 `data/station_weather.csv` at commit `d0d76a940d9ad8065285c4a0324a268cf974cb97`; stock DSSAT 4.8 `Weather/UFGA8201.WTH` | All 365 daily records in 1982; UFGA station metadata and SRAD, TMAX, TMIN, RAIN values unchanged, including daily PAR preserved from the stock weather file |
| `gainesville_soil.csv` | Copied from lesson 05 `data/gainesville_soil.csv` at commit `84cb540657cd01002d5fddce8a84a94756218a27`; stock DSSAT 4.8 `Soil/SOIL.SOL`, profile `IBMZ910014` | Millhopper Fine Sand, all eight layers to 180 cm; profile values, layer values and -99 missing markers preserved |
| `filex.yaml` | Written for this lesson | Filled FileX template: two Gainesville maize density treatments, cultivar IB0035, planting 26 February 1982 |
| `experiment.yaml` | Written for this lesson | Experiment data: treatment 2 at 8 plants/m2 and water/nitrogen simulation off for both treatments |

## Predecessor comparison

Verified against the committed CSVs on `course/04-own-weather` and `course/05-own-soil`, available in neighboring worktrees; neither predecessor lesson folder is required inside this lesson's checkout.
SHA-256 of the copied committed bytes:

- `station_weather.csv`: `761304c1362cfa9b57e69695c3611106d904272982782606138452a8ec370b60`
- `gainesville_soil.csv`: `25067aed490b57342a98bf4bd5b3c4f7ba5a9afdd6df544859f80c3f46c029c6`
