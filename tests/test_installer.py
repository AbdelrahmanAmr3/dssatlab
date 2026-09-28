import io
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error
import urllib.request

import pytest

from dssatlab import installer
from dssatlab.errors import DSSATInstallError


@pytest.fixture(autouse=True)
def block_external_calls(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected network or subprocess call")

    monkeypatch.setattr(urllib.request, "urlopen", unexpected)
    monkeypatch.setattr("subprocess.run", unexpected)


def test_cache_root_xdg(tmp_path, monkeypatch):
    location = tmp_path / "cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(location))
    assert installer.cache_root() == location / "dssatlab" / "installs"
    assert not location.exists()


def test_cache_root_home(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert installer.cache_root() == tmp_path / ".cache" / "dssatlab" / "installs"
    assert not (tmp_path / ".cache").exists()


@pytest.mark.parametrize("tag", ["v4.8.6.0", "4.8.6.0"])
def test_resolve_latest(tag, monkeypatch):
    def urlopen(url, **kwargs):
        assert url == "https://api.github.com/repos/DSSAT/dssat-csm-os/releases/latest"
        return io.BytesIO(json.dumps({"tag_name": tag}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert installer.resolve_version("latest") == "4.8.6.0"


@pytest.mark.parametrize("error", [urllib.error.URLError("offline"),
    urllib.error.HTTPError("https://api.github.com", 403, "rate limited", {}, None),
    TimeoutError("timed out")])
def test_resolve_latest_network_error(error, monkeypatch):
    def urlopen(*args, **kwargs):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(DSSATInstallError) as caught:
        installer.resolve_version("latest")
    message = str(caught.value)
    assert "releases/latest" in message
    assert str(error) in message
    assert "version" in message


@pytest.mark.parametrize("payload", [b"not json", b"\xff", b"[]", b"{}",
    b'{"tag_name": null}', b'{"tag_name": ""}', b'{"tag_name": "v"}'])
def test_resolve_latest_invalid_response(payload, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(payload))
    with pytest.raises(DSSATInstallError, match="releases/latest"):
        installer.resolve_version("latest")


def test_resolve_concrete_version_without_network():
    assert installer.resolve_version("4.8.6.0") == "4.8.6.0"


@pytest.mark.parametrize("missing", [(), ("git",), ("cmake", "gfortran"),
    ("git", "cmake", "gfortran")])
def test_check_prerequisites(missing, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda tool: None if tool in missing else f"/bin/{tool}")
    if not missing:
        assert installer.check_prerequisites() is None
        return
    with pytest.raises(DSSATInstallError) as caught:
        installer.check_prerequisites()
    message = str(caught.value)
    assert f"Missing required tools on PATH: {', '.join(missing)}." in message
    assert "apt install git cmake gfortran" in message


def test_find_cached_install(tmp_path):
    executable = tmp_path / "dscsm048"
    executable.touch()
    (tmp_path / "manifest.json").write_text(json.dumps({"executable": str(executable)}))
    assert installer.find_cached_install("4.8.6.0", tmp_path) == executable


@pytest.mark.parametrize("payload", [None, "not json", "[]", "{}",
    '{"executable": null}', '{"executable": 1}', '{"executable": "missing"}'])
def test_find_cached_install_miss(tmp_path, payload):
    if payload is not None:
        (tmp_path / "manifest.json").write_text(payload)
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


def test_find_cached_install_rejects_directory(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"executable": str(tmp_path)}))
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


def test_find_cached_install_unreadable(tmp_path, monkeypatch):
    def unreadable(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_text", unreadable)
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


@pytest.mark.parametrize("relative", ["bin/dscsm048", "bin/DSCSM048.EXE", "nested/DsCsM048"])
@pytest.mark.parametrize("commit_status", ["success", "nonzero", "oserror"])
def test_build_commands_and_manifest(tmp_path, monkeypatch, relative, commit_status):
    install_dir = tmp_path / "managed install" / "4.8.6.0"
    source = install_dir / "source"
    build = install_dir / "build"
    executable = build / relative
    calls = []

    def run(command, *, capture_output, text):
        assert capture_output is True and text is True
        calls.append(command)
        if command[:2] == ["cmake", "--build"]:
            executable.parent.mkdir(parents=True)
            executable.touch()
        if "rev-parse" in command:
            if commit_status == "oserror":
                raise OSError("git unavailable")
            return SimpleNamespace(returncode=int(commit_status == "nonzero"),
                                   stdout="abc1234\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", run)
    assert installer.build_dssat("4.8.6.0", install_dir) == executable
    assert calls[:3] == [
        ["git", "clone", "--depth", "1", "--branch", "v4.8.6.0",
         "https://github.com/DSSAT/dssat-csm-os", str(source)],
        ["cmake", "-S", str(source), "-B", str(build), "-DCMAKE_BUILD_TYPE=RELEASE"],
        ["cmake", "--build", str(build), "--parallel"],
    ]
    assert calls[3:] == [["git", "-C", str(source), "rev-parse", "--short", "HEAD"]]
    manifest = json.loads((install_dir / "manifest.json").read_text())
    expected = {"version": "4.8.6.0", "tag": "v4.8.6.0",
                "executable": str(executable), "platform": "linux"}
    if commit_status == "success":
        expected["commit"] = "abc1234"
    assert manifest == expected


@pytest.mark.parametrize("failed_step", [0, 1, 2])
def test_build_failure_includes_command_and_output_tails(tmp_path, monkeypatch, failed_step):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        failed = len(calls) == failed_step + 1
        return SimpleNamespace(returncode=1 if failed else 0,
            stdout="\n".join(f"stdout-{i:02}" for i in range(30)),
            stderr="\n".join(f"stderr-{i:02}" for i in range(30)))

    monkeypatch.setattr("subprocess.run", run)
    with pytest.raises(DSSATInstallError) as caught:
        installer.build_dssat("4.8.6.0", tmp_path)
    message = str(caught.value)
    assert len(calls) == failed_step + 1
    assert all(argument in message for argument in calls[-1])
    assert "stderr-29" in message and "stdout-29" in message
    assert "stderr-00" not in message and "stdout-00" not in message
    assert not (tmp_path / "manifest.json").exists()


def test_build_cannot_start_command(tmp_path, monkeypatch):
    def run(*args, **kwargs):
        raise FileNotFoundError("git disappeared")

    monkeypatch.setattr("subprocess.run", run)
    with pytest.raises(DSSATInstallError, match="git disappeared"):
        installer.build_dssat("4.8.6.0", tmp_path)


def test_build_missing_executable(tmp_path, monkeypatch):
    build = tmp_path / "build"
    (build / "bin" / "dscsm048").mkdir(parents=True)
    (build / "bin" / "unrelated").touch()
    monkeypatch.setattr("subprocess.run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout="", stderr=""))
    with pytest.raises(DSSATInstallError) as caught:
        installer.build_dssat("4.8.6.0", tmp_path)
    message = str(caught.value)
    assert "succeeded" in message
    assert str(build / "bin") in message and str(build) in message
    assert "dscsm048" in message
    assert not (tmp_path / "manifest.json").exists()
