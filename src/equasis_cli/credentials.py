"""Locate, store, and remove Equasis credentials.

Credentials are resolved in this order:

1. ``--username`` and ``--password`` command-line options
2. ``EQUASIS_USERNAME`` and ``EQUASIS_PASSWORD`` environment variables
3. The credentials file written by ``equasis configure --setup``

The credentials file lives in the user's configuration directory
(``$XDG_CONFIG_HOME/equasis-cli`` or ``~/.config/equasis-cli`` on Linux and macOS,
``%APPDATA%\\equasis-cli`` on Windows) and is created with owner-only permissions.
"""

from __future__ import annotations

import enum
import json
import logging
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

APP_NAME = "equasis-cli"
FILE_NAME = "credentials.json"
ENV_USERNAME = "EQUASIS_USERNAME"
ENV_PASSWORD = "EQUASIS_PASSWORD"  # noqa: S105 - environment variable name, not a secret


class CredentialSource(str, enum.Enum):
    ARGUMENTS = "command-line options"
    ENVIRONMENT = "environment variables"
    CONFIG_FILE = "credentials file"


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str
    source: CredentialSource

    def __repr__(self) -> str:  # never expose the password in logs or tracebacks
        return f"Credentials(username={self.username!r}, source={self.source.value!r})"


def default_config_dir() -> Path:
    """Return the platform-appropriate configuration directory."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME
    return Path.home() / ".config" / APP_NAME


class CredentialStore:
    """Reads and writes the credentials file and resolves credential sources."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or default_config_dir()

    @property
    def path(self) -> Path:
        return self.config_dir / FILE_NAME

    def resolve(
        self, username: str | None = None, password: str | None = None
    ) -> Credentials | None:
        """Return the highest-priority complete set of credentials, if any."""
        if username and password:
            return Credentials(username, password, CredentialSource.ARGUMENTS)
        env_username = os.environ.get(ENV_USERNAME)
        env_password = os.environ.get(ENV_PASSWORD)
        if env_username and env_password:
            return Credentials(env_username, env_password, CredentialSource.ENVIRONMENT)
        stored = self.load()
        if stored:
            return Credentials(stored[0], stored[1], CredentialSource.CONFIG_FILE)
        return None

    def load(self) -> tuple[str, str] | None:
        """Read the credentials file; ``None`` if it is missing or unreadable."""
        path = self.path
        if not path.is_file():
            return None
        self._warn_if_exposed(path)
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("could not read %s: %s", path, exc)
            return None
        if not isinstance(data, dict):
            logger.warning("ignoring %s: unexpected format", path)
            return None
        username, password = data.get("username"), data.get("password")
        if isinstance(username, str) and isinstance(password, str) and username and password:
            return username, password
        return None

    def save(self, username: str, password: str) -> Path:
        """Write credentials atomically with owner-only permissions."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"username": username, "password": password}, indent=2) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=".credentials.", dir=self.config_dir)
        try:
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(temp_name, self.path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return self.path

    def clear(self) -> bool:
        """Delete the credentials file. Returns ``True`` if a file was removed."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True

    def describe(self) -> dict[str, Any]:
        """Report which credential sources are configured (never the values)."""
        stored = self.load()
        return {
            "environment": {
                ENV_USERNAME: bool(os.environ.get(ENV_USERNAME)),
                ENV_PASSWORD: bool(os.environ.get(ENV_PASSWORD)),
            },
            "file": {
                "path": str(self.path),
                "exists": self.path.is_file(),
                "complete": stored is not None,
                "username": stored[0] if stored else None,
            },
        }

    @staticmethod
    def _warn_if_exposed(path: Path) -> None:
        if os.name != "posix":
            return
        try:
            mode = path.stat().st_mode
        except OSError:
            return
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            logger.warning("%s is readable by other users; run: chmod 600 %s", path, path)
