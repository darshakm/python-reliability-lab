"""Public exceptions raised by the reliability lab client."""

from __future__ import annotations


class ReliabilityLabError(Exception):
    """Base class for errors exposed by this package."""


class OrderClientError(ReliabilityLabError):
    """Base class for failures while retrieving an order."""


class AuthenticationError(OrderClientError):
    """The upstream service rejected the supplied credentials."""


class RequestTimeoutError(OrderClientError):
    """The upstream request exceeded its configured timeout."""


class MalformedResponseError(OrderClientError):
    """The upstream response could not be parsed into a valid order."""


class UpstreamServiceError(OrderClientError):
    """The upstream service failed outside the caller's control."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
