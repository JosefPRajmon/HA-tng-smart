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
        self._pending = False
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_heat_temp"
        self._optimistic_value: float | None = None

    @property
    def available(self) -> bool:
        return super().available and not self._pending

    def _handle_coordinator_update(self) -> None:
        # Jakmile skutečná data ze serveru dohoní naši optimistickou
        # hodnotu (čerpadlo si vyzvedlo a potvrdilo nové nastavení),
        # přestaneme ji vnucovat a necháme mluvit real data.
        if self._optimistic_value is not None:
            real = self.coordinator.data.get("CurrentHeatingWaterTemp")
            if real is not None and int(real) == int(self._optimistic_value):
                self._optimistic_value = None
        super()._handle_coordinator_update()

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
        if self._optimistic_value is not None:
            return self._optimistic_value
        return self.coordinator.data.get("CurrentHeatingWaterTemp")

    async def async_set_native_value(self, value: float) -> None:
        self._pending = True
        self._optimistic_value = value
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_settings(heat_temp_const=int(round(value)))
        finally:
            self._pending = False
            self.async_write_ha_state()
