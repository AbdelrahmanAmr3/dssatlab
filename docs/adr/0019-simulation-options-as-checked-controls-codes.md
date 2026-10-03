# 0019: Simulation options as checked controls codes, and initial conditions off

Status: accepted (2026-10-02). Extends 0005's experiment data sections.

## Context

The DSSAT_Test course cases (gap rows F1 and F2) could not be rebuilt from experiment data: the
course FileX set PHOTO L, SYMBI N, TILL Y, CO2 R, RESID R and full initial-condition detail (root
mass, rhizobia, residue N and incorporation), and several use IC 0. `controls` only took
start_date, water, nitrogen, output_interval and years, and the FileX template writes fixed codes
(PHOTO C, TILL N, CO2 M).

DSSAT's own code list (`SIMULATION.CDE`, 4.8) and the stock FileX disagree: the list has CO2 W/M/D
and PHOTO C/R/L, while 16 stock FileX use CO2 R and 4 use PHOTO V.

## Decision

- New `controls` fields under plain names, each one DSSAT column: `symbiosis` SYMBI, `phosphorus`
  PHOSP, `potassium` POTAS, `tillage` TILL, `co2` CO2, `photosynthesis` PHOTO, `evapotranspiration`
  EVAPO, `infiltration` INFIL, `soil_organic_matter` MESOM, `soil_evaporation` MESEV, `soil_layers`
  MESOL, `residue` RESID. They are written like `water` and `nitrogen`: the treatment's controls level
  is copied and only named columns change.
- A field accepts the active (not `!`-commented) `SIMULATION.CDE` codes plus the codes stock DSSAT
  4.8 FileX use in that column. Letters are quoted, case-sensitive strings; `soil_layers` is the
  integer 1, 2 or 3. One table (field, block, column, codes) feeds the check and the writer.
- The FileX template keeps its fixed codes; a user who wants PHOTO L sets it.
- New optional `initial_conditions` fields write ICRT, ICND, ICRN, ICRE, ICREN, ICREP, ICRIP and
  ICRID; omitted ones write -99.
- `initial_conditions: "off"` (a quoted string) sets the treatment's IC level to 0 in the copy.
  `null` is not accepted, because an empty YAML key would silently turn initial conditions off.

## Consequences

- Generated weather, replicates (WTHER, NREPS, RSEED), pests and chemicals (DISES, CHEM), automatic
  management and rotation-component controls stay out until their own versions.
- A copied FileX whose controls level lacks a named column still fails with the existing
  "has no row with columns" error.
