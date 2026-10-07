# Friction: Your own soil

No blocking friction was found. The lesson uses the public dssatlab API; the stock FileX is unchanged, and the CSVs preserve the stock values in the template writers' columns.

## 1. A stock soil profile must be transcribed into the soil template — non-blocking

- **Student action:** When starting from an existing stock `.SOL` profile, copy its profile values and layer values into the columns of `write_soil_template()`, repeating profile values on every row. This course supplies the completed `gainesville_soil.csv` so the student can concentrate on using and changing it.
- **Why awkward:** `summarize_soil()` accepts soil-template data and rejects a stock `.SOL` path. The public API can copy stock soil unchanged for a Simulation but has no helper to extract one profile into template data; the implementer had to transcribe all eight layers and map the headers.
- **Suggested change:** Provide a public, explicit conversion helper for a named stock soil profile, preserving all supported values and reporting any unsupported fields.
- **Classification:** **non-blocking**; fixture preparation can faithfully transcribe stock values without editing DSSAT files or calling private API.

## 2. Successful runs keep stock-data warnings in a file — non-blocking

- **Student action:** Inspect the run result's `outputs` to locate `WARNING.OUT` and read it separately if investigating the run's warnings.
- **Why awkward:** All four runs completed, but their warning files report hydraulic conductivity treated as missing, soil photosynthesis factor `SLPF = 0.92`, and low radiation of 0.80 MJ/m²/day on day 98 of 1982. The successful run result does not summarize these warnings for the student.
- **Suggested change:** Expose a public warning summary on the run result, with a short guide example that avoids printing machine paths.
- **Classification:** **non-blocking**; the case yields complete results, and the notebook preserves the stock input values.

## Validation

Case: stock `Maize/UFGA8201.MZX`, treatment 1, Gainesville maize McCurdy 84aa (`IB0035`), planted on 26 February 1982. Water and nitrogen simulation remain on. Despite the RAINFED LOW NITROGEN name, the stock treatment includes 13 mm of irrigation on 4 March; the notebook states this and keeps it unchanged.

The weather CSV contains all 365 days of stock `Weather/UFGA8201.WTH`, station UFGA at 29.630° N, 82.370° W and 10 m elevation. Its columns exactly match `write_weather_template()`, including `tav`, `amp`, `refht` and `wndht`; optional daily PAR is omitted as in the writer's example. The soil CSV contains every column of `write_soil_template()`, preserving all profile and layer values for `IBMZ910014` from stock `Soil/SOIL.SOL`.

| Profile | Layers | Depth (cm) | Extractable water (mm) | HWAM (kg/ha) | Change from full (kg/ha) |
| --- | --- | --- | --- | --- | --- |
| Full | 8 | 180 | 160.95 | 2293 | 0 |
| Shallow | 4 | 60 | 37.05 | 1480 | -813 |
| Your turn default | 5 | 90 | 55.65 | 2274 | -19 |

The full profile gives anthesis on 13 May and maturity on 4 July 1982, matching the reference lesson's treatment 1 yield and dates. The notebook explains that reducing storage capacity does not establish a specific cause of the yield change. It also calls out the surprisingly small response at 90 cm without asserting an unsupported mechanism.

The full Simulation check returns `Problems: []`. A deliberately invalid DataFrame copy with `sdul == slll` in the top layer produces a clear strict-water-limit-order message; it is never run and does not change the valid data. The shallower profiles retain the stock FileX initial conditions extending to 180 cm, as permitted by the public API and described in the soil guide.

The validated DSSAT executable identifies itself as 4.8.5.017 pre-release. Validation uses process-local `PYTHONPATH` pointing to this worktree's `src`, because the existing editable install resolves to the main checkout. `LOCALAPPDATA`, `IPYTHONDIR`, `JUPYTER_RUNTIME_DIR` and pytest's base temporary directory are under system temp outside this worktree; the mandatory setup cell is unchanged.

Both final consecutive `python course/execute.py 05_own_soil` executions printed `05_own_soil: ok`. All 15 static course tests passed using `--basetemp` outside this worktree and `-p no:cacheprovider`. The self-contained Your turn cell also passed in a fresh kernel with only LESSON, setup and tools before it; the inline plot was visually checked, and the notebook's UTF-8 symbols were checked for `??`, `m?` and ` ? ` corruption.
