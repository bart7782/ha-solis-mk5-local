"""Sensor entities for the Solis MK5 Local integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolisMk5ConfigEntry
from .const import DOMAIN
from .coordinator import SolisMk5Coordinator


@dataclass(frozen=True, kw_only=True)
class SolisMk5SensorDescription(SensorEntityDescription):
    """Sensor description with staleness/restore behaviour."""

    # Energy counters and timestamps stay valid while the inverter is off
    # overnight; live measurements do not and go unavailable when stale.
    stays_available: bool = False
    # Restore the last value after a Home Assistant restart (before the
    # stick's first push, which can take ~6 minutes or all night).
    restore: bool = False
    expose_raw: bool = False


SENSORS: tuple[SolisMk5SensorDescription, ...] = (
    SolisMk5SensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SolisMk5SensorDescription(
        key="energy_today",
        translation_key="energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        stays_available=True,
        restore=True,
    ),
    SolisMk5SensorDescription(
        key="energy_total",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        stays_available=True,
        restore=True,
    ),
    SolisMk5SensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SolisMk5SensorDescription(
        key="ac_voltage",
        translation_key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SolisMk5SensorDescription(
        key="ac_current",
        translation_key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolisMk5SensorDescription(
        key="ac_frequency",
        translation_key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolisMk5SensorDescription(
        key="dc_voltage_1",
        translation_key="dc_voltage_1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolisMk5SensorDescription(
        key="dc_current_1",
        translation_key="dc_current_1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolisMk5SensorDescription(
        key="dc_voltage_2",
        translation_key="dc_voltage_2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolisMk5SensorDescription(
        key="dc_current_2",
        translation_key="dc_current_2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolisMk5SensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        stays_available=True,
        restore=True,
        expose_raw=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolisMk5ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SolisMk5Sensor(coordinator, entry, description) for description in SENSORS
    )


class SolisMk5Sensor(CoordinatorEntity[SolisMk5Coordinator], RestoreSensor):
    """A sensor fed by frames the stick pushes to the local server."""

    entity_description: SolisMk5SensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolisMk5Coordinator,
        entry: SolisMk5ConfigEntry,
        description: SolisMk5SensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._restored_value: datetime | float | int | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if not self.entity_description.restore or self._live_value is not None:
            return
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._restored_value = last.native_value

    @property
    def _live_value(self) -> datetime | float | int | None:
        return (self.coordinator.data or {}).get(self.entity_description.key)

    @property
    def native_value(self) -> datetime | float | int | None:
        if (value := self._live_value) is not None:
            return value
        return self._restored_value

    @property
    def available(self) -> bool:
        if self.entity_description.stays_available:
            return self.native_value is not None
        return self._live_value is not None and not self.coordinator.is_stale

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        if not self.entity_description.expose_raw:
            return None
        if raw := (self.coordinator.data or {}).get("raw_hex"):
            return {"raw_frame_hex": raw}
        return None
