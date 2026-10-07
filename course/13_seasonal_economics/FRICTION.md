# Friction: Seasonal analysis and economics

No blocking friction was found for this stock soybean case. The lesson uses public dssatlab API and unchanged stock DSSAT inputs.

## 1. Scenario management replaces the whole input — non-blocking

- **What the student must do:** Include the ten-season weather controls, constant CO₂ mode and seed in every scenario's management dictionary, even when only irrigation changes.
- **Why it is awkward:** A management override replaces the whole base management input. Omitting the repeated controls would restore the stock one-season measured-weather controls, making the comparisons inconsistent or invalid with a climate file alone.
- **Suggested change:** Add a guide example for irrigation-only seasonal scenarios that explicitly shows repeated controls and explains whole-input replacement.
- **Classification:** **non-blocking**; complete management dictionaries use the supported public API.

## 2. Price sections match FileX treatment numbers — non-blocking

- **What the student must do:** Keep all four options as scenarios of soybean treatment 1 so the unchanged `DEFAULT.PRI` soybean treatment 1 section applies to every option.
- **Why it is awkward:** Scenario labels are not price selectors; a student who creates new numbered treatments for the options cannot use the default price section for them. The crop and `TRNO` must match, and a used Summary quantity left missing makes net return missing even if its price is zero.
- **Suggested change:** Add a public price-file inspection helper that lists priced crop/treatment pairs, expected prices, and required quantities before running a seasonal comparison.
- **Classification:** **non-blocking**; the notebook displays `TRNO`, economic quantities, and missing counts, and links the copied price file.

## 3. A common seed does not give all options shared weather — non-blocking

- **What the student must do:** Treat these options as separate ten-season weather samples, even though they all use seed 1234.
- **Why it is awkward:** The seed reproduces each option's results, but weather differs between options in later seasons; differences between these ten-season samples cannot be attributed solely to irrigation. Saved `Weather.OUT` reports 0.0 mm rainfall for base versus 29.2 mm for Auto 40% on 1980 day 170.
- **Suggested change:** Document this limitation in the generated-weather and seasonal guides, and provide a public-API example using shared weather across options for an irrigation comparison.
- **Classification:** **non-blocking**; the lesson reports reproducible samples and explains the limitation without attributing their differences solely to irrigation.

## Case and validation

The case is stock `Soybean/UFGA7901.SBX`, treatment 1, Gainesville Bragg soybean (`IB0001`) on profile `IBSB910015` from stock `Soil/SOIL.SOL`.
The stock irrigation schedule contains nine applications totalling 113 mm; the three scenarios remove this schedule and use no irrigation, or automatic irrigation at 40% and 70% available-water thresholds in the top 30 cm.
Automatic irrigation refills to 100% with efficiency 0.75; the source FileX is unchanged.

The installed Gainesville daily weather has only nine consecutive seasons from the case's 1979 start (1979–1987; no 1988 file).
The ticket permits generated weather for a short stock station, so the lesson supplies unchanged `Weather/Climate/UFGA.CLI` and selects WGEN, ten seasons, seed 1234 and `co2="D"` through public controls.
[DSSAT CO₂ modes](https://github.com/DSSAT/dssat-csm-os/blob/v4.8.5.0/Weather/CO2VAL.for) define `D` as static CO₂; the inherited `M` time series previously varied from 336.8 to 351.8 ppm over these seasons.
With `D`, all six saved `Weather.OUT` files (four main options and two exercise options) hold CO₂ at 380.0 ppm across every season.
Season labels 1979–1988 describe generated weather, not observed historical weather.

The unchanged stock `Economic/DEFAULT.PRI` prices soybean treatment 1.
All 40 main comparison rows have numeric net returns; seed quantity `DWAP` is 100 kg/ha, and applied N quantities are zero.
Stock maize was excluded during case selection because its missing `DWAP` would prevent numeric returns at the required unchanged default prices; no quantities were filled or price components disabled.

| Option | Seasons | Mean HWAM (kg/ha) | HWAM sample sd (kg/ha) | Mean net return ($/ha) | Net-return sample sd ($/ha) | Missing returns |
|---|---:|---:|---:|---:|---:|---:|
| base: stock schedule | 10 | 3343.5 | 496.34 | 464.92 | 158.83 | 0 |
| Rainfed | 10 | 2912.7 | 817.43 | 496.06 | 261.58 | 0 |
| Auto 40% | 10 | 3755.9 | 170.44 | 639.59 | 108.76 | 0 |
| Auto 70% | 10 | 3922.6 | 119.21 | 506.23 | 87.00 | 0 |

The self-contained exercise defaults to a 60% threshold: mean HWAM 3894.2 kg/ha, irrigation 166.1 mm, and net return $577.09/ha (sample sd $94.84/ha), with no missing returns.
Prices are held at their expected values and CO₂ is constant; the reported risk is weather-driven variation within each option, without sampling price distributions.
The seed reproduces each option's results, but weather differs between options in later seasons; differences between these ten-season samples cannot be attributed solely to irrigation.

During original case selection, GitHub access was blocked, so the supplied `.lesson_issue.md` and `.course_spec.md` copies were read and left outside the lesson changes.
No `AGENTS.md` exists in the worktree; the ancestor repository's `AGENTS.md` was read along with `CONTEXT.md`, the course skeleton, both reference lessons, and the named guides.
The additional supporting soil and climate inputs are inventoried in `data/SOURCE.md`; unchanged genotype files come from the installed data directory.

The existing editable install points at the main checkout, so execution uses process-local `PYTHONPATH` set to this worktree's `src`.
Process-local `LOCALAPPDATA`, `IPYTHONDIR`, and `JUPYTER_RUNTIME_DIR` point to system-temp directories outside the worktree to allow discovery and kernel configuration in the restricted environment; the required setup cell is unchanged.
Pytest also uses an external system-temp `--basetemp` and disables its cache provider.

Both final consecutive `python course/execute.py 13_seasonal_economics` runs printed `13_seasonal_economics: ok`.
`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all 15 tests.
The inline box plot was visually inspected, the four stock input files were verified byte-for-byte against the installation, and the notebook contains no corrupted text or unit labels.
