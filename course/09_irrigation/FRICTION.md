# Friction

No blocking dssatlab friction was found. The lesson uses public API and unchanged stock DSSAT inputs.

## 1. Two irrigation settings share one controls factor — non-blocking

- **What the student must do:** Build nine labelled controls dictionaries with nested loops, pairing each management depth with each threshold, and retain water, nitrogen, refill, method and efficiency in every dictionary.
- **Why it is awkward:** A sweep factor is an entire experiment-data section, so depth and threshold cannot be two independent factors. The student must assemble their grid inside one `controls` factor and recover the two numeric settings from those dictionaries for the heatmaps.
- **Suggested change:** Add a guide example for a two-variable automatic-irrigation grid, explaining section replacement and how to retain numeric labels for plotting.
- **Classification:** **non-blocking**; the public controls factor accepts all nine complete dictionaries and runs them correctly.

## 2. The sweep adds an unlabelled base row — non-blocking

- **What the student must do:** Recognize the rainfed `base` row, whose controls label is `None`, and remove it before pivoting the numeric grid into heatmaps.
- **Why it is awkward:** Nine controls settings produce ten rows, and the rainfed row has no depth or threshold. It also repeats the rainfed reference already run for the potential-yield comparison.
- **Suggested change:** Offer an optional way to omit the base while preserving the current default, and document base filtering before grid plots.
- **Classification:** **non-blocking**; the lesson shows all ten rows, then explicitly selects the nine automatic settings for plotting.

## 3. Automatic-irrigation percentages lack reference limits in the guide — non-blocking

- **What the student must do:** Consult [DSSAT documentation](https://dssat.net/wp-content/uploads/2011/10/DSSAT-vol2.pdf) to interpret the automatic-irrigation threshold and refill percentages.
- **Why it is awkward:** `docs/guide/experiment.md` lists `auto_irrigation_threshold` and `auto_irrigation_refill` units merely as `%`, without defining their reference limits or management depth. Threshold is plant-available water remaining between the lower limit and drained upper limit within that depth; refill 100% targets the drained upper limit.
- **Suggested change:** Document both percentages' reference limits and the role of `auto_irrigation_depth` in the guide's automatic-management section.
- **Classification:** **non-blocking**; the controls work, and the lesson now defines the percentage basis explicitly.

## Case and results

The case is stock `Maize/UFGA8201.MZX`, treatment 1, with `Weather/UFGA8201.WTH` and `Soil/SOIL.SOL`, copied byte-for-byte from the installed DSSAT data directory. The cultivar is McCurdy 84aa (`IB0035`), planting is 26 February 1982, and soil profile `IBMZ910014` is Millhopper Fine Sand. No additional case files or genotype files are bundled.

The stock treatment labelled RAINFED has one 13 mm irrigation event. Experiment data removes reported events with `irrigation: []`; rainfed controls use `irrigation_management: "N"`, while automatic settings use `"A"`. Nitrogen simulation is off throughout; water simulation is on except in the potential-production reference.

Rainfed HWAM is 2,010 kg/ha with IRCM 0 mm. Potential HWAM is 11,859 kg/ha with IRCM 0 mm because water simulation is off; this is a model reference, not an irrigated management recommendation.

Automatic irrigation uses refill 100%, furrow method `IR001`, and efficiency 1. The executed grid is:

| Depth (cm) | Threshold (%) | HWAM (kg/ha) | IRCM (mm) |
| --- | --- | --- | --- |
| 15 | 30 | 10649 | 161 |
| 15 | 50 | 10937 | 198 |
| 15 | 70 | 11859 | 289 |
| 30 | 30 | 11016 | 173 |
| 30 | 50 | 11691 | 194 |
| 30 | 70 | 11859 | 265 |
| 60 | 30 | 11428 | 169 |
| 60 | 50 | 11854 | 231 |
| 60 | 70 | 11859 | 275 |

All three 70% settings match potential yield despite different irrigation totals. At each depth, higher thresholds increase yield and applied irrigation in this season; applied irrigation does not increase consistently with depth.

The self-contained exercise at depth 30 cm and threshold 50% gives HWAM 11,691 kg/ha and IRCM 194 mm at efficiency 1, versus 11,559 kg/ha and 344 mm at efficiency 0.5. It rebuilds its own inputs and experiment data and needs only the LESSON, setup and tools cells.

## Validation

The existing editable install resolves to the main checkout, so execution uses process-local `PYTHONPATH` pointing to this worktree's `src`. Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` point to system temporary directories outside the worktree so the exact setup cell can save discovery config and start a kernel. This is an execution-environment restriction; the notebook setup is unchanged.

Both final consecutive `python course/execute.py 09_irrigation` executions printed `09_irrigation: ok`. The standalone exercise also passed in a fresh kernel with only the LESSON, setup and tools cells before it. All 15 tests in `tests/test_course.py` passed with `--basetemp` outside the worktree and `-p no:cacheprovider`.

The two inline heatmaps were visually checked for readable values, axes, units and colour scales. All notebook cells are executed, the setup cell matches `SETUP_CELL` exactly, and the notebook has no corrupted `??`, `m?` or ` ? ` text.
