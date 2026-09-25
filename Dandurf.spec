# -*- mode: python ; coding: utf-8 -*-
#
# Onedir build (priecinok dist\Zanshin\ s .exe + kniznicami) -
# ZAMERNE nie --onefile. Onefile pri kazdom spusteni rozbaluje seba sameho
# do %TEMP%\_MEIxxxxxx, co Windows Smart App Control / Defender vyhodnocuje
# ako podozrive "self-extracting" spravanie (typicka signatura dropperov).
# Onedir nic nerozbaluje za behu - .exe len nacita kniznice z vlastneho
# priecinka. Inno Setup (Dandurf.iss) potom cely tento priecinok skladá
# do jedneho instalacneho balicka, takze pouzivatel stale dostane jeden
# setup.exe na spustenie.
#
# uac_admin=False (viz EXE nizsie): appka NEZIADA administratorske prava.
# POZN: povodne tu bolo `uac_admin=True` s odovodnenim, ze Smart App Control
# povazuje globalne klavesove hooky bez elevacie za podozrive. To uz NEPLATI
# a zamerne sa to nevracia:
#   - klavesovy hook (WH_KEYBOARD_LL) z neverejnych verzii admin prava
#     nepotreboval ani vtedy - overene nazivo (gui_harness_auto.py); pred
#     prvou verejnou alfou bol zruseny, globalne hooky appka dnes nema,
#   - instalator uz nejde do C:\Program Files, ale do %LOCALAPPDATA%\Programs
#     (PrivilegesRequired=lowest v Dandurf.iss), takze UAC netreba ani tam,
#   - elevovany proces + overlay nad hrou je presne profil, ktory anti-cheaty
#     (Vanguard, EAC, VAC) hodnotia najprisnejsie.
# Viz SAFETY.md. Nikdy to nevracaj na admin.
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
# POZN: tu sa pribaloval vyvojovy subor s App ID pre Steam. Zanshin nema
# ziadnu integraciu so Steamom (0.2), takze build nic take nebali.

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
        # cestina a bulharcina (0.2) - i18n.py ich vklada importom na konci
        # suboru; PyInstaller ho najde aj sam, toto je poistka, aby build
        # nikdy neostal bez nich (bez modulu by import i18n pri starte spadol
        # na ImportError - appka by sa vobec nespustila).
        'i18n_cs_bg',
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
    name='Zanshin',
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
    # ADMIN VYPNUTY (bolo True). Elevovany proces + overlay nad hrou je
    # presne profil, ktory anti-cheaty (Vanguard, EAC, VAC) hodnotia
    # najprisnejsie (viz SAFETY.md).
    # Globalne hooky appka nema - klavesovy hook z neverejnych verzii bol
    # zruseny pred prvou verejnou alfou. Instalator (Dandurf.iss) preto
    # instaluje do profilu pouzivatela bez UAC - to zaroven odstranuje
    # "Error 707" pri instalacii.
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    # UPX VYPNUTY aj tu - dovod je pri `upx=False` v EXE vyssie.
    upx=False,
    name='Zanshin',
)
