"""On-disk cache of Equasis pages.

Caching avoids repeating identical requests within a short period, which keeps
load on Equasis low, makes repeated lookups instant, and lets an interrupted
batch be re-run without fetching completed items again.

Pages are stored as HTML files named by a hash of the request. Only regular
content pages are cached; login, error, and not-found pages never are. Cached
pages include the name of the Equasis account that fetched them, so the cache
directory is created with owner-only permissions.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_NAME = "equasis-cli"
DEFAULT_TTL = timedelta(hours=24)


def default_cache_dir() -> Path:
    """Return the platform-appropriate cache directory."""
    override = os.environ.get("EQUASIS_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / APP_NAME / "Cache"
    return Path.home() / ".cache" / APP_NAME


@dataclass(frozen=True)
class CachedPage:
    html: str
    fetched_at: datetime


@dataclass(frozen=True)
class CacheStats:
    directory: Path
    entries: int
    size_bytes: int
    oldest: datetime | None
    newest: datetime | None


class PageCache:
    """Stores Equasis pages for ``ttl`` after they were fetched."""

    def __init__(
        self,
        directory: Path | None = None,
        *,
        ttl: timedelta = DEFAULT_TTL,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.directory = directory or default_cache_dir()
        self.ttl = ttl
        self._clock = clock

    @property
    def pages_dir(self) -> Path:
        return self.directory / "pages"

    @staticmethod
    def key(
        method: str,
        path: str,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> str:
        """Stable identifier for a request."""
        payload = json.dumps(
            [method.upper(), path, sorted((params or {}).items()), sorted((data or {}).items())],
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.pages_dir / f"{key}.html"

    def get(self, key: str) -> CachedPage | None:
        """Return the cached page if it exists and is younger than the TTL."""
        path = self._path(key)
        try:
            modified = path.stat().st_mtime
        except OSError:
            return None
        if self._clock() - modified > self.ttl.total_seconds():
            return None
        try:
            html = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return CachedPage(html=html, fetched_at=datetime.fromtimestamp(modified, timezone.utc))

    def put(self, key: str, html: str) -> None:
        """Store a page atomically."""
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            for directory in (self.directory, self.pages_dir):
                directory.chmod(0o700)
        target = self._path(key)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(html, encoding="utf-8")
            os.replace(temporary, target)
        except OSError:
            temporary.unlink(missing_ok=True)

    def clear(self) -> int:
        """Delete every cached page. Returns the number of pages removed."""
        removed = 0
        if not self.pages_dir.is_dir():
            return removed
        for page in self.pages_dir.glob("*.html"):
            try:
                page.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    def stats(self) -> CacheStats:
        pages = list(self.pages_dir.glob("*.html")) if self.pages_dir.is_dir() else []
        stamps = [p.stat() for p in pages]
        times = [datetime.fromtimestamp(s.st_mtime, timezone.utc) for s in stamps]
        return CacheStats(
            directory=self.directory,
            entries=len(pages),
            size_bytes=sum(s.st_size for s in stamps),
            oldest=min(times) if times else None,
            newest=max(times) if times else None,
        )
