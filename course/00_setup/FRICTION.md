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
- **Why it is awkward:** the message says installation is supported only on Linux/Colab "in v0.1", even though this worktree's package is 0.22.0; it can suggest a later version might enable Windows builds.
- **Suggested change:** remove the obsolete version qualifier and explicitly direct Windows users to install DSSAT 4.8 and connect to it.
- **Classification:** **non-blocking**; the notebook guards the build with the Colab condition and explains the message in its troubleshooting note.

## 3. Saved config requires a writable profile - non-blocking

- **What the student must do:** use a writable application-data location when their execution environment restricts writes to the normal Windows profile.
- **Why it is awkward:** `connect()` always saves the selected executable, even if discovery already found it; a restricted environment needs additional configuration unrelated to crop modelling.
- **Suggested change:** avoid rewriting an unchanged saved executable and report an actionable DSSAT error if config cannot be saved.
- **Classification:** **non-blocking**; validation directs process-local `LOCALAPPDATA` to system temp, as in the reference lessons, without changing package code or DSSAT files.

## Course development limitation - non-blocking

- **What the student must do:** during course development on Windows, install the course and development extras from the repository, as the course README instructs.
- **Why it is awkward:** the Colab branch uses the shared `dssatlab[course]>=0.23,<0.24` pin, while this worktree is still 0.22.0; this Windows validation cannot establish that the release-time Colab path works.
- **Suggested change:** complete the planned T17/T18 release and Colab verification before advertising the course as ready, then regenerate the notebook.
- **Classification:** **non-blocking** for this Windows lesson implementation; the notebook clearly labels its development status and Windows outputs. Colab verification remains pending in the parent spec.

## Validation

The real existing installation is `C:/DSSAT48/DSCSM048.EXE`; no stock data files were copied or edited.
The saved notebook shows Python **3.14.7**, detection fields `windows`, `AMD64` and `DSCSM048.EXE`, and successful connecting with `File exists: True` in both the main step and the exercise.
The troubleshooting table shows **three** setup errors with complete recovery instructions; the notebook explains the documented **51-character** managed-install prefix limit.

The notebook has eight setup steps plus one self-contained exercise.
It includes the lesson identifier, but deliberately has no shared setup cell, `data/`, `SOURCE.md` or actual `runs/` copy.
The later lessons' three copy commands are displayed as text only.

Execution uses process-local `PYTHONPATH` pointing at this worktree's `src`, because the existing editable install resolves to the main checkout.
Process-local `LOCALAPPDATA`, `IPYTHONDIR` and `JUPYTER_RUNTIME_DIR` point into system temp outside the worktree; `PYTHONDONTWRITEBYTECODE=1` avoids writing validation bytecode.
The executor emitted Windows kernel transport/event-loop warnings outside the notebook; all saved lesson outputs are free of user names and errors.

Both consecutive `python course/execute.py 00_setup` runs printed `00_setup: ok`.
The exercise also passed in fresh kernels with only the tools cell preceding it, for automatic discovery and explicit `C:/DSSAT48` directory selection.
`python -m pytest -q tests/test_course.py --basetemp=<system-temp-folder> -p no:cacheprovider` passed all **15 tests**.
UTF-8 inspection found no `??`, `m?`, ` ? ` or corrupted lesson-title separator or Python icons.
