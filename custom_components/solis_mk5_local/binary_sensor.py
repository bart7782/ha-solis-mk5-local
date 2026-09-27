"""Binary sensor telling whether the stick's data is live."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolisMk5ConfigEntry
from .const import DOMAIN
from .coordinator import SolisMk5Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolisMk5ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SolisMk5LiveSensor(entry.runtime_data, entry)])


class SolisMk5LiveSensor(CoordinatorEntity[SolisMk5Coordinator], BinarySensorEntity):
    """On while the newest frame is recent enough to act on.

    Meant for automations that switch loads on solar power: only trust the
    power reading while this is on. With polling it is on all day; with the
    push alone it is on for about a minute and a half after each push.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "live"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: SolisMk5Coordinator, entry: SolisMk5ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}-live"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_live
