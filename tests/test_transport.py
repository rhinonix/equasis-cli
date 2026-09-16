"""Tests for HTTP pacing, retries, and response capture."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests
import responses

from equasis_cli.exceptions import NetworkError, RateLimitedError
from equasis_cli.transport import BASE_URL, RetryPolicy, Transport


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_transport(clock: FakeClock, **kwargs: object) -> Transport:
    policy = RetryPolicy(max_retries=2, base_delay=1.0, jitter=0.0)
    return Transport(sleep=clock.sleep, clock=clock.time, retry=policy, **kwargs)  # type: ignore[arg-type]


@responses.activate
def test_successful_request_returns_body_and_sends_parameters() -> None:
    clock = FakeClock()
    responses.get(
        BASE_URL + "restricted/ShipInfo?fs=ShipInfo&P_IMO=9811000", body="<html>ok</html>"
    )
    transport = make_transport(clock, min_interval=0)

    body = transport.get("restricted/ShipInfo", params={"fs": "ShipInfo", "P_IMO": "9811000"})

    assert body == "<html>ok</html>"
    assert "equasis-cli/" in responses.calls[0].request.headers["User-Agent"]


@responses.activate
def test_requests_are_paced() -> None:
    clock = FakeClock()
    responses.get(BASE_URL + "page", body="a")
    transport = make_transport(clock, min_interval=1.5)

    transport.get("page")
    clock.now += 0.5
    transport.get("page")

    assert clock.sleeps == [pytest.approx(1.0)]


@responses.activate
@pytest.mark.parametrize("status", [500, 502, 503, 504, 522])
def test_transient_statuses_are_retried(status: int) -> None:
    clock = FakeClock()
    responses.get(BASE_URL + "page", status=status)
    responses.get(BASE_URL + "page", body="recovered")
    transport = make_transport(clock, min_interval=0)

    assert transport.get("page") == "recovered"
    assert clock.sleeps == [1.0]


@responses.activate
@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(status: int) -> None:
    clock = FakeClock()
    responses.get(BASE_URL + "page", status=status)
    transport = make_transport(clock, min_interval=0)

    with pytest.raises(NetworkError) as raised:
        transport.get("page")

    assert raised.value.status_code == status
    assert len(responses.calls) == 1
    assert clock.sleeps == []


@responses.activate
def test_retry_after_header_is_honoured_and_429_raises_rate_limited() -> None:
    clock = FakeClock()
    for _ in range(3):
        responses.get(BASE_URL + "page", status=429, headers={"Retry-After": "7"})
    transport = make_transport(clock, min_interval=0)

    with pytest.raises(RateLimitedError):
        transport.get("page")

    assert clock.sleeps == [7.0, 7.0]
    assert len(responses.calls) == 3


@responses.activate
def test_connection_errors_are_retried_then_reported() -> None:
    clock = FakeClock()
    responses.get(BASE_URL + "page", body=requests.ConnectionError("boom"))
    transport = make_transport(clock, min_interval=0)

    with pytest.raises(NetworkError, match="could not reach Equasis"):
        transport.get("page")

    assert len(responses.calls) == 3
    assert clock.sleeps == [1.0, 2.0]


@responses.activate
def test_save_html_writes_each_response(tmp_path: Path) -> None:
    clock = FakeClock()
    responses.post(BASE_URL + "restricted/Search?fs=Search", body="<html>results</html>")
    transport = make_transport(clock, min_interval=0, save_html_dir=tmp_path / "pages")

    transport.post("restricted/Search?fs=Search", data={"P_ENTREE": "TORM"})

    saved = list((tmp_path / "pages").iterdir())
    assert [p.name for p in saved] == ["001-post-restricted-Search.html"]
    assert saved[0].read_text(encoding="utf-8") == "<html>results</html>"


def test_retry_delay_grows_and_is_capped() -> None:
    policy = RetryPolicy(base_delay=2.0, backoff=2.0, max_delay=10.0, jitter=0.0)
    assert [policy.delay(n) for n in range(4)] == [2.0, 4.0, 8.0, 10.0]
    assert policy.delay(0, retry_after=300) == 10.0
