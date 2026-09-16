"""Find Orisec panels on the local network by asking every address for one.

A panel has never been seen to announce itself: there is no mDNS or SSDP record
to subscribe to, and Home Assistant's DHCP discovery needs a hardware address
prefix or a hostname pattern that nobody has reported from a panel yet. What a
panel does reliably do is answer a well-formed frame, so discovery here is
active. Every address that could hold a panel is sent one info request, and
whatever answers with a frame this client can decode is a panel.

The CRC is what makes that identification safe: a reply counts only if its
declared length matches the datagram and its CRC matches the bytes in front of
it, which is not something an unrelated service sharing the UDP port produces
by accident. See the discovery page in the documentation for what was ruled out
and what is still unconfirmed against hardware.
"""

from __future__ import annotations

import logging
import socket
from collections.abc import Callable, Iterable
from ipaddress import IPv4Address, IPv4Network
from time import monotonic

from .const import (
    CMD_INFO_REQUEST,
    DEFAULT_PORT,
    DISCOVERY_TIMEOUT,
    MAX_DISCOVERY_NETWORK_SIZE,
)
from .protocol import ProtocolError, Submessage, pack_message, unpack_message

_LOGGER = logging.getLogger(__name__)

PROBE = pack_message(Submessage(cmd_id=CMD_INFO_REQUEST))


def default_discovery_socket_factory() -> socket.socket:
    """Return the UDP socket a scan sends from.

    Broadcast is enabled because each network's broadcast address is probed
    alongside its hosts, and kept as a module-level hook so tests can swap in a
    fake socket the same way the client's factory can.
    """

    scan_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    scan_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return scan_socket


def probe_addresses(networks: Iterable[IPv4Network]) -> list[str]:
    """Return the addresses worth probing across `networks`, each one once.

    A network's broadcast address goes first, so a panel that answers broadcasts
    is found without waiting for the sweep to reach it. Loopback and link-local
    networks cannot hold a panel worth finding, and a network larger than
    `MAX_DISCOVERY_NETWORK_SIZE` would take longer to sweep than anyone will
    wait in front of a config flow, so both are skipped rather than scanned.
    """

    addresses: dict[str, None] = {}

    for network in networks:
        if network.is_loopback or network.is_link_local:
            continue
        if network.num_addresses > MAX_DISCOVERY_NETWORK_SIZE:
            _LOGGER.debug("Not scanning %s: larger than %s addresses", network, MAX_DISCOVERY_NETWORK_SIZE)
            continue
        for address in (network.broadcast_address, *network.hosts()):
            addresses[str(address)] = None

    return list(addresses)


def discover_panel_hosts(
    networks: Iterable[IPv4Network],
    *,
    port: int = DEFAULT_PORT,
    timeout: float = DISCOVERY_TIMEOUT,
    socket_factory: Callable[[], socket.socket] | None = None,
) -> list[str]:
    """Probe `networks` and return the addresses a panel answered from.

    This blocks: every probe goes out first, then replies are collected until
    `timeout` has elapsed, because a sweep that waited for each address in turn
    would take the timeout multiplied by the size of the network. Answers arrive
    in whatever order panels send them, and one panel can answer twice - once to
    the broadcast and once to its own address - so the hosts are de-duplicated
    and returned in address order.
    """

    addresses = probe_addresses(networks)
    if not addresses:
        return []

    found: set[str] = set()
    scan_socket = (socket_factory or default_discovery_socket_factory)()

    try:
        for address in addresses:
            try:
                scan_socket.sendto(PROBE, (address, port))
            except OSError as err:
                # One address that cannot be reached - an interface that went
                # down, a broadcast the host refuses - must not end the scan.
                _LOGGER.debug("Could not probe %s: %s", address, err)

        deadline = monotonic() + timeout
        while (remaining := deadline - monotonic()) > 0:
            scan_socket.settimeout(remaining)
            try:
                payload, (host, _) = scan_socket.recvfrom(4096)
            except OSError:
                # How a scan normally ends: the socket ran out of time, so
                # every panel that was going to answer has answered. A socket
                # that failed outright has nothing left to give either.
                break

            if _is_panel_reply(payload):
                found.add(host)
            else:
                _LOGGER.debug("Ignoring reply from %s: not an Orisec frame", host)
    finally:
        scan_socket.close()

    return sorted(found, key=IPv4Address)


def _is_panel_reply(payload: bytes) -> bool:
    """Return whether `payload` is a frame only a panel would have sent."""

    try:
        return bool(unpack_message(payload))
    except ProtocolError:
        return False
