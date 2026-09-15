"""Tests for login, session state and keepalive behaviour."""

from __future__ import annotations

import pytest

from custom_components.orisec.api import AuthenticationError, ResponseError
from custom_components.orisec.const import (
    CMD_INFO_REQUEST,
    CMD_INFO_RESPONSE,
    CMD_KEEPALIVE,
    CMD_LOGIN,
    CMD_SESSION_INFO,
    KEEPALIVE_PAYLOAD,
)
from custom_components.orisec.protocol import Submessage, pack_message

LOGIN_REPLY = pack_message(
    Submessage(cmd_id=CMD_LOGIN),
    Submessage(cmd_id=CMD_SESSION_INFO, data=b"\x01\x02"),
    Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x14\x00"),
)


class TestLoginRequest:
    def test_asks_for_login_and_panel_info_in_one_datagram(self, make_client) -> None:
        client, fake_socket = make_client([LOGIN_REPLY])

        client.login()

        assert fake_socket.sent_submessages() == [
            Submessage(cmd_id=CMD_LOGIN, start=1, count=1, data=b"1234"),
            Submessage(cmd_id=CMD_INFO_REQUEST, start=1, count=1, data=b""),
        ]

    def test_sends_the_password_as_ascii_bytes(self, make_client) -> None:
        client, fake_socket = make_client([LOGIN_REPLY], password="9876")

        client.login()

        assert fake_socket.sent_submessages()[0].data == b"9876"

    def test_rejects_a_non_ascii_password_before_touching_the_network(self, make_client) -> None:
        client, fake_socket = make_client(password="pässword")

        with pytest.raises(AuthenticationError, match="ASCII"):
            client.login()

        assert fake_socket.sent_packets == []


class TestLoginResult:
    def test_caches_the_session_info_block(self, make_client) -> None:
        client, _ = make_client([LOGIN_REPLY])

        client.login()

        assert client.read_session_info() == b"\x01\x02"

    def test_caches_the_panel_model(self, make_client) -> None:
        client, fake_socket = make_client([LOGIN_REPLY])

        client.login()

        assert client.read_panel_model() == 20
        assert len(fake_socket.sent_packets) == 1

    def test_raises_when_the_panel_does_not_acknowledge_the_login(self, make_client) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x14\x00"))]
        )

        with pytest.raises(AuthenticationError, match="did not acknowledge login"):
            client.login()

    def test_raises_when_the_panel_omits_the_model_info(self, make_client) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_LOGIN))])

        with pytest.raises(ResponseError, match="did not return model info"):
            client.login()

    def test_succeeds_when_the_panel_omits_the_optional_session_block(self, make_client) -> None:
        client, _ = make_client(
            [
                pack_message(
                    Submessage(cmd_id=CMD_LOGIN),
                    Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x14\x00"),
                )
            ]
        )

        client.login()

        assert client.read_panel_model() == 20

    def test_leaves_session_info_unavailable_when_the_panel_omits_it(self, make_client) -> None:
        client, _ = make_client(
            [
                pack_message(
                    Submessage(cmd_id=CMD_LOGIN),
                    Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x14\x00"),
                )
            ]
        )
        client.login()

        with pytest.raises(ResponseError, match="only available after login"):
            client.read_session_info()


class TestReadSessionInfo:
    def test_raises_before_a_successful_login(self, make_client) -> None:
        client, _ = make_client()

        with pytest.raises(ResponseError, match="only available after login"):
            client.read_session_info()


class TestKeepalive:
    def test_sends_the_fixed_keepalive_submessage(self, make_client) -> None:
        client, fake_socket = make_client()

        client.keepalive()

        assert fake_socket.sent_submessages() == [
            Submessage(cmd_id=CMD_KEEPALIVE, start=1, count=2, data=KEEPALIVE_PAYLOAD)
        ]

    def test_does_not_wait_for_a_reply(self, make_client) -> None:
        client, fake_socket = make_client(recv_error=AssertionError("keepalive must not read a reply"))

        client.keepalive()

        assert len(fake_socket.sent_packets) == 1
