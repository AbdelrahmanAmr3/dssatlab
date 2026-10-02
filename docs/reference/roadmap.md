# Roadmap

What each version added, and what is deliberately not built yet. The full history is in the [changelog](../changelog.md).

## Done

| Version | What it does |
|---|---|
| 0.1 | Detect the environment, find and check a DSSAT executable (`connect()`), build DSSAT on Linux (`install()`). |
| 0.2 | Run one existing FileX with `run()`, in a new run directory beside it. |
| 0.3 | A `Simulation` from your own weather data: a fixed weather template, strict `check()`, a generated DSSAT weather file, `run()`. |
| 0.3.1 | A `Simulation` with your own soil data: a fixed soil template, strict `check()`, a generated `SOIL.SOL` soil file, `run()`. |
| 0.3.2 | A `Simulation` with your own management data: a fixed YAML management template or dict, strict checks, FileX section writing (planting, irrigation, fertilizer), `run()`. |
| 0.4 | Read and plot DSSAT outputs: `read_summary()`, `read_plant_growth()`, `to_dataframe()`, and `plot_plant_growth()`. Access via `result.summary()`, `result.plant_growth()`, and `result.plot()`. |
| 0.5 | Run all or selected FileX treatments and what-if scenarios in separate folders (`run_treatments()`), scenario template (`write_scenario_template()`), merge summaries (`combine_summaries()`), and read three more output files: `SoilWat.OUT` (`read_soil_water()`), `PlantN.OUT` (`read_plant_nitrogen()`), and `Weather.OUT` (`read_weather()`). Access via `result.soil_water()`, `result.plant_nitrogen()`, and `result.weather()`. |
| 0.6 | Experiment data: `cultivar`, `initial_conditions` and `controls` sections beside planting, irrigation and fertilizer, applied to a copy of an existing FileX, and `write_experiment_template()`. Proven on real DSSAT with maize and wheat. |
| 0.7 | FileX template: write a FileX for one field, one treatment and one crop (maize, wheat) from your own weather and soil, `write_filex_template()`; scenario name in `TNAM`; experiment data sets the station and soil ID of the copied FileX. Proven on real DSSAT. |
| 0.8 | Observed data: a commented CSV template (`write_observed_template()`), comparison with Summary and Plant growth (`evaluate()`), an `Evaluation` with paired errors, RMSE, mean bias and Willmott's d-index, and a 1:1 scatter (`plot_evaluation()`). DSSAT's own column names and units; all observed data and matching problems in one `DSSATCheckError`. |
| 0.9 | Read FileA/FileT as observed data (`read_dssat_observed()`), overlay measurements on Plant growth (`plot_observed()`), and read the DSSAT evaluation (`read_dssat_evaluation()`, `result.dssat_evaluation()`). No FileA/FileT is written (ADR 0008). |
| 0.10 | Ten template crops: maize, wheat, rice, soybean, potato, sorghum, pearl millet, barley, peanut and dry bean; potato planting fields and harvest date; `list_crops()` and `list_cultivars()`. |
| 0.11 | Multi-treatment experiments from scratch: FileX template `treatments` list, experiment data per treatment number, whole experiment written to simulation folder, and `run_treatments(filex_template=...)`. |
| 0.11.1 | Several fields from scratch: FileX template `treatment_fields` list, per-field `weather=` and `soil=` dicts, shared station and soil ID rules, and one `SOIL.SOL` with all profiles. |
| 0.12 | Seasonal analysis: experiment data controls `years` (NYERS), weather coverage check across seasons, per-season Summary rows, and `summarize_seasons()`. |
| 0.13 | Sequence analysis: multi-year crop rotations from a sequence FileX, batch file and mode Q (`Simulation.run()`), pre-run sequence checks, controls `years` and `start_date`, and `summarize_seasons()` per rotation component. |
| 0.13.1 | A rotation from the FileX template: 2 to 9 components (crops and fallows), DSSAT day-of-year date checks, cycle NYERS by default, controls `years`, write `.SQX`, and genotype file copying. |
| 0.13.2 | Experiment data per rotation component keyed by R: planting, cultivar, fertilizer and irrigation for copied and template sequences, component period checks, and edits applied in every cycle through Simulation, run_treatments and scenarios. |

## Deliberately not built yet

Each of these is a later phase, kept out so the package stays small and each step can be proven on real DSSAT.

| Not built | Why it waits |
|---|---|
| Full FileX or other output parsing | Six output files (Summary.OUT, PlantGro.OUT, SoilWat.OUT, PlantN.OUT, Weather.OUT, Evaluate.OUT) are read as of 0.9; reading other output files (ET.OUT, OVERVIEW.OUT, etc.) and full FileX parsing wait for later phases. |
| Multi-field FileX with copied FileX, more crops | Several fields from scratch are supported as of 0.11.1; multiple fields for copied FileX and further crops wait for later phases. |
| Other management operations | Planting, irrigation, and inorganic fertilizer are supported; operations like tillage, organic amendments, harvest, and chemical applications wait for later phases. |
| Choosing a soil profile from DSSAT's own soil files | Only the user's own single-profile soil template is supported; selecting from existing `.SOL` libraries is a later step. |
| Unit converters | The weather template is in DSSAT's own units, and nothing is converted silently. |
| Gap filling or any automatic repair | `check()` reports problems and the user decides how to treat missing data. |
| Warnings | `check()` either reports a problem or passes; there is no softer level yet. |
| Optional weather columns beyond the template | The template is one fixed shape so it can be checked strictly. |
| Model selection | Not needed to run one FileX treatment. |
| Parallel execution, resume, and timeouts | Multi-treatment and scenario runs execute sequentially in isolated folders; parallel execution, resuming interrupted runs, retries, and timeouts wait for later phases. |
| Managed cleanup | Removing managed installs is out of scope for now. |
