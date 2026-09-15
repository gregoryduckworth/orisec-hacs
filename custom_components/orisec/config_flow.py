"""Config and options flows for the Orisec integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import AuthenticationError, OrisecError, OrisecLocalClient, PanelLayout
from .const import (
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): NumberSelector(
            NumberSelectorConfig(
                min=MIN_SCAN_INTERVAL,
                max=MAX_SCAN_INTERVAL,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        ),
    }
)


async def async_read_layout(hass: HomeAssistant, data: Mapping[str, Any]) -> PanelLayout:
    """Log in to the panel described by ``data`` and return what it is made of.

    Raises the client's own errors so each caller can map them to the form
    error it wants to show.
    """

    client = OrisecLocalClient(data[CONF_HOST], data[CONF_PASSWORD], port=data[CONF_PORT])

    def _read() -> PanelLayout:
        with client:
            client.login()
            return client.read_layout()

    return await hass.async_add_executor_job(_read)


class OrisecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Walk the user through adding one panel."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the panel address and password, then prove they work."""

        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {**user_input, CONF_PORT: int(user_input[CONF_PORT])}
            layout, errors = await self._async_probe(user_input)

            if layout is not None:
                await self.async_set_unique_id(layout.serial_number)
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title=_entry_title(layout), data=user_input)

        # Offer back what the user typed, minus the password the panel rejected.
        suggested = {key: value for key, value in (user_input or {}).items() if key != CONF_PASSWORD}

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, suggested),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start the re-authentication prompt raised by a failing poll."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Take a new password for an entry that already exists."""

        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            candidate = {**entry.data, **user_input}
            layout, errors = await self._async_probe(candidate)

            if layout is not None:
                await self.async_set_unique_id(layout.serial_number)
                self._abort_if_unique_id_mismatch(reason="wrong_panel")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={CONF_HOST: entry.data[CONF_HOST]},
            errors=errors,
        )

    async def _async_probe(self, data: Mapping[str, Any]) -> tuple[PanelLayout | None, dict[str, str]]:
        """Return the panel layout, or the form error explaining why there is none."""

        try:
            return await async_read_layout(self.hass, data), {}
        except AuthenticationError:
            return None, {"base": "invalid_auth"}
        except (OrisecError, OSError):
            return None, {"base": "cannot_connect"}
        except Exception:  # The form has to survive an unexpected bug, not disappear.
            _LOGGER.exception("Unexpected error connecting to the Orisec panel")
            return None, {"base": "unknown"}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OrisecOptionsFlow:
        """Return the options flow for an existing entry."""

        return OrisecOptionsFlow()


class OrisecOptionsFlow(OptionsFlow):
    """Let the user retune how often the panel is polled."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show and save the poll interval."""

        if user_input is not None:
            return self.async_create_entry(data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, self.config_entry.options),
        )


def _entry_title(layout: PanelLayout) -> str:
    """Name the entry after the panel's serial number when it reports one."""

    return f"Orisec {layout.serial_number}" if layout.serial_number else "Orisec panel"
