"""Local UDP client for Orisec alarm panels."""

from __future__ import annotations

import socket
from struct import unpack
from typing import Callable

from .const import (
    CMD_AREA_COUNT,
    CMD_AREA_NAMES,
    CMD_INFO_REQUEST,
    CMD_INFO_RESPONSE,
    CMD_KEEPALIVE,
    CMD_LOGIN,
    CMD_MAX_ZONES,
    CMD_MOTION_EVENTS,
    CMD_PANEL_STATUS,
    CMD_SERIAL_NUMBER,
    CMD_SESSION_INFO,
    CMD_ZONE_COUNT,
    CMD_ZONE_NAMES,
    CMD_ZONE_STATUS,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    KEEPALIVE_PAYLOAD,
)
from .protocol import ProtocolError, Submessage, pack_message, unpack_message


class OrisecError(RuntimeError):
    """Base error for the Orisec local client."""


class AuthenticationError(OrisecError):
    """Raised when panel authentication fails."""


class ResponseError(OrisecError):
    """Raised when an expected panel response is missing or malformed."""


class OrisecLocalClient:
    """Small synchronous client for Orisec's local UDP protocol."""

    def __init__(
        self,
        host: str,
        password: str,
        *,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        socket_factory: Callable[[], socket.socket] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._socket_factory = socket_factory or (lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
        self._socket: socket.socket | None = None
        self._session_info: bytes | None = None
        self._panel_model: int | None = None

    def __enter__(self) -> "OrisecLocalClient":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        """Open the UDP socket if needed."""

        if self._socket is not None:
            return

        self._socket = self._socket_factory()
        self._socket.settimeout(self.timeout)

    def close(self) -> None:
        """Close the UDP socket."""

        if self._socket is None:
            return

        self._socket.close()
        self._socket = None

    def query(self, cmd_id: int, *, start: int = 1, count: int = 1, data: bytes = b"") -> Submessage:
        """Send a single command and return its response."""

        responses = self.query_many([Submessage(cmd_id=cmd_id, start=start, count=count, data=data)])
        grouped = self._group_responses(responses)
        if cmd_id not in grouped:
            raise ResponseError(f"Panel did not return response for command 0x{cmd_id:04X}")
        return grouped[cmd_id][0]

    def query_many(self, submessages: list[Submessage]) -> list[Submessage]:
        """Send one UDP datagram containing one or more submessages."""

        self.open()
        assert self._socket is not None

        self._send(submessages)

        try:
            payload, _ = self._socket.recvfrom(4096)
        except (socket.timeout, TimeoutError) as exc:
            raise OrisecError(f"Timed out waiting for response from {self.host}:{self.port}") from exc

        try:
            responses = unpack_message(payload)
        except ProtocolError as exc:
            raise ResponseError(str(exc)) from exc

        return responses

    def send(self, *submessages: Submessage) -> None:
        """Send one UDP datagram without waiting for a response."""

        self.open()
        self._send(list(submessages))

    def login(self) -> None:
        """Authenticate to the panel and prime basic panel info."""

        try:
            password = self.password.encode("ascii")
        except UnicodeEncodeError as exc:
            raise AuthenticationError("Panel password must contain only ASCII characters") from exc

        responses = self._group_responses(
            self.query_many(
                [
                    Submessage(cmd_id=CMD_LOGIN, data=password),
                    Submessage(cmd_id=CMD_INFO_REQUEST),
                ]
            )
        )

        if CMD_LOGIN not in responses:
            raise AuthenticationError("Panel did not acknowledge login")
        if CMD_INFO_RESPONSE not in responses:
            raise ResponseError("Panel did not return model info")
        if CMD_SESSION_INFO in responses:
            self._session_info = responses[CMD_SESSION_INFO][0].data
        self._panel_model = self._decode_panel_model(responses[CMD_INFO_RESPONSE][0].data)

    def keepalive(self) -> None:
        """Keep the current session alive."""

        self.send(Submessage(cmd_id=CMD_KEEPALIVE, count=2, data=KEEPALIVE_PAYLOAD))

    def read_session_info(self) -> bytes:
        """Return the raw session info block."""

        if self._session_info is None:
            raise ResponseError("Session info is only available after login")
        return self._session_info

    def read_panel_model(self) -> int:
        """Return the panel model number."""

        if self._panel_model is not None:
            return self._panel_model

        responses = self._group_responses(self.query_many([Submessage(cmd_id=CMD_INFO_REQUEST)]))
        if CMD_INFO_RESPONSE not in responses:
            raise ResponseError("Panel did not return model info")
        self._panel_model = self._decode_panel_model(responses[CMD_INFO_RESPONSE][0].data)
        return self._panel_model

    def read_panel_status_raw(self) -> bytes:
        """Return the raw 14-byte panel status payload."""

        return self.query(CMD_PANEL_STATUS).data

    def read_serial_number(self) -> str:
        """Return the serial number string."""

        try:
            serial = self.query(CMD_SERIAL_NUMBER).data.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ResponseError("Serial number payload was not valid ASCII") from exc
        return serial.split("\x00", 1)[0]

    def read_max_zones(self) -> int:
        """Return the maximum zones supported by the panel."""

        return self._decode_uint16(self.query(CMD_MAX_ZONES).data, "max zones")

    def read_zone_count(self) -> int:
        """Return the number of configured zones."""

        return self._decode_uint16(self.query(CMD_ZONE_COUNT).data, "zone count")

    def read_area_count(self) -> int:
        """Return the number of configured areas."""

        return self._decode_uint16(self.query(CMD_AREA_COUNT).data, "area count")

    def read_zone_names(self, count: int) -> list[str]:
        """Return zone names."""

        return self._decode_strings(self.query(CMD_ZONE_NAMES, count=count).data, count)

    def read_area_names(self, count: int) -> list[str]:
        """Return area names."""

        return self._decode_strings(self.query(CMD_AREA_NAMES, count=count).data, count)

    def read_zone_status(self, count: int) -> list[int]:
        """Return zone status values as 8-bit or 16-bit integers based on payload width."""

        data = self.query(CMD_ZONE_STATUS, count=count).data
        if len(data) == count:
            return list(data)
        if len(data) == count * 2:
            return list(unpack(f"<{count}H", data))
        raise ResponseError("Zone status payload length did not match the requested count")

    def read_motion_events(self, count: int) -> list[int]:
        """Return 2-byte little-endian motion values for each zone."""

        data = self.query(CMD_MOTION_EVENTS, count=count).data
        expected_length = count * 2
        if len(data) != expected_length:
            raise ResponseError("Motion payload length did not match the requested count")
        return list(unpack(f"<{count}H", data))

    @staticmethod
    def _decode_uint16(data: bytes, label: str) -> int:
        if len(data) < 2:
            raise ResponseError(f"{label} payload was too short")
        return unpack("<H", data[:2])[0]

    @staticmethod
    def _decode_strings(data: bytes, count: int) -> list[str]:
        try:
            values = [part.decode("ascii") for part in data.split(b"\x00")]
        except UnicodeDecodeError as exc:
            raise ResponseError("String payload was not valid ASCII") from exc
        if values and values[-1] == "":
            values.pop()
        if len(values) < count:
            values.extend([""] * (count - len(values)))
        return values[:count]

    @staticmethod
    def _decode_panel_model(data: bytes) -> int:
        if len(data) < 4:
            raise ResponseError("Panel model payload was too short")
        return unpack("<HH", data[:4])[1]

    @staticmethod
    def _group_responses(responses: list[Submessage]) -> dict[int, list[Submessage]]:
        grouped: dict[int, list[Submessage]] = {}
        for response in responses:
            grouped.setdefault(response.cmd_id, []).append(response)
        return grouped

    def _send(self, submessages: list[Submessage]) -> None:
        assert self._socket is not None
        self._socket.sendto(pack_message(*submessages), (self.host, self.port))
