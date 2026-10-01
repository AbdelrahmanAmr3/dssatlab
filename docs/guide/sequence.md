# Sequence analysis

A single-crop or seasonal simulation evaluates one crop grown in isolated seasons. In crop rotations, however, crops are grown one after another on the same field over multiple years (for example, dry bean followed by fallow, followed by soybean and fallow), with the soil water and nitrogen state carried over continuously from one crop to the next. In DSSAT, this is a **sequence analysis**.

In `dssatlab`, you run a sequence simply by creating a `Simulation` for a treatment that defines a sequence in an existing FileX. `dssatlab` detects the rotation components automatically, checks all inputs, writes a batch file (`DSSBatch.v48`) into the simulation folder, and runs DSSAT in sequence mode (`Q`) without needing any extra flags ([ADR 0013](../adr/0013-sequences-run-in-mode-q-through-a-batch-file.md)).

## What is a sequence in a FileX?

In a standard FileX (`*.SQX` or other experiment files), a sequence is a treatment number (`N`) that appears on multiple rows in the `*TREATMENTS` section. Each row represents one **rotation component**, distinguished by its rotation component number in the `R` column:

```text
*TREATMENTS
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 1 0 Bean                       1  1  0  1  1  1  0  0  0  0  0  0  1
 1 2 1 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  1  2
 1 3 1 0 Bean                       1  1  0  0  2  1  0  0  0  0  0  0  3
 1 4 1 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  2  2
 1 5 1 0 Soybean                    3  1  0  0  1  1  0  0  0  0  0  0  4
 1 6 1 0 Fallow                     2  1  0  0  0  0  0  0  0  0  0  3  2
```

Here, treatment 1 is a sequence of 6 rotation components: bean (`BN`), fallow (`FA`), bean (`BN`), fallow (`FA`), soybean (`SB`), and fallow (`FA`). Each component has its own cultivar (`CU`), planting (`MP`), irrigation (`MI`), and simulation controls (`SM`) levels, but all components grow on the same field (`FL 1`).

DSSAT runs the components sequentially: component 1 runs until harvest, component 2 (fallow) begins the very next day carrying over the soil water and nitrogen, and the cycle continues until the sequence's duration has elapsed.

## Run a sequence with `Simulation`

To run a sequence, pass the FileX path and sequence treatment number to `dl.Simulation`, along with your daily weather and soil data:

```python
import dssatlab as dl

sim = dl.Simulation(
    "UFGA7804.SQX",
    treatment=1,
    weather=weather_rows,
    soil="soil.csv",  # optional soil template; without it the sibling .SOL files are copied
    management={"treatments": {1: {"controls": {"years": 9}}}},
)

# 1. Run strict pre-run checks
problems = sim.check()
# Report: "FileX: treatment 1 is a sequence of 6 rotation components (R 1-6: BN, FA, BN, FA, SB, FA); it runs in DSSAT's sequence mode."

# 2. Run the simulation
result = sim.run()
```

When `sim.run()` executes, `dssatlab` writes `DSSBatch.v48` into the simulation folder and runs `<executable> Q DSSBatch.v48` with standard input closed, keeping your original FileX folder untouched.

## Sequence checks

Because DSSAT's sequence mode has strict formatting and execution constraints, `dssatlab` validates all sequence requirements before writing files or running DSSAT:

1. **FileX filename length**: DSSAT's sequence mode requires the FileX filename to be exactly 12 characters (8.3 format, e.g. `UFGA7804.SQX`). Shorter or longer names cause DSSAT to crash:
   ```text
   A sequence runs in DSSAT's sequence mode, which needs a FileX filename of exactly 12 characters (8 plus the extension, like UFGA7804.SQX); 'SEQ1.SQX' has 8. Rename the FileX.
   ```
2. **Distinct positive rotation component numbers (`R`)**: Every component row for the treatment must have a distinct, positive integer in column `R`:
   ```text
   Treatment 1 has rotation components R 1, 1: give each row of a sequence its own R number.
   ```
3. **Single field (`FL`)**: Every rotation component must use the same field number, ensuring weather and soil data match:
   ```text
   Treatment 1 is a sequence whose components use fields 1 and 2; dssatlab writes one weather file and one soil profile, so give every component the same field (FL).
   ```
4. **`NREPS` must be 1**: With measured daily weather, running multiple replicates repeats identical rows:
   ```text
   FileX NREPS 5 for sequence treatment 1: with measured weather every replicate repeats the same rows. Set NREPS to 1.
   ```
5. **Weather coverage through the sequence's last day**: Weather data must continuously cover the simulation start date through the sequence's last day. Under DSSAT's sequence end rule (`CSM.for`), the sequence ends at:
   `(start year + years)` at the start date's day of year, minus one day.
   For example, if the sequence starts on `1978-04-20` and runs for `NYERS 10` (or `controls: years: 10`), the end date is `1988-04-18` (since 1988 is a leap year). If weather data ends earlier (e.g. `1987-12-31`), `check()` reports:
   ```text
   FileX NYERS 10: the sequence runs from 1978-04-20 through 1988-04-18, after the weather data ends (1987-12-31). Supply weather through 1988-04-18, or fewer years.
   ```
   If `years` was set via experiment data controls, the prefix is `Controls years 10: ...`.
6. **Experiment data restrictions**: For a sequence, experiment data currently accepts only `controls` with `years` and/or `start_date` (applied to a copy of the first component's controls level):
   ```text
   Treatment 1 is a sequence of 6 rotation components; experiment data for a sequence takes only controls years and start_date. Edit the components in the FileX for other changes.
   ```
   To modify cultivars, planting dates, or fertilizer for individual rotation components, edit them directly in the FileX.

## The WTHER and FNAME traps in DSSAT sample sequence files

DSSAT ships sample sequence files (such as `UFGA7804.SQX`) that contain configuration settings that silently break automated runs with your own data:

- **`WTHER W` in `*SIMULATION CONTROLS -> METHODS`**: Sets weather generation mode to `W` (weather generator), causing DSSAT to generate artificial weather from climate files (`UFGA.CLI`) and silently ignore your supplied weather data.
- **`FNAME Y` in `*SIMULATION CONTROLS -> OUTPUTS`**: Tells DSSAT to name output files after the experiment name (such as `UFGA7804.OSU`) instead of standard names like `Summary.OUT`, leaving no summary file for `dssatlab` to read.
- **`NREPS 5` in `*SIMULATION CONTROLS -> GENERAL`**: Runs 5 replicates of identical simulated rows.

`dssatlab` checks for these settings in every copied FileX (whether a sequence or not) and raises a `DSSATCheckError`:

```text
FileX WTHER 'W' in controls level 1 (treatment 1): DSSAT would generate weather and ignore the weather data supplied. Set WTHER to M.
FileX FNAME 'Y' in controls level 1 (treatment 1): DSSAT would name its output files after the experiment (UFGA7804.OSU) instead of Summary.OUT, which dssatlab reads. Set FNAME to N.
```

### How to fix a copied FileX

Before running a copied DSSAT sequence file, edit the text or modify a copy using simple string replacements:

```python
from pathlib import Path

path = Path("UFGA7804.SQX")
text = path.read_text(encoding="latin-1")

# 1. Set measured weather in all METHODS rows: W -> M
text = text.replace(" ME              W ", " ME              M ")

# 2. Set standard output filenames in all OUTPUTS rows: Y -> N
text = text.replace(" OU              Y ", " OU              N ")

# 3. Set NREPS to 1 in level 1's GENERAL row: 5 -> 1
text = text.replace(" 1 GE             10     5 ", " 1 GE             10     1 ")

path.write_text(text, encoding="latin-1")
```

Once updated, the FileX passes all checks.

## Summary rows and rotation components

In a sequence analysis, `result.summary()` returns one row per rotation component run:

- `R#`: The rotation component number (e.g. 1 to 6).
- `CR`: The crop code for that component (`BN` for dry bean, `FA` for fallow, `SB` for soybean).
- `HWAM`: Harvested yield (kg/ha) for that component run (`0` or missing for fallow).
- `PDAT`, `MDAT`: Planting and maturity dates for each individual crop cycle.

```python
import pandas as pd

summary_df = pd.DataFrame(result.summary())
print(summary_df[["R#", "CR", "PDAT", "MDAT", "HWAM"]])
```

### Continuous soil water series

While `Summary.OUT` produces separate rows for each component run, daily outputs like `SoilWat.OUT` (`result.soil_water()`) and `Weather.OUT` (`result.weather()`) produce **one continuous series** spanning the entire multi-year sequence. DSSAT writes them only when the first component's OUTPUTS row asks for them (`WAOUT Y` for soil water, `GROUT Y` for plant growth); `UFGA7804.SQX` ships with both set to `N`. You can inspect or plot the carry-over of soil water between successive crops across years:

```python
soil_water = dl.to_dataframe(result.soil_water())
# Continuous daily series from the start date across all rotation cycles
```

## Summarise sequence statistics with `summarize_seasons`

When you pass sequence summary rows to `summarize_seasons()`, `dssatlab` automatically groups rows by `(scenario, treatment, component)`:

```python
stats = dl.summarize_seasons(result.summary(), variables=["HWAM"])
df = dl.to_dataframe(stats)
print(df[["component", "crop", "variable", "seasons", "mean", "min", "max"]])
```

Output for `UFGA7804.SQX` treatment 1 with Gainesville weather 1978-1987 and controls `years: 9` (28 component runs):

```text
   component crop variable  seasons     mean   min   max
0          1   BN     HWAM        5   903.20   508  1754
1          2   FA     HWAM        5     0.00     0     0
2          3   BN     HWAM        5  1039.80   356  1534
3          4   FA     HWAM        5     0.00     0     0
4          5   SB     HWAM        4  3123.25  1855  3951
5          6   FA     HWAM        4     0.00     0     0
```

Grouping by `component` ensures that fallow zero yields do not dilute crop yields, and different crops in the rotation (such as bean and soybean) are summarized separately.

## Run several sequences with `run_treatments`

If a FileX contains multiple sequences (for example, comparing a 2-year rotation in treatment 1 with a 3-year rotation in treatment 2), calling `run_treatments()` with `treatments=None` automatically identifies each distinct treatment number once and executes each sequence in its own simulation folder:

```python
results = dl.run_treatments(
    filex="ROTATIONS.SQX",
    weather=weather_rows,
)

combined = dl.combine_summaries(results)
all_stats = dl.summarize_seasons(combined, variables=["HWAM"])
```

Each sequence is simulated independently in DSSAT sequence mode, and `combine_summaries()` preserves the scenario, treatment, rotation component (`R#`), and crop (`CR`) for analysis across rotations.
