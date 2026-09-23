# TnG Air Smart – Home Assistant Integration

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/JosefPRajmon/HA-tng-smart?include_prereleases&sort=semver)](https://github.com/JosefPRajmon/HA-tng-smart/releases)
[![License](https://img.shields.io/github/license/JosefPRajmon/HA-tng-smart)](LICENSE)

Neoficiální vlastního integrace pro **Home Assistant**, která umožňuje sledování a řízení systémů vytápění a tepelných čerpadel **TnG-Air Smart** ([tngsmart.cz](https://tngsmart.cz/)).

---

## ⚠️ Důležité upozornění (Disclaimer)

* Jedná se o **neoficiální komunitní integraci** vyvíjenou nezávisle na společnosti TnG – Air.CZ, s. r. o.
* **Status žádosti:** Výrobce/poskytovatel služby TnG-Air byl kontaktován s oficiální žádostí o povolení / schválení k provozu této integrace.
* Použití této integrace je na vlastní nebezpečí. Autor nenese žádnou odpovědnost za případné škody nebo výpadky služby způsobené použitím tohoto softwaru.

---

## ✨ Hlavní funkce

- 🌡️ **Sledování teplot:** Zobrazení aktuální a požadované teploty v místnosti i venkovní teploty.
- 🎛️ **Řízení klimatu (`climate` entita):** Nastavení požadované teploty a provozních režimů (topení, chlazení, ekologický režim, vypnuto).
- 📊 **Stavové senzory:** Přehled o stavu čerpadla, aktivních výstupech a chybových hlášeních.
- ⚡ **Automatizace:** Možnost propojení s dalšími prvky v Home Assistantu (např. útlum při odchodu z domova, fotovoltaika apod.).

---

## 📋 Požadavky

- Funkční účet na portálu [TnG Air Smart](https://tngsmart.cz/).
- Funkční instalace **Home Assistant** (verze 2023.x nebo novější).
- [HACS](https://hacs.xyz/) (doporučeno pro snadnou instalaci a aktualizace).

---

## 🚀 Instalace

### Možnost A: Přes HACS (Doporučeno)

1. V Home Assistantu otevřete **HACS** -> **Integrace**.
2. V pravém horním rohu klikněte na ikonu tři teček (`⋮`) a vyberte **Vlastní repozitáře** (*Custom repositories*).
3. Do pole **URL** vložte:
   ```text
   [https://github.com/JosefPRajmon/HA-tng-smart](https://github.com/JosefPRajmon/HA-tng-smart)