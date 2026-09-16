"""equasis-cli: command-line and Python access to Equasis maritime data.

Example::

    from equasis_cli import EquasisClient

    with EquasisClient("user@example.com", "password") as client:
        vessel = client.get_vessel("9811000")
        print(vessel.name, vessel.flag, len(vessel.inspections))
"""

import logging

from ._version import __version__
from .client import EquasisClient
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    EquasisError,
    InvalidInputError,
    LayoutChangedError,
    NetworkError,
    NotFoundError,
    RateLimitedError,
    SessionExpiredError,
)
from .models import (
    Company,
    CompanySummary,
    Fleet,
    FleetVessel,
    Inspection,
    SearchResults,
    ShipSummary,
    Vessel,
    to_jsonable,
)
from .transport import RetryPolicy, Transport

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "AuthenticationError",
    "Company",
    "CompanySummary",
    "ConfigurationError",
    "EquasisClient",
    "EquasisError",
    "Fleet",
    "FleetVessel",
    "Inspection",
    "InvalidInputError",
    "LayoutChangedError",
    "NetworkError",
    "NotFoundError",
    "RateLimitedError",
    "RetryPolicy",
    "SearchResults",
    "SessionExpiredError",
    "ShipSummary",
    "Transport",
    "Vessel",
    "__version__",
    "to_jsonable",
]
