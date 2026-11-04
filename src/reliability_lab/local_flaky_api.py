"""Loopback HTTP server for deterministic integration and fault experiments."""

from __future__ import annotations

import socket
import threading
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast
from urllib.parse import unquote, urlparse


@dataclass(frozen=True, slots=True)
class PlannedHttpResponse:
    status_code: int = 200
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)
    delay: float = 0
    disconnect: bool = False

    def __post_init__(self) -> None:
        if self.delay < 0:
            raise ValueError("delay must not be negative")


@dataclass(frozen=True, slots=True)
class HttpRequestObservation:
    order_id: str
    authorization_present: bool
    response_status: int | None
    disconnected: bool


class LocalFlakyOrderApi:
    """Serve finite per-order HTTP scripts on an ephemeral loopback port."""

    def __init__(
        self, scripts: Mapping[str, Sequence[PlannedHttpResponse]]
    ) -> None:
        self._scripts = {
            order_id: deque(responses)
            for order_id, responses in scripts.items()
        }
        if any(not responses for responses in self._scripts.values()):
            raise ValueError("every order script must contain a response")
        self._observations: list[HttpRequestObservation] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> LocalFlakyOrderApi:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                prefix = "/orders/"
                if not parsed.path.startswith(prefix):
                    self.send_error(404)
                    return
                order_id = unquote(parsed.path[len(prefix) :])
                response = owner._next_response(order_id)
                authorization_present = self.headers.get("Authorization") is not None

                if response.delay:
                    time.sleep(response.delay)
                if response.disconnect:
                    owner._record(
                        HttpRequestObservation(
                            order_id=order_id,
                            authorization_present=authorization_present,
                            response_status=None,
                            disconnected=True,
                        )
                    )
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return

                self.send_response(response.status_code)
                for name, value in response.headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(response.body)))
                self.end_headers()
                try:
                    self.wfile.write(response.body)
                except BrokenPipeError:
                    pass
                owner._record(
                    HttpRequestObservation(
                        order_id=order_id,
                        authorization_present=authorization_present,
                        response_status=response.status_code,
                        disconnected=False,
                    )
                )

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        self._server = server
        self._thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.01),
            name="local-flaky-orders-api",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        del exc_info
        assert self._server is not None
        assert self._thread is not None
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("server is not running")
        host, port = cast(tuple[str, int], self._server.server_address)
        return f"http://{host}:{port}"

    @property
    def observations(self) -> tuple[HttpRequestObservation, ...]:
        with self._lock:
            return tuple(self._observations)

    def _next_response(self, order_id: str) -> PlannedHttpResponse:
        with self._lock:
            script = self._scripts.get(order_id)
            if script is None or not script:
                return PlannedHttpResponse(status_code=500, body=b"script exhausted")
            return script.popleft()

    def _record(self, observation: HttpRequestObservation) -> None:
        with self._lock:
            self._observations.append(observation)
