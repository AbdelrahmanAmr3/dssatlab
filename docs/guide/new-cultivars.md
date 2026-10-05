# Define a new cultivar under your own code

Use experiment data to define a cultivar absent from the crop's `.CUL` file.
Give your code, an existing ecotype and every cultivar coefficient. dssatlab
adds one line at the end of the first `@VAR#` table in the simulation folder's
`.CUL` copy and points the treatment at your code. Source `.CUL`, `.ECO` and
`.SPE` files stay unchanged.

## Prepare the definition

Generate the [experiment template](experiment.md#generate-the-experiment-template)
with `dl.write_experiment_template("experiment.yaml")`. In its cultivar section,
choose an unused code and uncomment `ecotype`, `name` and `coefficients`.
The following maize definition copies IB0035's values; it demonstrates the file
writing and does not represent a calibrated cultivar. Save it as `new.yaml`:

```yaml
treatments:
  1:
    cultivar:
      crop: "MZ"
      code: "NC0001"
      ecotype: "IB0001"
      name: "New maize"
      coefficients: {P1: 259, P2: 1.193, P5: 947.1, G2: 924.3, G3: 8.168, PHINT: 43}
```

Use the coefficient names after `ECO#` in the **first** `@VAR#` table of your
crop's `.CUL`. Every coefficient is required, with no defaults. Other models
have different names and column widths; the maize example cannot be reused
for soybean or rice. A missing-coefficient problem lists all omitted names;
unknown names list the valid names. Values must be finite numbers that fit
their fixed-width columns without exponent notation.

| Field | Rule for a new cultivar |
|---|---|
| `crop` | The treatment's two-letter DSSAT crop code, such as `MZ` |
| `code` | Six printable ASCII characters without spaces; absent from every readable row of the crop's `.CUL`, including later tables. Cannot start with `!`, `@`, `*` or `$`. `DL0001`–`DL9999` are reserved for changed cultivars. |
| `ecotype` | Required: six printable ASCII characters without spaces, listed in the `.ECO` with the `.CUL`'s stem when that file exists |
| `name` | Optional: at most 16 printable ASCII characters, including spaces; defaults to `code` |
| `coefficients` | Required: every coefficient after `ECO#` in the first table, using exact names and DSSAT's own units |

The first table must have `ECO#` in columns 31–36. For a copied FileX, supply
the crop's one `.CUL` and its required `.ECO`/`.SPE` companions beside the FileX.
For a FileX template, they come from the DSSAT data directory.
Rice (`RICER048`) has no `.ECO`, so its ecotype is checked only for format.
For an unrecognized model without an `.ECO`, only the format is checked too;
a recognized model requiring `.ECO` reports a missing-file problem.

## Run with a copied FileX

Use the definition as the existing `management` argument (which accepts all
experiment data). Prepare `weather.csv` in the weather template shape with
coverage for the FileX dates, and its soil and genotype companions:

```python
import dssatlab as dl

sim = dl.Simulation(
    filex="UFGA8201.MZX", treatment=1, weather="weather.csv",
    management="new.yaml", executable=r"C:\DSSAT48\DSCSM048.EXE",
)
problems = sim.check()
if not problems:
    result = sim.run()
    print(result.summary())
```

An unknown FileX cultivar such as soybean IB1000 works the same way: define
that exact code with a soybean ecotype and all soybean coefficients in
experiment data. Missing original course coefficients remain missing inputs;
substituting stock values is an approximation, not course equivalence.

## Run from a FileX template

Keep an installed cultivar such as IB0035 in the maize FileX template and
apply `new.yaml` to replace it for treatment 1. Prepare `filex.yaml`,
`weather.csv` and `soil.csv` using the [Simulation guide](simulation.md):

```python
sim = dl.Simulation(
    filex_template="filex.yaml", weather="weather.csv", soil="soil.csv",
    management="new.yaml", executable=r"C:\DSSAT48\DSCSM048.EXE",
)
problems = sim.check()
if not problems:
    result = sim.run()
    print(result.summary())
```

Both paths run all checks before writing. A new cultivar keeps your code;
an existing code with `coefficients` writes a changed cultivar under a
`DLnnnn` code. For an existing code, omit `ecotype` and `name`, or choose a
new code to define a new cultivar.

Scenarios and [sweeps](sweeps.md) get separate simulation folders, so each
can define the same new code differently. Within one template experiment,
repeated definitions of a code must agree. Rotation components reject
`ecotype`, `name` and `coefficients`. New ecotypes, species edits and listing
new entries through `list_cultivars()` are outside this feature.

The four maize, soybean and rice proofs and the FileX level bug they found
are recorded in [ADR 0030](../adr/0030-new-cultivars-under-the-users-own-code.md#real-dssat-proof).
