# Steam build — čo doplniť a ako spustiť

Táto zložka je **kostra Steam depotu**. Nie je hotová na spustenie —
chýbajú v nej čísla, ktoré dostaneš až po založení appky na
[partner.steamgames.com](https://partner.steamgames.com). To sa odtiaľto
spraviť nedá (je za tvojím Steamworks účtom a platbou $100). Nižšie je
presný zoznam, čo doplniť.

## Predpoklady (jednorazovo)

1. **Steamworks účet** + zaplatený App Fee ($100). Dostaneš **App ID**.
2. V Steamworks pre appku vytvor **jeden depot**. Dostaneš **Depot ID**
   (býva App ID + 1).
3. Stiahni **`steamcmd`** ([návod Valve](https://developer.valvesoftware.com/wiki/SteamCMD)).
4. Nastav appku ako **Software / Application**, nie Game — Zanshin nie je
   hra (viď `../STEAM_BUILD.md`).

## Čo doplniť

V **`app_build.vdf`** nahraď dva `PLACEHOLDER`:
- `"AppID" "0000000"` → tvoje App ID
- `"0000001"` (Depot ID) → tvoje Depot ID

To je všetko — cesty (`ContentRoot`, `BuildOutput`) sú relatívne a fungujú
tak, ako sú.

## Build (na Windows)

```powershell
# 1. postav .exe bez UAC (Steam variant)
pyinstaller ZanshinDojoSync_steam.spec

# 2. over, že vznikol dist\ZanshinDojoSync\ZanshinDojoSync.exe

# 3. nahraj depot na Steam
steamcmd +login TVOJ_UCET +run_app_build "%CD%\steam\app_build.vdf" +quit
```

Po dobehnutí sa build objaví v Steamworks → tvoja appka → **SteamPipe →
Builds**, odkiaľ ho pošleš na `default` alebo `beta` vetvu.

## Testovanie počas vývoja

Vedľa `.exe` daj súbor **`steam_appid.txt`** s tvojím App ID (len číslo).
Umožní appke spustiť sa cez Steam API mimo Steamu počas ladenia. **Do
finálneho depotu nepatrí** — Steam ho pri publikovaní ignoruje, ale je
čistejšie ho tam nedávať.

## Steamworks SDK — potrebuješ ho vôbec?

Appka **funguje aj bez SDK** — `steam_integration.py` (v koreni projektu)
je napísaný tak, že keď `steamworks` modul chýba, ticho sa vypne a appka
beží ďalej ako doteraz. SDK doplň, len ak chceš:
- **herný čas** (Steam ho počíta aj bez SDK, keď appka beží — netreba nič),
- **achievementy alebo Rich Presence** (to už SDK vyžaduje).

Pre alpha to nechaj tak — vydaj bez SDK, pridaj neskôr.
