from __future__ import annotations

import asyncio
import json

import pytest

from reliability_lab.client import OrderClient
from reliability_lab.exceptions import (
    MalformedResponseError,
    RequestTimeoutError,
    UpstreamServiceError,
)
from reliability_lab.local_flaky_api import (
    LocalFlakyOrderApi,
    PlannedHttpResponse,
)
from reliability_lab.retry import RetryPolicy, execute_resiliently


def order_body(order_id: str) -> bytes:
    return json.dumps(
        {
            "id": order_id,
            "customer_id": "cust_http",
            "status": "pending",
            "amount": "10.00",
            "currency": "USD",
            "created_at": "2026-11-03T12:00:00Z",
        }
    ).encode()


def test_real_http_boundary_sends_auth_and_parses_order() -> None:
    with LocalFlakyOrderApi(
        {"ord_1": [PlannedHttpResponse(body=order_body("ord_1"))]}
    ) as server:
        order = OrderClient(
            base_url=server.base_url, api_key="secret"
        ).get_order("ord_1")

    assert order.id == "ord_1"
    assert server.observations[0].authorization_present


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (PlannedHttpResponse(body=b"not-json"), MalformedResponseError),
        (PlannedHttpResponse(disconnect=True), UpstreamServiceError),
        (PlannedHttpResponse(status_code=503), UpstreamServiceError),
    ],
)
def test_real_http_fault_matrix(
    response: PlannedHttpResponse, error_type: type[Exception]
) -> None:
    with LocalFlakyOrderApi({"ord_1": [response]}) as server:
        client = OrderClient(base_url=server.base_url, api_key="secret")
        with pytest.raises(error_type):
            client.get_order("ord_1")


def test_real_http_timeout() -> None:
    with LocalFlakyOrderApi(
        {
            "ord_1": [
                PlannedHttpResponse(body=order_body("ord_1"), delay=0.05)
            ]
        }
    ) as server:
        client = OrderClient(
            base_url=server.base_url,
            api_key="secret",
            timeout=0.005,
        )
        with pytest.raises(RequestTimeoutError):
            client.get_order("ord_1")


def test_real_http_503_then_recovery_through_retry_layer() -> None:
    async def scenario() -> None:
        with LocalFlakyOrderApi(
            {
                "ord_1": [
                    PlannedHttpResponse(status_code=503),
                    PlannedHttpResponse(body=order_body("ord_1")),
                ]
            }
        ) as server:
            client = OrderClient(base_url=server.base_url, api_key="secret")
            order = await execute_resiliently(
                lambda: asyncio.to_thread(client.get_order, "ord_1"),
                safety="safe",
                policy=RetryPolicy(max_attempts=2, initial_delay=0),
            )

        assert order.id == "ord_1"
        assert len(server.observations) == 2

    asyncio.run(scenario())
