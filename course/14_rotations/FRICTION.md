# Friction: Crop rotations

No blocking lesson friction was found: the ticket's unchanged stock sequence runs through the public `run()` API.
No DSSAT input was edited, and no private dssatlab API was used.

## 1. Simulation rejects the stock weather series - non-blocking

- **Student action:** Use `dl.run()` on the copied FileX and its stock weather and soil files, as the ticket requires, rather than building a `Simulation`.
- **Why awkward:** `Simulation.check(verbose=False)` rejects the stock station's elevation change from 285 m (1989-1994) to 200 m (1995 onward), emitting one elevation problem per affected weather row. It also reports duplicate dates in the 2007, 2009 and 2015 stock weather files; the weather cannot pass its checks unchanged.
- **Suggested change:** Define and document an explicit policy for running stock weather whose station metadata changes or dates repeat, and consolidate repeated check messages. Preserve strict checks for user weather data and never silently repair the stock inputs.
- **Classification:** **non-blocking** for this lesson; the ticket explicitly chooses `run()` and its unchanged input files, which produce 55 complete Summary rows without a missing-weather warning.

## 2. Successful runs still need warning inspection - non-blocking

- **Student action:** Read `WARNING.OUT` separately and distinguish warnings from a missing-weather failure; the notebook displays three distinct warning messages and reports whether weather ran out.
- **Why awkward:** Exit status 0 does not surface the stock warnings: zero saturated hydraulic conductivity is treated as missing, tillage depths are capped at implement limits, and some solar radiation values are below 1 MJ/m2/day. The 2008 maize component also has a slowed-grain-filling maturity warning, but that warning and a zero yield do not establish the cause of the zero.
- **Suggested change:** Expose a public warning summary on the run result, with compact distinct messages and a clear indication of missing-weather warnings.
- **Classification:** **non-blocking**; all requested yield and soil carbon results are available without changing the stock inputs.

## 3. Direct run-result display exposes machine paths - non-blocking

- **Student action:** Assign the result of `run()`, print its directory with `.relative_to(HERE).as_posix()`, and list output file names on one line.
- **Why awkward:** The default run-result representation includes an absolute path, while students need portable notebook outputs and a compact output inventory.
- **Suggested change:** Offer a public display helper accepting a base directory and use relative paths in teaching examples.
- **Classification:** **non-blocking**; ordinary public `pathlib` operations suffice.

## Validation notes

The case is stock `Sequence/MSKB8902.SQX`, treatment 1, at Kellogg Biological Station, with all 28 `Weather/MSKB*.WTH` files for 1989-2016 and unchanged `Soil/SOIL.SOL` containing profile `MSKB890006` (Kalamazoo Loam).
Unmodified genotype files come from the installed DSSAT data directory, and no extra case inputs were needed.
The executable identifies itself as DSSAT 4.8.5.017 pre-release.

The FileX holds 56 rotation components and NYERS 27, starting on 1 March 1989.
DSSAT completes 55 components (28 crops and 27 fallows), stopping after wheat component 55 ends on 12 July 2016; component 56 is not run.
Weather through 2016 is sufficient, and `WARNING.OUT` contains no `Weather record not found` message.

Maize has 10 cropped components with HWAM mean 6,400.3 kg/ha and range 0-10,947 kg/ha; soybean has 10 with mean 2,901.8 and range 704-4,518; wheat has 8 with mean 3,923.6 and range 2,604-5,568.
The notebook retains the surprising 2008 maize zero (R# 39) and makes no unsupported claim about its cause.
Summary `OCAM` is organic carbon in soil, excluding the surface carbon included in `OCTAM` (the installed DSSAT `DATA.CDE` definitions were checked during authoring).

Soil organic carbon at the first and last reported component ends is 57,886 and 71,120 kg C/ha, a difference of 13,234 kg C/ha.
These simulated stocks fluctuate across crops and fallows; they are neither daily observations nor evidence of an effect relative to another rotation, and the first value is after the first maize crop.
The self-contained Your turn cell runs the unchanged sequence afresh and shows component yields for an editable crop code, defaulting to maize.

Validation uses process-local `PYTHONPATH` pointing to this worktree's `src` because the editable installation points to another checkout.
Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` point to system temporary directories outside the worktree so the exact setup cell can write its configuration.
The notebook setup remains byte-identical to `SETUP_CELL` in `tests/test_course.py`; these validation-environment settings do not change it.

Both final consecutive `python course/execute.py 14_rotations` commands printed `14_rotations: ok`, including the fresh-run maize exercise.
The two runs saved by the second execution have identical parsed Summary rows, complete HWAM/OCAM/end dates for components 1-55, 27 fallows with zero yield and no planting date, and no missing-weather warning.

`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all 15 tests.
A separate fresh-kernel check used only the LESSON, setup, tools and Your turn cells, with `chosen_crop = "SB"`, and returned all 10 soybean component rows; it needed no earlier analysis cells.

Both inline plots were visually inspected for readable dates, crop labels and units.
Every bundled stock input is byte-identical to its installed source and decodes as UTF-8; the notebook passed the `??`, `m?` and ` ? ` corruption scan.
Only `course/14_rotations/` contains lesson changes, and all validation scratch directories are outside the worktree.

The requested commit was attempted, but staging failed because the linked worktree git index is read-only (`index.lock`: permission denied).
The completed lesson files remain uncommitted; the supplied issue/spec copies were not staged.
