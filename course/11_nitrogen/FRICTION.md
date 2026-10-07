# Friction: Nitrogen rates and N fixation

No blocking dssatlab friction was found.
The lesson uses only the public API and unchanged stock input files; experiment data edits the simulation copies.

## 1. A sweep includes duplicate zero-N baselines — non-blocking

- **Student action:** Filter `scenario != "base"` before comparing the five N rates for each water regime.
- **Why awkward:** Five rates over two treatments return twelve Summary rows, including two base rows whose zero-N inputs repeat the labelled zero-N scenarios.
- **Suggested change:** Offer an optional way to omit the base runs, and show the filtering pattern in the sweep guide.
- **Classification:** **non-blocking**; the notebook explicitly explains and removes the repeated rows.

## 2. Stock treatment names do not establish the water regime — non-blocking

- **Student action:** Inspect the stock FileX irrigation levels and Summary's `IRCM`, rather than assuming that RAINFED or IRRIGATED in a treatment name describes its events.
- **Why awkward:** Maize treatment 1 labelled RAINFED has a 13 mm irrigation; peanut treatment 1 labelled IRRIGATED points at MI 0 and applies no irrigation. A student could misinterpret the N comparison from the names alone.
- **Suggested change:** Add a public treatment-management preview showing inherited irrigation and fertilizer schedules and their totals.
- **Classification:** **non-blocking**; `irrigation: []` makes the maize comparison rainfall-only through the documented API, and the peanut table shows zero irrigation in both runs.

## 3. Fractional fertilizer amounts are rounded in DSSAT inputs — non-blocking

- **Student action:** Compare the requested rate with `NICM` and document the simulated rate after DSSAT rounds each application.
- **Why awkward:** The exercise requests 75 kg N/ha split into two 37.5 kg N/ha applications. dssatlab's generated FileX retains 37.5 for each event, but DSSAT rounds each to 38 while preparing `DSSAT48.INP`, so both simulations apply 76 kg N/ha; the nitrogen balance records 76.00 and `Summary.OUT` reports `NICM = 76`.
- **Suggested change:** Document DSSAT's input rounding and its effect on simulated rates in the fertilizer guide, with a fractional-rate example and the `NICM` comparison. The rounding occurs during [DSSAT's internal input preparation](https://github.com/DSSAT/dssat-csm-os/blob/v4.8.5.0/InputModule/optempy2k.for#L385-L395).
- **Classification:** **non-blocking**; the notebook shows requested and applied N, explains input rounding, and makes no edits to DSSAT files.

## Case and results

The maize case uses stock `Maize/UFGA8201.MZX`, treatments 1 and 3, cultivar McCurdy 84aa (`IB0035`), with `Weather/UFGA8201.WTH` and profile `IBMZ910014` in `Soil/SOIL.SOL`.
Water and nitrogen simulation remain on; treatment 1's irrigation is removed and treatment 3 keeps its stock schedule (264 mm).
The stock fertilizer schedules are replaced by 0, 50, 100, 150 and 200 kg N/ha, split equally between 7 April and 17 May 1982 as ammonium nitrate (`FE001`), broadcast without incorporation (`AP001`), with a 10 cm depth field.

| N rate (kg N/ha) | Rainfed HWAM (kg/ha) | Irrigated HWAM (kg/ha) |
| --- | --- | --- |
| 0 | 602 | 620 |
| 50 | 2073 | 4419 |
| 100 | 1832 | 7019 |
| 150 | 1872 | 8951 |
| 200 | 2091 | 9896 |

The rainfed curve is uneven; the notebook describes its smaller N response as consistent with water limitation without claiming that yield alone explains the dip.

The peanut case uses stock `Peanut/UFGA7901.PNX`, treatment 1, Florunner (`IB0002`), with `Weather/UFGA7901.WTH` and profile `IBPN910015` in the same stock soil file.
Water and nitrogen simulation remain on, no fertilizer is supplied, and stock MI 0 supplies no irrigation in either run.
Only the symbiosis control differs between the two simulations.

| Symbiosis | HWAM (kg/ha) | CNAM (kg N/ha) | Final NFXC (kg N/ha) |
| --- | --- | --- | --- |
| Y, fixation on | 4423 | 326 | 307.3 |
| N, fixation off | 462 | 26 | 0.0 |

The editable 75 kg N/ha exercise yields 2119 kg/ha rainfed and 5823 kg/ha irrigated, gains of 1517 and 5203 kg/ha over their zero-N baselines; both simulations apply 76 kg N/ha after DSSAT rounds each application to 38 kg N/ha.

## Execution environment

GitHub access was blocked, so the supplied local issue and parent-spec copies were read; neither is included in the lesson.
The existing editable install resolves to another checkout, so validation sets process-local `PYTHONPATH` to this worktree's `src`.
Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` use system-temp directories outside the worktree, allowing the exact setup cell to run without changing it.

Genotype files are supplied by the installed DSSAT data directory; all five bundled input files are listed exactly once in `data/SOURCE.md`.

## Validation

Both final consecutive `python course/execute.py 11_nitrogen` runs printed `11_nitrogen: ok` against real DSSAT.
The executed notebook includes two inline matplotlib plots, and both were visually checked for labels, units and readable dates.
The self-contained Your turn cell also passed in a fresh kernel after only the lesson identifier, exact setup and tools cells.

`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all 15 tests.
The setup cell matches `SETUP_CELL` exactly, all stock inputs match their installed source bytes and decode as UTF-8, and the notebook has no `??`, `m?` or ` ? ` corruption matches.
No pytest temporary folder was created in the worktree.
