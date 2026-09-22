# -*- mode: python ; coding: utf-8 -*-
#
# ============================================================================
# STEAM BUILD - odvodene od Dandurf.spec, jediny rozdiel: uac_admin=False.
#
# Na Steame appka bezi z kniznice Steamu (steamapps\common), ktoru Steam
# spravuje bez UAC. Keby si .exe pytal admin prava:
#   - hrac dostane UAC vyzvu pri KAZDOM spusteni (na Steame nezvykle),
#   - Steam Overlay a herny cas sa rozbiju (Steam sa k elevovanemu procesu
#     nedostane),
#   - anti-cheat hodnoti elevovany proces + overlay najprisnejsie.
# Od verzie 2.1 appka ziadne globalne hooky NEINSTALUJE - aktivita sa
# zistuje cez GetLastInputInfo, co vracia jedine pocet milisekund od
# posledneho vstupu. Viz SAFETY.md a STEAM_BUILD.md.
#
# Build:  pyinstaller ZanshinDojoSync_steam.spec
# ============================================================================
#
# Onedir build (priecinok dist\ZanshinDojoSync\ s .exe + kniznicami) -
# ZAMERNE nie --onefile. Onefile pri kazdom spusteni rozbaluje seba sameho
# do %TEMP%\_MEIxxxxxx, co Windows Smart App Control / Defender vyhodnocuje
# ako podozrive "self-extracting" spravanie (typicka signatura dropperov).
# Onedir nic nerozbaluje za behu - .exe len nacita kniznice z vlastneho
# priecinka. Inno Setup (Dandurf.iss) potom cely tento priecinok skladá
# do jedneho instalacneho balicka, takze pouzivatel stale dostane jeden
# setup.exe na spustenie.
#
# POZN: tento odstavec kedysi odovodnoval `uac_admin=True` (Smart App Control
# vraj potrebuje elevaciu pri globalnych hookoch). Pre Steam to neplati a
# hodnota je nizsie natvrdo False - dovody su v hlavicke vyssie. Odstavec tu
# zostava len preto, aby nikto pri porovnavani s Dandurf.spec nemyslel, ze
# sa na uac_admin zabudlo.
import os
from PyInstaller.utils.hooks import collect_all

comtypes_datas, comtypes_binaries, comtypes_hidden = collect_all('comtypes')
edge_datas, edge_binaries, edge_hidden = collect_all('edge_tts')
certifi_datas, certifi_binaries, certifi_hidden = collect_all('certifi')
ctk_datas, ctk_binaries, ctk_hidden = collect_all('customtkinter')
numpy_datas, numpy_binaries, numpy_hidden = collect_all('numpy')
pygame_datas, pygame_binaries, pygame_hidden = collect_all('pygame')
psutil_datas, psutil_binaries, psutil_hidden = collect_all('psutil')

extra_datas = []
if os.path.isdir('assets'):
    extra_datas.append(('assets', 'assets'))
# steam_appid.txt sa pribali len ak existuje (vyvojovy subor); do
# finalneho Steam depotu netreba - Steam ho aj tak ignoruje.
if os.path.isfile('steam_appid.txt'):
    extra_datas.append(('steam_appid.txt', '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=(comtypes_binaries + edge_binaries + certifi_binaries
             + ctk_binaries + numpy_binaries + pygame_binaries + psutil_binaries),
    datas=(comtypes_datas + edge_datas + certifi_datas + ctk_datas
          + numpy_datas + pygame_datas + psutil_datas + extra_datas),
    hiddenimports=[
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
        'comtypes',
        'comtypes.stream',
        'pystray._win32',
        'edge_tts',
        'aiohttp',
        'certifi',
        'customtkinter',
        'numpy',
        'pygame',
        'psutil',
        'steam_integration',
    ] + comtypes_hidden + edge_hidden + certifi_hidden + ctk_hidden + numpy_hidden + pygame_hidden + psutil_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZanshinDojoSync',
    icon='Dandurf.ico',
    # Metadata .exe (nazov, autor, popis, verzia) - bez tohto sa zabaleny
    # .exe hlasi s prazdnou zalozkou "Podrobnosti". Viz version_info.txt.
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX VYPNUTY: komprimovany .exe sa pri spusteni sam rozbaluje v
    # pamati, co je signatura baleneho malveru - Defender/SmartScreen
    # na to reaguju heuristikou, ktora sa meni s kazdou aktualizaciou
    # definicii (preto build, ktory najprv isiel, zacne zrazu padat do
    # karanteny bez jedinej zmeny v kode). Uspora miesta za to nestoji.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,   # STEAM: ziadne UAC, viz hlavicka
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    # UPX VYPNUTY: komprimovany .exe sa pri spusteni sam rozbaluje v
    # pamati, co je signatura baleneho malveru - Defender/SmartScreen
    # na to reaguju heuristikou, ktora sa meni s kazdou aktualizaciou
    # definicii (preto build, ktory najprv isiel, zacne zrazu padat do
    # karanteny bez jedinej zmeny v kode). Uspora miesta za to nestoji.
    upx=False,
    name='ZanshinDojoSync',
)
