"""Exception hierarchy for equasis-cli.

Every error raised deliberately by the package derives from :class:`EquasisError`
so callers can handle failures without catching unrelated exceptions.
"""

from __future__ import annotations


class EquasisError(Exception):
    """Base class for all equasis-cli errors."""


class ConfigurationError(EquasisError):
    """Credentials or settings are missing or invalid."""


class InvalidInputError(EquasisError, ValueError):
    """A user-supplied value (for example an IMO number) is malformed."""


class AuthenticationError(EquasisError):
    """Equasis rejected the supplied credentials."""


class SessionExpiredError(EquasisError):
    """The Equasis session expired and could not be re-established."""


class NotFoundError(EquasisError):
    """The requested vessel or company does not exist in Equasis."""


class LayoutChangedError(EquasisError):
    """An Equasis page no longer matches the structure the parser expects.

    This usually means Equasis changed its website and equasis-cli needs an
    update. Re-running with ``--save-html DIR`` captures the page for a bug report.
    """


class NetworkError(EquasisError):
    """Equasis could not be reached or returned an unexpected HTTP error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitedError(NetworkError):
    """Equasis kept responding with HTTP 429 after all retries."""
