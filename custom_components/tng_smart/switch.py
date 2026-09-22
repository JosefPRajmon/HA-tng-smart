"""Switch entity: zapnutí/vypnutí topení domu a bojleru."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
            TngHeatSwitch(coordinator, entry),
            TngBoilerSwitch(coordinator, entry),
        ]
    )


class _TngSwitchBase(CoordinatorEntity[TngCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._entry = entry
        self._pending = False

    @property
    def available(self) -> bool:
        return super().available and not self._pending

    async def _do_write(self, **kwargs) -> None:
        self._pending = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_settings(**kwargs)
        finally:
            self._pending = False
            self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data[CONF_HEAT_PUMP_HASH])},
            name=self._entry.title,
            manufacturer="TnG Air",
            model="TnG Smart tepelné čerpadlo",
        )


class TngHeatSwitch(_TngSwitchBase):
    _attr_name = "Vytápění domu"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_heat_switch"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("HeatingOn"))

    async def async_turn_on(self, **kwargs) -> None:
        await self._do_write(heat_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._do_write(heat_on=False)


class TngBoilerSwitch(_TngSwitchBase):
    _attr_name = "Ohřev bojleru"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_boiler_switch"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("BoilerOn"))

    async def async_turn_on(self, **kwargs) -> None:
        await self._do_write(boiler_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._do_write(boiler_on=False)
