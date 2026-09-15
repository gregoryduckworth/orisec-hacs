"""Polling coordinator for a single Orisec panel."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, OrisecError, OrisecLocalClient, PanelLayout, PanelState
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type OrisecConfigEntry = ConfigEntry[OrisecDataUpdateCoordinator]


class OrisecDataUpdateCoordinator(DataUpdateCoordinator[PanelState]):
    """Polls one panel over UDP and shares the result with every entity."""

    config_entry: OrisecConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OrisecConfigEntry,
        client: OrisecLocalClient,
        layout: PanelLayout,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.layout = layout

    async def _async_update_data(self) -> PanelState:
        """Poll the panel off the event loop, because the client blocks."""

        return await self.hass.async_add_executor_job(self._read_state)

    def _read_state(self) -> PanelState:
        """Log in and read one snapshot.

        Every poll re-authenticates rather than holding a session open between
        polls: the protocol is connectionless UDP, so a session that silently
        expired is indistinguishable from a panel that stopped answering.
        """

        try:
            with self.client as client:
                client.login()
                return client.read_state(self.layout.zone_count)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (OrisecError, OSError) as err:
            raise UpdateFailed(str(err)) from err
