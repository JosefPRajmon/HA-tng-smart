"""Climate entita: termostat pro vytápění domu (on/off + cílová teplota)."""
from __future__ import annotations

import asyncio

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HEAT_PUMP_HASH, DOMAIN, MAX_HEAT_TEMP, MIN_HEAT_TEMP
from .coordinator import TngCoordinator

# Než reálně odešleme novou teplotu, počkáme chvíli - když někdo rychle
# klikne na +/- víckrát za sebou, pošleme až tu poslední hodnotu, ne
# každé kliknutí zvlášť.
_TEMP_DEBOUNCE_SECONDS = 0.8


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: TngCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TngHeatClimate(coordinator, entry)])


class TngHeatClimate(CoordinatorEntity[TngCoordinator], ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = "Vytápění domu"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = MIN_HEAT_TEMP
    _attr_max_temp = MAX_HEAT_TEMP
    _attr_target_temperature_step = 1

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_climate"
        # Optimistické hodnoty - dokud čerpadlo nepotvrdí totéž zpátky,
        # věříme tomu, co jsme sami odeslali, místo abychom blikali zpátky
        # na starou hodnotu kvůli zpoždění na straně čerpadla.
        self._optimistic_hvac_mode: HVACMode | None = None
        self._optimistic_temp: float | None = None
        self._temp_debounce_task: asyncio.Task | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data[CONF_HEAT_PUMP_HASH])},
            name=self._entry.title,
            manufacturer="TnG Air",
            model="TnG Smart tepelné čerpadlo",
        )

    @property
    def hvac_mode(self) -> HVACMode:
        if self._optimistic_hvac_mode is not None:
            return self._optimistic_hvac_mode
        return HVACMode.HEAT if self.coordinator.data.get("HeatingOn") else HVACMode.OFF

    @property
    def target_temperature(self) -> float | None:
        if self._optimistic_temp is not None:
            return self._optimistic_temp
        return self.coordinator.data.get("CurrentHeatingWaterTemp")

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.get("LiveRoomTemp") or self.coordinator.data.get(
            "RoomTemperature"
        )

    def _handle_coordinator_update(self) -> None:
        if self._optimistic_hvac_mode is not None:
            real_on = bool(self.coordinator.data.get("HeatingOn"))
            if (self._optimistic_hvac_mode == HVACMode.HEAT) == real_on:
                self._optimistic_hvac_mode = None
        if self._optimistic_temp is not None:
            real_temp = self.coordinator.data.get("CurrentHeatingWaterTemp")
            if real_temp is not None and int(real_temp) == int(self._optimistic_temp):
                self._optimistic_temp = None
        super()._handle_coordinator_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._optimistic_hvac_mode = hvac_mode
        self.async_write_ha_state()
        await self.coordinator.async_write_settings(heat_on=(hvac_mode == HVACMode.HEAT))

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._optimistic_temp = temperature
        self.async_write_ha_state()

        if self._temp_debounce_task:
            self._temp_debounce_task.cancel()
        self._temp_debounce_task = self.hass.async_create_task(
            self._debounced_set_temp(temperature)
        )

    async def _debounced_set_temp(self, temperature: float) -> None:
        try:
            await asyncio.sleep(_TEMP_DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return
        await self.coordinator.async_write_settings(heat_temp_const=int(round(temperature)))
