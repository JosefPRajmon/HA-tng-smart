"""Coordinator: pravidelně (a on-demand po zápisu) stahuje stav čerpadla."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TngApiClient, TngApiError, TngAuthError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class TngCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, client: TngApiClient, heat_pump_hash: str):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.heat_pump_hash = heat_pump_hash

    async def _async_update_data(self) -> dict:
        try:
            return await self.hass.async_add_executor_job(
                self.client.get_installation_status, self.heat_pump_hash
            )
        except TngAuthError as err:
            raise UpdateFailed(f"Přihlášení selhalo: {err}") from err
        except TngApiError as err:
            raise UpdateFailed(f"Chyba API: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Neočekávaná chyba: {err}") from err
