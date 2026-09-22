"""Synchronní klient pro webové rozhraní tngsmart.cz.

Reverse-engineered z ASP.NET WebForms webu: přihlášení přes session cookie,
čtení stavu parsováním JS proměnných vložených do HTML, zápis nastavení
přes jediný JSON endpoint /api/HeatPumpInsertBasicSettings_v3/...

Tato třída je čistě synchronní (requests) - v Home Assistantu se volá
přes hass.async_add_executor_job, viz coordinator.py.
"""
from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

_LOGGER = logging.getLogger(__name__)

from .const import BASE_URL, CROSSROAD_URL, INSTALLATIONS_URL, LOGIN_URL


class TngAuthError(Exception):
    """Chybné přihlašovací údaje."""


class TngApiError(Exception):
    """Obecná chyba komunikace s API."""


@dataclass
class TngInstallation:
    """Jedna instalace (čerpadlo) na účtu."""

    heat_pump_hash: str
    mac_address: str
    description: str
    thermostat_id: int | None = None


class TngApiClient:
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; HomeAssistant-TngSmart/0.1)"}
        )
        self._logged_in = False
        self._auth_ids: dict | None = None
        self._crossroad_visited = False

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #
    def login(self) -> None:
        r = self._session.get(LOGIN_URL, timeout=15)
        r.raise_for_status()

        viewstate = self._extract_hidden(r.text, "__VIEWSTATE")
        viewstategen = self._extract_hidden(r.text, "__VIEWSTATEGENERATOR")

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstategen,
            "ctl00$MainContent$UserName": self._username,
            "ctl00$MainContent$Password": self._password,
            "ctl00$MainContent$ctl01": "Přihlásit se",
        }

        r2 = self._session.post(LOGIN_URL, data=payload, timeout=15,
                                 allow_redirects=True)
        r2.raise_for_status()

        if "Login" in r2.url and "MainContent_Password" in r2.text:
            self._logged_in = False
            raise TngAuthError("Přihlášení selhalo - zkontroluj údaje.")

        self._logged_in = True
        self._crossroad_visited = False
        self._auth_ids = {
            "UserId": self._extract_js_var(r2.text, "UserId"),
            "UserName": self._extract_js_var(r2.text, "UserName", string=True),
            "UserIdHash": self._extract_js_var(r2.text, "UserIdHash", string=True),
        }

    def _ensure_login(self) -> None:
        if not self._logged_in:
            self.login()

    def _ensure_crossroad_visited(self) -> None:
        """MyInstallations vyžaduje, aby session nejdřív 'prošla' přes
        CrossRoad (server si tam nejspíš do Session state uloží vybranou
        instalaci) - jinak vrací jinou stránku bez proměnné HeatPump."""
        if self._crossroad_visited:
            return
        r = self._session.get(CROSSROAD_URL, timeout=15)
        r.raise_for_status()
        self._crossroad_visited = True
        if not self._auth_ids or not self._auth_ids.get("UserId"):
            self._auth_ids = {
                "UserId": self._extract_js_var(r.text, "UserId"),
                "UserName": self._extract_js_var(r.text, "UserName", string=True),
                "UserIdHash": self._extract_js_var(r.text, "UserIdHash", string=True),
            }

    @staticmethod
    def _extract_hidden(html: str, field_id: str) -> str:
        m = re.search(rf'id="{field_id}"[^>]*value="([^"]*)"', html)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_js_var(html: str, name: str, string: bool = False):
        if string:
            m = re.search(rf'{name}\s*=\s*"([^"]*)"', html)
        else:
            m = re.search(rf"{name}\s*=\s*(\d+)", html)
        return m.group(1) if m else None

    # ------------------------------------------------------------------ #
    # Discovery - seznam instalací z hlavní stránky (CrossRoad)
    # ------------------------------------------------------------------ #
    def get_installations(self) -> list[TngInstallation]:
        self._ensure_login()
        self._ensure_crossroad_visited()

        r = self._session.get(CROSSROAD_URL, timeout=15)
        r.raise_for_status()

        m = re.search(r"var HpAndThermostatData\s*=\s*(\[.*?\]);", r.text, re.S)
        if not m:
            _LOGGER.debug(
                "HpAndThermostatData nenalezeno. URL po requestu: %s, status: %s, "
                "délka odpovědi: %d znaků, prvních 300 znaků: %s",
                r.url, r.status_code, len(r.text), r.text[:300],
            )
            raise TngApiError(
                "Na stránce CrossRoad se nepodařilo najít seznam instalací "
                "(HpAndThermostatData). Zapni si debug log pro "
                "custom_components.tng_smart a zkus to znovu."
            )

        raw = re.sub(r'"\\/Date\((-?\d+)\)\\/"', r"\1", m.group(1))
        items = json.loads(raw)

        installations = []
        for item in items:
            installations.append(
                TngInstallation(
                    heat_pump_hash=item["HeatPumpHash"],
                    mac_address="",  # doplní se při prvním get_status()
                    description=item.get("HeatPumpDescription") or "TnG Smart",
                    thermostat_id=item.get("ThermostatId"),
                )
            )
        return installations

    # ------------------------------------------------------------------ #
    # Čtení stavu
    # ------------------------------------------------------------------ #
    def get_installation_status(self, heat_pump_hash: str) -> dict:
        """Vrátí aktuální stav jedné instalace z HpAndThermostatData na
        stránce CrossRoad. Na rozdíl od get_status() (viz níže) tahle
        cesta u tohoto účtu spolehlivě funguje i z čerstvé (neprohlížečové)
        session, takže ji používáme jako primární zdroj dat pro čtení."""
        self._ensure_login()

        r = self._session.get(CROSSROAD_URL, timeout=15)
        r.raise_for_status()

        m = re.search(r"var HpAndThermostatData\s*=\s*(\[.*?\]);", r.text, re.S)
        if not m:
            _LOGGER.debug(
                "HpAndThermostatData nenalezeno v get_installation_status. "
                "URL: %s, status: %s, délka: %d",
                r.url, r.status_code, len(r.text),
            )
            raise TngApiError(
                "Na stránce CrossRoad se nepodařilo najít seznam instalací."
            )

        raw = re.sub(r'"\\/Date\((-?\d+)\)\\/"', r"\1", m.group(1))
        items = json.loads(raw)

        if not self._auth_ids or not self._auth_ids.get("UserId"):
            self._auth_ids = {
                "UserId": self._extract_js_var(r.text, "UserId"),
                "UserName": self._extract_js_var(r.text, "UserName", string=True),
                "UserIdHash": self._extract_js_var(r.text, "UserIdHash", string=True),
            }

        for item in items:
            if item.get("HeatPumpHash") == heat_pump_hash:
                return item

        raise TngApiError(
            f"Instalace s hashem {heat_pump_hash} nebyla na CrossRoad "
            "nalezena."
        )

    def get_latest_data_point(self, heat_pump_hash: str, minutes: int = 15) -> dict | None:
        """Vrátí poslední naměřený bod z /api/HeatPumpData/ - skutečné
        aktuální teploty (na rozdíl od CrossRoad, kde CurrentHeatingWaterTemp
        je nastavená/cílová hodnota, ne reálně měřená). URL má formát
        {hash}-{fromMs}-{toMs}-{0} - fromMs/toMs jsou unix časy v ms,
        poslední 0 je nejspíš "bez agregace".
        Vrací dict {"t": venkovní, "tb": bojler, "tt": místnost,
        "tw": voda na výstupu} v °C (float), nebo None, pokud selže."""
        self._ensure_login()

        to_ms = int(time.time() * 1000)
        from_ms = to_ms - minutes * 60 * 1000
        url = f"{BASE_URL}/api/HeatPumpData/{heat_pump_hash}-{from_ms}-{to_ms}-0"

        r = self._session.get(url, timeout=15)
        r.raise_for_status()

        # Endpoint umí vracet JSON i XML podle Accept hlavičky/klienta -
        # naše requests session dostává JSON, tak ho zkusíme první.
        try:
            payload = r.json()
            points = payload.get("First") or []
            if not points:
                _LOGGER.debug("HeatPumpData (JSON) nevrátilo žádné body.")
                return None
            latest = points[-1]
            result: dict = {}
            for key in ("t", "tb", "tt", "tw"):
                val = latest.get(key)
                if val is not None:
                    result[key] = val / 10.0
            result["time"] = latest.get("time")
            return result
        except (ValueError, AttributeError):
            pass  # není to JSON, zkusíme XML níže

        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            _LOGGER.debug(
                "Nepodařilo se naparsovat HeatPumpData ani jako JSON, ani "
                "jako XML: %s",
                r.text[:300],
            )
            return None

        points = [el for el in root.iter() if el.tag.split("}")[-1] == "HeatPumpDataShort"]
        if not points:
            _LOGGER.debug("HeatPumpData nevrátilo žádné body pro dané okno.")
            return None

        latest = points[-1]
        raw = {child.tag.split("}")[-1]: child.text for child in latest}

        result: dict = {}
        for key in ("t", "tb", "tt", "tw"):
            val = raw.get(key)
            if val is None:
                continue
            try:
                result[key] = int(val) / 10.0
            except ValueError:
                pass
        result["time"] = raw.get("time")
        return result

    def write_settings(
        self,
        heat_pump_hash: str,
        mac_address: str,
        heat_on: bool,
        heat_temp_const: int,
        boiler_on: bool,
        boiler_temp: int,
        pool_on: bool = False,
        pool_temp: int = 37,
    ) -> None:
        """Zapíše základní nastavení. Regulace/LeadingThermostat/EquitCurve
        a vlastní ekvitermní křivka jsou napevno podle aktuálního nastavení
        účtu (Termostat TnG RF, křivka č. 4) - dokud neumíme spolehlivě
        přečíst plný stav z MyInstallations, měnit je odsud neumíme."""
        self._ensure_login()

        # Server chce MAC jako holý hex řetězec bez dvojteček/pomlček -
        # očistíme i tady pro jistotu (kdyby konfigurace obsahovala starší,
        # neočištěný formát).
        mac_address = re.sub(r"[^0-9A-Fa-f]", "", mac_address).upper()

        packet = {
            "HeatSet": {
                "Heat": heat_on,
                "HeatingMode": 0,
                "EquitCurve": 4,
                "Boost": False,
                "EmergencyMode": False,
                "ExtendedHeatSet": {"Regulation": 3, "LeadingThermostat": 1},
            },
            "HeatTemp_Const": heat_temp_const,
            "HeatTempEqCustom_P20": 34,
            "HeatTempEqCustom_P10": 38,
            "HeatTempEqCustom_P0": 42,
            "HeatTempEqCustom_M10": 46,
            "HeatTempEqCustom_M20": 50,
            "BoilerSet": {"Boiler": boiler_on, "Boost": False, "Sensor": False},
            "BoilerTemp": boiler_temp,
            "PoolSet": {"Pool": pool_on, "Boost": False},
            "PoolTemp": pool_temp,
            "AccSecure": True,
        }

        if not self._auth_ids or not self._auth_ids.get("UserId"):
            raise TngApiError(
                "Chybí přihlašovací identifikátory (UserId/UserIdHash) - "
                "nejdřív se musí povést alespoň jedno čtení stavu."
            )

        url = (
            f"{BASE_URL}/api/HeatPumpInsertBasicSettings_v3/"
            f"{self._auth_ids['UserId']}-{heat_pump_hash}-{mac_address}-"
            f"{self._auth_ids['UserName']}-{self._auth_ids['UserIdHash']}"
        )

        r = self._session.post(url, json=packet, timeout=15)
        _LOGGER.debug(
            "write_settings POST %s -> status %s, tělo odpovědi: %r, "
            "odeslaný packet: %s",
            url, r.status_code, r.text[:500], packet,
        )
        r.raise_for_status()

    def get_status(self, heat_pump_hash: str) -> dict:
        self._ensure_login()
        self._ensure_crossroad_visited()

        url = f"{INSTALLATIONS_URL}?HeatPumpHash={heat_pump_hash}"
        r = self._session.get(url, timeout=15)
        r.raise_for_status()

        m = re.search(r"var HeatPump\s*=\s*(\{.*?\});", r.text, re.S)
        if not m:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S)
            title = title_match.group(1).strip() if title_match else "?"
            has_crossroad_data = "HpAndThermostatData" in r.text
            _LOGGER.debug(
                "HeatPump nenalezeno. URL: %s, status: %s, délka: %d, "
                "title: %r, obsahuje HpAndThermostatData: %s, "
                "prvních 500 znaků (repr): %r",
                r.url, r.status_code, len(r.text), title,
                has_crossroad_data, r.text[:500],
            )
            raise TngApiError(
                "Nepodařilo se najít proměnnou HeatPump ve stránce - "
                "session možná vypršela nebo je hash čerpadla špatně."
            )

        raw = re.sub(r'"\\/Date\((-?\d+)\)\\/"', r"\1", m.group(1))
        data = json.loads(raw)

        if not self._auth_ids or not self._auth_ids.get("UserId"):
            self._auth_ids = {
                "UserId": self._extract_js_var(r.text, "UserId"),
                "UserName": self._extract_js_var(r.text, "UserName", string=True),
                "UserIdHash": self._extract_js_var(r.text, "UserIdHash", string=True),
            }

        data["_auth"] = self._auth_ids
        return data

    # ------------------------------------------------------------------ #
    # Zápis nastavení
    # ------------------------------------------------------------------ #
    def send_settings(
        self,
        status: dict,
        heat: dict | None = None,
        boiler: dict | None = None,
        pool: dict | None = None,
        heat_temp_const: int | None = None,
        boiler_temp: int | None = None,
        pool_temp: int | None = None,
    ) -> None:
        self._ensure_login()

        settings = status["Settings"]
        auth = status["_auth"]

        cur_heat = dict(settings["HeatSet"])
        cur_boiler = dict(settings["BoilerSet"])
        cur_pool = dict(settings["PoolSet"])

        if heat:
            cur_heat.update(heat)
        if boiler:
            cur_boiler.update(boiler)
        if pool:
            cur_pool.update(pool)

        extended = settings["HeatSet"].get("ExtendedHeatSet") or {}

        packet = {
            "HeatSet": {
                "Heat": cur_heat.get("Heat", False),
                "HeatingMode": cur_heat.get("HeatingMode", 0),
                "EquitCurve": settings.get("EquitCurve", 4),
                "Boost": cur_heat.get("Boost", False),
                "EmergencyMode": cur_heat.get("EmergencyMode", False),
                "ExtendedHeatSet": {
                    "Regulation": extended.get("Regulation", 0),
                    "LeadingThermostat": extended.get("LeadingThermostat", 1),
                },
            },
            "HeatTemp_Const": (
                heat_temp_const
                if heat_temp_const is not None
                else settings["HeatTemp_Const"]["ShortValue"]
            ),
            "HeatTempEqCustom_P20": settings["HeatTempCustom_P20"]["ShortValue"],
            "HeatTempEqCustom_P10": settings["HeatTempCustom_P10"]["ShortValue"],
            "HeatTempEqCustom_P0": settings["HeatTempCustom_0"]["ShortValue"],
            "HeatTempEqCustom_M10": settings["HeatTempCustom_M10"]["ShortValue"],
            "HeatTempEqCustom_M20": settings["HeatTempCustom_M20"]["ShortValue"],
            "BoilerSet": {
                "Boiler": cur_boiler.get("Boiler", False),
                "Boost": cur_boiler.get("Boost", False),
                "Sensor": cur_boiler.get("Sensor", False),
            },
            "BoilerTemp": (
                boiler_temp
                if boiler_temp is not None
                else settings["BoilerTemp"]["ShortValue"]
            ),
            "PoolSet": {
                "Pool": cur_pool.get("Pool", False),
                "Boost": cur_pool.get("Boost", False),
            },
            "PoolTemp": (
                pool_temp
                if pool_temp is not None
                else settings["PoolTemp"]["ShortValue"]
            ),
            "AccSecure": settings.get("AccumulationSecure", True),
        }

        url = (
            f"{BASE_URL}/api/HeatPumpInsertBasicSettings_v3/"
            f"{auth['UserId']}-{status['HeatPumpHash']}-"
            f"{status['MacAddress']}-{auth['UserName']}-{auth['UserIdHash']}"
        )

        r = self._session.post(url, json=packet, timeout=15)
        r.raise_for_status()
