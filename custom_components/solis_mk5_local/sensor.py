"""Sensor entities for the Solis MK5 Local integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import monotonic

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolisMk5ConfigEntry
from .const import DIAGNOSTIC_MIN_INTERVAL, DOMAIN
from .coordinator import SolisMk5Coordinator


@dataclass(frozen=True, kw_only=True)
class SolisMk5SensorDescription(SensorEntityDescription):
    """Sensor description with staleness/restore behaviour."""

    # Energy counters and timestamps stay valid while the inverter is off
    # overnight; live measurements do not and go unavailable when stale.
    stays_available: bool = False
    # Restore the last value after a Home Assistant restart (before the
    # stick's first frame, which can take all night).
    restore: bool = False
    # Write at most once per DIAGNOSTIC_MIN_INTERVAL; see const.py.
    throttled: bool = False
    # Show where the newest frame came from (poll or push) as an attribute.
    expose_source: bool = False


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
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="ac_voltage",
        translation_key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="ac_current",
        translation_key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="ac_frequency",
        translation_key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="dc_voltage_1",
        translation_key="dc_voltage_1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="dc_current_1",
        translation_key="dc_current_1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="dc_voltage_2",
        translation_key="dc_voltage_2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="dc_current_2",
        translation_key="dc_current_2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttled=True,
    ),
    SolisMk5SensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        stays_available=True,
        restore=True,
        expose_source=True,
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
    """A sensor fed by the frames of the stick, polled or pushed."""

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
        self._last_write: float | None = None
        self._last_written_available: bool | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if not self.entity_description.restore or self._live_value is not None:
            return
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._restored_value = last.native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write the new state, unless this sensor is throttled and wrote recently.

        A change in availability is always written straight away.
        """
        available = self.available
        if (
            self.entity_description.throttled
            and self._last_write is not None
            and available == self._last_written_available
            and monotonic() - self._last_write < DIAGNOSTIC_MIN_INTERVAL
        ):
            return
        self._last_write = monotonic()
        self._last_written_available = available
        super()._handle_coordinator_update()

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
        if not self.entity_description.expose_source:
            return None
        if source := self.coordinator.last_source:
            return {"source": source}
        return None
