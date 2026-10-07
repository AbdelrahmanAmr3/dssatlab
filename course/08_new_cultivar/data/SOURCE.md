# Input sources

All inputs are unchanged stock DSSAT 4.8 files, distributed under DSSAT's BSD-style licence.
This lesson bundles genotype companions because defining a new cultivar adds a row to the simulation folder's `.CUL` copy.
The notebook supplies the new cultivar's coefficients through experiment data; the bundled files stay unchanged.

| file | origin | what it is |
| --- | --- | --- |
| `UFGA7901.SBX` | Stock DSSAT 4.8, `Soybean/UFGA7901.SBX` | Gainesville soybean FileX; treatment 1 is irrigated Bragg (`IB0001`), planted 19 June 1979 |
| `UFGA7901.WTH` | Stock DSSAT 4.8, `Weather/UFGA7901.WTH` | Gainesville daily weather for 1979, including PAR |
| `SOIL.SOL` | Stock DSSAT 4.8, `Soil/SOIL.SOL` | Soil profiles, including the FileX's IBSB910015 (Millhopper Fine Sand) |
| `SBGRO048.CUL` | Stock DSSAT 4.8, `Genotype/SBGRO048.CUL` | Soybean cultivar coefficients; source Bragg (`IB0001`) uses ecotype `SB0701` |
| `SBGRO048.ECO` | Stock DSSAT 4.8, `Genotype/SBGRO048.ECO` | Soybean ecotype coefficients, including `SB0701` |
| `SBGRO048.SPE` | Stock DSSAT 4.8, `Genotype/SBGRO048.SPE` | Soybean species coefficients required by CROPGRO |
