"""Core behavior with isolated files and a mocked installer contract."""
import importlib.util
import json
import os
import platform
import shutil
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dssatlab import config, core, installer
from dssatlab.errors import DSSATInstallError, DSSATNotFoundError
from dssatlab.installer import find_cached_install as _real_find_cached_install


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)})
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "test-arch")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "config")
    monkeypatch.setattr(core, "_WINDOWS_DEFAULT", tmp_path / "DSSAT48", raising=False)
    monkeypatch.setattr(installer, "cache_root", lambda: tmp_path / "cache", raising=False)
    monkeypatch.setattr(installer, "find_cached_install", lambda *args: None, raising=False)
    for name in ("resolve_version", "check_prerequisites", "build_dssat"):
        monkeypatch.setattr(installer, name, Mock(side_effect=AssertionError(name)), raising=False)
    for target in ("builtins.input", "subprocess.run", "urllib.request.urlopen"):
        monkeypatch.setattr(target, Mock(side_effect=AssertionError(target)))


def executable_at(tmp_path, folder="existing", name="dscsm048"):
    executable = tmp_path / folder / name
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("mock executable", encoding="utf-8")
    executable.chmod(0o755)
    return executable


@pytest.mark.parametrize("system, expected", [("Windows", "windows"), ("Linux", "linux"), ("Darwin", "other")])
@pytest.mark.parametrize("colab", [False, True])
def test_detect_environment_without_writes(tmp_path, monkeypatch, system, expected, colab):
    monkeypatch.setattr(platform, "system", lambda: system)
    finder = Mock(return_value=object() if colab else None)
    monkeypatch.setattr(importlib.util, "find_spec", finder)
    assert core.detect() == core.EnvironmentInfo(expected, colab, "test-arch", None)
    finder.assert_called_once_with("google.colab")
    assert not config.config_dir().exists()
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("error", [ModuleNotFoundError, ValueError])
def test_detect_handles_unavailable_colab_spec(monkeypatch, error):
    monkeypatch.setattr(importlib.util, "find_spec", Mock(side_effect=error))
    assert core.detect().is_colab is False


@pytest.mark.parametrize("origin", ["config", "env", "default", "managed"])
def test_detect_and_connect_share_read_only_discovery(tmp_path, monkeypatch, origin):
    executable = executable_at(tmp_path)
    if origin == "config":
        config.save_config({"executable": str(executable)})
    elif origin == "env":
        monkeypatch.setenv("DSSAT_HOME", str(executable.parent))
    elif origin == "default":
        monkeypatch.setattr(shutil, "which", lambda name: str(executable))
    else:
        (tmp_path / "cache" / "4.8.6.0").mkdir(parents=True)
        monkeypatch.setattr(installer, "find_cached_install", lambda *args: executable)
    save = Mock()
    monkeypatch.setattr(config, "save_config", save)
    assert core.detect().dssat_executable == executable
    save.assert_not_called()
    connection = core.connect(interactive=False)
    assert connection.executable == executable
    assert connection.source == origin
    assert connection.version == ("4.8.6.0" if origin == "managed" else None)
    save.assert_called_once()


def test_linux_managed_cache_prefers_highest_version(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "find_cached_install", _real_find_cached_install)
    older = executable_at(tmp_path, "cache/4.8.6.0/build/bin")
    newer = executable_at(tmp_path, "cache/4.8.10.0/build/bin")
    for version, executable in (("4.8.6.0", older), ("4.8.10.0", newer)):
        manifest = tmp_path / "cache" / version / "manifest.json"
        manifest.write_text(json.dumps({"executable": str(executable)}))
    connection = core.connect(interactive=False)
    assert connection.executable == newer
    assert connection.version == "4.8.10.0"


def test_explicit_executable_wins_and_is_saved(tmp_path, monkeypatch):
    explicit = executable_at(tmp_path, "explicit")
    other = executable_at(tmp_path, "other")
    config.save_config({"executable": str(other)})
    monkeypatch.setenv("DSSAT_HOME", str(other.parent))
    monkeypatch.setattr(shutil, "which", lambda name: str(other))
    connection = core.connect(other.parent, executable=explicit, interactive=False)
    assert connection == core.DSSATConnection(explicit, explicit.parent, None, "explicit")
    assert config.load_config() == {
        "executable": str(explicit), "root": str(explicit.parent),
        "version": None, "source": "explicit",
    }


@pytest.mark.parametrize("name", ["dscsm048", "DSCSM048.EXE", "DsCsM048.ExE"])
@pytest.mark.parametrize("directory", [False, True])
def test_path_resolves_before_saved_config(tmp_path, name, directory):
    executable = executable_at(tmp_path, name=name)
    config.save_config({"executable": str(executable_at(tmp_path, "other"))})
    connection = core.connect(executable.parent if directory else executable, interactive=False)
    assert connection.executable == executable
    assert connection.version is None
    assert connection.source == "explicit"


@pytest.mark.parametrize("argument", ["executable", "path"])
@pytest.mark.parametrize("kind", ["missing", "wrong-name", "directory"])
def test_invalid_explicit_choice_does_not_fall_back(tmp_path, argument, kind):
    valid = executable_at(tmp_path)
    config.save_config({"executable": str(valid)})
    candidate = tmp_path / "dscsm048"
    if kind == "wrong-name":
        candidate = executable_at(tmp_path, "bad", "other.exe")
    elif kind == "directory":
        candidate.mkdir()
    with pytest.raises(DSSATNotFoundError, match="executable"):
        core.connect(**{argument: candidate}, interactive=False)


def test_posix_requires_execute_permission(tmp_path, monkeypatch):
    executable = executable_at(tmp_path)
    access = Mock(return_value=False)
    monkeypatch.setattr(core, "os", SimpleNamespace(name="posix", access=access, X_OK=os.X_OK))
    with pytest.raises(DSSATNotFoundError):
        core.connect(executable=executable, interactive=False)
    access.assert_called_once_with(executable, os.X_OK)


def test_saved_managed_connection_preserves_root_and_version(tmp_path):
    executable = executable_at(tmp_path, "cache/4.8.6.0/build/bin")
    root = tmp_path / "cache" / "4.8.6.0"
    config.save_config({"executable": str(executable), "root": str(root),
                        "version": "4.8.6.0", "source": "managed"})
    assert core.connect(interactive=False) == core.DSSATConnection(executable, root, "4.8.6.0", "config")


@pytest.mark.parametrize("contents", ["{broken", "[]", "null", '{"executable": 42}',
                                     '{"executable": ""}', '{"executable": "missing"}'])
def test_corrupt_or_stale_config_falls_through(tmp_path, monkeypatch, contents):
    config.config_dir().mkdir()
    config.config_file().write_text(contents, encoding="utf-8")
    executable = executable_at(tmp_path)
    monkeypatch.setenv("DSSAT_HOME", str(executable.parent))
    assert core.connect(interactive=False).executable == executable


def test_environment_precedes_path(tmp_path, monkeypatch):
    executable = executable_at(tmp_path)
    monkeypatch.setenv("DSSAT_HOME", str(executable.parent))
    monkeypatch.setattr(shutil, "which", lambda name: str(executable_at(tmp_path, "other")))
    assert core.connect(interactive=False).source == "env"


def test_windows_default_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    executable = executable_at(tmp_path, "DSSAT48", "DSCSM048.EXE")
    assert core.connect(interactive=False) == core.DSSATConnection(executable, executable.parent, None, "default")


def test_linux_path_precedes_cache(tmp_path, monkeypatch):
    executable = executable_at(tmp_path)
    which = Mock(return_value=str(executable))
    monkeypatch.setattr(shutil, "which", which)
    monkeypatch.setattr(installer, "cache_root", Mock(side_effect=AssertionError("cache")))
    assert core.connect(interactive=False).executable == executable
    which.assert_called_once_with("dscsm048")


@pytest.mark.parametrize("system", ["Windows", "Linux", "Darwin"])
def test_missing_noninteractive_connection_has_actionable_error(monkeypatch, system):
    monkeypatch.setattr(platform, "system", lambda: system)
    with pytest.raises(DSSATNotFoundError) as error:
        core.connect(interactive=False)
    for text in ("DSSAT", "configuration", "DSSAT_HOME", "PATH", "executable=", "install()"):
        assert text in str(error.value)


def test_windows_prompt_remembers_path(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    executable = executable_at(tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt: str(executable.parent))
    connection = core.connect()
    assert connection.source == "manual"
    assert config.load_config()["executable"] == str(executable)


@pytest.mark.parametrize("answer", ["n", "", "maybe"])
def test_linux_declining_install_does_not_write_config(monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    with pytest.raises(DSSATNotFoundError):
        core.connect()
    assert not config.config_file().exists()


def test_linux_consent_installs_without_double_save(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: " YES ")
    executable = executable_at(tmp_path)
    monkeypatch.setattr(installer, "resolve_version", Mock(return_value="4.8.6.0"))
    monkeypatch.setattr(installer, "find_cached_install", lambda *args: executable)
    save = Mock()
    monkeypatch.setattr(config, "save_config", save)
    assert core.connect().source == "managed"
    installer.resolve_version.assert_called_once_with("latest")
    save.assert_called_once()


@pytest.mark.parametrize("system", ["Windows", "Darwin"])
def test_install_rejects_non_linux(monkeypatch, system):
    monkeypatch.setattr(platform, "system", lambda: system)
    with pytest.raises(DSSATInstallError, match="Linux/Colab.*v0.1"):
        core.install()


@pytest.mark.parametrize("cached", [False, True])
def test_install_builds_once_and_reuses_cache(tmp_path, monkeypatch, cached):
    executable = executable_at(tmp_path, "cache/4.8.6.0/build/bin")
    install_dir = tmp_path / "cache" / "4.8.6.0"
    lookup = Mock(side_effect=[executable if cached else None, executable])
    resolve = Mock(return_value="4.8.6.0")
    check = Mock()
    build = Mock(return_value=executable)
    for name, fake in (("resolve_version", resolve), ("find_cached_install", lookup),
                       ("check_prerequisites", check), ("build_dssat", build)):
        monkeypatch.setattr(installer, name, fake)
    expected = core.DSSATConnection(executable, install_dir, "4.8.6.0", "managed")
    assert core.install() == expected
    assert core.install("4.8.6.0") == expected
    assert [call.args for call in resolve.call_args_list] == [("latest",), ("4.8.6.0",)]
    assert [call.args for call in lookup.call_args_list] == [("4.8.6.0", install_dir)] * 2
    assert check.call_count == build.call_count == (0 if cached else 1)
    if not cached:
        build.assert_called_once_with("4.8.6.0", install_dir)
    assert config.load_config()["version"] == "4.8.6.0"


@pytest.mark.parametrize("stage", ["resolve_version", "check_prerequisites", "build_dssat"])
def test_install_propagates_errors_without_saving(monkeypatch, stage):
    monkeypatch.setattr(installer, "resolve_version", lambda version: "4.8.6.0")
    monkeypatch.setattr(installer, "check_prerequisites", lambda: None)
    monkeypatch.setattr(installer, stage, Mock(side_effect=DSSATInstallError(stage)))
    with pytest.raises(DSSATInstallError, match=stage):
        core.install()
    assert not config.config_file().exists()
