#!/usr/bin/env python3
"""Probe a real Orisec panel over the local UDP protocol and print what it reports.

This is the quickest way to check the client against actual hardware: it needs
no Home Assistant install, only the panel's IP and a user password.

    python3 scripts/probe.py --host 192.168.1.50 --password 1234

Every read is attempted independently, so a command the panel does not support
is reported as a single failed row instead of aborting the run.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.orisec.api import (  # noqa: E402
    AuthenticationError,
    OrisecError,
    OrisecLocalClient,
)
from custom_components.orisec.const import DEFAULT_PORT, DEFAULT_TIMEOUT  # noqa: E402


def _format(value: Any) -> str:
    """Render a panel value for the terminal."""

    if isinstance(value, bytes):
        return value.hex(" ") or "(empty)"
    if isinstance(value, list):
        if not value:
            return "(none)"
        return "\n".join(f"    {index:>3}. {item}" for index, item in enumerate(value, start=1))
    return str(value)


def _read(label: str, read: Callable[[], Any]) -> Any:
    """Run one panel read, printing the result or the reason it failed."""

    try:
        value = read()
    except OrisecError as err:
        print(f"{label}:\n    ! {err}")
        return None

    rendered = _format(value)
    separator = "\n" if "\n" in rendered else " "
    print(f"{label}:{separator}{rendered}")
    return value


def probe(client: OrisecLocalClient) -> None:
    """Log in and dump every panel read the client knows about."""

    client.login()
    print("login: ok\n")

    _read("serial number", client.read_serial_number)
    _read("panel model", client.read_panel_model)
    _read("panel status (raw)", client.read_panel_status_raw)

    max_zones = _read("max zones", client.read_max_zones)
    zone_count = _read("configured zones", client.read_zone_count)
    area_count = _read("areas", client.read_area_count)

    if zone_count:
        _read("zone names", lambda: client.read_zone_names(zone_count))
        _read("zone status", lambda: client.read_zone_status(zone_count))
        _read("motion events", lambda: client.read_motion_events(zone_count))
    elif max_zones:
        print("zone names:\n    ! skipped, panel reports 0 configured zones")

    if area_count:
        _read("area names", lambda: client.read_area_names(area_count))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", required=True, help="panel IP address or hostname")
    parser.add_argument("--password", required=True, help="panel user password")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"UDP port (default {DEFAULT_PORT})")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"per-request timeout in seconds (default {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args(argv)

    print(f"probing {args.host}:{args.port} (timeout {args.timeout}s)\n")

    try:
        with OrisecLocalClient(args.host, args.password, port=args.port, timeout=args.timeout) as client:
            probe(client)
    except AuthenticationError as err:
        print(f"error: authentication failed: {err}", file=sys.stderr)
        return 2
    except OrisecError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except OSError as err:
        print(f"error: could not reach {args.host}:{args.port}: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
