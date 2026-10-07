# Input sources

The three DSSAT files are unchanged stock DSSAT 4.8 inputs, distributed under DSSAT's BSD-style licence.
The CSV treats the same Gainesville measurements as your station data; no daily values or station values were changed.
Unmodified genotype files come from the installed DSSAT data directory.

| file | origin | what it is |
| --- | --- | --- |
| `UFGA8201.MZX` | Stock DSSAT 4.8, `Maize/UFGA8201.MZX` | Lesson 01 Gainesville maize FileX; treatment 1, cultivar McCurdy 84aa (`IB0035`) |
| `SOIL.SOL` | Stock DSSAT 4.8, `Soil/SOIL.SOL` | Lesson 01 stock soil file, containing Millhopper Fine Sand profile `IBMZ910014` |
| `UFGA8201.WTH` | Stock DSSAT 4.8, `Weather/UFGA8201.WTH` | Original 1982 Gainesville daily weather, used for the yield comparison |
| `station_weather.csv` | Written for this course from `Weather/UFGA8201.WTH` | All 365 days of 1982 in the weather template, including PAR and station metadata |

## CSV mapping

`INSI`, `LAT`, `LONG`, `ELEV`, `TAV`, `AMP`, `REFHT` and `WNDHT` become `station`, `latitude`, `longitude`, `elevation`, `tav`, `amp`, `refht` and `wndht`, repeated on every row.
Daily `DATE` becomes an ISO calendar date: `82001` is 1982-01-01 and `82365` is 1982-12-31.
`SRAD`, `TMAX`, `TMIN`, `RAIN` and `PAR` become the corresponding lower-case columns with their stock values and DSSAT units preserved.
