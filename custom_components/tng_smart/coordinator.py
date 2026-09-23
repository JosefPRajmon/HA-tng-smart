"""Coordinator: pravidelně (a on-demand po zápisu) stahuje stav čerpadla."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TngApiClient, TngApiError, TngAuthError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS, DEFAULT_THERMOSTAT_SCHEDULE

_LOGGER = logging.getLogger(__name__)


class TngCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, client: TngApiClient, heat_pump_hash: str,
                 mac_address: str):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.heat_pump_hash = heat_pump_hash
        self.mac_address = mac_address

        # Termostat nemá read API - hodnoty se jen "pamatují" v HA (entity
        # je obnoví po restartu přes RestoreEntity) a vždy posílají všechny
        # najednou, protože zápis je "vše nebo nic".
        self.thermostat_state: dict = {
            "day_temp": 20.0,
            "night_temp": 24.0,
            "day_night_mode": False,
        }

    async def _async_update_data(self) -> dict:
        try:
            status = await self.hass.async_add_executor_job(
                self.client.get_installation_status, self.heat_pump_hash
            )
        except TngAuthError as err:
            raise UpdateFailed(f"Přihlášení selhalo: {err}") from err
        except TngApiError as err:
            raise UpdateFailed(f"Chyba API: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Neočekávaná chyba: {err}") from err

        # Živá data (skutečně měřené teploty) - nekritické, pokud selžou,
        # necháme jen fallback na hodnoty z CrossRoad.
        try:
            live = await self.hass.async_add_executor_job(
                self.client.get_latest_data_point, self.heat_pump_hash
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Nepodařilo se načíst živá data: %s", err)
            live = None

        if live:
            if "t" in live:
                status["LiveOutsideTemp"] = live["t"]
            if "tt" in live:
                status["LiveRoomTemp"] = live["tt"]
            if "tw" in live:
                status["LiveWaterTemp"] = live["tw"]
            if "tb" in live:
                status["LiveBoilerTemp"] = live["tb"]

        return status

    def current_write_kwargs(self) -> dict:
        """Poskládá výchozí hodnoty pro zápis z posledního známého stavu -
        aby zápis jedné věci (např. zapnutí topení) omylem nevynuloval
        ostatní (bojler, bazén)."""
        data = self.data or {}
        return {
            "heat_on": bool(data.get("HeatingOn")),
            "heat_temp_const": int(data.get("CurrentHeatingWaterTemp") or 42),
            "boiler_on": bool(data.get("BoilerOn")),
            "boiler_temp": 50,
            "pool_on": False,
            "pool_temp": 37,
        }

    async def async_write_settings(self, **kwargs) -> None:
        merged = self.current_write_kwargs()
        merged.update(kwargs)
        await self.hass.async_add_executor_job(
            lambda: self.client.write_settings(
                self.heat_pump_hash, self.mac_address, **merged
            )
        )
        await self.async_request_refresh()

    async def async_write_thermostat_settings(self) -> None:
        thermostat_id = (self.data or {}).get("ThermostatId")
        if not thermostat_id:
            raise UpdateFailed("Neznámé ThermostatId - termostat zatím nenačetl data.")

        state = self.thermostat_state
        await self.hass.async_add_executor_job(
            lambda: self.client.write_thermostat_settings(
                thermostat_id,
                state["day_temp"],
                state["night_temp"],
                state["day_night_mode"],
                DEFAULT_THERMOSTAT_SCHEDULE,
            )
        )
