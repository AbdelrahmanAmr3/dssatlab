# Friction

## 1. Cultivar checks ignored the installed genotype file - resolved

- **What the student previously had to do:** Supply `SBGRO048.CUL` beside the copied `UFGA7901.SBX` before running cultivar overrides, even though `list_cultivars("soybean")` could already list the installed stock cultivars.
- **Why it was awkward or wrong:** The cultivar check searched only beside the source FileX and did not find the installed genotype file. Unmodified genotype files must come from the installed DSSAT data directory rather than being bundled with the lesson.
- **Suggested change:** Resolve the stock cultivar file from the selected executable's data directory when no sibling cultivar file exists, consistently with `list_cultivars()`, and stage the necessary genotype files through the public API. Retain a supplied sibling override.
- **Classification:** Originally **blocking**, now **resolved: fixed by #353/#354**. PR #354 is not merged yet; validation uses its implementation from the sibling `wt-fix-cul` worktree. No DSSAT file was edited, no private API was used, and no unmodified genotype file was bundled or manually staged.

The original execution stopped before launching simulations with seven cultivar-check problems, each reporting that no soybean `.CUL` file existed beside the FileX.
With the fix, the prescribed comparison and exercise execute using the installed genotype files.

## Validation status

The case inputs are unchanged stock `Soybean/UFGA7901.SBX`, `Weather/UFGA7901.WTH` and `Soil/SOIL.SOL`, containing profile `IBSB910015` (Millhopper Fine Sand).
Treatment 1 is irrigated Bragg (`IB0001`), planted on 19 June 1979 at 47 plants/m², with 76 cm rows and 4 cm planting depth.
All scenarios retain its management, including water and nitrogen simulation.

Crop listing shows soybean code `SB`, model `CRGRO048`, and 56 cultivars in this installation.
Filtering codes `990001` through `990013` shows all 13 generic groups, including 000, 00 and 0.
The comparison uses groups 1, 3, 5, 6, 7, 8 and 10; the editable exercise defaults to groups 2, 4, 6, 8 and 10.

| Scenario | HWAM (kg/ha) | MDAT |
| --- | ---: | --- |
| base (Bragg) | 3114 | 1979-10-12 |
| MG 1 | 1763 | 1979-08-28 |
| MG 3 | 2392 | 1979-09-08 |
| MG 5 | 2912 | 1979-09-24 |
| MG 6 | 3154 | 1979-10-03 |
| MG 7 | 3114 | 1979-10-13 |
| MG 8 | 3004 | 1979-10-24 |
| MG 10 | 3338 | 1979-11-06 |

The exercise shows HWAM of 2011, 2750, 3154, 3004 and 3338 kg/ha for MG 2, 4, 6, 8 and 10, respectively, with MDAT of 1979-09-01, 1979-09-16, 1979-10-03, 1979-10-24 and 1979-11-06.

Every execution and test sets process-local `PYTHONPATH` to the absolute path of the sibling `wt-fix-cul/src` directory.
Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` use system temporary directories outside the worktree so the unchanged setup cell runs in the restricted environment.
The setup cell is byte-identical to the merged reference lessons and `SETUP_CELL` in `tests/test_course.py`.

Both consecutive runs of `python course/execute.py 03_cultivars` returned `03_cultivars: ok`.
All 11 code cells have execution counts and no error outputs; the comparison includes an inline bar plot.
`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all **15 tests**.

Commit preparation was attempted with only `course/03_cultivars` selected, for a commit carrying `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
Git could not create the worktree index lock (`Permission denied`), so the completed lesson remains uncommitted; the original issue/spec copies were left untouched.
