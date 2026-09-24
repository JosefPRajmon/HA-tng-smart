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
        TngTempSensor(coordinator, entry, "Venkovní teplota", "outside_air",
                      ["LiveOutsideTemp", "AirTemperature"], "mdi:weather-sunny"),
        TngTempSensor(coordinator, entry, "Teplota vody na výstupu", "water_out",
                      ["LiveWaterTemp", "CurrentHeatingWaterTemp"], "mdi:water-thermometer"),
        TngTempSensor(coordinator, entry, "Teplota v bojleru", "boiler_temp",
                      ["LiveBoilerTemp", "CurrentBoilerTemp"], "mdi:water-boiler"),
    ]

    if coordinator.data.get("ThermostatId"):
        entities.append(
            TngTempSensor(coordinator, entry, "Teplota v místnosti", "room_temp",
                          ["ThermostatRoomTemp", "LiveRoomTemp", "RoomTemperature"],
                          "mdi:home-thermometer")
        )

    async_add_entities(entities)


class TngTempSensor(CoordinatorEntity[TngCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry,
                 name: str, key: str, data_fields: list[str], icon: str | None = None):
        super().__init__(coordinator)
        self._entry = entry
        self._data_fields = data_fields
        self._attr_name = name
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_{key}"
        if icon:
            self._attr_icon = icon

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
        for field in self._data_fields:
            value = self.coordinator.data.get(field)
            if value is not None and value > _NO_DATA_SENTINEL:
                return value
        return None
