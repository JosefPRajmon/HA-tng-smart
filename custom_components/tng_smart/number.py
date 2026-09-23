"""Number entity: denní a noční teplota pokojového termostatu.

Termostat (na rozdíl od tepelného čerpadla) nemá žádné API pro čtení
aktuálního nastavení - hodnoty se jen "pamatují" v Home Assistantu
(RestoreEntity je obnoví i po restartu) a při každé změně se odešlou
všechny najednou (den, noc, režim, rozvrh), protože zápis je vše-nebo-nic.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_HEAT_PUMP_HASH, DOMAIN, MAX_THERMOSTAT_TEMP, MIN_THERMOSTAT_TEMP
from .coordinator import TngCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: TngCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        TngThermostatDayTemp(coordinator, entry),
        TngThermostatNightTemp(coordinator, entry),
    ])


class _TngThermostatTempBase(RestoreEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_THERMOSTAT_TEMP
    _attr_native_max_value = MAX_THERMOSTAT_TEMP
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_assumed_state = True
    _state_key: str = ""

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self._entry = entry
        self._pending = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data[CONF_HEAT_PUMP_HASH])},
            name=self._entry.title,
            manufacturer="TnG Air",
            model="TnG Smart tepelné čerpadlo",
        )

    @property
    def available(self) -> bool:
        return not self._pending

    @property
    def native_value(self) -> float:
        return self.coordinator.thermostat_state[self._state_key]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self.coordinator.thermostat_state[self._state_key] = float(last_state.state)
            except ValueError:
                pass

    async def async_set_native_value(self, value: float) -> None:
        self._pending = True
        self.coordinator.thermostat_state[self._state_key] = value
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_thermostat_settings()
        finally:
            self._pending = False
            self.async_write_ha_state()


class TngThermostatDayTemp(_TngThermostatTempBase):
    _attr_name = "Termostat - denní teplota"
    _state_key = "day_temp"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_thermostat_day_temp"


class TngThermostatNightTemp(_TngThermostatTempBase):
    _attr_name = "Termostat - noční teplota"
    _state_key = "night_temp"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_thermostat_night_temp"
