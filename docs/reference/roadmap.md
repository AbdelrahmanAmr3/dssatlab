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

## Deliberately not built yet

Each of these is a later phase, kept out so the package stays small and each step can be proven on real DSSAT.

| Not built | Why it waits |
|---|---|
| Full FileX or output parsing | `run()` returns the files DSSAT wrote and does not read them. Parsing needs its own design. |
| FileX authoring | Users bring an existing FileX; building experiments from Python is a later step. |
| Other management operations | Planting, irrigation, and inorganic fertilizer are supported; operations like tillage, organic amendments, harvest, and chemical applications wait for later phases. |
| Choosing a soil profile from DSSAT's own soil files | Only the user's own single-profile soil template is supported; selecting from existing `.SOL` libraries is a later step. |
| Unit converters | The weather template is in DSSAT's own units, and nothing is converted silently. |
| Gap filling or any automatic repair | `check()` reports problems and the user decides how to treat missing data. |
| Warnings | `check()` either reports a problem or passes; there is no softer level yet. |
| Optional weather columns beyond the template | The template is one fixed shape so it can be checked strictly. |
| Model selection | Not needed to run one FileX treatment. |
| Batch mode and timeouts | One `Simulation` is one treatment; more than one per object is later. |
| Managed cleanup | Removing managed installs is out of scope for now. |
