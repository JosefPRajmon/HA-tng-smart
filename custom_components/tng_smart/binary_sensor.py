"""Binary sensor entity: stavy zapnuto/vypnuto čtené z CrossRoad."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HEAT_PUMP_HASH, DOMAIN
from .coordinator import TngCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: TngCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TngOnOffSensor(coordinator, entry, "Vytápění domu", "heating_on", "HeatingOn", "mdi:radiator"),
            TngOnOffSensor(coordinator, entry, "Ohřev bojleru", "boiler_on", "BoilerOn", "mdi:water-boiler"),
        ]
    )


class TngOnOffSensor(CoordinatorEntity[TngCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry,
                 name: str, key: str, data_field: str, icon: str | None = None):
        super().__init__(coordinator)
        self._entry = entry
        self._data_field = data_field
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
    def is_on(self) -> bool | None:
        return bool(self.coordinator.data.get(self._data_field))
