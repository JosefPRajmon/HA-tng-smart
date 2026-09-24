"""Config flow pro TnG Smart - přihlásíš se jménem/heslem, zbytek se najde samo."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .api import TngApiClient, TngAuthError, TngApiError
from .const import CONF_HEAT_PUMP_HASH, CONF_DESCRIPTION, CONF_MAC_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class TngConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._installations: list = []
        self._chosen_installation = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            client = TngApiClient(self._username, self._password)
            try:
                installations = await self.hass.async_add_executor_job(
                    self._login_and_discover, client
                )
            except TngAuthError:
                errors["base"] = "invalid_auth"
            except TngApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Neočekávaná chyba při přihlašování")
                errors["base"] = "unknown"
            else:
                self._installations = installations
                if len(installations) == 1:
                    self._chosen_installation = installations[0]
                    return await self.async_step_mac_address()
                if len(installations) > 1:
                    return await self.async_step_pick_installation()
                errors["base"] = "no_installations"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    def _login_and_discover(client: TngApiClient):
        client.login()
        return client.get_installations()

    async def async_step_pick_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        options = {
            inst.heat_pump_hash: (inst.description or inst.heat_pump_hash)
            for inst in self._installations
        }

        if user_input is not None:
            chosen_hash = user_input[CONF_HEAT_PUMP_HASH]
            self._chosen_installation = next(
                i for i in self._installations if i.heat_pump_hash == chosen_hash
            )
            return await self.async_step_mac_address()

        schema = vol.Schema({vol.Required(CONF_HEAT_PUMP_HASH): vol.In(options)})
        return self.async_show_form(step_id="pick_installation", data_schema=schema)

    async def async_step_mac_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            return await self._finish(
                self._chosen_installation, user_input[CONF_MAC_ADDRESS]
            )

        schema = vol.Schema({vol.Required(CONF_MAC_ADDRESS): str})
        return self.async_show_form(
            step_id="mac_address", data_schema=schema, errors=errors
        )

    async def _finish(self, installation, mac_address: str) -> FlowResult:
        await self.async_set_unique_id(installation.heat_pump_hash)
        self._abort_if_unique_id_configured()

        # Server chce MAC bez dvojteček/pomlček/mezer (holý hex řetězec).
        normalized_mac = re.sub(r"[^0-9A-Fa-f]", "", mac_address).upper()

        return self.async_create_entry(
            title=installation.description or "TnG Smart",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_HEAT_PUMP_HASH: installation.heat_pump_hash,
                CONF_MAC_ADDRESS: normalized_mac,
                CONF_DESCRIPTION: installation.description,
            },
        )
