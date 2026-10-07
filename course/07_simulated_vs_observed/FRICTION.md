# Friction: Simulated vs observed

No blocking dssatlab friction was found on the stock Gainesville case.
The lesson uses only public dssatlab API and unchanged stock inputs.

## 1. Selecting dated observations requires a manual coverage audit — non-blocking

- **What the student must do:** Read Plant growth, build treatment/date pairs, select matching FileT rows, and display the excluded rows before calling `evaluate()`.
- **Why it is awkward:** The stock FileT includes six measurements on 8 July 1982, but simulated growth ends on 4 July; `evaluate()` correctly rejects unmatched dates, while `plot_observed()` correctly displays them. A beginner must build a filtering and reporting step to understand the different requirements.
- **Suggested change:** Add a public coverage-report helper that returns matched observations and explicit exclusions with reasons; retain strict matching in `evaluate()` and never silently drop data.
- **Classification:** **non-blocking**; ordinary Python treatment/date membership checks select 72 of 78 dated rows without changing any measurements or DSSAT files.

## 2. Default plot labels omit meanings and units — non-blocking

- **What the student must do:** Set labels on the returned matplotlib Axes, enlarge six-treatment growth plots, and format dates before showing them.
- **Why it is awkward:** Default labels use variable codes alone (`LAID`, `GWAD`) or simply Observed/Simulated, so students cannot see the native units; a six-treatment legend also benefits from smaller text and two columns.
- **Suggested change:** Give known variables their meanings and units by default, format dates, and size legends for multi-treatment plots.
- **Classification:** **non-blocking**; the returned public matplotlib Axes supports these changes.

## 3. Constant observed dates make the d-index surprising — non-blocking

- **What the student must do:** Interpret d-index alongside RMSE and bias rather than treating it as a standalone measure of model quality.
- **Why it is awkward:** All six observed anthesis dates are 12 May, and all six simulated dates are 13 May. Willmott's d-index is therefore 0 despite an RMSE of only 1 day; the value is mathematically consistent, but the statistics table alone does not explain it.
- **Suggested change:** Add a constant-observation example to the evaluation guide, explaining why a small common error can produce d-index 0.
- **Classification:** **non-blocking**; the notebook explains this directly from its displayed dates and statistics. This is interpretation friction, not a calculation bug.

## Validation

The case is stock `Maize/UFGA8201.MZX`, all six Gainesville maize treatments, cultivar McCurdy 84aa (`IB0035`), with `Weather/UFGA8201.WTH`, `Soil/SOIL.SOL` (profile `IBMZ910014`), and the matching `Maize/UFGA8201.MZA` and `.MZT`.
No additional case inputs or genotype files are bundled.

All six observed treatments are simulated. Each has 13 dated measurements and 12 exact matches in Plant growth, from 26 February to 4 July 1982; the six dated rows on 8 July are excluded from Evaluation and retained in both growth plots.
The lesson deliberately selects HWAM, ADAT and MDAT from FileA and LAID and GWAD from the matched FileT rows; other supported measurements are not part of that comparison, and the exercise evaluates CWAD.
The reader omits unsupported stock columns and unmeasured `-99` values.

Simulated HWAM for treatments 1–6 is 2293, 2293, 8207, 11854, 7718 and 10293 kg/ha, versus observed 2929, 3130, 6850, 11881, 6375 and 9344 kg/ha.
Yield errors (simulated minus observed) are -636, -837, +1357, -27, +1343 and +949 kg/ha.
HWAM has n=6, RMSE=970.523 kg/ha, bias=+358.167 kg/ha and d-index=0.980.
ADAT has n=6, RMSE=1 day, bias=+1 day and d-index=0; MDAT has n=6, RMSE=0 days, bias=0 days and d-index=1.
LAID has n=72, RMSE=0.502 m² leaf/m² ground, bias=-0.081 and d-index=0.953; GWAD has n=72, RMSE=497.640 kg/ha, bias=+131.583 kg/ha and d-index=0.992.
The self-contained CWAD exercise has n=72, RMSE=828.849 kg/ha, bias=+141.819 kg/ha and d-index=0.995.

Validation uses process-local `PYTHONPATH` pointing to this worktree's `src`, because the existing editable installation resolves to the main checkout.
Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` point to system temporary directories outside the worktree so the restricted environment can save discovery and kernel configuration; the exact setup cell is unchanged.
The executable identifies itself in the run output as DSSAT 4.8.5.017 pre-release.

Both final consecutive `python course/execute.py 07_simulated_vs_observed` runs printed `07_simulated_vs_observed: ok`.
All 15 tests in `tests/test_course.py` passed with `--basetemp` outside the worktree and `-p no:cacheprovider`; no test temporary folders were created in the worktree.
The exercise also passed in a fresh kernel with only LESSON, setup and tools cells before it; its default CWAD result does not depend on earlier lesson cells.
All four inline plots were visually inspected for readable labels and dates. The setup cell is exact, the five stock input copies are byte-identical, and notebook encoding searches for `??`, `m?` and ` ? ` found no corruption.
