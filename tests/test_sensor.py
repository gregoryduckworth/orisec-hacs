"""Tests for the entities the config entry generates from the panel."""

from __future__ import annotations

import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import PANEL_MODEL, PANEL_SERIAL, FakePanel
from .test_init import setup_entry

ZONE_ENTITY_ID = "sensor.orisec_ori_0001_front_door"

pytestmark = pytest.mark.usefixtures("panel_sockets")


class TestZoneSensors:
    async def test_creates_one_entity_per_configured_zone(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        assert hass.states.get(ZONE_ENTITY_ID) is not None
        assert hass.states.get("sensor.orisec_ori_0001_hall_pir") is not None

    async def test_names_each_zone_the_way_the_panel_does(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        assert hass.states.get(ZONE_ENTITY_ID).attributes["friendly_name"] == (
            f"Orisec {PANEL_SERIAL} Front door"
        )

    async def test_falls_back_to_the_zone_number_when_the_panel_leaves_a_name_blank(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.zone_names = ["", "Hall PIR"]
        await setup_entry(hass, config_entry)

        assert hass.states.get("sensor.orisec_ori_0001_zone_1") is not None

    async def test_reports_the_status_word_the_panel_returned(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.zone_status = [5, 1]
        await setup_entry(hass, config_entry)

        assert hass.states.get(ZONE_ENTITY_ID).state == "5"

    async def test_exposes_the_panel_zone_number(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        assert hass.states.get("sensor.orisec_ori_0001_hall_pir").attributes["zone"] == 2

    async def test_picks_up_a_zone_added_to_the_panel_on_reload(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        await setup_entry(hass, config_entry)
        panel.zone_names = ["Front door", "Hall PIR", "Garage"]
        panel.zone_status = [0, 1, 1]

        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.orisec_ori_0001_garage").state == "1"

    async def test_creates_no_zone_entities_for_an_unconfigured_panel(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.zone_names = []
        panel.zone_status = []
        await setup_entry(hass, config_entry)

        assert hass.states.get(ZONE_ENTITY_ID) is None

    async def test_gives_every_zone_a_stable_unique_id(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        entry = er.async_get(hass).async_get(ZONE_ENTITY_ID)

        assert entry.unique_id == f"{PANEL_SERIAL}_zone_1"


class TestDiagnosticSensors:
    @pytest.mark.parametrize(
        ("entity_id", "expected"),
        [
            ("sensor.orisec_ori_0001_serial_number", PANEL_SERIAL),
            ("sensor.orisec_ori_0001_model", str(PANEL_MODEL)),
            ("sensor.orisec_ori_0001_configured_zones", "2"),
            ("sensor.orisec_ori_0001_areas", "1"),
            ("sensor.orisec_ori_0001_panel_status", "00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d"),
        ],
    )
    async def test_reports_what_the_panel_says_about_itself(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        entity_id: str,
        expected: str,
    ) -> None:
        await setup_entry(hass, config_entry)

        assert hass.states.get(entity_id).state == expected

    @pytest.mark.parametrize(
        "entity_id",
        [
            "sensor.orisec_ori_0001_serial_number",
            "sensor.orisec_ori_0001_model",
            "sensor.orisec_ori_0001_configured_zones",
            "sensor.orisec_ori_0001_areas",
            "sensor.orisec_ori_0001_panel_status",
        ],
    )
    async def test_keeps_panel_facts_out_of_the_main_dashboard(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, entity_id: str
    ) -> None:
        await setup_entry(hass, config_entry)

        entry = er.async_get(hass).async_get(entity_id)

        assert entry.entity_category is EntityCategory.DIAGNOSTIC

    async def test_lists_the_area_names_alongside_the_count(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        assert hass.states.get("sensor.orisec_ori_0001_areas").attributes["areas"] == ["House"]


class TestPanelWithoutASerialNumber:
    async def test_falls_back_to_the_entry_id_for_unique_ids(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.serial_number = ""
        await setup_entry(hass, config_entry)

        entry = er.async_get(hass).async_get("sensor.orisec_ori_0001_front_door")

        assert entry.unique_id == f"{config_entry.entry_id}_zone_1"

    async def test_leaves_the_device_serial_number_empty(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.serial_number = ""
        await setup_entry(hass, config_entry)

        entry = er.async_get(hass).async_get("sensor.orisec_ori_0001_front_door")
        device = hass.data["device_registry"].async_get(entry.device_id)

        assert device.serial_number is None
