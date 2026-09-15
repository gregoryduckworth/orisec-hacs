"""Helpers for the Orisec local UDP protocol."""

from __future__ import annotations

from dataclasses import dataclass
from struct import pack, unpack_from


class ProtocolError(ValueError):
    """Raised when a protocol packet cannot be decoded."""


@dataclass(frozen=True)
class Submessage:
    """A single Orisec protocol submessage."""

    cmd_id: int
    start: int = 1
    count: int = 1
    data: bytes = b""


def crc16_xmodem(data: bytes) -> int:
    """Return the CRC used by the observed Orisec protocol frames."""

    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def pack_submessage(submessage: Submessage) -> bytes:
    """Encode a submessage."""

    return (
        pack("<HHHH", submessage.cmd_id, submessage.start, submessage.count, len(submessage.data))
        + submessage.data
    )


def pack_message(*submessages: Submessage) -> bytes:
    """Encode a complete UDP payload."""

    body = b"".join(pack_submessage(submessage) for submessage in submessages)
    total_length = 2 + len(body) + 2
    payload = pack("<H", total_length) + body
    return payload + pack("<H", crc16_xmodem(payload))


def unpack_message(payload: bytes) -> list[Submessage]:
    """Decode a complete UDP payload."""

    if len(payload) < 4:
        raise ProtocolError("Payload too short")

    declared_length = unpack_from("<H", payload, 0)[0]
    if declared_length != len(payload):
        raise ProtocolError("Payload length does not match header")

    expected_crc = unpack_from("<H", payload, len(payload) - 2)[0]
    actual_crc = crc16_xmodem(payload[:-2])
    if expected_crc != actual_crc:
        raise ProtocolError("CRC mismatch")

    offset = 2
    end = len(payload) - 2
    submessages: list[Submessage] = []

    while offset < end:
        if offset + 8 > end:
            raise ProtocolError("Truncated submessage header")

        cmd_id, start, count, data_len = unpack_from("<HHHH", payload, offset)
        offset += 8
        if offset + data_len > end:
            raise ProtocolError("Truncated submessage payload")

        submessages.append(
            Submessage(
                cmd_id=cmd_id,
                start=start,
                count=count,
                data=payload[offset : offset + data_len],
            )
        )
        offset += data_len

    return submessages
