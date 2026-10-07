# Input inventory

All inputs are unchanged stock DSSAT 4.8 files. Genotype files come from the installed DSSAT data directory.
The soil and climate files support the copied FileX; no daily weather file is needed under WGEN.

| file | origin | what it is |
|---|---|---|
| `UFGA7901.SBX` | DSSAT 4.8 `Soybean/UFGA7901.SBX` | Gainesville Bragg soybean FileX; treatment 1 has scheduled irrigation |
| `UFGA.CLI` | DSSAT 4.8 `Weather/Climate/UFGA.CLI` | Stock Gainesville climate file with WGEN parameters for ten generated-weather seasons |
| `SOIL.SOL` | DSSAT 4.8 `Soil/SOIL.SOL` | Stock soil profiles including treatment 1's `IBSB910015` |
| `DEFAULT.PRI` | DSSAT 4.8 `Economic/DEFAULT.PRI` | Expected crop prices and production costs, including soybean treatment 1 |
