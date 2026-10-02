# Releasing to PyPI

Credentials are intentionally not stored here.

## 1. Clean environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## 2. Test

```bash
python -m pytest
```

## 3. Build and validate

```bash
rm -rf dist build
python -m build
python -m twine check dist/*
```

Before tagging, `CHANGELOG.md` must have an entry for this version (added, changed, fixed), and the docs must build:

```bash
python -m pip install -e '.[docs]'
python -m mkdocs build --strict
```

Use the PowerShell/Explorer equivalent for removing build folders on Windows if needed.

## 4. Inspect

Confirm the wheel contains only the intended package and metadata. Install the wheel into a fresh environment and verify:

```python
import dssatlab
print(dssatlab.detect())
```

with no extra runtime Python packages.

## 5. TestPyPI (recommended)

If credentials are available:

```bash
python -m twine upload --repository testpypi dist/*
```

Install from TestPyPI in a clean environment and smoke-test it.

## 6. PyPI

```bash
python -m twine upload dist/*
```

Do not store API tokens in the repository. Trusted Publishing can be added later; it is not required for v0.1.

## 7. Docs update (after every release)

Every new version is followed by an update of the docs site, through a pull request like any other change:

- `CHANGELOG.md`: the entry for the new version, copied from the GitHub release notes.
- The Guide pages the release changes, and the Roadmap (move items from deferred to done).
- The API reference, if the exported names or their docstrings changed, and the Architecture page, if modules changed.
- `python -m mkdocs build --strict` passes; the site deploys from `master` after the pull request is merged.
