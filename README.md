# dssatlab

This is the public source repository for the planned `dssatlab` Python package.
The package will help Python users find and install DSSAT-CSM.

This repository currently contains packaging and release setup only. It does
not yet provide working DSSAT functionality and has not been published to PyPI.
The first release will follow implementation and release checks.

## Build and release

To check packaging on GitHub, open **Actions > Publish to PyPI > Run workflow**
and choose `master`. This builds the wheel and source archive, checks them with
Twine, and saves them as a workflow artifact. A manual run does not upload to PyPI.

For a functional release, update `version` in `pyproject.toml`, commit the change,
and publish a GitHub release using a new tag on that commit. For example, package
version `0.1.0` uses tag `v0.1.0`. Publishing the release starts the PyPI workflow;
saving a draft or pushing a tag alone does not. Development versions (`.dev`)
are currently blocked from publication.

The PyPI Trusted Publisher must use owner `AbdelrahmanAmr3`, repository `dssatlab`,
workflow `release.yml`, and environment `pypi`.

Existing tags keep their original source and workflow. The existing `0.1` tag
predates this release trigger and does not match the package version. Prepare
a new release from the updated source when the package is ready.
