"""Coordinator: pravidelně (a on-demand po zápisu) stahuje stav čerpadla."""
from __future__ import annotations

from datetime import timedelta
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TngApiClient, TngApiError, TngAuthError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS, DEFAULT_THERMOSTAT_SCHEDULE, OPTIMISTIC_TTL_SECONDS

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

        # Termostat: přednostně věříme skutečnému stavu z MyThermostat
        # (viz get_thermostat_status). "overrides" drží hodnoty, které jsme
        # sami odeslali a ještě je server/čerpadlo nepotvrdilo zpátky -
        # jakmile se objeví shoda ve skutečných datech, override zmizí.
        self.thermostat_overrides: dict = {}
        self._thermostat_defaults = {
            "day_temp": 20.0,
            "night_temp": 24.0,
            "day_night_mode": False,
        }
        self._thermostat_field_map = {
            "day_temp": "ThermostatDayTemp",
            "night_temp": "ThermostatNightTemp",
            "day_night_mode": "ThermostatDayNightMode",
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

        # Stav termostatu - taky nekritické, pokud selže necháme jen
        # lokálně zapamatované/výchozí hodnoty (viz get_thermostat_value).
        thermostat_id = status.get("ThermostatId")
        if thermostat_id:
            try:
                thermo = await self.hass.async_add_executor_job(
                    self.client.get_thermostat_status, thermostat_id
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Nepodařilo se načíst stav termostatu: %s", err)
                thermo = None

            if thermo:
                status.update(thermo)
                # Jakmile skutečná data dohoní to, co jsme sami odeslali,
                # přestaneme tu hodnotu vnucovat.
                for field, data_key in self._thermostat_field_map.items():
                    if field not in self.thermostat_overrides:
                        continue
                    real = thermo.get(data_key)
                    if real is None:
                        continue
                    override, _set_at = self.thermostat_overrides[field]
                    matches = (
                        bool(real) == bool(override)
                        if field == "day_night_mode"
                        else abs(float(real) - float(override)) < 0.01
                    )
                    if matches:
                        del self.thermostat_overrides[field]

        return status

    def get_thermostat_value(self, field: str):
        """Hodnota pole termostatu (day_temp/night_temp/day_night_mode):
        naše nepotvrzená (a ještě neprošlá) změna > skutečná data ze
        serveru > výchozí."""
        if field in self.thermostat_overrides:
            value, set_at = self.thermostat_overrides[field]
            if time.monotonic() - set_at < OPTIMISTIC_TTL_SECONDS:
                return value
            del self.thermostat_overrides[field]
        data_key = self._thermostat_field_map[field]
        real = (self.data or {}).get(data_key)
        if real is not None:
            return real
        return self._thermostat_defaults[field]

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

    async def async_write_thermostat_settings(self, **field_updates) -> None:
        """field_updates: libovolná podmnožina day_temp/night_temp/
        day_night_mode - co chybí, doplní se z get_thermostat_value()."""
        now = time.monotonic()
        for field, value in field_updates.items():
            self.thermostat_overrides[field] = (value, now)

        thermostat_id = (self.data or {}).get("ThermostatId")
        if not thermostat_id:
            raise UpdateFailed("Neznámé ThermostatId - termostat zatím nenačetl data.")

        day_temp = self.get_thermostat_value("day_temp")
        night_temp = self.get_thermostat_value("night_temp")
        day_night_mode = self.get_thermostat_value("day_night_mode")

        await self.hass.async_add_executor_job(
            lambda: self.client.write_thermostat_settings(
                thermostat_id, day_temp, night_temp, day_night_mode,
                DEFAULT_THERMOSTAT_SCHEDULE,
            )
        )
        await self.async_request_refresh()
