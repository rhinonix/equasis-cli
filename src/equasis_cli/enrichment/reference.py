"""Country and Maritime Identification Digit (MID) reference data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class Country:
    alpha3: str
    alpha2: str | None
    name: str


def _load(name: str) -> Any:
    return json.loads(
        resources.files(__package__).joinpath("data").joinpath(name).read_text("utf-8")
    )


@lru_cache(maxsize=1)
def countries() -> dict[str, Country]:
    """ISO 3166-1 countries keyed by alpha-3 code."""
    data = _load("countries.json")
    return {
        code: Country(alpha3=code, alpha2=entry["alpha2"], name=entry["name"])
        for code, entry in data["countries"].items()
    }


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    data = _load("countries.json")
    index = {entry["name"].casefold(): code for code, entry in data["countries"].items()}
    index.update({alias.casefold(): code for alias, code in data["aliases"].items()})
    return index


@lru_cache(maxsize=1)
def _mids() -> dict[str, str]:
    return {mid: entry["alpha3"] for mid, entry in _load("mids.json")["mids"].items()}


def country(alpha3: str | None) -> Country | None:
    """Look up a country by ISO alpha-3 code."""
    return countries().get(alpha3.upper()) if alpha3 else None


def country_by_name(name: str | None) -> Country | None:
    """Look up a country by name or common alias (case-insensitive)."""
    if not name:
        return None
    code = _names().get(name.strip().casefold())
    return countries().get(code) if code else None


def mmsi_country(mmsi: str | None) -> Country | None:
    """Country allocated the MID of a ship station MMSI.

    Ship station MMSIs start with the three-digit MID (first digit 2-7). Other
    station types (coast stations, aircraft, aids to navigation) return ``None``.
    """
    if not mmsi or len(mmsi) != 9 or not mmsi.isdigit() or mmsi[0] not in "234567":
        return None
    code = _mids().get(mmsi[:3])
    return countries().get(code) if code else None
