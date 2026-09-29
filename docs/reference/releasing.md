# Releasing

This page summarizes the release process for publishing `dssatlab` to PyPI. The authoritative instructions are maintained in [RELEASING.md on GitHub](https://github.com/AbdelrahmanAmr3/dssatlab/blob/master/RELEASING.md).

## Manual release process

The manual release procedure consists of six steps executed in an isolated environment:

### 1. Clean environment

Create and activate a fresh virtual environment, upgrade pip, and install development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

### 2. Run tests

Execute the automated test suite to ensure all unit tests pass:

```bash
python -m pytest
```

### 3. Build and validate distributions

Remove previous build artifacts, generate source and wheel distributions using `build`, and validate the artifacts with `twine`:

```bash
rm -rf dist build
python -m build
python -m twine check dist/*
```

On Windows, use equivalent PowerShell commands (`Remove-Item -Recurse -Force dist, build`) to remove artifact folders.

### 4. Inspect package contents

Confirm the wheel contains only the package files and metadata. In an isolated environment without optional dependencies, install the built wheel and verify runtime behavior:

```python
import dssatlab
print(dssatlab.detect())
```

Verify that no unexpected runtime dependencies are required.

### 5. TestPyPI upload (recommended)

If TestPyPI credentials or tokens are configured, upload distribution artifacts for smoke testing:

```bash
python -m twine upload --repository testpypi dist/*
```

Install the uploaded package from TestPyPI in a fresh environment to verify installation and basic discovery.

### 6. Publish to PyPI

Upload the validated distributions to PyPI:

```bash
python -m twine upload dist/*
```

Do not store PyPI credentials or API tokens in the repository.

## Automated CI publishing

Publishing can also be triggered via GitHub Actions using the `.github/workflows/workflow.yml` workflow:

- **Trigger**: Runs automatically when a GitHub release is published, or manually via `workflow_dispatch`.
- **Version verification**: Confirms that the release tag matches the version specified in `pyproject.toml` and ensures development versions (`.dev`) are rejected.
- **Verification and build**: Installs `.[dev]`, runs `python -m pytest`, builds the distribution packages, and runs `twine check`.
- **Trusted publishing**: Deploys artifacts to PyPI using PyPA's official GitHub Action (`pypa/gh-action-pypi-publish`) via OIDC trusted publishing without stored repository secrets.
