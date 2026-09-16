"""Shared fakes and fixtures for the Orisec tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from struct import pack

import pytest
from homeassistant.components import network
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.orisec import api, discovery
from custom_components.orisec.api import OrisecLocalClient
from custom_components.orisec.const import (
    CMD_AREA_COUNT,
    CMD_AREA_NAMES,
    CMD_INFO_REQUEST,
    CMD_INFO_RESPONSE,
    CMD_LOGIN,
    CMD_MAX_ZONES,
    CMD_MOTION_EVENTS,
    CMD_PANEL_STATUS,
    CMD_SERIAL_NUMBER,
    CMD_SESSION_INFO,
    CMD_ZONE_COUNT,
    CMD_ZONE_NAMES,
    CMD_ZONE_STATUS,
    DOMAIN,
)
from custom_components.orisec.protocol import Submessage, pack_message, unpack_message

PANEL_HOST = "192.168.1.50"
PANEL_PORT = 20202
PANEL_PASSWORD = "1234"
PANEL_SERIAL = "ORI-0001"
PANEL_MODEL = 40
LOCAL_ADDRESS = "192.168.1.10"
LOCAL_PREFIX = 24


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load `custom_components/orisec` in every test."""


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


@dataclass
class FakePanel:
    """A panel that answers real protocol frames, so nothing above the socket is mocked.

    Tests drive the integration by mutating these attributes between polls, the
    same way a real panel changes underneath a running Home Assistant.
    """

    password: str = PANEL_PASSWORD
    serial_number: str = PANEL_SERIAL
    model: int = PANEL_MODEL
    max_zones: int = 32
    zone_names: list[str] = field(default_factory=lambda: ["Front door", "Hall PIR"])
    area_names: list[str] = field(default_factory=lambda: ["House"])
    zone_status: list[int] = field(default_factory=lambda: [0, 1])
    motion_events: list[int] = field(default_factory=lambda: [0, 7])
    panel_status: bytes = bytes(range(14))
    error: BaseException | None = None

    def respond(self, requests: list[Submessage]) -> bytes:
        """Pack the panel's answer to one datagram."""

        replies: list[Submessage] = []
        for request in requests:
            replies.extend(self._reply_to(request))
        return pack_message(*replies)

    def _reply_to(self, request: Submessage) -> list[Submessage]:
        if request.cmd_id == CMD_LOGIN:
            if request.data.decode("ascii") != self.password:
                return []
            return [
                Submessage(cmd_id=CMD_LOGIN, data=b"\x01"),
                Submessage(cmd_id=CMD_SESSION_INFO, data=b"session"),
            ]

        payloads = {
            CMD_INFO_REQUEST: (CMD_INFO_RESPONSE, pack("<HH", 0, self.model)),
            CMD_SERIAL_NUMBER: (CMD_SERIAL_NUMBER, self.serial_number.encode("ascii") + b"\x00"),
            CMD_MAX_ZONES: (CMD_MAX_ZONES, pack("<H", self.max_zones)),
            CMD_ZONE_COUNT: (CMD_ZONE_COUNT, pack("<H", len(self.zone_names))),
            CMD_AREA_COUNT: (CMD_AREA_COUNT, pack("<H", len(self.area_names))),
            CMD_ZONE_NAMES: (CMD_ZONE_NAMES, _pack_names(self.zone_names)),
            CMD_AREA_NAMES: (CMD_AREA_NAMES, _pack_names(self.area_names)),
            CMD_ZONE_STATUS: (CMD_ZONE_STATUS, bytes(self.zone_status)),
            CMD_MOTION_EVENTS: (CMD_MOTION_EVENTS, _pack_words(self.motion_events)),
            CMD_PANEL_STATUS: (CMD_PANEL_STATUS, self.panel_status),
        }

        cmd_id, data = payloads[request.cmd_id]
        return [Submessage(cmd_id=cmd_id, count=request.count, data=data)]


def _pack_names(names: list[str]) -> bytes:
    return b"".join(name.encode("ascii") + b"\x00" for name in names)


def _pack_words(values: list[int]) -> bytes:
    return pack(f"<{len(values)}H", *values)


class FakePanelSocket:
    """A UDP socket that hands every datagram to a `FakePanel` and returns its answer."""

    def __init__(self, panel: FakePanel) -> None:
        self._panel = panel
        self._pending: bytes | None = None
        self.sent_packets: list[tuple[bytes, tuple[str, int]]] = []
        self.timeout: float | None = None
        self.close_count = 0

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
        self.sent_packets.append((payload, address))
        if self._panel.error is not None:
            raise self._panel.error
        self._pending = self._panel.respond(unpack_message(payload))

    def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
        assert self._pending is not None, "The client read a datagram it never asked for"
        pending, self._pending = self._pending, None
        return pending, (PANEL_HOST, PANEL_PORT)

    def close(self) -> None:
        self.close_count += 1


@pytest.fixture
def panel() -> FakePanel:
    """The panel the integration talks to in tests."""

    return FakePanel()


@pytest.fixture
def panel_sockets(panel: FakePanel, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[FakePanelSocket]]:
    """Point every client built inside the integration at `panel`."""

    sockets: list[FakePanelSocket] = []

    def _factory() -> FakePanelSocket:
        socket = FakePanelSocket(panel)
        sockets.append(socket)
        return socket

    monkeypatch.setattr(api, "default_socket_factory", _factory)
    yield sockets


PANEL_REPLY = pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=pack("<HH", 0, PANEL_MODEL)))


class FakeDiscoverySocket:
    """A UDP socket that answers a discovery probe on behalf of some addresses.

    Every probe sent to an address in `panel_hosts` queues one reply, so a scan
    finds exactly the panels a test put on the network and nothing else.
    """

    def __init__(
        self,
        panel_hosts: Iterable[str] = (),
        *,
        reply: bytes | None = None,
        source: str | None = None,
        unreachable: Iterable[str] = (),
        recv_error: BaseException | None = None,
    ) -> None:
        self._panel_hosts = set(panel_hosts)
        self._reply = PANEL_REPLY if reply is None else reply
        self._source = source
        self._unreachable = set(unreachable)
        self._recv_error = recv_error
        self._queued: list[tuple[bytes, tuple[str, int]]] = []
        self.probed: list[tuple[str, int]] = []
        self.probes: list[bytes] = []
        self.timeout: float | None = None
        self.close_count = 0

    @property
    def probed_hosts(self) -> list[str]:
        return [host for host, _ in self.probed]

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
        host, port = address
        if host in self._unreachable:
            raise OSError("network is unreachable")

        self.probed.append((host, port))
        self.probes.append(payload)
        if host in self._panel_hosts:
            self._queued.append((self._reply, (self._source or host, port)))

    def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
        if self._recv_error is not None:
            raise self._recv_error
        if not self._queued:
            raise TimeoutError
        return self._queued.pop(0)

    def close(self) -> None:
        self.close_count += 1


@pytest.fixture
def panels_on_the_network() -> list[str]:
    """The addresses that answer a discovery probe. Override to change the scan."""

    return [PANEL_HOST]


@pytest.fixture(autouse=True)
def discovery_sockets(
    panels_on_the_network: list[str], monkeypatch: pytest.MonkeyPatch
) -> list[FakeDiscoverySocket]:
    """Keep every scan the flow runs on fake sockets, and record the ones it opened."""

    sockets: list[FakeDiscoverySocket] = []

    def _factory() -> FakeDiscoverySocket:
        scan_socket = FakeDiscoverySocket(panels_on_the_network)
        sockets.append(scan_socket)
        return scan_socket

    monkeypatch.setattr(discovery, "default_discovery_socket_factory", _factory)
    return sockets


@pytest.fixture(autouse=True)
def local_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give a scan one enabled network to sweep, whatever the machine running the tests has."""

    adapters = [
        {
            "name": "eth0",
            "index": 1,
            "enabled": True,
            "auto": True,
            "default": True,
            "ipv4": [{"address": LOCAL_ADDRESS, "network_prefix": LOCAL_PREFIX}],
            "ipv6": [],
        },
        {
            "name": "eth1",
            "index": 2,
            "enabled": False,
            "auto": False,
            "default": False,
            "ipv4": [{"address": "10.0.0.10", "network_prefix": 24}],
            "ipv6": [],
        },
    ]

    async def _async_get_adapters(hass: object) -> list[dict]:
        return adapters

    monkeypatch.setattr(network, "async_get_adapters", _async_get_adapters)


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry for the fake panel, not yet added to Home Assistant."""

    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Orisec {PANEL_SERIAL}",
        unique_id=PANEL_SERIAL,
        data={CONF_HOST: PANEL_HOST, CONF_PORT: PANEL_PORT, CONF_PASSWORD: PANEL_PASSWORD},
    )
