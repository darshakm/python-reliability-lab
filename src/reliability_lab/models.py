"""Domain models and validation at the external-data boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast

type OrderStatus = Literal["pending", "processing", "shipped", "cancelled"]

_VALID_STATUSES: Final = frozenset(
    {"pending", "processing", "shipped", "cancelled"}
)
_REQUIRED_FIELDS: Final = frozenset(
    {"id", "customer_id", "status", "amount", "currency", "created_at"}
)


@dataclass(frozen=True, slots=True)
class Order:
    """A validated, immutable order returned by an external system.

    Constructing an ``Order`` directly expects already-parsed domain values.
    Use :meth:`from_dict` to validate and parse an untrusted API mapping.
    """

    id: str
    customer_id: str
    status: OrderStatus
    amount: Decimal
    currency: str
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_non_empty_string("id", self.id)
        _validate_non_empty_string("customer_id", self.customer_id)

        if not isinstance(self.status, str) or self.status not in _VALID_STATUSES:
            allowed = ", ".join(sorted(_VALID_STATUSES))
            raise ValueError(f"status must be one of: {allowed}")

        if not isinstance(self.amount, Decimal):
            raise TypeError("amount must be a Decimal")
        if not self.amount.is_finite():
            raise ValueError("amount must be finite")
        if self.amount < 0:
            raise ValueError("amount must not be negative")

        if not isinstance(self.currency, str):
            raise TypeError("currency must be a string")
        if (
            len(self.currency) != 3
            or not self.currency.isascii()
            or not self.currency.isalpha()
        ):
            raise ValueError("currency must be a three-letter ASCII code")
        if self.currency != self.currency.upper():
            raise ValueError("currency must be uppercase")

        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

    @classmethod
    def from_dict(cls, data: object) -> Order:
        """Parse an exact API record, rejecting missing or unexpected fields."""

        if not isinstance(data, dict):
            raise TypeError("order data must be a dictionary")
        if not all(isinstance(key, str) for key in data):
            raise TypeError("order data keys must be strings")

        keys = set(data)
        missing = _REQUIRED_FIELDS - keys
        unexpected = keys - _REQUIRED_FIELDS
        if missing:
            raise ValueError(f"missing fields: {', '.join(sorted(missing))}")
        if unexpected:
            raise ValueError(f"unexpected fields: {', '.join(sorted(unexpected))}")

        return cls(
            id=_require_string(data["id"], "id"),
            customer_id=_require_string(data["customer_id"], "customer_id"),
            status=_parse_status(data["status"]),
            amount=_parse_amount(data["amount"]),
            currency=_require_string(data["currency"], "currency"),
            created_at=_parse_timestamp(data["created_at"]),
        )


def _validate_non_empty_string(field: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value or value != value.strip():
        message = f"{field} must be non-empty and have no surrounding whitespace"
        raise ValueError(message)


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    return value


def _parse_status(value: object) -> OrderStatus:
    if not isinstance(value, str) or value not in _VALID_STATUSES:
        allowed = ", ".join(sorted(_VALID_STATUSES))
        raise ValueError(f"status must be one of: {allowed}")
    return cast(OrderStatus, value)


def _parse_amount(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise TypeError("amount must be a decimal-compatible number")
    if isinstance(value, str) and (not value or value != value.strip()):
        raise ValueError("amount must be a valid decimal number")

    try:
        # str(float) avoids importing the float's binary approximation into Decimal.
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("amount must be a valid decimal number") from error


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("created_at must be an ISO 8601 string")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("created_at must be a valid ISO 8601 timestamp") from error

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must include a timezone offset")
    return parsed
