"""Konstanty pro integraci TnG Smart."""

DOMAIN = "tng_smart"

CONF_HEAT_PUMP_HASH = "heat_pump_hash"
CONF_MAC_ADDRESS = "mac_address"
CONF_DESCRIPTION = "description"

BASE_URL = "https://tngsmart.cz"
LOGIN_URL = f"{BASE_URL}/Pages/Login"
CROSSROAD_URL = f"{BASE_URL}/Pages/Account/CrossRoad"
INSTALLATIONS_URL = f"{BASE_URL}/Pages/Account/MyInstallations"

UPDATE_INTERVAL_SECONDS = 120

MIN_HEAT_TEMP = 15
MAX_HEAT_TEMP = 55
MIN_BOILER_TEMP = 18
MAX_BOILER_TEMP = 60
MIN_POOL_TEMP = 18
MAX_POOL_TEMP = 40
