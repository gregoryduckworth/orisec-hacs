"""Focused tests for the local protocol/client helpers."""

from __future__ import annotations

import unittest

from custom_components.orisec.api import OrisecLocalClient
from custom_components.orisec.const import (
    CMD_INFO_RESPONSE,
    CMD_INFO_REQUEST,
    CMD_LOGIN,
    CMD_MAX_ZONES,
    CMD_MOTION_EVENTS,
    CMD_SESSION_INFO,
    CMD_KEEPALIVE,
    CMD_ZONE_NAMES,
)
from custom_components.orisec.protocol import Submessage, crc16_xmodem, pack_message, unpack_message


class FakeSocket:
    """Simple fake UDP socket for client tests."""

    def __init__(self, responses: list[bytes]) -> None:
        self._responses = list(responses)
        self.sent_packets: list[tuple[bytes, tuple[str, int]]] = []
        self.timeout = None
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
        self.sent_packets.append((payload, address))

    def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
        return self._responses.pop(0), ("panel", 20202)

    def close(self) -> None:
        self.closed = True


class ProtocolTests(unittest.TestCase):
    def test_crc16_matches_reference_vector(self) -> None:
        self.assertEqual(crc16_xmodem(b"123456789"), 0x29B1)

    def test_pack_unpack_round_trip(self) -> None:
        payload = pack_message(
            Submessage(cmd_id=0x0001, data=b"1234"),
            Submessage(cmd_id=0x045A, count=1),
        )

        decoded = unpack_message(payload)

        self.assertEqual(
            decoded,
            [
                Submessage(cmd_id=0x0001, start=1, count=1, data=b"1234"),
                Submessage(cmd_id=0x045A, start=1, count=1, data=b""),
            ],
        )

    def test_client_parses_known_responses(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(
                    Submessage(cmd_id=CMD_LOGIN),
                    Submessage(cmd_id=CMD_SESSION_INFO, data=b"\x01\x02"),
                    Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x14\x00"),
                ),
                pack_message(Submessage(cmd_id=CMD_MAX_ZONES, data=b"\x14\x00")),
                pack_message(Submessage(cmd_id=CMD_ZONE_NAMES, count=2, data=b"Front Door\x00Hall\x00")),
                pack_message(Submessage(cmd_id=CMD_MOTION_EVENTS, count=2, data=b"\x01\x00\x00\x00")),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.50",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        client.login()
        self.assertEqual(client.read_session_info(), b"\x01\x02")
        self.assertEqual(client.read_panel_model(), 20)
        self.assertEqual(client.read_max_zones(), 20)
        self.assertEqual(client.read_zone_names(2), ["Front Door", "Hall"])
        self.assertEqual(client.read_motion_events(2), [1, 0])
        client.keepalive()
        client.close()

        self.assertEqual(fake_socket.sent_packets[0][1], ("192.168.1.50", 20202))
        keepalive_payload = unpack_message(fake_socket.sent_packets[-1][0])
        self.assertEqual(keepalive_payload, [Submessage(cmd_id=CMD_KEEPALIVE, start=1, count=2, data=b"\x01\x00\x02\x04")])
        self.assertTrue(fake_socket.closed)

    def test_client_can_request_panel_model_without_login(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x28\x00")),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.51",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        self.assertEqual(client.read_panel_model(), 40)
        packet = unpack_message(fake_socket.sent_packets[0][0])
        self.assertEqual(packet, [Submessage(cmd_id=CMD_INFO_REQUEST, start=1, count=1, data=b"")])


if __name__ == "__main__":
    unittest.main()
