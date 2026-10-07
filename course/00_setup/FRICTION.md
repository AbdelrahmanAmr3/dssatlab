# Friction: Setup on Colab or Windows

No blocking dssatlab friction was found in the Windows setup lesson.
There is no crop case, no bundled input data and no DSSAT simulation in Lesson 00.
All dssatlab calls use the public API.

## 1. Discovery displays a personal path - non-blocking

- **What the student must do:** assign `dl.detect()` to a variable and display the operating system, architecture and executable filename separately; likewise assign `connect()` and `install()` rather than displaying their returned paths.
- **Why it is awkward:** displaying the discovery dictionary or a returned executable path can expose the student's user name through a home or managed-cache directory.
- **Suggested change:** add a public discovery display helper with an option to hide home-directory components and use it in introductory examples.
- **Classification:** **non-blocking**; the notebook displays the filename only and explains that the actual `dssat_path` is a `Path` or `None`.

## 2. The unsupported-platform error still names v0.1 - non-blocking

- **What the student must do:** interpret the `DSSATInstallError` message as a platform restriction and use an existing Windows installation with `connect()`.
- **Why it is awkward:** the message says installation is supported only on Linux/Colab "in v0.1"; the obsolete version qualifier can suggest a later version might enable Windows builds.
- **Suggested change:** remove the obsolete version qualifier and explicitly direct Windows users to install DSSAT 4.8 and connect to it.
- **Classification:** **non-blocking**; the notebook guards the build with the Colab condition and explains the message in its troubleshooting note.

## 3. Saved config requires a writable profile - non-blocking

- **What the student must do:** use a writable application-data location when their execution environment restricts writes to the normal Windows profile.
- **Why it is awkward:** `connect()` always saves the selected executable, even if discovery already found it; a restricted environment needs additional configuration unrelated to crop modelling.
- **Suggested change:** avoid rewriting an unchanged saved executable and report an actionable DSSAT error if config cannot be saved.
- **Classification:** **non-blocking**; validation directs process-local `LOCALAPPDATA` to system temp, as in the reference lessons, without changing package code or DSSAT files.

## 4. Pip and repository-clone failures hide diagnostics - non-blocking

- **What the student must do:** diagnose a failed Colab package installation or repository clone from a `CalledProcessError` without seeing the captured diagnostics in cells 4 and 7.
- **Why it is awkward:** both subprocess calls use `capture_output=True` with `check=True`; on failure, captured stderr is not displayed, so beginners cannot see the underlying pip or git problem.
- **Suggested change:** display captured stderr on failure, while keeping successful installation and clone output quiet.
- **Classification:** **non-blocking**; the Windows route skips these guarded commands, and Colab validation remains pending.

## Colab validation remains pending - non-blocking

- **What the student must do:** on Colab, install the pinned course package and build DSSAT in the runtime using the guarded cells.
- **Why it is awkward:** executing on Windows skips the Colab installation and build, so the saved outputs do not establish that this route succeeds.
- **Suggested change:** complete the parent spec's planned release and Colab verification, then regenerate the notebook.
- **Classification:** **non-blocking** for this Windows revision; the notebook identifies its saved outputs as Windows results. Colab verification remains pending.

## Validation

The real existing installation is `C:/DSSAT48/DSCSM048.EXE`; no stock data files were copied or edited.
The saved notebook shows Python **3.14.7**, detection fields `windows`, `AMD64` and `DSCSM048.EXE`, and successful connecting with `File exists: True` in both the main step and the exercise.
The troubleshooting table shows **three** setup errors with recovery instructions: missing DSSAT, unsupported installation platform and missing build tools.

The notebook now has **six** walkthrough steps plus **one** self-contained exercise, with all imports and `%matplotlib inline` in the tools cell immediately after the lesson identifier and its short introductory sentence.
It includes the lesson identifier, but deliberately has no shared setup cell, `data/`, `SOURCE.md` or actual `runs/` copy.
The later lessons' three copy commands are displayed as text only; the copy explanation still says what is removed and where fresh inputs come from.
Folder assignment is part of the connecting step, whose table shows `HERE` as `.` and `RUNS` as `runs` using `.relative_to(HERE).as_posix()`.
Before displaying that table, the notebook checks `HERE.name == LESSON` and `(HERE / "lesson.ipynb").is_file()`; the instructions require the kernel current directory to be `course/00_setup`.
Each walkthrough cell shows one printed result or table, with no cell mixing a printed report and an unassigned returned value.

Windows instructions tell students to install DSSAT 4.8 into `C:\DSSAT48`, run `python -m pip install "dssatlab[course]" jupyterlab ipykernel`, and download or clone the repository.
They then run `cd course/00_setup` from the repository folder and `python -m jupyter lab lesson.ipynb` with that Python kernel.
The `install()` explanation covers what it builds, first-build duration, subsequent reuse, and the executable and data directory under `~/.cache/dssatlab/<version>` by default or `$XDG_CACHE_HOME/dssatlab/<version>` when configured.
The copy explanation and recap identify rerunning the setup cell as the action that removes previous results; restarting the kernel alone does not remove them.

Execution uses process-local `PYTHONPATH` pointing at this worktree's `src`, because the existing editable install resolves to the main checkout.
Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` point into system temp outside the worktree; `PYTHONDONTWRITEBYTECODE=1` avoids writing validation bytecode.
The executor emitted Windows kernel transport/event-loop warnings outside the notebook; all saved lesson outputs are free of user names and errors.

Both consecutive `python course/execute.py 00_setup` runs printed `00_setup: ok` after the revision.
The exercise also passed in fresh kernels with only the tools cell preceding it, for automatic discovery and explicit `C:/DSSAT48` directory selection.
`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all **15 tests**.
The test file and `SETUP_CELL` are byte-identical to their pre-revision versions, and every later lesson retains the exact shared setup cell.
No validation temp folders were created in this worktree.
