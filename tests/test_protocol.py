"""Focused tests for the local protocol/client helpers."""

from __future__ import annotations

import unittest

from custom_components.orisec.api import AuthenticationError, OrisecLocalClient, ResponseError
from custom_components.orisec.const import (
    CMD_INFO_RESPONSE,
    CMD_INFO_REQUEST,
    CMD_LOGIN,
    CMD_MAX_ZONES,
    CMD_MOTION_EVENTS,
    CMD_SESSION_INFO,
    CMD_KEEPALIVE,
    CMD_SERIAL_NUMBER,
    CMD_ZONE_NAMES,
    CMD_ZONE_STATUS,
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

    def test_decode_strings_preserves_empty_positions(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(Submessage(cmd_id=CMD_ZONE_NAMES, count=3, data=b"Front Door\x00\x00Hall \x00")),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.52",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        self.assertEqual(client.read_zone_names(3), ["Front Door", "", "Hall "])

    def test_query_many_preserves_duplicate_command_ids(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(
                    Submessage(cmd_id=CMD_ZONE_NAMES, count=1, data=b"Front Door\x00"),
                    Submessage(cmd_id=CMD_ZONE_NAMES, count=1, data=b"Hall\x00"),
                ),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.53",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        responses = client.query_many([Submessage(cmd_id=CMD_ZONE_NAMES, count=2)])
        self.assertEqual(
            responses,
            [
                Submessage(cmd_id=CMD_ZONE_NAMES, start=1, count=1, data=b"Front Door\x00"),
                Submessage(cmd_id=CMD_ZONE_NAMES, start=1, count=1, data=b"Hall\x00"),
            ],
        )

    def test_short_payload_decoders_raise_response_error(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(Submessage(cmd_id=CMD_MAX_ZONES, data=b"\x14")),
                pack_message(Submessage(cmd_id=CMD_MOTION_EVENTS, count=2, data=b"\x01\x00\x00")),
                pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x14")),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.54",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        with self.assertRaises(ResponseError):
            client.read_max_zones()
        with self.assertRaises(ResponseError):
            client.read_motion_events(2)
        with self.assertRaises(ResponseError):
            client.read_panel_model()

    def test_invalid_serial_payload_raises_response_error(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b"\xff\xfe\x00")),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.55",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        with self.assertRaises(ResponseError):
            client.read_serial_number()

    def test_zone_status_supports_two_byte_entries(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(Submessage(cmd_id=CMD_ZONE_STATUS, count=2, data=b"\x01\x00\x02\x00")),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.56",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        self.assertEqual(client.read_zone_status(2), [1, 2])

    def test_invalid_string_payload_raises_response_error(self) -> None:
        fake_socket = FakeSocket(
            [
                pack_message(Submessage(cmd_id=CMD_ZONE_NAMES, count=1, data=b"\xff\x00")),
            ]
        )

        client = OrisecLocalClient(
            "192.168.1.57",
            "1234",
            socket_factory=lambda: fake_socket,
        )

        with self.assertRaises(ResponseError):
            client.read_zone_names(1)

    def test_non_ascii_password_raises_authentication_error(self) -> None:
        client = OrisecLocalClient("192.168.1.58", "päss")

        with self.assertRaisesRegex(AuthenticationError, "ASCII"):
            client.login()


if __name__ == "__main__":
    unittest.main()
