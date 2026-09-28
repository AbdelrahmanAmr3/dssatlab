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
