"""Switch entity: zapnutí/vypnutí bojleru (topení domu řeší climate.py)
a přepínač režimu den/noc pro termostat."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HEAT_PUMP_HASH, DOMAIN
from .coordinator import TngCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: TngCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        TngBoilerSwitch(coordinator, entry),
        TngThermostatDayNightSwitch(coordinator, entry),
    ])


class TngBoilerSwitch(CoordinatorEntity[TngCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Ohřev bojleru"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_boiler_switch"
        # Optimistická hodnota - dokud čerpadlo nepotvrdí totéž zpátky,
        # zobrazujeme to, co jsme sami odeslali (žádné blikání zpátky na
        # starou hodnotu kvůli zpoždění na straně čerpadla).
        self._optimistic_state: bool | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data[CONF_HEAT_PUMP_HASH])},
            name=self._entry.title,
            manufacturer="TnG Air",
            model="TnG Smart tepelné čerpadlo",
        )

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        return bool(self.coordinator.data.get("BoilerOn"))

    def _handle_coordinator_update(self) -> None:
        if self._optimistic_state is not None:
            real = bool(self.coordinator.data.get("BoilerOn"))
            if real == self._optimistic_state:
                self._optimistic_state = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        self._optimistic_state = True
        self.async_write_ha_state()
        await self.coordinator.async_write_settings(boiler_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        self._optimistic_state = False
        self.async_write_ha_state()
        await self.coordinator.async_write_settings(boiler_on=False)


class TngThermostatDayNightSwitch(CoordinatorEntity[TngCoordinator], RestoreEntity, SwitchEntity):
    """Přepínač 'sleduj denní/noční rozvrh' pro termostat. Skutečná hodnota
    se čte z MyThermostat (DayNightEnabled); RestoreEntity je jen záchranná
    síť, dokud první čtení neproběhne."""

    _attr_has_entity_name = True
    _attr_name = "Termostat - režim den/noc"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._entry = entry
        self._pending = False
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_thermostat_day_night_mode"

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
        return super().available and not self._pending

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.get_thermostat_value("day_night_mode"))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (self.coordinator.data or {}).get("ThermostatDayNightMode") is not None:
            return
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in ("on", "off"):
            self.coordinator.thermostat_overrides["day_night_mode"] = last_state.state == "on"

    async def _set(self, value: bool) -> None:
        self._pending = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_thermostat_settings(day_night_mode=value)
        finally:
            self._pending = False
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)
