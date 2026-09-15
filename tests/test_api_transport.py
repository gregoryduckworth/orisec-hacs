"""Tests for socket lifecycle and datagram exchange in the local client."""

from __future__ import annotations

import pytest

from custom_components.orisec.api import OrisecError, OrisecLocalClient, ResponseError
from custom_components.orisec.const import CMD_MAX_ZONES, CMD_ZONE_NAMES, DEFAULT_PORT, DEFAULT_TIMEOUT
from custom_components.orisec.protocol import Submessage, pack_message

from .conftest import FakeSocket, RecordingSocketFactory


class TestOpen:
    def test_applies_the_configured_timeout_to_the_socket(self, make_client) -> None:
        client, fake_socket = make_client(timeout=7.5)

        client.open()

        assert fake_socket.timeout == 7.5

    def test_applies_the_default_timeout_when_none_is_given(self, make_client) -> None:
        client, fake_socket = make_client()

        client.open()

        assert fake_socket.timeout == DEFAULT_TIMEOUT

    def test_reuses_the_existing_socket_when_called_again(self) -> None:
        factory = RecordingSocketFactory([FakeSocket()])
        client = OrisecLocalClient("panel.local", "1234", socket_factory=factory)

        client.open()
        client.open()

        assert len(factory.created) == 1

    def test_creates_a_new_socket_after_the_previous_one_was_closed(self) -> None:
        factory = RecordingSocketFactory([FakeSocket(), FakeSocket()])
        client = OrisecLocalClient("panel.local", "1234", socket_factory=factory)

        client.open()
        client.close()
        client.open()

        assert len(factory.created) == 2


class TestClose:
    def test_closes_the_underlying_socket(self, make_client) -> None:
        client, fake_socket = make_client()
        client.open()

        client.close()

        assert fake_socket.close_count == 1

    def test_is_a_no_op_when_the_socket_was_never_opened(self, make_client) -> None:
        client, fake_socket = make_client()

        client.close()

        assert fake_socket.close_count == 0

    def test_does_not_close_twice(self, make_client) -> None:
        client, fake_socket = make_client()
        client.open()

        client.close()
        client.close()

        assert fake_socket.close_count == 1


class TestContextManager:
    def test_yields_the_client_itself(self, make_client) -> None:
        client, _ = make_client()

        with client as entered:
            assert entered is client

    def test_opens_the_socket_on_entry(self, make_client) -> None:
        client, fake_socket = make_client()

        with client:
            assert fake_socket.timeout == DEFAULT_TIMEOUT

    def test_closes_the_socket_on_exit(self, make_client) -> None:
        client, fake_socket = make_client()

        with client:
            pass

        assert fake_socket.closed

    def test_closes_the_socket_when_the_body_raises(self, make_client) -> None:
        client, fake_socket = make_client()

        with pytest.raises(RuntimeError, match="boom"), client:
            raise RuntimeError("boom")

        assert fake_socket.closed


class TestSend:
    def test_opens_the_socket_on_first_use(self, make_client) -> None:
        client, fake_socket = make_client()

        client.send(Submessage(cmd_id=CMD_MAX_ZONES))

        assert fake_socket.timeout == DEFAULT_TIMEOUT

    def test_addresses_the_configured_host_and_port(self, make_client) -> None:
        client, fake_socket = make_client(host="10.0.0.9", port=30303)

        client.send(Submessage(cmd_id=CMD_MAX_ZONES))

        assert fake_socket.sent_packets[0][1] == ("10.0.0.9", 30303)

    def test_defaults_to_the_documented_panel_port(self, make_client) -> None:
        client, fake_socket = make_client(host="10.0.0.9")

        client.send(Submessage(cmd_id=CMD_MAX_ZONES))

        assert fake_socket.sent_packets[0][1] == ("10.0.0.9", DEFAULT_PORT)

    def test_packs_every_submessage_into_one_datagram(self, make_client) -> None:
        client, fake_socket = make_client()

        client.send(Submessage(cmd_id=CMD_MAX_ZONES), Submessage(cmd_id=CMD_ZONE_NAMES, count=2))

        assert len(fake_socket.sent_packets) == 1
        assert fake_socket.sent_submessages() == [
            Submessage(cmd_id=CMD_MAX_ZONES, start=1, count=1, data=b""),
            Submessage(cmd_id=CMD_ZONE_NAMES, start=1, count=2, data=b""),
        ]

    def test_does_not_wait_for_a_reply(self, make_client) -> None:
        client, fake_socket = make_client(recv_error=AssertionError("the client must not read a reply"))

        client.send(Submessage(cmd_id=CMD_MAX_ZONES))

        assert len(fake_socket.sent_packets) == 1


class TestQueryMany:
    def test_returns_every_submessage_in_the_reply(self, make_client) -> None:
        client, _ = make_client(
            [
                pack_message(
                    Submessage(cmd_id=CMD_ZONE_NAMES, count=1, data=b"Front Door\x00"),
                    Submessage(cmd_id=CMD_ZONE_NAMES, count=1, data=b"Hall\x00"),
                )
            ]
        )

        responses = client.query_many([Submessage(cmd_id=CMD_ZONE_NAMES, count=2)])

        assert responses == [
            Submessage(cmd_id=CMD_ZONE_NAMES, start=1, count=1, data=b"Front Door\x00"),
            Submessage(cmd_id=CMD_ZONE_NAMES, start=1, count=1, data=b"Hall\x00"),
        ]

    def test_reports_a_timeout_with_the_panel_address(self, make_client) -> None:
        client, _ = make_client(recv_error=TimeoutError(), host="10.0.0.9", port=30303)

        with pytest.raises(OrisecError, match=r"10\.0\.0\.9:30303"):
            client.query_many([Submessage(cmd_id=CMD_MAX_ZONES)])

    def test_reports_an_undecodable_reply_as_a_response_error(self, make_client) -> None:
        client, _ = make_client([b"\xff\xff\x00\x00"])

        with pytest.raises(ResponseError, match="Payload length does not match header"):
            client.query_many([Submessage(cmd_id=CMD_MAX_ZONES)])

    def test_lets_unexpected_socket_errors_propagate(self, make_client) -> None:
        client, _ = make_client(recv_error=OSError("network is unreachable"))

        with pytest.raises(OSError, match="network is unreachable"):
            client.query_many([Submessage(cmd_id=CMD_MAX_ZONES)])


class TestQuery:
    def test_sends_the_requested_addressing_fields(self, make_client) -> None:
        client, fake_socket = make_client([pack_message(Submessage(cmd_id=CMD_ZONE_NAMES, data=b"Hall\x00"))])

        client.query(CMD_ZONE_NAMES, start=3, count=4, data=b"ab")

        assert fake_socket.sent_submessages() == [
            Submessage(cmd_id=CMD_ZONE_NAMES, start=3, count=4, data=b"ab")
        ]

    def test_returns_the_first_submessage_matching_the_command(self, make_client) -> None:
        client, _ = make_client(
            [
                pack_message(
                    Submessage(cmd_id=CMD_MAX_ZONES, data=b"\x14\x00"),
                    Submessage(cmd_id=CMD_ZONE_NAMES, count=1, data=b"Hall\x00"),
                    Submessage(cmd_id=CMD_ZONE_NAMES, count=1, data=b"Kitchen\x00"),
                )
            ]
        )

        assert client.query(CMD_ZONE_NAMES).data == b"Hall\x00"

    def test_raises_when_the_panel_answers_a_different_command(self, make_client) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_MAX_ZONES, data=b"\x14\x00"))])

        with pytest.raises(ResponseError, match="0x0460"):
            client.query(CMD_ZONE_NAMES)

    def test_raises_when_the_panel_answers_with_nothing(self, make_client) -> None:
        client, _ = make_client([pack_message()])

        with pytest.raises(ResponseError, match="0x045A"):
            client.query(CMD_MAX_ZONES)


class TestErrorHierarchy:
    def test_response_error_is_an_orisec_error(self) -> None:
        assert issubclass(ResponseError, OrisecError)

    def test_orisec_error_is_a_runtime_error(self) -> None:
        assert issubclass(OrisecError, RuntimeError)
