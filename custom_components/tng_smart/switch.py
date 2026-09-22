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
    _data_field: str = ""

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._entry = entry
        self._pending = False
        self._optimistic_state: bool | None = None

    @property
    def available(self) -> bool:
        return super().available and not self._pending

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        return bool(self.coordinator.data.get(self._data_field))

    def _handle_coordinator_update(self) -> None:
        if self._optimistic_state is not None:
            real = bool(self.coordinator.data.get(self._data_field))
            if real == self._optimistic_state:
                self._optimistic_state = None
        super()._handle_coordinator_update()

    async def _do_write(self, new_state: bool, **kwargs) -> None:
        self._pending = True
        self._optimistic_state = new_state
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
    _data_field = "HeatingOn"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_heat_switch"

    async def async_turn_on(self, **kwargs) -> None:
        await self._do_write(True, heat_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._do_write(False, heat_on=False)


class TngBoilerSwitch(_TngSwitchBase):
    _attr_name = "Ohřev bojleru"
    _data_field = "BoilerOn"

    def __init__(self, coordinator: TngCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HEAT_PUMP_HASH]}_boiler_switch"

    async def async_turn_on(self, **kwargs) -> None:
        await self._do_write(True, boiler_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._do_write(False, boiler_on=False)
