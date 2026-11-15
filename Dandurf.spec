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
import importlib.util
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

comtypes_datas, comtypes_binaries, comtypes_hidden = collect_all('comtypes')
edge_datas, edge_binaries, edge_hidden = collect_all('edge_tts')
certifi_datas, certifi_binaries, certifi_hidden = collect_all('certifi')
ctk_datas, ctk_binaries, ctk_hidden = collect_all('customtkinter')
numpy_datas, numpy_binaries, numpy_hidden = collect_all('numpy')
pygame_datas, pygame_binaries, pygame_hidden = collect_all('pygame')
psutil_datas, psutil_binaries, psutil_hidden = collect_all('psutil')

# --------------------------------------------------------------------------
# Poistka pre edge-tts stiahnuty appkou (tlacidlo "Aktualizovat hlas")
# --------------------------------------------------------------------------
# hlas_kniznica.py vie za behu nacitat novsi edge-tts z PyPI - stiahne LEN
# jeho vlastny kod (edge_tts/*.py), nic ine. Ten kod sa ale importuje cez
# Python zabaleny v tomto .exe a ten ma len moduly, ktore PyInstaller pri
# builde videl. Novsi edge-tts moze siahnut po module, ktory dnesny
# nepouziva (alebo po inom podmodule aiohttp) - import by zlyhal a appka by
# aktualizaciu odmietla ako "incompatible" (treba novy Zanshin). Preto build
# bali o kus viac, nez dnesny edge-tts naozaj taha:
#
# 1. Zavislosti edge-tts cele (vsetky podmoduly, data, kniznice aj metadata):
#    aiohttp a co ziada on (aiohappyeyeballs, aiosignal, attrs = moduly attr
#    a attrs, frozenlist, multidict, propcache, yarl a jeho idna), tabulate
#    a typing_extensions; certifi je cely uz vyssie. Metadata (dist-info)
#    treba aj preto, lebo appka podla nich overi verzie, ktore novy edge-tts
#    ziada (Requires-Dist) - bez nich by verziu len odhadovala.
#    Bez .py zdrojakov ako dat (include_py_files=False) - bytecode v PYZ
#    staci. Bez __main__ (to su prikazy `python -m ...`, appka ich nespusta)
#    a z aiohttp bez testovacich modulov: pytest_plugin by do buildu
#    dotiahol cely pytest, worker gunicorn a test_utils unittest.
#    Balik, ktory tu nie je (starsi aiohttp napr. nemal propcache), sa
#    preskoci - build kvoli nemu nespadne.
_EDGE_ZAVISLOSTI = ('aiohttp', 'aiohappyeyeballs', 'aiosignal', 'attr', 'attrs',
                    'frozenlist', 'multidict', 'propcache', 'yarl', 'idna',
                    'tabulate')
_BEZ_TESTOV = ('aiohttp.pytest_plugin', 'aiohttp.test_utils', 'aiohttp.worker')


def _bez_main(meno):
    return not meno.endswith('.__main__')


def _bez_testov(meno):
    return _bez_main(meno) and meno not in _BEZ_TESTOV


def _je_tu(meno):
    return importlib.util.find_spec(meno) is not None


dep_datas, dep_binaries, dep_hidden = [], [], []
for _balik in _EDGE_ZAVISLOSTI:
    if _je_tu(_balik):
        _d, _b, _h = collect_all(_balik, include_py_files=False,
                                 filter_submodules=_bez_testov)
        dep_datas += _d
        dep_binaries += _b
        dep_hidden += _h
# typing_extensions je jeden modul, nie balik - collect_all by len varoval
if _je_tu('typing_extensions'):
    dep_hidden.append('typing_extensions')
    dep_datas += copy_metadata('typing_extensions')

# 2. Rozumny zoznam standardnej kniznice, po ktorej edge-tts siaha alebo by
#    mohol: dnesny 7.3.1 pouziva argparse, asyncio, concurrent.futures,
#    contextlib, dataclasses, datetime, email.utils, functools, io, json,
#    logging, queue, re, secrets, shutil, ssl, struct, time, typing, uuid a
#    xml.sax.saxutils - zoznam ich ma vsetky a k nim pribuzne (dalsi kus
#    toho isteho balika, ina hashovacia funkcia, ...).
#    Cele baliky, tiez bez __main__ (asyncio.__main__ by dotiahol cely
#    REPL).
_STDLIB_BALIKY = ('asyncio', 'concurrent', 'email', 'html', 'http', 'json',
                  'logging', 'urllib', 'xml')
_STDLIB_MODULY = (
    # siet a sifrovanie (WebSocket, token Sec-MS-GEC, hlavicky)
    'ssl', 'socket', 'selectors', 'ipaddress', 'hashlib', 'hmac', 'secrets',
    'uuid', 'base64', 'binascii', 'struct', 'zlib', 'random',
    # cas (hodiny pre token, hlavicka Date)
    'datetime', 'time', 'calendar',
    # text a SSML
    're', 'string', 'textwrap', 'unicodedata', 'codecs',
    # jazyk a typy
    'abc', 'collections', 'contextlib', 'contextvars', 'copy', 'dataclasses',
    'enum', 'functools', 'inspect', 'itertools', 'math', 'numbers',
    'operator', 'types', 'typing', 'warnings', 'weakref',
    # subory, procesy a prikazovy riadok edge-tts
    'argparse', 'io', 'mimetypes', 'pathlib', 'platform', 'queue', 'shlex',
    'shutil', 'signal', 'subprocess', 'tempfile', 'threading', 'traceback',
    'zipfile',
    # nacitanie balika a zistenie verzii
    'importlib.abc', 'importlib.machinery', 'importlib.metadata',
    'importlib.resources', 'importlib.util',
)
stdlib_hidden = list(_STDLIB_MODULY)
for _balik in _STDLIB_BALIKY:
    stdlib_hidden += collect_submodules(_balik, filter=_bez_main)
# Velkost: nemerana (cely Analysis trva minuty). Odhad je do 2 MB navyse k
# dist\Zanshin\ - zdrojaky vsetkeho v bodoch 1 a 2 maju spolu ~5 MB, velku
# cast z toho (asyncio, email, http.client, json, logging, ssl, klient
# aiohttp, yarl, multidict) build balil uz doteraz a bytecode v PYZ je
# komprimovany. Nove su hlavne xml, http.server, server cast aiohttp a
# email.mime. Build trva o par sekund dlhsie (zoznam podmodulov).

extra_datas = []
if os.path.isdir('assets'):
    extra_datas.append(('assets', 'assets'))
# POZN: tu sa pribaloval vyvojovy subor s App ID pre Steam. Zanshin nema
# ziadnu integraciu so Steamom (0.2), takze build nic take nebali.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=(comtypes_binaries + edge_binaries + certifi_binaries
             + ctk_binaries + numpy_binaries + pygame_binaries + psutil_binaries
             + dep_binaries),
    datas=(comtypes_datas + edge_datas + certifi_datas + ctk_datas
          + numpy_datas + pygame_datas + psutil_datas + dep_datas + extra_datas),
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
    ] + comtypes_hidden + edge_hidden + certifi_hidden + ctk_hidden + numpy_hidden + pygame_hidden + psutil_hidden
      # poistka pre stiahnuty edge-tts - viz vyssie
      + dep_hidden + stdlib_hidden,
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
