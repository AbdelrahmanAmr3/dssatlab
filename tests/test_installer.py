import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import urllib.error
import urllib.request

import pytest

from dssatlab import config, core, installer
from dssatlab.errors import DSSATInstallError


@pytest.fixture(autouse=True)
def block_external_calls(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected network or subprocess call")

    monkeypatch.setattr(urllib.request, "urlopen", unexpected)
    monkeypatch.setattr("subprocess.run", unexpected)


@pytest.fixture
def build_prefix(tmp_path, monkeypatch):
    prefix = tmp_path / "4.8.6.0"
    # Pytest's temporary paths can exceed DSSAT's limit; boundary tests use 51.
    monkeypatch.setattr(installer, "MAX_PREFIX_LENGTH", max(51, len(str(prefix))))
    return prefix


def test_cache_root_xdg(tmp_path, monkeypatch):
    location = tmp_path / "cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(location))
    assert installer.cache_root() == location / "dssatlab"
    assert not location.exists()


def test_cache_root_home(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert installer.cache_root() == tmp_path / ".cache" / "dssatlab"
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
    prefix = tmp_path / "4.8.6.0"
    prefix.mkdir()
    executable = prefix / "dscsm048"
    executable.touch()
    (prefix / "manifest.json").write_text(json.dumps({
        "prefix": str(prefix), "executable": str(executable)}))
    assert installer.find_cached_install("4.8.6.0", prefix) == executable


@pytest.mark.parametrize("prefix", [None, "", 1, [], {}])
def test_find_cached_install_rejects_invalid_prefix(tmp_path, prefix):
    executable = tmp_path / "dscsm048"
    executable.touch()
    (tmp_path / "manifest.json").write_text(json.dumps({
        "prefix": prefix, "executable": str(executable)}))
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


def test_find_cached_install_rejects_v01_manifest(tmp_path):
    executable = tmp_path / "dscsm048"
    executable.touch()
    (tmp_path / "manifest.json").write_text(json.dumps({"executable": str(executable)}))
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


@pytest.mark.parametrize("payload", [None, "not json", "[]", "{}",
    '{"prefix": "dssat", "executable": null}',
    '{"prefix": "dssat", "executable": 1}',
    '{"prefix": "dssat", "executable": ""}',
    '{"prefix": "dssat", "executable": "missing"}'])
def test_find_cached_install_miss(tmp_path, payload):
    if payload is not None:
        (tmp_path / "manifest.json").write_text(payload)
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


def test_find_cached_install_rejects_directory(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "prefix": str(tmp_path), "executable": str(tmp_path)}))
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


def test_find_cached_install_unreadable(tmp_path, monkeypatch):
    def unreadable(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_text", unreadable)
    assert installer.find_cached_install("4.8.6.0", tmp_path) is None


@pytest.mark.parametrize("existing_source", [False, True])
def test_install_reuses_source_and_installed_prefix(tmp_path, monkeypatch, build_prefix, existing_source):
    install_dir = prefix = build_prefix
    work = tmp_path / "work" / "4.8.6.0"
    source = work / "source"
    executable = prefix / "dscsm048"
    if existing_source:
        source.mkdir(parents=True)
        (source / "CMakeLists.txt").touch()
    calls = []

    def run(command, *, capture_output, text):
        calls.append(command)
        if command[:2] == ["git", "clone"]:
            if source.exists() and any(source.iterdir()):
                return SimpleNamespace(returncode=128, stdout="", stderr="source is not empty")
            source.mkdir(parents=True, exist_ok=True)
        if command[:2] == ["cmake", "--install"]:
            prefix.mkdir()
            executable.touch()
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda tool: f"/bin/{tool}")
    monkeypatch.setattr(installer, "cache_root", lambda: tmp_path)
    monkeypatch.setattr(config, "config_file", lambda: tmp_path / "config.json")
    monkeypatch.setattr("subprocess.run", run)
    assert core.install("4.8.6.0") == executable
    assert ["cmake", "--install", str(work / "build")] in calls
    assert sum(command[:2] == ["git", "clone"] for command in calls) == (0 if existing_source else 1)
    manifest = json.loads((install_dir / "manifest.json").read_text())
    assert manifest["prefix"] == str(prefix)
    assert manifest["executable"] == str(executable)
    assert config.load_config() == {"executable": str(executable)}
    calls.clear()
    assert core.install("4.8.6.0") == executable
    assert calls == []


@pytest.mark.parametrize("commit_status", ["success", "nonzero", "oserror"])
def test_build_commands_and_manifest(tmp_path, monkeypatch, build_prefix, commit_status):
    install_dir = prefix = build_prefix
    work = tmp_path / "work" / "4.8.6.0"
    source = work / "source"
    build = work / "build"
    executable = prefix / "dscsm048"
    calls = []

    def run(command, *, capture_output, text):
        assert capture_output is True and text is True
        calls.append(command)
        if command[:2] == ["git", "clone"]:
            assert work.is_dir()
            source.mkdir()
            (source / "CMakeLists.txt").touch()
        if command[:2] == ["cmake", "--build"]:
            (build / "bin").mkdir(parents=True)
            (build / "bin" / "dscsm048").touch()
        if command[:2] == ["cmake", "--install"]:
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
    assert calls[:4] == [
        ["git", "clone", "--depth", "1", "--branch", "v4.8.6.0",
         "https://github.com/DSSAT/dssat-csm-os", str(source)],
        ["cmake", "-S", str(source), "-B", str(build), "-DCMAKE_BUILD_TYPE=RELEASE",
         f"-DCMAKE_INSTALL_PREFIX={prefix}"],
        ["cmake", "--build", str(build), "--parallel"],
        ["cmake", "--install", str(build)],
    ]
    assert calls[4:] == [["git", "-C", str(source), "rev-parse", "--short", "HEAD"]]
    manifest = json.loads((install_dir / "manifest.json").read_text())
    expected = {"version": "4.8.6.0", "tag": "v4.8.6.0",
                "prefix": str(prefix), "executable": str(executable), "platform": "linux"}
    if commit_status == "success":
        expected["commit"] = "abc1234"
    assert manifest == expected
    assert source.is_dir() and build.is_dir()
    assert not (prefix / "source").exists()
    assert not (prefix / "build").exists()


@pytest.mark.parametrize("failed_step", [0, 1, 2, 3])
def test_build_failure_includes_command_and_output_tails(build_prefix, monkeypatch, failed_step):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        failed = len(calls) == failed_step + 1
        return SimpleNamespace(returncode=1 if failed else 0,
            stdout="\n".join(f"stdout-{i:02}" for i in range(30)),
            stderr="\n".join(f"stderr-{i:02}" for i in range(30)))

    monkeypatch.setattr("subprocess.run", run)
    with pytest.raises(DSSATInstallError) as caught:
        installer.build_dssat("4.8.6.0", build_prefix)
    message = str(caught.value)
    assert len(calls) == failed_step + 1
    assert all(argument in message for argument in calls[-1])
    assert "stderr-29" in message and "stdout-29" in message
    assert "stderr-00" not in message and "stdout-00" not in message
    assert not (build_prefix / "manifest.json").exists()


def test_build_cannot_start_command(build_prefix, monkeypatch):
    def run(*args, **kwargs):
        raise FileNotFoundError("git disappeared")

    monkeypatch.setattr("subprocess.run", run)
    with pytest.raises(DSSATInstallError, match="git disappeared"):
        installer.build_dssat("4.8.6.0", build_prefix)


@pytest.mark.parametrize("installed_directory", [False, True])
def test_build_missing_executable(tmp_path, monkeypatch, build_prefix, installed_directory):
    build = tmp_path / "work" / "4.8.6.0" / "build"
    (build / "bin").mkdir(parents=True)
    (build / "bin" / "dscsm048").touch()
    executable = build_prefix / "dscsm048"
    if installed_directory:
        executable.mkdir(parents=True)
    monkeypatch.setattr("subprocess.run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout="", stderr=""))
    with pytest.raises(DSSATInstallError) as caught:
        installer.build_dssat("4.8.6.0", build_prefix)
    message = str(caught.value)
    assert "succeeded" in message
    assert str(executable) in message
    assert "Inspect" in message
    assert not (build_prefix / "manifest.json").exists()


@pytest.mark.parametrize("length", [52, 80])
def test_build_rejects_long_prefix_before_side_effects(tmp_path, monkeypatch, length):
    prefix = Path(tmp_path.anchor) / ("p" * (length - len(tmp_path.anchor)))
    mkdir = Mock(side_effect=AssertionError("must not create directories"))
    run = Mock(side_effect=AssertionError("must not run commands"))
    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr("subprocess.run", run)
    with pytest.raises(DSSATInstallError) as caught:
        installer.build_dssat("4.8.6.0", prefix)
    message = str(caught.value)
    for detail in (str(prefix), str(length), "51", "XDG_CACHE_HOME", "~/dl", "try again"):
        assert detail in message
    mkdir.assert_not_called()
    run.assert_not_called()


def test_build_allows_exactly_51_character_prefix(tmp_path, monkeypatch):
    # Use a synthetic absolute prefix: tmp_path itself may be longer than 51.
    prefix = Path(tmp_path.anchor) / ("p" * (51 - len(tmp_path.anchor)))
    assert len(str(prefix)) == 51
    executable = prefix / "dscsm048"
    monkeypatch.setattr(Path, "mkdir", Mock())
    monkeypatch.setattr(Path, "is_file", lambda path: path == executable)
    monkeypatch.setattr(Path, "write_text", Mock())
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr("subprocess.run", run)
    assert installer.build_dssat("4.8.6.0", prefix) == executable
    commands = [call.args[0] for call in run.call_args_list]
    assert f"-DCMAKE_INSTALL_PREFIX={prefix}" in commands[1]
    assert commands[3][:2] == ["cmake", "--install"]
