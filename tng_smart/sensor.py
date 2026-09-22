"""Sensor entity: teploty čtené z CrossRoad (HpAndThermostatData)."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HEAT_PUMP_HASH, DOMAIN
from .coordinator import TngCoordinator

# CrossRoad používá tuhle sentinelovou hodnotu, když senzor/bojler nemá data
# (např. bojler je vypnutý a nemá čidlo). Bereme jako "neznámo".
_NO_DATA_SENTINEL = -1000


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: TngCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        TngTempSensor(coordinator, entry, "Venkovní teplota", "outside_air", "AirTemperature"),
        TngTempSensor(coordinator, entry, "Teplota vody na výstupu", "water_out", "CurrentHeatingWaterTemp"),
        TngTempSensor(coordinator, entry, "Teplota v bojleru", "boiler_temp", "CurrentBoilerTemp"),
    ]

    if coordinator.data.get("ThermostatId"):
        entities.append(
            TngTempSensor(coordinator, entry, "Teplota v místnosti", "room_temp", "RoomTemperature")
        )

    async_add_entities(entities)


class TngTempSensor(CoordinatorEntity[TngCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry,
                 name: str, key: str, data_field: str):
        super().__init__(coordinator)
        self._entry = entry
        self._data_field = data_field
        self._attr_name = name
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data[CONF_HEAT_PUMP_HASH])},
            name=self._entry.title,
            manufacturer="TnG Air",
            model="TnG Smart tepelné čerpadlo",
        )

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.get(self._data_field)
        if value is None or value <= _NO_DATA_SENTINEL:
            return None
        return value
