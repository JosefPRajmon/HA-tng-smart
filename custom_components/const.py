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

CONF_THERMOSTAT_ID = "thermostat_id"

MIN_THERMOSTAT_TEMP = 10
MAX_THERMOSTAT_TEMP = 30

# Jak dlouho (v sekundách) věříme naší vlastní odeslané hodnotě, než se
# vzdáme čekání na potvrzení a začneme znovu důvěřovat datům ze serveru
# (i kdyby se lišila - třeba proto, že někdo změnil nastavení přímo na
# webu tngsmart.cz).
OPTIMISTIC_TTL_SECONDS = 300

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_CZECH_NAMES = {
    "Monday": "Pondělí",
    "Tuesday": "Úterý",
    "Wednesday": "Středa",
    "Thursday": "Čtvrtek",
    "Friday": "Pátek",
    "Saturday": "Sobota",
    "Sunday": "Neděle",
}

# Výchozí rozsahy hodin (denní teplota) v pořadí WEEKDAYS, dokud se
# nenačte/needituje skutečný rozvrh - odvozeno z reálného nastavení účtu.
DEFAULT_SCHEDULE_RANGES = [
    "6-8,16-22",  # Po
    "6-8,16-22",  # Út
    "6-8,16-22",  # St
    "6-8,16-22",  # Čt
    "6-8,16-22",  # Pá
    "6-22",       # So
    "6-22",       # Ne
]

# Tyhle hodnoty se u tebe (podle zachycených requestů) prakticky nemění -
# bereme je jako pevné defaulty, ať nemusíme řešit MyInstallations.
# Pokud si v budoucnu přes web přepneš "Zdroj regulace" nebo "Bivalence",
# je potřeba je tu ručně přepsat.
DEFAULT_HEATING_MODE = 0
DEFAULT_EQUIT_CURVE = 4
DEFAULT_HEAT_REGULATION = 3
DEFAULT_LEADING_THERMOSTAT = 1
DEFAULT_CUSTOM_P20 = 34
DEFAULT_CUSTOM_P10 = 38
DEFAULT_CUSTOM_P0 = 42
DEFAULT_CUSTOM_M10 = 46
DEFAULT_CUSTOM_M20 = 50
DEFAULT_BOILER_TEMP = 50
DEFAULT_POOL_TEMP = 37
DEFAULT_ACC_SECURE = True
