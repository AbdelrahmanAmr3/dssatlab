# Friction: Climate change

No blocking dssatlab friction was found on the stock Gainesville maize case.
The lesson uses only public API and unchanged stock inputs.

## 1. Effective weather names and units differ from experiment data — non-blocking

- **What the student must do:** Read each run with `dl.read_weather()` and select `CO2D`, `TMXD`, `TMND` and `SRAD`, then label the table with ppm, degrees C and MJ/m²/day.
- **Why it is awkward:** The experiment data uses `co2`, `tmax`, `tmin` and `srad`, while the output reader retains DSSAT's different column names. The default CO2 is not obvious from the stock weather file; the first weather-output row shows 340.7 ppm, so students need this extra step to understand what their elevated value replaces.
- **Suggested change:** Document these input-to-output names together and offer a public weather-output display helper with units, including an environment-comparison example.
- **Classification:** **non-blocking**; the public weather reader and ordinary table construction confirm the effective changes without altering DSSAT files.

## Validation

The case uses stock `Maize/UFGA8201.MZX`, treatment 1, with cultivar McCurdy 84aa (`IB0035`), `Weather/UFGA8201.WTH` and `Soil/SOIL.SOL` (profile `IBMZ910014`). All three committed inputs match their stock files byte-for-byte; unmodified genotype files come from the installed DSSAT data directory.

Water and nitrogen simulation are off for every simulation. The planting date remains 26 February 1982; each environment event starts on the simulation start date, 25 February 1982. The CO2, temperature and radiation changes are separate comparisons with the default environment, not cumulative changes.

| Environment | HWAM (kg/ha) | Change (kg/ha) | ADAT | MDAT | Days from planting to maturity |
| --- | --- | --- | --- | --- | --- |
| Default | 11859 | 0 | 1982-05-13 | 1982-07-04 | 128 |
| CO2 replaced with 550 ppm | 12349 | +490 | 1982-05-13 | 1982-07-04 | 128 |
| Tmax and Tmin each +2 °C | 10186 | -1673 | 1982-05-05 | 1982-06-24 | 118 |
| Radiation multiplied by 0.9 | 10724 | -1135 | 1982-05-13 | 1982-07-04 | 128 |

The first weather-output row confirms default CO2 340.7 ppm versus 550 ppm, temperatures 27.2/10.6 °C versus 29.2/12.6 °C, and radiation 14.8 versus 13.3 MJ/m²/day. Radiation output rounds to one decimal place. Earlier maturity under warming is consistent with a shorter growing period contributing to lower yield; the lesson does not claim to separate all temperature effects or predict future farm yields.

The self-contained Your turn cell defaults to 700 ppm: HWAM is 12455 kg/ha, 596 kg/ha above the default, with maturity still 4 July. It also executed in a fresh kernel with only the LESSON, setup and tools cells before it; no earlier simulation cells were needed.

Two consecutive `python course/execute.py 10_climate_change` executions both printed `10_climate_change: ok`. All 15 static course tests passed with `python -m pytest -q tests/test_course.py`, `--basetemp` under system temp outside this worktree, and `-p no:cacheprovider`. The setup cell is copied directly from `SETUP_CELL` in `tests/test_course.py`; the encoding scan found no `??`, `m?`, ` ? ` or replacement characters, and the saved inline plot was visually checked.

Validation uses process-local `PYTHONPATH` pointing to this worktree's `src`, and process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` under system temp. This allows the unchanged setup cell to save discovery config in the restricted execution environment; it does not change student code or DSSAT files. Jupyter emitted host-side event-loop and transport warnings, but the notebook contains no error outputs.
