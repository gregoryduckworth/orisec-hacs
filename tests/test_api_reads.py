"""Tests for the panel read commands and their payload decoding."""

from __future__ import annotations

import pytest

from custom_components.orisec.api import ResponseError
from custom_components.orisec.const import (
    CMD_AREA_COUNT,
    CMD_AREA_NAMES,
    CMD_INFO_REQUEST,
    CMD_INFO_RESPONSE,
    CMD_MAX_ZONES,
    CMD_MOTION_EVENTS,
    CMD_PANEL_STATUS,
    CMD_SERIAL_NUMBER,
    CMD_ZONE_COUNT,
    CMD_ZONE_NAMES,
    CMD_ZONE_STATUS,
)
from custom_components.orisec.protocol import Submessage, pack_message

INFO_REPLY = pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x28\x00"))


class TestReadPanelModel:
    def test_requests_the_info_command(self, make_client) -> None:
        client, fake_socket = make_client([INFO_REPLY])

        client.read_panel_model()

        assert fake_socket.sent_submessages() == [
            Submessage(cmd_id=CMD_INFO_REQUEST, start=1, count=1, data=b"")
        ]

    def test_decodes_the_model_from_the_second_word(self, make_client) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x99\x99\x28\x00"))]
        )

        assert client.read_panel_model() == 40

    def test_ignores_trailing_bytes_after_the_model_word(self, make_client) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x28\x00junk"))]
        )

        assert client.read_panel_model() == 40

    def test_queries_the_panel_only_once(self, make_client) -> None:
        client, fake_socket = make_client([INFO_REPLY])

        client.read_panel_model()
        client.read_panel_model()

        assert len(fake_socket.sent_packets) == 1

    def test_raises_when_the_panel_omits_the_info_response(self, make_client) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_MAX_ZONES, data=b"\x14\x00"))])

        with pytest.raises(ResponseError, match="did not return model info"):
            client.read_panel_model()

    def test_raises_when_the_model_payload_is_too_short(self, make_client) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_INFO_RESPONSE, data=b"\x00\x00\x14"))])

        with pytest.raises(ResponseError, match="Panel model payload was too short"):
            client.read_panel_model()


class TestReadPanelStatusRaw:
    def test_returns_the_payload_unchanged(self, make_client) -> None:
        status = bytes(range(14))
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_PANEL_STATUS, data=status))])

        assert client.read_panel_status_raw() == status


class TestReadSerialNumber:
    def test_decodes_an_ascii_serial(self, make_client) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b"CPD0001"))])

        assert client.read_serial_number() == "CPD0001"

    def test_stops_at_the_first_terminator(self, make_client) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b"CPD0001\x00\x00PAD"))]
        )

        assert client.read_serial_number() == "CPD0001"

    def test_returns_an_empty_string_for_an_empty_payload(self, make_client) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b""))])

        assert client.read_serial_number() == ""

    def test_raises_when_the_payload_is_not_ascii(self, make_client) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b"\xff\xfe\x00"))])

        with pytest.raises(ResponseError, match="not valid ASCII"):
            client.read_serial_number()


COUNT_READERS = [
    pytest.param("read_max_zones", CMD_MAX_ZONES, "max zones", id="max-zones"),
    pytest.param("read_zone_count", CMD_ZONE_COUNT, "zone count", id="zone-count"),
    pytest.param("read_area_count", CMD_AREA_COUNT, "area count", id="area-count"),
]


class TestCountReaders:
    @pytest.mark.parametrize(("method", "cmd_id", "label"), COUNT_READERS)
    def test_requests_its_own_command(self, make_client, method: str, cmd_id: int, label: str) -> None:
        client, fake_socket = make_client([pack_message(Submessage(cmd_id=cmd_id, data=b"\x14\x00"))])

        getattr(client, method)()

        assert fake_socket.sent_submessages() == [Submessage(cmd_id=cmd_id, start=1, count=1, data=b"")]

    @pytest.mark.parametrize(("method", "cmd_id", "label"), COUNT_READERS)
    def test_decodes_a_little_endian_word(self, make_client, method: str, cmd_id: int, label: str) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, data=b"\x2c\x01"))])

        assert getattr(client, method)() == 300

    @pytest.mark.parametrize(("method", "cmd_id", "label"), COUNT_READERS)
    def test_ignores_bytes_beyond_the_first_word(
        self, make_client, method: str, cmd_id: int, label: str
    ) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, data=b"\x14\x00\xff\xff"))])

        assert getattr(client, method)() == 20

    @pytest.mark.parametrize(("method", "cmd_id", "label"), COUNT_READERS)
    def test_raises_when_the_payload_is_shorter_than_a_word(
        self, make_client, method: str, cmd_id: int, label: str
    ) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, data=b"\x14"))])

        with pytest.raises(ResponseError, match=f"{label} payload was too short"):
            getattr(client, method)()


NAME_READERS = [
    pytest.param("read_zone_names", CMD_ZONE_NAMES, id="zone-names"),
    pytest.param("read_area_names", CMD_AREA_NAMES, id="area-names"),
]


class TestNameReaders:
    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_asks_for_the_requested_number_of_entries(self, make_client, method: str, cmd_id: int) -> None:
        client, fake_socket = make_client(
            [pack_message(Submessage(cmd_id=cmd_id, count=2, data=b"A\x00B\x00"))]
        )

        getattr(client, method)(2)

        assert fake_socket.sent_submessages() == [Submessage(cmd_id=cmd_id, start=1, count=2, data=b"")]

    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_splits_null_terminated_names(self, make_client, method: str, cmd_id: int) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=cmd_id, count=2, data=b"Front Door\x00Hall\x00"))]
        )

        assert getattr(client, method)(2) == ["Front Door", "Hall"]

    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_preserves_unnamed_positions(self, make_client, method: str, cmd_id: int) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=cmd_id, count=3, data=b"Front Door\x00\x00Hall \x00"))]
        )

        assert getattr(client, method)(3) == ["Front Door", "", "Hall "]

    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_pads_when_the_panel_returns_fewer_names(self, make_client, method: str, cmd_id: int) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, count=3, data=b"Hall\x00"))])

        assert getattr(client, method)(3) == ["Hall", "", ""]

    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_truncates_when_the_panel_returns_more_names(self, make_client, method: str, cmd_id: int) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, count=2, data=b"A\x00B\x00C\x00"))])

        assert getattr(client, method)(2) == ["A", "B"]

    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_keeps_a_final_name_without_a_terminator(self, make_client, method: str, cmd_id: int) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, count=2, data=b"Hall\x00Kitchen"))])

        assert getattr(client, method)(2) == ["Hall", "Kitchen"]

    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_returns_blanks_for_an_empty_payload(self, make_client, method: str, cmd_id: int) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, count=2, data=b""))])

        assert getattr(client, method)(2) == ["", ""]

    @pytest.mark.parametrize(("method", "cmd_id"), NAME_READERS)
    def test_raises_when_a_name_is_not_ascii(self, make_client, method: str, cmd_id: int) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=cmd_id, count=1, data=b"\xff\x00"))])

        with pytest.raises(ResponseError, match="String payload was not valid ASCII"):
            getattr(client, method)(1)


class TestReadZoneStatus:
    def test_asks_for_the_requested_number_of_zones(self, make_client) -> None:
        client, fake_socket = make_client(
            [pack_message(Submessage(cmd_id=CMD_ZONE_STATUS, count=3, data=b"\x01\x02\x03"))]
        )

        client.read_zone_status(3)

        assert fake_socket.sent_submessages() == [
            Submessage(cmd_id=CMD_ZONE_STATUS, start=1, count=3, data=b"")
        ]

    def test_reads_one_byte_per_zone_when_the_payload_matches_the_count(self, make_client) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=CMD_ZONE_STATUS, count=3, data=b"\x01\x02\xff"))]
        )

        assert client.read_zone_status(3) == [1, 2, 255]

    def test_reads_two_bytes_per_zone_when_the_payload_is_twice_the_count(self, make_client) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=CMD_ZONE_STATUS, count=2, data=b"\x01\x00\x00\x01"))]
        )

        assert client.read_zone_status(2) == [1, 256]

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(b"\x01", id="under-one-byte-each"),
            pytest.param(b"\x01\x02\x03", id="between-the-two-widths"),
            pytest.param(b"\x01\x02\x03\x04\x05", id="over-two-bytes-each"),
        ],
    )
    def test_raises_when_the_payload_fits_neither_width(self, make_client, data: bytes) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_ZONE_STATUS, count=2, data=data))])

        with pytest.raises(ResponseError, match="Zone status payload length did not match"):
            client.read_zone_status(2)


class TestReadMotionEvents:
    def test_asks_for_the_requested_number_of_zones(self, make_client) -> None:
        client, fake_socket = make_client(
            [pack_message(Submessage(cmd_id=CMD_MOTION_EVENTS, count=2, data=b"\x01\x00\x00\x00"))]
        )

        client.read_motion_events(2)

        assert fake_socket.sent_submessages() == [
            Submessage(cmd_id=CMD_MOTION_EVENTS, start=1, count=2, data=b"")
        ]

    def test_decodes_two_little_endian_bytes_per_zone(self, make_client) -> None:
        client, _ = make_client(
            [pack_message(Submessage(cmd_id=CMD_MOTION_EVENTS, count=2, data=b"\x01\x00\x2c\x01"))]
        )

        assert client.read_motion_events(2) == [1, 300]

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(b"\x01\x00\x00", id="one-byte-short"),
            pytest.param(b"\x01\x00\x02\x00\x03\x00", id="one-zone-too-many"),
        ],
    )
    def test_raises_when_the_payload_length_does_not_match_the_count(self, make_client, data: bytes) -> None:
        client, _ = make_client([pack_message(Submessage(cmd_id=CMD_MOTION_EVENTS, count=2, data=data))])

        with pytest.raises(ResponseError, match="Motion payload length did not match"):
            client.read_motion_events(2)


class TestReadLayout:
    def test_collects_everything_that_describes_the_panel(self, make_client) -> None:
        client, _ = make_client(
            [
                pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b"ORI-0001\x00")),
                INFO_REPLY,
                pack_message(Submessage(cmd_id=CMD_ZONE_COUNT, data=b"\x02\x00")),
                pack_message(Submessage(cmd_id=CMD_AREA_COUNT, data=b"\x01\x00")),
                pack_message(Submessage(cmd_id=CMD_ZONE_NAMES, data=b"Front door\x00Hall PIR\x00")),
                pack_message(Submessage(cmd_id=CMD_AREA_NAMES, data=b"House\x00")),
            ]
        )

        layout = client.read_layout()

        assert layout.serial_number == "ORI-0001"
        assert layout.model == 40
        assert layout.zone_names == ["Front door", "Hall PIR"]
        assert layout.area_names == ["House"]

    def test_counts_the_zones_it_found_names_for(self, make_client) -> None:
        client, _ = make_client(
            [
                pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b"ORI-0001\x00")),
                INFO_REPLY,
                pack_message(Submessage(cmd_id=CMD_ZONE_COUNT, data=b"\x02\x00")),
                pack_message(Submessage(cmd_id=CMD_AREA_COUNT, data=b"\x01\x00")),
                pack_message(Submessage(cmd_id=CMD_ZONE_NAMES, data=b"Front door\x00Hall PIR\x00")),
                pack_message(Submessage(cmd_id=CMD_AREA_NAMES, data=b"House\x00")),
            ]
        )

        assert client.read_layout().zone_count == 2

    def test_skips_the_name_reads_a_bare_panel_cannot_answer(self, make_client) -> None:
        client, fake_socket = make_client(
            [
                pack_message(Submessage(cmd_id=CMD_SERIAL_NUMBER, data=b"ORI-0001\x00")),
                INFO_REPLY,
                pack_message(Submessage(cmd_id=CMD_ZONE_COUNT, data=b"\x00\x00")),
                pack_message(Submessage(cmd_id=CMD_AREA_COUNT, data=b"\x00\x00")),
            ]
        )

        layout = client.read_layout()

        assert layout.zone_names == []
        assert layout.area_names == []
        assert len(fake_socket.sent_packets) == 4


class TestReadState:
    def test_reads_the_panel_and_its_zones_in_one_pass(self, make_client) -> None:
        client, _ = make_client(
            [
                pack_message(Submessage(cmd_id=CMD_PANEL_STATUS, data=bytes(range(14)))),
                pack_message(Submessage(cmd_id=CMD_ZONE_STATUS, data=b"\x00\x01")),
            ]
        )

        state = client.read_state(2)

        assert state.panel_status == bytes(range(14))
        assert state.zone_status == [0, 1]

    def test_does_not_ask_a_zoneless_panel_about_zones(self, make_client) -> None:
        client, fake_socket = make_client(
            [pack_message(Submessage(cmd_id=CMD_PANEL_STATUS, data=bytes(range(14))))]
        )

        state = client.read_state(0)

        assert state.zone_status == []
        assert len(fake_socket.sent_packets) == 1
