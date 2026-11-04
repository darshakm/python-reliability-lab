"""Typed HTTP client for the orders API."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPResponse
from typing import Final, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from reliability_lab.exceptions import (
    AuthenticationError,
    MalformedResponseError,
    RequestTimeoutError,
    UpstreamServiceError,
)
from reliability_lab.models import Order

_AUTH_FAILURES: Final = frozenset({401, 403})


@dataclass(frozen=True, slots=True)
class RawResponse:
    """Transport-neutral response data used by :class:`OrderClient`."""

    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


type Transport = Callable[[Request, float], RawResponse]
type WallClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _stdlib_transport(request: Request, timeout: float) -> RawResponse:
    """Execute a request with the standard library HTTP transport."""

    with urlopen(request, timeout=timeout) as response:
        typed_response = cast(HTTPResponse, response)
        return RawResponse(
            status_code=typed_response.status,
            body=typed_response.read(),
            headers=dict(typed_response.headers.items()),
        )


class OrderClient:
    """Retrieve and validate orders from a JSON HTTP API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 5.0,
        transport: Transport = _stdlib_transport,
        wall_clock: WallClock = _utc_now,
    ) -> None:
        normalized_url = base_url.rstrip("/")
        if not normalized_url.startswith(("https://", "http://")):
            raise ValueError("base_url must use http or https")
        if not api_key or api_key != api_key.strip():
            raise ValueError(
                "api_key must be non-empty and have no surrounding whitespace"
            )
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self._base_url = normalized_url
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport
        self._wall_clock = wall_clock

    def get_order(self, order_id: str) -> Order:
        """Fetch one order, translating transport and payload failures."""

        if not order_id or order_id != order_id.strip():
            raise ValueError(
                "order_id must be non-empty and have no surrounding whitespace"
            )

        encoded_id = quote(order_id, safe="")
        request = Request(
            f"{self._base_url}/orders/{encoded_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="GET",
        )

        try:
            response = self._transport(request, self._timeout)
        except HTTPError as error:
            if error.code in _AUTH_FAILURES:
                raise AuthenticationError(
                    "orders API rejected the credentials"
                ) from error
            raise UpstreamServiceError(
                f"orders API returned HTTP {error.code}",
                status_code=error.code,
                retry_after_seconds=_parse_retry_after(
                    dict(error.headers.items()) if error.headers else {},
                    self._wall_clock(),
                ),
            ) from error
        except TimeoutError as error:
            raise RequestTimeoutError("orders API request timed out") from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise RequestTimeoutError("orders API request timed out") from error
            raise UpstreamServiceError("orders API request failed") from error
        except OSError as error:
            raise UpstreamServiceError("orders API request failed") from error

        self._raise_for_status(response.status_code, response.headers)
        return self._parse_order(response.body)

    def _raise_for_status(
        self, status_code: int, headers: Mapping[str, str]
    ) -> None:
        if 200 <= status_code < 300:
            return
        if status_code in _AUTH_FAILURES:
            raise AuthenticationError("orders API rejected the credentials")
        raise UpstreamServiceError(
            f"orders API returned HTTP {status_code}",
            status_code=status_code,
            retry_after_seconds=_parse_retry_after(headers, self._wall_clock()),
        )

    @staticmethod
    def _parse_order(body: bytes) -> Order:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MalformedResponseError("orders API returned invalid JSON") from error

        try:
            return Order.from_dict(payload)
        except (TypeError, ValueError) as error:
            raise MalformedResponseError(
                "orders API returned an invalid order payload"
            ) from error


def _parse_retry_after(
    headers: Mapping[str, str], now: datetime
) -> float | None:
    value = next(
        (value for key, value in headers.items() if key.casefold() == "retry-after"),
        None,
    )
    if value is None:
        return None

    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - now).total_seconds())

    return seconds if seconds >= 0 else None
