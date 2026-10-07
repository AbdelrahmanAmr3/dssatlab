# Friction

No blocking dssatlab friction was found. The lesson uses public API, stock DSSAT inputs and experiment data to add cultivars; it does not hand-edit DSSAT files.

## 1. Reading a source cultivar requires text parsing — non-blocking

- **Student action:** Find Bragg's row and the first `@VAR#` header in `SBGRO048.CUL`, match the coefficient names to their values, and type all 18 values into the new cultivar definition.
- **Why awkward:** `list_cultivars()` returns codes and names, without ecotypes or coefficients. Starting a new definition from a known cultivar requires understanding the `.CUL` layout and risks transcription errors; the notebook compares the typed values with the source row to make the single change visible.
- **Suggested change:** Add a public helper that reads a cultivar's ecotype and coefficients from a supplied `.CUL` into the experiment-data shape, with a soybean example in the new-cultivar guide.

## 2. Cultivar experiment data uses the `management` argument — non-blocking

- **Student action:** Pass the cultivar experiment data to `Simulation` as `management=experiment`.
- **Why awkward:** Cultivar coefficients are broader than management data, so the argument name does not clearly describe the experiment data it accepts; notebook cell 14 explains this naming hurdle.
- **Suggested change:** Add an `experiment` argument alias, retaining `management` for compatibility.

## Validation notes

The case is stock `Soybean/UFGA7901.SBX`, irrigated treatment 1, Gainesville, planted on 19 June 1979. It uses `Weather/UFGA7901.WTH`, `Soil/SOIL.SOL` (profile IBSB910015) and the three bundled `Genotype/SBGRO048` companions (`.CUL`, `.ECO`, `.SPE`), as required by the ticket for a new cultivar.

Bragg (`IB0001`) and new cultivar `NC0001` share ecotype `SB0701`. All 18 coefficients are supplied; only `EM-FL` changes, from 19.5 to 23.5 photothermal days, with the stock management and simulation controls retained.

Bragg flowers on 1 August and matures on 12 October 1979 (43 and 115 days after planting), with HWAM 3,114 kg/ha. `NC0001` flowers on 8 August and matures on 16 October (50 and 119 days after planting), with HWAM 2,974 kg/ha: flowering is 7 days later, maturity 4 days later, and yield 140 kg/ha lower.

The new line's peak leaf area index is higher despite its lower seed yield. The lesson states this explicitly and attributes no unsupported cause to the yield response; the hypothetical line is not calibrated against observed data.

The exercise defines `NC0002` with `EM-FL = 21.5` photothermal days. Its flowering and maturity dates are 5 August and 14 October (47 and 117 days after planting), and HWAM is 3,039 kg/ha.

The editable installation initially resolved to another tree. Real execution uses process-local `PYTHONPATH` pointing to this worktree's `src`, plus `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` in system temporary directories outside the worktree to accommodate sandbox restrictions; the shared setup cell stays unchanged.

Both consecutive executions of `python course/execute.py 08_new_cultivar` print `08_new_cultivar: ok`. All 15 tests in `tests/test_course.py` pass with `--basetemp` outside the worktree and `-p no:cacheprovider`.

The exercise also passes in a fresh kernel with only the lesson identifier, setup and tools cells before it, using a separate disposable directory under `runs/` for the proof. All six bundled stock inputs match the DSSAT originals byte-for-byte, all text files decode as UTF-8, the notebook has no `??`, `m?` or ` ? ` corruption tokens, and the inline canopy plot was visually inspected.
