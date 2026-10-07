# Friction: Seasonal analysis and economics

No blocking friction was found for this stock soybean case. The lesson uses public dssatlab API and unchanged stock DSSAT inputs.

## 1. Scenario management replaces the whole input — non-blocking

- **What the student must do:** Include the ten-season weather controls and seed in every scenario's management dictionary, even when only irrigation changes.
- **Why it is awkward:** A management override replaces the whole base management input. Omitting the repeated controls would restore the stock one-season measured-weather controls, making the comparisons inconsistent or invalid with a climate file alone.
- **Suggested change:** Add a guide example for irrigation-only seasonal scenarios that explicitly shows repeated controls and explains whole-input replacement.
- **Classification:** **non-blocking**; complete management dictionaries use the supported public API.

## 2. Price sections match FileX treatment numbers — non-blocking

- **What the student must do:** Keep all four options as scenarios of soybean treatment 1 so the unchanged `DEFAULT.PRI` soybean treatment 1 section applies to every option.
- **Why it is awkward:** Scenario labels are not price selectors; a student who creates new numbered treatments for the options cannot use the default price section for them. The crop and `TRNO` must match, and a used Summary quantity left missing makes net return missing even if its price is zero.
- **Suggested change:** Add a public price-file inspection helper that lists priced crop/treatment pairs, expected prices, and required quantities before running a seasonal comparison.
- **Classification:** **non-blocking**; the notebook displays `TRNO`, economic quantities, and missing counts, and links the copied price file.

## Case and validation

The case is stock `Soybean/UFGA7901.SBX`, treatment 1, Gainesville Bragg soybean (`IB0001`) on profile `IBSB910015` from stock `Soil/SOIL.SOL`.
The stock irrigation schedule contains nine applications totalling 113 mm; the three scenarios remove this schedule and use no irrigation, or automatic irrigation at 40% and 70% available-water thresholds in the top 30 cm.
Automatic irrigation refills to 100% with efficiency 0.75; the source FileX is unchanged.

The installed Gainesville daily weather has only nine consecutive seasons from the case's 1979 start (1979–1987; no 1988 file).
The ticket permits generated weather for a short stock station, so the lesson supplies unchanged `Weather/Climate/UFGA.CLI` and selects WGEN, ten seasons, and seed 1234 through public controls.
Season labels 1979–1988 describe generated weather, not observed historical weather.

The unchanged stock `Economic/DEFAULT.PRI` prices soybean treatment 1.
All 40 main comparison rows have numeric net returns; seed quantity `DWAP` is 100 kg/ha, and applied N quantities are zero.
Stock maize was excluded during case selection because its missing `DWAP` would prevent numeric returns at the required unchanged default prices; no quantities were filled or price components disabled.

| Option | Seasons | Mean HWAM (kg/ha) | HWAM sample sd (kg/ha) | Mean net return ($/ha) | Net-return sample sd ($/ha) | Missing returns |
|---|---:|---:|---:|---:|---:|---:|
| base: stock schedule | 10 | 3125.6 | 495.03 | 395.19 | 158.41 | 0 |
| Rainfed | 10 | 2710.0 | 781.58 | 431.20 | 250.11 | 0 |
| Auto 40% | 10 | 3522.0 | 202.52 | 564.74 | 119.23 | 0 |
| Auto 70% | 10 | 3713.8 | 123.09 | 434.07 | 85.87 | 0 |

The self-contained exercise defaults to a 60% threshold: mean HWAM 3673.6 kg/ha, irrigation 169.9 mm, and net return $500.85/ha (sample sd $99.64/ha), with no missing returns.
Prices are held at their expected values; the reported risk is weather-driven variation, without sampling price distributions.

GitHub access was blocked, so the supplied `.lesson_issue.md` and `.course_spec.md` copies were read and left outside the lesson changes.
No `AGENTS.md` exists in the worktree; the ancestor repository's `AGENTS.md` was read along with `CONTEXT.md`, the course skeleton, both reference lessons, and the named guides.
The additional supporting soil and climate inputs are inventoried in `data/SOURCE.md`; unchanged genotype files come from the installed data directory.

The existing editable install points at the main checkout, so execution uses process-local `PYTHONPATH` set to this worktree's `src`.
Process-local `LOCALAPPDATA`, `IPYTHONDIR`, and `JUPYTER_RUNTIME_DIR` point to system-temp directories outside the worktree to allow discovery and kernel configuration in the restricted environment; the required setup cell is unchanged.
Pytest also uses an external system-temp `--basetemp` and disables its cache provider.

Both final consecutive `python course/execute.py 13_seasonal_economics` runs printed `13_seasonal_economics: ok`.
`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all 15 tests.
The inline box plot was visually inspected, the four stock input files were verified byte-for-byte against the installation, and the notebook contains no `??`, `m?`, or ` ? ` corruption markers.
