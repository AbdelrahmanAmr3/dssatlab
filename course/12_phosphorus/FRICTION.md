# Friction: Phosphorus

No blocking friction was found: real DSSAT produces different grain yields at the requested P rates using the public dssatlab API.
All stock inputs are unchanged, and no genotype files or extra case inputs are bundled.

## 1. Reading the inherited soil analysis needs FileX text inspection — non-blocking

- **What the student must do:** Find treatment 7's SA level and read its soil-analysis rows from the copied FileX before comparing P rates.
- **Why it is awkward:** There is no public helper returning an existing treatment's soil analysis in the experiment-data shape. A short text inspection is needed to show the starting extractable P and identify the inherited level; the notebook reads but never edits the FileX.
- **Suggested change:** Provide a public treatment-inspection helper exposing the selected soil analysis, its date, method codes and layers, with DSSAT units.
- **Classification:** **non-blocking**; omission of `soil_analysis` preserves SA 7 in every simulation.

## 2. Varying P requires a complete fertilizer schedule — non-blocking

- **What the student must do:** Include the two unchanged N applications in each P-rate schedule, along with the P event, dates, material codes, application codes and depths.
- **Why it is awkward:** A fertilizer sweep replaces the whole section. Supplying only a P event would remove the stock N applications, so the student must explicitly retain 60 + 60 kg N/ha to isolate the P-rate comparison.
- **Suggested change:** Add a public helper to inspect an inherited fertilizer schedule and a teaching example for changing one nutrient while preserving the other events.
- **Classification:** **non-blocking**; all three complete schedules are visible in the notebook and Summary confirms NICM 120 kg N/ha throughout.

## 3. The sweep adds a duplicate zero-P base run — non-blocking

- **What the student must do:** Recognize the `base` row and exclude it when plotting the labelled P rates.
- **Why it is awkward:** Three factor values produce four Summary rows, and both the base and labelled zero-P scenario yield 929 kg/ha. Plotting all rows would show the reference twice.
- **Suggested change:** Offer an option to omit the base run while retaining the existing default, and document the filtering pattern.
- **Classification:** **non-blocking**; the notebook shows every row before filtering the base from the plots.

## 4. A successful stock-case run contains consequential warnings — non-blocking

- **What the student must do:** Open `WARNING.OUT` to learn about DSSAT's adjustments despite successful checks and execution.
- **Why it is awkward:** At all three P rates, DSSAT changes initial residue P from 0.100% to 0.256% to maintain its allowed C:P ratio, warns about very low nutrient concentration in residues, and forces the two deep N applications into the second soil layer. These warnings are not surfaced by the public run result.
- **Suggested change:** Expose a public warning summary on the run result, including model adjustments, and make it available in teaching examples.
- **Classification:** **non-blocking**; complete yields and growth output are available, and the notebook displays a compact warning excerpt without modifying the case.

## Validation

The case is stock `Maize/GHWA0401.MZX`, Wa, Ghana, treatment 7 (N120 P0), cultivar OBATANPA (`GH0010`). Inputs are stock `Weather/GHWA0301.WTH`, `Weather/GHWA0401.WTH` and `Soil/GH.SOL`, containing soil profile `GHWA040001`.
The simulation starts on 10 October 2003 and plants on 17 June 2004; both yearly weather files are required. Every scenario retains SA 7 and IC 7, rather than switching among the stock treatments with their different starting soil P and residue histories.

SA 7 has extractable P of 2.3, 1.9, 2.4, 2.3 and 2.3 mg/kg at bottom depths 5, 20, 40, 60 and 90 cm, respectively. Its analysis date is 10 October 2003 and P method is SA002. The bundled FileX notes describe these starting values as estimates based on 2003 measurements and subsequent simulations.

Phosphorus simulation is explicitly enabled through `controls.phosphorus: "Y"`; stock water and nitrogen simulation stay on. Elemental P is applied on 15 June 2004, using stock FE013/AP004 placement at 10 cm. Stock FE005/AP007 N applications remain at 5 cm on 5 and 15 July, 60 kg N/ha each.

With the installed DSSAT 4.8.5.017 pre-release executable, PICM 0, 20 and 40 kg P/ha give HWAM 929, 4232 and 4171 kg/ha and CWAM 1998, 12928 and 13214 kg/ha, respectively. NICM is 120 kg N/ha in every row. The 40-P grain yield is 61 kg/ha below 20-P even though biomass rises; the lesson does not infer a mechanism or an optimal P rate from these outputs.
The default self-contained exercise compares 0 and 30 kg P/ha: HWAM is 929 and 4195 kg/ha, a gain of 3266 kg/ha.

Validation uses process-local `PYTHONPATH` pointing to this worktree's `src`, because the editable install resolves to the main checkout. `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` point to system-temp locations outside the worktree so the exact shared setup can save discovery configuration and start a kernel in this restricted environment. The setup cell is byte-identical to `tests/test_course.py`'s `SETUP_CELL`.

Both final consecutive `python course/execute.py 12_phosphorus` runs printed `12_phosphorus: ok`. All 15 tests passed with `python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider`; no pytest temporary folder was created in the worktree.
The Your turn cell also executed successfully in a fresh kernel with only the LESSON, exact setup and tools cells before it, reproducing the 0/30-P comparison above. Both saved inline plots were visually checked, the four stock inputs were verified byte-for-byte against the installation, and the notebook was checked for corrupted icons, units and title separators.
