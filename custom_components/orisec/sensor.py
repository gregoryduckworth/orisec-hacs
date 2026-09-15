"""Sensor entities generated from what the panel reports about itself."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import OrisecConfigEntry, OrisecDataUpdateCoordinator
from .entity import OrisecEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OrisecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one entity per configured zone plus the panel's diagnostics."""

    coordinator = entry.runtime_data
    layout = coordinator.layout

    entities: list[SensorEntity] = [
        OrisecZoneSensor(coordinator, index, name) for index, name in enumerate(layout.zone_names)
    ]
    entities.extend(
        [
            OrisecPanelStatusSensor(coordinator),
            OrisecSerialNumberSensor(coordinator),
            OrisecModelSensor(coordinator),
            OrisecZoneCountSensor(coordinator),
            OrisecAreaCountSensor(coordinator),
        ]
    )

    async_add_entities(entities)


class OrisecZoneSensor(OrisecEntity, SensorEntity):
    """The raw status word the panel reports for one zone.

    The panel returns an opaque integer per zone. Its bit layout is not
    confirmed against hardware yet, so the value is surfaced unchanged rather
    than guessed into an on/off state.
    """

    def __init__(self, coordinator: OrisecDataUpdateCoordinator, index: int, name: str) -> None:
        super().__init__(coordinator, f"zone_{index + 1}")
        self._index = index
        self._attr_name = name or f"Zone {index + 1}"

    @property
    def native_value(self) -> int:
        """Return the zone's status word.

        The panel always answers a zone status read with one value per zone it
        was asked about, and the client rejects any reply that does not, so
        this index is as valid as the layout the entity was built from.
        """

        return self.coordinator.data.zone_status[self._index]

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Expose the panel's own numbering so automations can address the zone."""

        return {"zone": self._index + 1}


class OrisecPanelStatusSensor(OrisecEntity, SensorEntity):
    """The raw panel status block, rendered as hex."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "panel_status"

    def __init__(self, coordinator: OrisecDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "panel_status")

    @property
    def native_value(self) -> str:
        """Return the status bytes as a spaced hex string."""

        return self.coordinator.data.panel_status.hex(" ")


class OrisecSerialNumberSensor(OrisecEntity, SensorEntity):
    """The panel's serial number."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "serial_number"

    def __init__(self, coordinator: OrisecDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "serial_number")
        self._attr_native_value = coordinator.layout.serial_number


class OrisecModelSensor(OrisecEntity, SensorEntity):
    """The panel's model number."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "model"

    def __init__(self, coordinator: OrisecDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "model")
        self._attr_native_value = coordinator.layout.model


class OrisecZoneCountSensor(OrisecEntity, SensorEntity):
    """How many zones the panel has configured."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "zone_count"

    def __init__(self, coordinator: OrisecDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "zone_count")
        self._attr_native_value = coordinator.layout.zone_count


class OrisecAreaCountSensor(OrisecEntity, SensorEntity):
    """How many areas the panel has configured, and what they are called."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "area_count"

    def __init__(self, coordinator: OrisecDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "area_count")
        self._attr_native_value = len(coordinator.layout.area_names)
        self._attr_extra_state_attributes = {"areas": coordinator.layout.area_names}
