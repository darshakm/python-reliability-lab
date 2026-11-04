from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from reliability_lab.models import Order


def valid_order_data() -> dict[str, object]:
    return {
        "id": "ord_123",
        "customer_id": "cust_456",
        "status": "shipped",
        "amount": 149.99,
        "currency": "USD",
        "created_at": "2026-10-25T14:30:00Z",
    }


def test_from_dict_parses_valid_order() -> None:
    order = Order.from_dict(valid_order_data())

    assert order.id == "ord_123"
    assert order.status == "shipped"
    assert order.amount == Decimal("149.99")
    assert order.created_at == datetime(2026, 10, 25, 14, 30, tzinfo=UTC)


def test_order_is_immutable() -> None:
    order = Order.from_dict(valid_order_data())

    with pytest.raises(FrozenInstanceError):
        order.status = "cancelled"  # type: ignore[misc]


@pytest.mark.parametrize("status", ["delivered", "SHIPPED", "", 1, None])
def test_rejects_invalid_status(status: object) -> None:
    data = valid_order_data()
    data["status"] = status

    with pytest.raises(ValueError, match="status must be one of"):
        Order.from_dict(data)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0.10", Decimal("0.10")), (10, Decimal("10")), (0.1, Decimal("0.1"))],
)
def test_parses_amount_without_binary_float_artifacts(
    raw: object, expected: Decimal
) -> None:
    data = valid_order_data()
    data["amount"] = raw

    assert Order.from_dict(data).amount == expected


@pytest.mark.parametrize("amount", [-1, "NaN", "Infinity", True, "not-money"])
def test_rejects_invalid_amount(amount: object) -> None:
    data = valid_order_data()
    data["amount"] = amount

    with pytest.raises((TypeError, ValueError)):
        Order.from_dict(data)


@pytest.mark.parametrize(
    "timestamp",
    ["2026-10-25T14:30:00", "not-a-date", "", 1, None],
)
def test_rejects_invalid_or_naive_timestamp(timestamp: object) -> None:
    data = valid_order_data()
    data["created_at"] = timestamp

    with pytest.raises((TypeError, ValueError)):
        Order.from_dict(data)


def test_accepts_non_utc_timezone_offset() -> None:
    data = valid_order_data()
    data["created_at"] = "2026-10-25T14:30:00-07:00"

    assert Order.from_dict(data).created_at.utcoffset() is not None


@pytest.mark.parametrize("currency", ["usd", "US", "USDD", "12D", "€UR", 1])
def test_rejects_invalid_currency(currency: object) -> None:
    data = valid_order_data()
    data["currency"] = currency

    with pytest.raises((TypeError, ValueError)):
        Order.from_dict(data)


@pytest.mark.parametrize("field", ["id", "customer_id"])
@pytest.mark.parametrize("value", ["", " ", " ord_123 ", 123, None])
def test_rejects_invalid_identifiers(field: str, value: object) -> None:
    data = valid_order_data()
    data[field] = value

    with pytest.raises((TypeError, ValueError)):
        Order.from_dict(data)


def test_rejects_missing_field() -> None:
    data = valid_order_data()
    del data["customer_id"]

    with pytest.raises(ValueError, match="missing fields: customer_id"):
        Order.from_dict(data)


def test_rejects_unexpected_field() -> None:
    data = valid_order_data()
    data["discount"] = "10.00"

    with pytest.raises(ValueError, match="unexpected fields: discount"):
        Order.from_dict(data)


@pytest.mark.parametrize("data", [None, [], "order", 42])
def test_rejects_non_dictionary_payload(data: object) -> None:
    with pytest.raises(TypeError, match="must be a dictionary"):
        Order.from_dict(data)


def test_direct_construction_requires_domain_types() -> None:
    with pytest.raises(TypeError, match="amount must be a Decimal"):
        Order(
            id="ord_123",
            customer_id="cust_456",
            status="pending",
            amount=10,  # type: ignore[arg-type]
            currency="USD",
            created_at=datetime.now(UTC),
        )
