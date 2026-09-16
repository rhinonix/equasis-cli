"""Tests for credential resolution and storage."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from equasis_cli.credentials import (
    CredentialSource,
    CredentialStore,
    default_config_dir,
)


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CredentialStore:
    monkeypatch.delenv("EQUASIS_USERNAME", raising=False)
    monkeypatch.delenv("EQUASIS_PASSWORD", raising=False)
    return CredentialStore(tmp_path / "config")


def test_resolution_order(store: CredentialStore, monkeypatch: pytest.MonkeyPatch) -> None:
    assert store.resolve() is None

    store.save("file@example.com", "file-secret")
    creds = store.resolve()
    assert creds is not None
    assert (creds.username, creds.source) == ("file@example.com", CredentialSource.CONFIG_FILE)

    monkeypatch.setenv("EQUASIS_USERNAME", "env@example.com")
    monkeypatch.setenv("EQUASIS_PASSWORD", "env-secret")
    creds = store.resolve()
    assert creds is not None
    assert creds.source is CredentialSource.ENVIRONMENT

    creds = store.resolve("arg@example.com", "arg-secret")
    assert creds is not None
    assert creds.source is CredentialSource.ARGUMENTS


def test_password_is_not_in_repr(store: CredentialStore) -> None:
    store.save("user@example.com", "hunter2")
    assert "hunter2" not in repr(store.resolve())


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_saved_file_is_private(store: CredentialStore) -> None:
    path = store.save("user@example.com", "secret")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "username": "user@example.com",
        "password": "secret",
    }


def test_legacy_file_with_extra_keys_is_accepted(store: CredentialStore) -> None:
    store.config_dir.mkdir(parents=True)
    store.path.write_text(
        json.dumps({"username": "u", "password": "p", "created_by": "equasis-cli", "note": "x"}),
        encoding="utf-8",
    )
    assert store.load() == ("u", "p")


def test_corrupt_file_is_ignored(store: CredentialStore) -> None:
    store.config_dir.mkdir(parents=True)
    store.path.write_text("{not json", encoding="utf-8")
    assert store.load() is None


def test_clear_and_describe(store: CredentialStore) -> None:
    assert store.clear() is False
    store.save("user@example.com", "secret")
    info = store.describe()
    assert info["file"]["complete"] is True
    assert info["file"]["username"] == "user@example.com"
    assert "secret" not in json.dumps(info)
    assert store.clear() is True
    assert not store.path.exists()


def test_default_config_dir_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_config_dir() == tmp_path / "equasis-cli"


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_group_readable_file_triggers_warning(
    store: CredentialStore, caplog: pytest.LogCaptureFixture
) -> None:
    path = store.save("user@example.com", "secret")
    path.chmod(0o644)
    store.load()
    assert "readable by other users" in caplog.text
