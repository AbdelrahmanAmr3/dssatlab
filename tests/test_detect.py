"""Check environment reporting without depending on the test runner's OS."""

import platform

import pytest

import dssatlab


@pytest.mark.parametrize(
    "system, machine, expected_os, expected_architecture",
    [
        ("Windows", "AMD64", "windows", "AMD64"),
        ("Windows", "ARM64", "windows", "ARM64"),
        ("Linux", "x86_64", "linux", "x86_64"),
        ("Darwin", "arm64", "darwin", "arm64"),
        ("FreeBSD", "amd64", "freebsd", "amd64"),
        ("", "", "unknown", "unknown"),
    ],
)
def test_detect_normalizes_os_and_handles_unknown_platform(
    monkeypatch, system, machine, expected_os, expected_architecture
):
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "machine", lambda: machine)
    monkeypatch.setattr(platform, "python_version", lambda: "3.12.10")

    info = dssatlab.detect()

    assert info.os_name == expected_os
    assert info.architecture == expected_architecture
    assert info.python_version == "3.12.10"
