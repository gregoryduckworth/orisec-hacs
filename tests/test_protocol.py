"""Tests for the Orisec packet encoding and decoding helpers."""

from __future__ import annotations

from struct import pack

import pytest

from custom_components.orisec.protocol import (
    ProtocolError,
    Submessage,
    crc16_xmodem,
    pack_message,
    pack_submessage,
    unpack_message,
)


def corrupt_last_byte(payload: bytes) -> bytes:
    """Return the payload with its final CRC byte flipped."""

    return payload[:-1] + bytes([payload[-1] ^ 0xFF])


def frame(body: bytes) -> bytes:
    """Wrap an arbitrary body in a well-formed length header and CRC trailer."""

    payload = pack("<H", 2 + len(body) + 2) + body
    return payload + pack("<H", crc16_xmodem(payload))


class TestCrc16Xmodem:
    def test_matches_the_published_check_vector(self) -> None:
        assert crc16_xmodem(b"123456789") == 0x29B1

    def test_returns_the_seed_for_an_empty_input(self) -> None:
        assert crc16_xmodem(b"") == 0xFFFF

    def test_detects_a_single_flipped_bit(self) -> None:
        assert crc16_xmodem(b"\x00") != crc16_xmodem(b"\x01")

    def test_depends_on_byte_order(self) -> None:
        assert crc16_xmodem(b"\x01\x02") != crc16_xmodem(b"\x02\x01")


class TestSubmessage:
    def test_defaults_to_a_single_empty_entry_starting_at_one(self) -> None:
        submessage = Submessage(cmd_id=0x0001)

        assert (submessage.start, submessage.count, submessage.data) == (1, 1, b"")


class TestPackSubmessage:
    def test_writes_the_four_header_fields_as_little_endian_words(self) -> None:
        encoded = pack_submessage(Submessage(cmd_id=0x045A, start=2, count=3, data=b"ab"))

        assert encoded == b"\x5a\x04\x02\x00\x03\x00\x02\x00ab"

    def test_declares_a_zero_length_body_when_there_is_no_data(self) -> None:
        encoded = pack_submessage(Submessage(cmd_id=0x0001))

        assert encoded == b"\x01\x00\x01\x00\x01\x00\x00\x00"


class TestPackMessage:
    def test_prefixes_the_total_datagram_length(self) -> None:
        payload = pack_message(Submessage(cmd_id=0x0001, data=b"1234"))

        assert payload[:2] == pack("<H", len(payload))

    def test_appends_a_crc_over_everything_before_it(self) -> None:
        payload = pack_message(Submessage(cmd_id=0x0001, data=b"1234"))

        assert payload[-2:] == pack("<H", crc16_xmodem(payload[:-2]))

    def test_encodes_an_empty_datagram_as_header_plus_crc(self) -> None:
        assert pack_message() == b"\x04\x00" + pack("<H", crc16_xmodem(b"\x04\x00"))

    def test_concatenates_submessages_in_the_given_order(self) -> None:
        payload = pack_message(Submessage(cmd_id=0x0001), Submessage(cmd_id=0x0002))

        assert payload[2:-2] == pack_submessage(Submessage(cmd_id=0x0001)) + pack_submessage(
            Submessage(cmd_id=0x0002)
        )


class TestUnpackMessage:
    def test_round_trips_multiple_submessages(self) -> None:
        submessages = [
            Submessage(cmd_id=0x0001, data=b"1234"),
            Submessage(cmd_id=0x045A, start=7, count=9, data=b""),
            Submessage(cmd_id=0x2850, start=1, count=2, data=b"\x00\xff"),
        ]

        assert unpack_message(pack_message(*submessages)) == submessages

    def test_returns_no_submessages_for_an_empty_datagram(self) -> None:
        assert unpack_message(pack_message()) == []

    def test_preserves_data_bytes_that_look_like_a_header(self) -> None:
        submessage = Submessage(cmd_id=0x0001, data=b"\x01\x00\x01\x00\x01\x00\x00\x00")

        assert unpack_message(pack_message(submessage)) == [submessage]

    @pytest.mark.parametrize(
        ("payload", "reason"),
        [
            pytest.param(b"", "Payload too short", id="empty"),
            pytest.param(b"\x03\x00\x00", "Payload too short", id="shorter-than-header-and-crc"),
            pytest.param(b"\xff\xff\x00\x00", "Payload length does not match header", id="length-mismatch"),
            pytest.param(
                corrupt_last_byte(pack_message(Submessage(cmd_id=0x0001))),
                "CRC mismatch",
                id="corrupt-crc",
            ),
            pytest.param(frame(b"\x01\x00\x01\x00"), "Truncated submessage header", id="partial-header"),
            pytest.param(
                frame(b"\x01\x00\x01\x00\x01\x00\x08\x00ab"),
                "Truncated submessage payload",
                id="data-shorter-than-declared",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, payload: bytes, reason: str) -> None:
        with pytest.raises(ProtocolError, match=reason):
            unpack_message(payload)

    def test_rejects_a_payload_whose_body_was_tampered_with(self) -> None:
        payload = bytearray(pack_message(Submessage(cmd_id=0x0001, data=b"1234")))
        payload[10] ^= 0xFF

        with pytest.raises(ProtocolError, match="CRC mismatch"):
            unpack_message(bytes(payload))


def test_protocol_error_is_a_value_error() -> None:
    assert issubclass(ProtocolError, ValueError)
