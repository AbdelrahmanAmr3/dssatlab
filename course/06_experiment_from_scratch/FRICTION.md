# Friction: An experiment from scratch

No blocking friction was found. The lesson uses public `dssatlab` exports, CSV data and YAML; it does not copy or hand-edit a stock FileX or call private functions.

## 1. A dictionary FileX template places results beside the notebook - non-blocking

- **What the student must do:** write the filled FileX template YAML under `RUNS` and pass its path through `filex_template=`, including in the self-contained exercise.
- **Why it is awkward:** passing the same template as an in-memory dictionary writes simulation folders in the current directory. In the first development execution, the exercise created two folders beside `lesson.ipynb`, outside the disposable `runs/` copy; there is no public run-directory argument.
- **Suggested change:** accept an explicit parent directory for generated simulation folders, and explain dictionary-versus-YAML output placement in the FileX-template guide.
- **Classification:** **non-blocking**; the supported YAML-path form puts the simulation folders beside that YAML in `runs/`. The final notebook uses that form, and development folders were moved into `runs/` before the repeat executions.

## 2. Changing density requires repeating the planting section - non-blocking

- **What the student must do:** supply the planting date, method, distribution, population, row spacing and depth again for treatment 2, and set emergence population to the same density.
- **Why it is awkward:** an experiment-data planting section replaces the whole section, so a population-only override fails the required-field checks. Students changing one factor must keep all the other planting details consistent.
- **Suggested change:** provide a public helper for making a complete planting override from a FileX template with selected values changed, and show a density-only example in the guide.
- **Classification:** **non-blocking**; the short experiment YAML explicitly supplies the complete section, and the exercise edits sowing and emergence populations together.

## 3. Stock-data warnings are only visible in WARNING.OUT - non-blocking

- **What the student must do:** inspect `WARNING.OUT` in a successful run directory to see how DSSAT interprets missing stock soil properties and unusual weather values.
- **Why it is awkward:** both density runs exit with status 0 but warn about soil photosynthesis factor SLPF 0.92, stock missing pH being set by DSSAT to 7, and solar radiation 0.80 MJ/m2/day on day 98 of 1982. These messages do not appear in the returned Summary or the successful run status.
- **Suggested change:** expose a public warning summary on the run result and demonstrate it in the guide, so students can distinguish complete outputs from assumptions made by DSSAT.
- **Classification:** **non-blocking**; both runs have complete yield, development and growth outputs. Stock CSV values and missing markers were preserved; no soil or weather values were changed to suppress warnings.

## Validation

The case is Gainesville maize, cultivar McCurdy 84aa (`IB0035`), planted on 26 February 1982 at 4 and 8 plants/m2, with 61 cm row spacing and 7 cm planting depth. Both treatments have water and nitrogen simulation off and harvest at maturity.
Weather contains all 365 days of stock `Weather/UFGA8201.WTH` for 1982 in the columns of `write_weather_template()`, with optional PAR omitted; rain totals 1544.5 mm.
Soil contains all eight layers of stock `Soil/SOIL.SOL` profile `IBMZ910014`, in the columns of `write_soil_template()`, to 180 cm with extractable water 160.95 mm.

The weather and soil CSVs were made independently because lessons 04/05 were not available in this worktree; their reviewer can align the files later. The two additional lesson-written inputs are `filex.yaml` (the filled template recipe) and `experiment.yaml` (treatment overrides).
The generated FileX holds both named treatments, and unchanged maize genotype files come from the installed DSSAT data directory.
The executable identifies itself as DSSAT 4.8.5.017 pre-release.

At 4 plants/m2, HWAM is 10080 kg/ha and CWAM is 17638 kg/ha. At 8 plants/m2, HWAM is 12093 kg/ha and CWAM is 24136 kg/ha.
The grain-yield gain is 2013 kg/ha (20.0%); both treatments reach anthesis on 13 May and maturity on 4 July 1982.
The default exercise at 6 plants/m2 gives HWAM 11371 kg/ha, 1291 kg/ha above the sparse treatment.

Both final consecutive `python course/execute.py 06_experiment_from_scratch` executions printed `06_experiment_from_scratch: ok`.
The Your turn cell also passed in a fresh kernel with only the LESSON, unchanged setup and tools cells; it rebuilt both simulations under `runs/` and reproduced the default exercise values.
The inline yield plot was visually checked; the setup matches `tests/test_course.py` byte-for-byte, and the notebook was checked for corrupted icons, units and middle dots.

Validation uses process-local `PYTHONPATH` pointing at this worktree's `src`, because the existing editable installation points to another checkout. Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` point to system-temp folders, so the unchanged setup cell can save its configuration in this restricted environment.
All 15 static course tests passed using `python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider`.
No validation or pytest temp folders were added to the worktree; generated DSSAT files stay in the ignored `runs/` directory.
