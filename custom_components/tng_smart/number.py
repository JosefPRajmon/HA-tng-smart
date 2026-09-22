"""Number entity: cílová (výstupní) teplota topení domu."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HEAT_PUMP_HASH, DOMAIN, MAX_HEAT_TEMP, MIN_HEAT_TEMP
from .coordinator import TngCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: TngCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TngHeatTempNumber(coordinator, entry)])


class TngHeatTempNumber(CoordinatorEntity[TngCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Výstupní teplota topení"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_HEAT_TEMP
    _attr_native_max_value = MAX_HEAT_TEMP
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_heat_temp"

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
        return self.coordinator.data.get("CurrentHeatingWaterTemp")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_settings(heat_temp_const=int(round(value)))
