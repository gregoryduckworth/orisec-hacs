"""Tests for the config, reauth and options flows."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.orisec.const import DEFAULT_SCAN_INTERVAL, DOMAIN

from .conftest import PANEL_HOST, PANEL_PASSWORD, PANEL_PORT, PANEL_SERIAL, FakePanel

USER_INPUT = {CONF_HOST: PANEL_HOST, CONF_PASSWORD: PANEL_PASSWORD, CONF_PORT: PANEL_PORT}


async def start_user_flow(hass: HomeAssistant) -> str:
    """Open the user flow and return its id."""

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


@pytest.mark.usefixtures("panel_sockets")
class TestUserFlow:
    async def test_creates_an_entry_from_a_reachable_panel(self, hass: HomeAssistant) -> None:
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Orisec {PANEL_SERIAL}"
        assert result["data"] == USER_INPUT

    async def test_identifies_the_entry_by_the_panel_serial_number(self, hass: HomeAssistant) -> None:
        flow_id = await start_user_flow(hass)

        await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == PANEL_SERIAL

    async def test_stores_the_port_as_an_integer(self, hass: HomeAssistant) -> None:
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, {**USER_INPUT, CONF_PORT: 20203.0})

        assert result["data"][CONF_PORT] == 20203

    async def test_falls_back_to_a_generic_title_when_the_panel_reports_no_serial(
        self, hass: HomeAssistant, panel: FakePanel
    ) -> None:
        panel.serial_number = ""
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert result["title"] == "Orisec panel"

    async def test_rejects_a_password_the_panel_refuses(self, hass: HomeAssistant, panel: FakePanel) -> None:
        panel.password = "9999"
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_reports_an_unreachable_panel(self, hass: HomeAssistant, panel: FakePanel) -> None:
        panel.error = OSError("network is unreachable")
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert result["errors"] == {"base": "cannot_connect"}

    async def test_reports_a_panel_that_never_answers(self, hass: HomeAssistant, panel: FakePanel) -> None:
        panel.error = TimeoutError()
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert result["errors"] == {"base": "cannot_connect"}

    async def test_keeps_the_form_alive_after_an_unexpected_error(
        self, hass: HomeAssistant, panel: FakePanel
    ) -> None:
        panel.error = ValueError("something nobody predicted")
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    async def test_lets_the_user_correct_a_bad_password_without_restarting(
        self, hass: HomeAssistant, panel: FakePanel
    ) -> None:
        panel.password = "9999"
        flow_id = await start_user_flow(hass)
        await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        result = await hass.config_entries.flow.async_configure(
            flow_id, {**USER_INPUT, CONF_PASSWORD: "9999"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY

    async def test_offers_the_host_back_but_not_the_rejected_password(
        self, hass: HomeAssistant, panel: FakePanel
    ) -> None:
        panel.password = "9999"
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
        suggestions = {
            key.schema: key.description["suggested_value"]
            for key in result["data_schema"].schema
            if key.description
        }

        assert suggestions == {CONF_HOST: PANEL_HOST, CONF_PORT: PANEL_PORT}

    async def test_refuses_to_add_the_same_panel_twice(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        config_entry.add_to_hass(hass)
        flow_id = await start_user_flow(hass)

        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    async def test_moves_a_known_panel_to_its_new_address(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        config_entry.add_to_hass(hass)
        flow_id = await start_user_flow(hass)

        await hass.config_entries.flow.async_configure(flow_id, {**USER_INPUT, CONF_HOST: "10.0.0.9"})

        assert config_entry.data[CONF_HOST] == "10.0.0.9"


@pytest.mark.usefixtures("panel_sockets")
class TestReauthFlow:
    async def test_asks_for_a_new_password(self, hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
        config_entry.add_to_hass(hass)

        result = await config_entry.start_reauth_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["description_placeholders"][CONF_HOST] == PANEL_HOST

    async def test_stores_a_password_the_panel_accepts(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.password = "4321"
        config_entry.add_to_hass(hass)
        result = await config_entry.start_reauth_flow(hass)

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "4321"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert config_entry.data[CONF_PASSWORD] == "4321"

    async def test_keeps_the_rest_of_the_entry_untouched(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.password = "4321"
        config_entry.add_to_hass(hass)
        result = await config_entry.start_reauth_flow(hass)

        await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "4321"})
        await hass.async_block_till_done()

        assert config_entry.data[CONF_HOST] == PANEL_HOST
        assert config_entry.data[CONF_PORT] == PANEL_PORT

    async def test_reprompts_when_the_new_password_is_also_wrong(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.password = "4321"
        config_entry.add_to_hass(hass)
        result = await config_entry.start_reauth_flow(hass)

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "0000"})

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_refuses_to_reauthenticate_against_a_different_panel(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, panel: FakePanel
    ) -> None:
        panel.serial_number = "ORI-9999"
        config_entry.add_to_hass(hass)
        result = await config_entry.start_reauth_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: PANEL_PASSWORD}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "wrong_panel"


@pytest.mark.usefixtures("panel_sockets")
class TestOptionsFlow:
    async def test_offers_the_default_interval_to_a_new_entry(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        defaults = {key.schema: key.default() for key in result["data_schema"].schema}

        assert result["step_id"] == "init"
        assert defaults == {CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL}

    async def test_saves_a_new_interval(self, hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
        config_entry.add_to_hass(hass)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 120.0}
        )
        await hass.async_block_till_done()

        assert result["data"] == {CONF_SCAN_INTERVAL: 120}

    async def test_offers_the_saved_interval_back(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(config_entry, options={CONF_SCAN_INTERVAL: 90})

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        suggestions = {
            key.schema: key.description["suggested_value"]
            for key in result["data_schema"].schema
            if key.description
        }

        assert suggestions == {CONF_SCAN_INTERVAL: 90}
