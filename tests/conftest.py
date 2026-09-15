"""Shared fakes and fixtures for the Orisec local client tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest

from custom_components.orisec.api import OrisecLocalClient
from custom_components.orisec.protocol import Submessage, unpack_message

PANEL_HOST = "192.168.1.50"
PANEL_PORT = 20202
PANEL_PASSWORD = "1234"


class FakeSocket:
    """In-memory stand-in for the UDP socket boundary.

    Replays a queue of pre-packed datagrams and records everything sent so
    tests can assert on the bytes that reached the panel.
    """

    def __init__(self, responses: Iterable[bytes] = (), *, recv_error: BaseException | None = None) -> None:
        self._responses = list(responses)
        self._recv_error = recv_error
        self.sent_packets: list[tuple[bytes, tuple[str, int]]] = []
        self.timeout: float | None = None
        self.close_count = 0

    @property
    def closed(self) -> bool:
        return self.close_count > 0

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
        self.sent_packets.append((payload, address))

    def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
        if self._recv_error is not None:
            raise self._recv_error
        if not self._responses:
            raise AssertionError("The client read more datagrams than the test queued")
        return self._responses.pop(0), (PANEL_HOST, PANEL_PORT)

    def close(self) -> None:
        self.close_count += 1

    def sent_submessages(self, index: int = -1) -> list[Submessage]:
        """Decode the submessages of a recorded datagram."""

        return unpack_message(self.sent_packets[index][0])


class RecordingSocketFactory:
    """Socket factory that hands out fresh fakes and counts how often it ran."""

    def __init__(self, sockets: Iterable[FakeSocket]) -> None:
        self._sockets = list(sockets)
        self.created: list[FakeSocket] = []

    def __call__(self) -> FakeSocket:
        fake_socket = self._sockets.pop(0) if self._sockets else FakeSocket()
        self.created.append(fake_socket)
        return fake_socket


ClientFactory = Callable[..., tuple[OrisecLocalClient, FakeSocket]]


@pytest.fixture
def make_client() -> ClientFactory:
    """Build a client wired to a fresh fake socket, returning both."""

    def _make_client(
        responses: Iterable[bytes] = (),
        *,
        recv_error: BaseException | None = None,
        host: str = PANEL_HOST,
        password: str = PANEL_PASSWORD,
        **kwargs: object,
    ) -> tuple[OrisecLocalClient, FakeSocket]:
        fake_socket = FakeSocket(responses, recv_error=recv_error)
        client = OrisecLocalClient(host, password, socket_factory=lambda: fake_socket, **kwargs)
        return client, fake_socket

    return _make_client
