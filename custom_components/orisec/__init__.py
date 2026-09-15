"""Orisec integration package."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .api import AuthenticationError, OrisecError, OrisecLocalClient, PanelLayout
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import OrisecConfigEntry, OrisecDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OrisecConfigEntry) -> bool:
    """Set up one panel from a config entry."""

    client = OrisecLocalClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PASSWORD],
        port=entry.data[CONF_PORT],
    )

    def _read_layout() -> PanelLayout:
        with client:
            client.login()
            return client.read_layout()

    try:
        layout = await hass.async_add_executor_job(_read_layout)
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (OrisecError, OSError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = OrisecDataUpdateCoordinator(
        hass,
        entry,
        client,
        layout,
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OrisecConfigEntry) -> bool:
    """Tear down a panel's entities and close its socket."""

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Closed unconditionally: an entry that failed to unload keeps polling, and
    # the client reopens its socket on the next read.
    await hass.async_add_executor_job(entry.runtime_data.client.close)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry so a changed poll interval takes effect."""

    await hass.config_entries.async_reload(entry.entry_id)


__all__ = [
    "DOMAIN",
    "async_reload_entry",
    "async_setup_entry",
    "async_unload_entry",
]
