"""Tests for setting up, polling, reloading and unloading a config entry."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.orisec.const import CMD_LOGIN, DEFAULT_SCAN_INTERVAL, DOMAIN, MANUFACTURER
from custom_components.orisec.protocol import unpack_message

from .conftest import PANEL_MODEL, PANEL_SERIAL, FakePanel, FakePanelSocket


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry to Home Assistant and let it finish setting up."""

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Move past the poll interval and let one full update land."""

    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    # The coordinator refreshes in a background task, which a plain drain does
    # not wait for. Draining twice instead only wins the race while the read
    # finishes quickly, so wait for the background task itself.
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("panel_sockets")
class TestSetup:
    async def test_loads_a_reachable_panel(self, hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
        await setup_entry(hass, config_entry)

        assert config_entry.state is ConfigEntryState.LOADED

    async def test_registers_one_device_for_the_panel(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, PANEL_SERIAL)})

        assert device is not None
        assert device.manufacturer == MANUFACTURER
        assert device.model == str(PANEL_MODEL)
        assert device.serial_number == PANEL_SERIAL

    async def test_polls_at_the_default_interval(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        assert config_entry.runtime_data.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)

    async def test_polls_at_the_interval_chosen_in_the_options(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(config_entry, options={CONF_SCAN_INTERVAL: 90})
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.runtime_data.update_interval == timedelta(seconds=90)

    async def test_retries_later_when_the_panel_is_unreachable(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.error = OSError("no route to host")

        await setup_entry(hass, config_entry)

        assert config_entry.state is ConfigEntryState.SETUP_RETRY

    async def test_asks_for_a_new_password_when_the_stored_one_stops_working(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.password = "9999"

        await setup_entry(hass, config_entry)

        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        assert [flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()] == [
            SOURCE_REAUTH
        ]


@pytest.mark.usefixtures("panel_sockets")
class TestPolling:
    async def test_picks_up_a_zone_that_changed(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        panel: FakePanel,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        await setup_entry(hass, config_entry)
        panel.zone_status = [3, 1]

        await poll(hass, freezer)

        assert hass.states.get("sensor.orisec_ori_0001_front_door").state == "3"

    async def test_marks_entities_unavailable_when_the_panel_stops_answering(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        panel: FakePanel,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        await setup_entry(hass, config_entry)
        panel.error = TimeoutError()

        await poll(hass, freezer)

        assert hass.states.get("sensor.orisec_ori_0001_front_door").state == "unavailable"

    async def test_starts_reauthentication_when_a_poll_is_rejected(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        panel: FakePanel,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        await setup_entry(hass, config_entry)
        panel.password = "9999"

        await poll(hass, freezer)

        assert [flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()] == [
            SOURCE_REAUTH
        ]

    async def test_opens_a_fresh_authenticated_session_for_every_poll(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        panel_sockets: list[FakePanelSocket],
        freezer: FrozenDateTimeFactory,
    ) -> None:
        await setup_entry(hass, config_entry)
        before = len(panel_sockets)

        await poll(hass, freezer)

        assert len(panel_sockets) == before + 1
        first_request = unpack_message(panel_sockets[-1].sent_packets[0][0])[0]
        assert first_request.cmd_id == CMD_LOGIN


@pytest.mark.usefixtures("panel_sockets")
class TestUnloadAndReload:
    async def test_unloads_cleanly(self, hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
        await setup_entry(hass, config_entry)

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.NOT_LOADED

    async def test_removes_the_entities_it_created(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.orisec_ori_0001_front_door").state == "unavailable"

    async def test_closes_the_panel_socket(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        panel_sockets: list[FakePanelSocket],
    ) -> None:
        await setup_entry(hass, config_entry)

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert panel_sockets[-1].close_count > 0

    async def test_reloads_when_the_poll_interval_changes(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        await setup_entry(hass, config_entry)

        hass.config_entries.async_update_entry(config_entry, options={CONF_SCAN_INTERVAL: 45})
        await hass.async_block_till_done()

        assert config_entry.runtime_data.update_interval == timedelta(seconds=45)
