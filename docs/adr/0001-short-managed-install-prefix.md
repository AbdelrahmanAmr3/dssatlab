# 0001: The managed install prefix must be short

Status: accepted (2026-09-29)

## Context

The managed install builds DSSAT with `cmake --install` into a prefix. The build writes that
prefix into every line of `DSSATPRO.L48`, and DSSAT reads that file on every run. On a real
Linux build of `v4.8.6.0` (aarch64), DSSAT failed with `Substring out of bounds` (exit 2 or
99) once the prefix was longer than 51 characters. It worked at 40, 50 and 51.

The first layout put the prefix at `~/.cache/dssatlab/installs/<version>/dssat`, which is
39 characters plus the home directory. That fails for any home directory longer than 12
characters (`/home/abdosaleh` is 15), and works on Colab (`/root`) only by luck.

## Decision

The prefix is `<cache>/dssatlab/<version>`. Source and build directories live in
`<cache>/dssatlab/work/<version>/`, outside the prefix. Before building, a prefix longer than
51 characters raises `DSSATInstallError` that gives the length and tells the user to set
`XDG_CACHE_HOME` to a shorter folder.

## Alternatives considered

- Keep the layout and only add the error. Rejected: it fails for a common home directory
  length, including the owner's.
- Add an `install(prefix=...)` argument. Rejected for v0.2: it adds public API and pushes
  the length rule onto every caller.

## Consequences

- The cache layout differs from v0.1 (`<cache>/dssatlab/installs/...`). Old entries are
  ignored and left on disk; cleaning them is out of scope.
- The 51-character limit was measured for one DSSAT release and one architecture. If a
  later release changes how `DSSATPRO` is read, the constant in the installer should be
  re-measured.
- Users with a home directory over about 27 characters must set `XDG_CACHE_HOME`.
