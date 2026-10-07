# Friction

No blocking dssatlab friction was found; the lesson uses only public API and unchanged stock inputs.

## 1. A planting-date factor needs the complete planting section — non-blocking

- **Student action:** Copy the stock planting details into a dictionary, then supply those details with each new date.
- **Why awkward:** Changing only the date still requires knowing the population, planting method, distribution, row spacing and depth, because a sweep replaces the whole section. The lesson preserves the stock values, including emergence population, row direction and sprout length.
- **Suggested change:** Add a public helper that reads a treatment's planting details into the experiment-data shape, with a guide example for a date-only sweep.

## 2. The sweep always includes an extra base run — non-blocking

- **Student action:** Recognize the unlabelled base row and select the seven dated scenarios before plotting.
- **Why awkward:** Seven factor values produce eight Summary rows, and the first date repeats the base planting date and yield. A student can count or plot the reference twice; the lesson shows all rows first and explicitly filters the base before plotting.
- **Suggested change:** Offer an optional way to omit the base run, retaining the current default, and show the base-row filtering pattern in the sweep guide.

## Validation notes

The case is stock `Maize/UFGA8201.MZX`, treatment 1, Gainesville maize cultivar McCurdy 84aa (`IB0035`), with `Weather/UFGA8201.WTH` and `Soil/SOIL.SOL` (profile IBMZ910014). Genotype files come from the installed DSSAT data directory.

Water and nitrogen simulation are disabled through experiment controls. The seven 14-day dates begin at the stock PDATE `82057` (26 February 1982); all other supplied planting details match the stock FileX.

The sandbox initially denied `connect()` writing saved configuration in the Windows profile. Validation uses process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` under system temporary directories outside the worktree, plus `PYTHONPATH` pointing to this worktree's `src`; the required setup cell is unchanged. This is an execution-environment restriction, not blocking student/API friction.

Both consecutive real-DSSAT executions print `02_planting_dates: ok`, including the self-contained 21-day exercise whose table and plot are now saved in the notebook. The exercise also passed in a fresh kernel with only the lesson identifier, setup and tools cells before it; no earlier simulation or sweep cells were needed. All 13 static course tests passed with `--basetemp` outside the worktree and `-p no:cacheprovider`.

The 14-day sweep's HWAM values, in date order, are 11859, 9254, 12321, 9958, 11640, 10217 and 7775 kg/ha. The standalone base and first sweep date both give 11859 kg/ha.

The 21-day exercise plants on 26 February, 19 March, 9 April, 30 April, 21 May, 11 June and 2 July 1982. Its HWAM values, in date order, are 11859, 12521, 9958, 9962, 7775, 9657 and 9589 kg/ha.

The 14-day yield curve zig-zags rather than declining smoothly: each sowing meets different 1982 weather during its season, while water and nitrogen simulation remain off. the lesson names no specific weather cause without showing supporting weather data.
