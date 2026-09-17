#!/usr/bin/env python3
"""Scan a network for Orisec panels and print the addresses that answered.

This is the same scan the config flow runs when you add a panel, without needing
Home Assistant, which makes it the way to find out whether a panel answers an
unauthenticated probe at all:

    python3 scripts/discover.py
    python3 scripts/discover.py --network 192.168.1.0/24 --timeout 5

Every address in the network is sent one info request and the replies are
collected until the timeout runs out. A reply only counts if it decodes as an
Orisec frame, CRC included, so anything listed here speaks the protocol.

Finding nothing is a result worth reporting too: it means panels answer probes
only once a session exists, and discovery has to be built on something else.
"""

from __future__ import annotations

import argparse
import socket
import sys
from ipaddress import IPv4Network
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.orisec.const import DEFAULT_PORT, DISCOVERY_TIMEOUT  # noqa: E402
from custom_components.orisec.discovery import (  # noqa: E402
    discover_panel_hosts,
    probe_addresses,
)


def local_network() -> IPv4Network:
    """Return the /24 around the address this machine sends from.

    A /24 is the guess, not a reading: the prefix is not discoverable from a
    socket. Pass `--network` for anything else.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as address_probe:
        # Connecting a UDP socket sends nothing; it only picks the source address.
        address_probe.connect(("192.0.2.1", 9))
        address = address_probe.getsockname()[0]

    return IPv4Network(f"{address}/24", strict=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--network",
        type=IPv4Network,
        help="network to scan in CIDR form (default: the /24 this machine is on)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"UDP port (default {DEFAULT_PORT})")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DISCOVERY_TIMEOUT,
        help=f"seconds to listen for answers (default {DISCOVERY_TIMEOUT:g})",
    )
    args = parser.parse_args(argv)

    network = args.network or local_network()
    addresses = probe_addresses([network])
    if not addresses:
        print(f"error: {network} is not a network worth scanning", file=sys.stderr)
        return 1

    print(f"scanning {len(addresses)} addresses in {network} on port {args.port} ({args.timeout:g}s)\n")

    try:
        hosts = discover_panel_hosts([network], port=args.port, timeout=args.timeout)
    except OSError as err:
        print(f"error: could not scan {network}: {err}", file=sys.stderr)
        return 1

    if not hosts:
        print("no panels answered.")
        print("A panel on this network may still only answer once logged in - try")
        print("scripts/probe.py against its address, and please report either result.")
        return 1

    print(f"{len(hosts)} panel(s) answered:")
    for host in hosts:
        print(f"    {host}:{args.port}")
    print("\nConfirm one with: python3 scripts/probe.py --host <address> --password <password>")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
