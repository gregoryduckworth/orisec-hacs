"""Shared entity base for the Orisec integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OrisecDataUpdateCoordinator


class OrisecEntity(CoordinatorEntity[OrisecDataUpdateCoordinator]):
    """Attaches every Orisec entity to the one device representing the panel."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OrisecDataUpdateCoordinator, key: str) -> None:
        super().__init__(coordinator)
        layout = coordinator.layout
        identifier = layout.serial_number or coordinator.config_entry.entry_id

        self._attr_unique_id = f"{identifier}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=MANUFACTURER,
            model=str(layout.model),
            name=coordinator.config_entry.title,
            serial_number=layout.serial_number or None,
        )
