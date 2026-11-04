"""Construct and display one validated immutable order."""

from reliability_lab import Order

order = Order.from_dict(
    {
        "id": "ord_123",
        "customer_id": "cust_456",
        "status": "shipped",
        "amount": "149.99",
        "currency": "USD",
        "created_at": "2026-10-25T14:30:00Z",
    }
)

print(f"{order.id}: {order.amount} {order.currency} ({order.status})")
