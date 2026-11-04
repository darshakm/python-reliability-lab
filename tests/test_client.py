from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import Message
from email.utils import format_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from reliability_lab.client import OrderClient, RawResponse
from reliability_lab.exceptions import (
    AuthenticationError,
    MalformedResponseError,
    RequestTimeoutError,
    UpstreamServiceError,
)


def valid_order_body() -> bytes:
    return json.dumps(
        {
            "id": "order/123",
            "customer_id": "cust_456",
            "status": "shipped",
            "amount": "149.99",
            "currency": "USD",
            "created_at": "2026-10-25T14:30:00Z",
        }
    ).encode()


def make_client(transport: Callable[[Request, float], RawResponse]) -> OrderClient:
    return OrderClient(
        base_url="https://orders.example.test/api/",
        api_key="secret-token",
        timeout=2.5,
        transport=transport,
    )


def test_get_order_sends_authentication_timeout_and_encoded_id() -> None:
    observed_request: Request | None = None
    observed_timeout: float | None = None

    def transport(request: Request, timeout: float) -> RawResponse:
        nonlocal observed_request, observed_timeout
        observed_request = request
        observed_timeout = timeout
        return RawResponse(200, valid_order_body())

    order = make_client(transport).get_order("order/123")

    assert order.id == "order/123"
    assert observed_request is not None
    assert observed_request.full_url == (
        "https://orders.example.test/api/orders/order%2F123"
    )
    assert observed_request.get_header("Authorization") == "Bearer secret-token"
    assert observed_request.get_header("Accept") == "application/json"
    assert observed_request.method == "GET"
    assert observed_timeout == 2.5


@pytest.mark.parametrize("status_code", [401, 403])
def test_translates_authentication_failures(status_code: int) -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        return RawResponse(status_code, b"")

    with pytest.raises(AuthenticationError):
        make_client(transport).get_order("ord_123")


def test_translates_http_error_from_standard_transport() -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del timeout
        raise HTTPError(request.full_url, 401, "unauthorized", Message(), None)

    with pytest.raises(AuthenticationError):
        make_client(transport).get_order("ord_123")


@pytest.mark.parametrize(
    "error",
    [TimeoutError(), URLError(TimeoutError())],
)
def test_translates_timeouts(error: BaseException) -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        raise error

    with pytest.raises(RequestTimeoutError):
        make_client(transport).get_order("ord_123")


def test_translates_network_failure_without_exposing_api_key() -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        raise URLError("connection refused")

    with pytest.raises(UpstreamServiceError) as caught:
        make_client(transport).get_order("ord_123")

    assert "secret-token" not in str(caught.value)


@pytest.mark.parametrize("status_code", [400, 404, 429, 500, 503])
def test_translates_upstream_status(status_code: int) -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        return RawResponse(status_code, b"")

    with pytest.raises(UpstreamServiceError) as caught:
        make_client(transport).get_order("ord_123")

    assert caught.value.status_code == status_code


def test_preserves_numeric_retry_after_guidance() -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        return RawResponse(429, b"", {"Retry-After": "7.5"})

    with pytest.raises(UpstreamServiceError) as caught:
        make_client(transport).get_order("ord_123")

    assert caught.value.retry_after_seconds == 7.5


def test_converts_http_date_retry_after_to_seconds() -> None:
    now = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    retry_at = format_datetime(now + timedelta(seconds=12), usegmt=True)

    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        return RawResponse(503, b"", {"retry-after": retry_at})

    client = OrderClient(
        base_url="https://orders.example.test",
        api_key="secret-token",
        transport=transport,
        wall_clock=lambda: now,
    )
    with pytest.raises(UpstreamServiceError) as caught:
        client.get_order("ord_123")

    assert caught.value.retry_after_seconds == 12


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"\xff",
        b"[]",
        b'{}',
        b'{"id": "ord_123", "unexpected": true}',
    ],
)
def test_translates_malformed_responses(body: bytes) -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        return RawResponse(200, body)

    with pytest.raises(MalformedResponseError):
        make_client(transport).get_order("ord_123")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"base_url": "ftp://example.test", "api_key": "key"}, "base_url"),
        ({"base_url": "https://example.test", "api_key": ""}, "api_key"),
        (
            {"base_url": "https://example.test", "api_key": "key", "timeout": 0},
            "timeout",
        ),
    ],
)
def test_rejects_invalid_configuration(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        OrderClient(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("order_id", ["", " ", " ord_123 "])
def test_rejects_invalid_order_id(order_id: str) -> None:
    def transport(request: Request, timeout: float) -> RawResponse:
        del request, timeout
        raise AssertionError("transport should not be called")

    with pytest.raises(ValueError, match="order_id"):
        make_client(transport).get_order(order_id)
