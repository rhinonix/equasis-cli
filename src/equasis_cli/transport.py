"""HTTP transport: session handling, pacing, retries, and response capture."""

from __future__ import annotations

import email.utils
import logging
import random
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

from ._version import __version__
from .exceptions import NetworkError, RateLimitedError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.equasis.org/EquasisWeb/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/128.0 Safari/537.36 equasis-cli/{__version__}"
)

_RETRYABLE_EXCEPTIONS = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
)


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with jitter for transient failures.

    Only network errors and the status codes in ``retry_statuses`` are retried;
    other HTTP errors (for example 403 or 404) fail immediately.
    """

    max_retries: int = 3
    base_delay: float = 2.0
    backoff: float = 2.0
    max_delay: float = 60.0
    jitter: float = 0.25
    retry_statuses: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504, 520, 521, 522, 523, 524})
    )

    def delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Seconds to wait before retry number ``attempt`` (starting at 0)."""
        delay = min(self.max_delay, self.base_delay * self.backoff**attempt)
        if self.jitter:
            delay *= 1 + random.uniform(-self.jitter, self.jitter)  # noqa: S311 - not security related
        if retry_after is not None:
            delay = max(delay, min(retry_after, self.max_delay))
        return max(0.0, delay)


class Transport:
    """Thin wrapper around :class:`requests.Session` tailored to Equasis.

    Args:
        min_interval: Minimum seconds between the start of consecutive requests.
            Keeps load on Equasis low and reduces the risk of account throttling.
        timeout: ``(connect, read)`` timeout in seconds.
        save_html_dir: If set, every response body is written to this directory
            to help diagnose parsing problems. Saved pages include the name of
            the logged-in Equasis account.
    """

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        min_interval: float = 1.0,
        timeout: tuple[float, float] = (10.0, 60.0),
        retry: RetryPolicy | None = None,
        session: requests.Session | None = None,
        save_html_dir: Path | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.min_interval = min_interval
        self.timeout = timeout
        self.retry = retry or RetryPolicy()
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
        self.save_html_dir = save_html_dir
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self._saved = 0

    def get(self, path: str, params: Mapping[str, str] | None = None) -> str:
        return self.request("GET", path, params=params)

    def post(self, path: str, data: Mapping[str, str]) -> str:
        return self.request("POST", path, data=data)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> str:
        """Perform a request and return the decoded body.

        Raises:
            RateLimitedError: if Equasis keeps answering HTTP 429.
            NetworkError: for connection failures and non-retryable HTTP errors.
        """
        url = self.base_url + path.lstrip("/")
        attempt = 0
        while True:
            self._pace()
            started = self._clock()
            try:
                response = self.session.request(
                    method, url, params=params, data=data, timeout=self.timeout
                )
            except _RETRYABLE_EXCEPTIONS as exc:
                if attempt >= self.retry.max_retries:
                    raise NetworkError(f"could not reach Equasis: {exc}") from exc
                delay = self.retry.delay(attempt)
                logger.warning(
                    "%s %s failed (%s); retrying in %.1fs", method, path, type(exc).__name__, delay
                )
            except requests.RequestException as exc:
                raise NetworkError(f"request to Equasis failed: {exc}") from exc
            else:
                elapsed = self._clock() - started
                logger.debug("%s %s -> %s in %.2fs", method, path, response.status_code, elapsed)
                status = response.status_code
                if status < 400:
                    body = response.text
                    self._save(method, path, body)
                    return body
                if status not in self.retry.retry_statuses:
                    raise NetworkError(
                        f"Equasis returned HTTP {status} for {path}", status_code=status
                    )
                if attempt >= self.retry.max_retries:
                    if status == 429:
                        raise RateLimitedError(
                            "Equasis is rate limiting requests (HTTP 429); wait and try again "
                            "with a larger --delay",
                            status_code=status,
                        )
                    raise NetworkError(
                        f"Equasis returned HTTP {status} for {path} after {attempt + 1} attempts",
                        status_code=status,
                    )
                delay = self.retry.delay(attempt, _retry_after(response))
                logger.warning(
                    "%s %s returned HTTP %s; retrying in %.1fs", method, path, status, delay
                )
            attempt += 1
            self._sleep(delay)

    def close(self) -> None:
        self.session.close()

    def _pace(self) -> None:
        if self._last_request is not None and self.min_interval > 0:
            wait = self._last_request + self.min_interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def _save(self, method: str, path: str, body: str) -> None:
        if self.save_html_dir is None:
            return
        self.save_html_dir.mkdir(parents=True, exist_ok=True)
        self._saved += 1
        slug = re.sub(r"[^A-Za-z0-9]+", "-", path.split("?", 1)[0]).strip("-") or "page"
        target = self.save_html_dir / f"{self._saved:03d}-{method.lower()}-{slug}.html"
        target.write_text(body, encoding="utf-8")
        logger.info("saved response to %s", target)


def _retry_after(response: requests.Response) -> float | None:
    """Parse a ``Retry-After`` header given in seconds or as an HTTP date."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    if value.strip().isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
