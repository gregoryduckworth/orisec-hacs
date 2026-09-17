"""Tests for the network scan that finds panels for the config flow."""

from __future__ import annotations

import socket
from ipaddress import IPv4Network

import pytest

from custom_components.orisec.const import (
    CMD_INFO_REQUEST,
    DEFAULT_PORT,
    MAX_DISCOVERY_NETWORK_SIZE,
)
from custom_components.orisec.discovery import (
    default_discovery_socket_factory,
    discover_panel_hosts,
    probe_addresses,
)
from custom_components.orisec.protocol import pack_message, unpack_message

from .conftest import PANEL_HOST, FakeDiscoverySocket

LOCAL_NETWORK = IPv4Network("192.168.1.0/24")
BROADCAST = "192.168.1.255"
OTHER_PANEL_HOST = "192.168.1.200"
# The largest network the scan is willing to sweep, as a prefix length.
LIMIT_PREFIX = 32 - (MAX_DISCOVERY_NETWORK_SIZE.bit_length() - 1)


def scan(
    scan_socket: FakeDiscoverySocket,
    networks: list[IPv4Network] | None = None,
    **kwargs: object,
) -> list[str]:
    """Run one scan of `networks` against a fake socket."""

    return discover_panel_hosts(
        [LOCAL_NETWORK] if networks is None else networks,
        socket_factory=lambda: scan_socket,
        **kwargs,
    )


class TestProbeAddresses:
    def test_probes_every_address_a_network_can_hold(self) -> None:
        addresses = probe_addresses([LOCAL_NETWORK])

        assert len(addresses) == 255
        assert PANEL_HOST in addresses

    def test_probes_the_broadcast_address_first(self) -> None:
        addresses = probe_addresses([LOCAL_NETWORK])

        assert addresses[0] == BROADCAST

    def test_probes_an_address_two_networks_share_only_once(self) -> None:
        addresses = probe_addresses([LOCAL_NETWORK, IPv4Network("192.168.1.0/25")])

        assert len(addresses) == len(set(addresses))

    def test_sweeps_a_network_at_the_size_limit(self) -> None:
        addresses = probe_addresses([IPv4Network(f"10.0.0.0/{LIMIT_PREFIX}")])

        assert len(addresses) == MAX_DISCOVERY_NETWORK_SIZE - 1

    def test_skips_a_network_too_large_to_sweep(self) -> None:
        addresses = probe_addresses([IPv4Network(f"10.0.0.0/{LIMIT_PREFIX - 1}")])

        assert addresses == []

    @pytest.mark.parametrize("cidr", ["127.0.0.0/24", "169.254.1.0/24"])
    def test_skips_a_network_that_cannot_hold_a_panel(self, cidr: str) -> None:
        addresses = probe_addresses([IPv4Network(cidr)])

        assert addresses == []

    def test_has_nothing_to_probe_without_networks(self) -> None:
        assert probe_addresses([]) == []


class TestDiscoverPanelHosts:
    def test_finds_the_address_a_panel_answered_from(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST])

        assert scan(scan_socket) == [PANEL_HOST]

    def test_finds_nothing_when_no_address_answers(self) -> None:
        scan_socket = FakeDiscoverySocket()

        assert scan(scan_socket) == []

    def test_asks_every_address_in_the_network(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST])

        scan(scan_socket)

        assert scan_socket.probed_hosts == probe_addresses([LOCAL_NETWORK])

    def test_asks_on_the_port_panels_listen_on(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST])

        scan(scan_socket)

        assert {port for _, port in scan_socket.probed} == {DEFAULT_PORT}

    def test_scans_a_port_a_panel_was_moved_to(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST])

        scan(scan_socket, port=20303)

        assert {port for _, port in scan_socket.probed} == {20303}

    def test_asks_for_the_panel_info_a_login_asks_for(self) -> None:
        scan_socket = FakeDiscoverySocket()

        scan(scan_socket)

        probes = {tuple(message.cmd_id for message in unpack_message(probe)) for probe in scan_socket.probes}
        assert probes == {(CMD_INFO_REQUEST,)}

    def test_reports_a_panel_that_answered_twice_only_once(self) -> None:
        scan_socket = FakeDiscoverySocket([BROADCAST, PANEL_HOST], source=PANEL_HOST)

        assert scan(scan_socket) == [PANEL_HOST]

    def test_returns_the_panels_it_found_in_address_order(self) -> None:
        scan_socket = FakeDiscoverySocket([OTHER_PANEL_HOST, PANEL_HOST])

        assert scan(scan_socket) == [PANEL_HOST, OTHER_PANEL_HOST]

    def test_ignores_an_answer_that_is_not_this_protocol(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST], reply=b"HTTP/1.1 400 Bad Request")

        assert scan(scan_socket) == []

    def test_ignores_a_frame_that_carries_no_submessage(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST], reply=pack_message())

        assert scan(scan_socket) == []

    def test_keeps_scanning_past_an_address_it_cannot_reach(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST], unreachable=[BROADCAST])

        assert scan(scan_socket) == [PANEL_HOST]

    def test_stops_collecting_when_the_socket_fails(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST], recv_error=OSError("network is down"))

        assert scan(scan_socket) == []

    def test_collects_nothing_once_the_time_budget_is_spent(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST])

        assert scan(scan_socket, timeout=0) == []
        assert scan_socket.probed_hosts

    def test_opens_no_socket_when_there_is_nothing_to_probe(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST])

        assert scan(scan_socket, networks=[]) == []
        assert scan_socket.probed == []

    def test_closes_the_socket_it_scanned_from(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST])

        scan(scan_socket)

        assert scan_socket.close_count == 1

    def test_closes_the_socket_even_when_the_scan_blows_up(self) -> None:
        scan_socket = FakeDiscoverySocket([PANEL_HOST], recv_error=ValueError("nobody predicted this"))

        with pytest.raises(ValueError):
            scan(scan_socket)

        assert scan_socket.close_count == 1


class TestDefaultDiscoverySocketFactory:
    """The one place a scan touches the real network stack."""

    def test_hands_out_an_unbound_udp_socket(self, socket_enabled: None) -> None:
        with default_discovery_socket_factory() as scan_socket:
            assert scan_socket.family is socket.AF_INET
            assert scan_socket.type is socket.SOCK_DGRAM

    def test_is_allowed_to_address_a_broadcast(self, socket_enabled: None) -> None:
        with default_discovery_socket_factory() as scan_socket:
            # Platforms report the flag as different truthy values, not always 1.
            assert scan_socket.getsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST)
