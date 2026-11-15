# -*- mode: python ; coding: utf-8 -*-
#
# Onedir build (folder dist\Zanshin\ with the .exe + libraries) -
# DELIBERATELY not --onefile. Onefile unpacks itself on every start into
# %TEMP%\_MEIxxxxxx, which Windows Smart App Control / Defender rates as
# suspicious "self-extracting" behaviour (a typical dropper signature).
# Onedir unpacks nothing at runtime - the .exe just loads libraries from its
# own folder. Inno Setup (Dandurf.iss) then packs this whole folder into one
# installer package, so the user still gets a single setup.exe to run.
#
# uac_admin=False (see EXE below): the app does NOT ask for administrator
# rights.
# NOTE: originally this was `uac_admin=True`, justified by Smart App Control
# treating global keyboard hooks without elevation as suspicious. That NO
# LONGER APPLIES and it is deliberately not coming back:
#   - the keyboard hook (WH_KEYBOARD_LL) from non-public versions did not
#     need admin rights even then - verified live (gui_harness_auto.py); it
#     was removed before the first public alpha, the app has no global hooks
#     today,
#   - the installer no longer goes to C:\Program Files but to
#     %LOCALAPPDATA%\Programs (PrivilegesRequired=lowest in Dandurf.iss), so
#     no UAC is needed there either,
#   - an elevated process + an overlay over the game is exactly the profile
#     that anti-cheats (Vanguard, EAC, VAC) judge most strictly.
# See SAFETY.md. Never switch this back to admin.
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
# Safety net for edge-tts downloaded by the app (the "Update voice" button)
# --------------------------------------------------------------------------
# hlas_kniznica.py can load a newer edge-tts from PyPI at runtime - it
# downloads ONLY its own code (edge_tts/*.py), nothing else. But that code is
# imported through the Python bundled in this .exe, and that one only has
# the modules PyInstaller saw at build time. A newer edge-tts may reach for a
# module today's one does not use (or for another aiohttp submodule) - the
# import would fail and the app would reject the update as "incompatible"
# (a new Zanshin is needed). That is why the build packs a bit more than
# today's edge-tts really pulls in:
#
# 1. The edge-tts dependencies in full (all submodules, data, libraries and
#    metadata): aiohttp and what it requires (aiohappyeyeballs, aiosignal,
#    attrs = modules attr and attrs, frozenlist, multidict, propcache, yarl
#    and its idna), tabulate and typing_extensions; certifi is already
#    included in full above. The metadata (dist-info) is also needed because
#    the app uses it to check the versions a new edge-tts requires
#    (Requires-Dist) - without it, it would only guess the version.
#    Without the .py sources as data (include_py_files=False) - the bytecode
#    in the PYZ is enough. Without __main__ (those are `python -m ...`
#    commands, the app does not run them) and, from aiohttp, without the
#    test modules: pytest_plugin would pull all of pytest into the build,
#    worker would pull gunicorn and test_utils unittest.
#    A package that is not here (an older aiohttp, e.g., had no propcache)
#    is skipped - the build does not fail because of it.
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
# typing_extensions is one module, not a package - collect_all would just warn
if _je_tu('typing_extensions'):
    dep_hidden.append('typing_extensions')
    dep_datas += copy_metadata('typing_extensions')

# 2. A sensible list of the standard library that edge-tts uses or might
#    use: today's 7.3.1 uses argparse, asyncio, concurrent.futures,
#    contextlib, dataclasses, datetime, email.utils, functools, io, json,
#    logging, queue, re, secrets, shutil, ssl, struct, time, typing, uuid and
#    xml.sax.saxutils - the list has all of them plus related ones (another
#    part of the same package, another hash function, ...).
#    Whole packages, again without __main__ (asyncio.__main__ would pull in
#    the whole REPL).
_STDLIB_BALIKY = ('asyncio', 'concurrent', 'email', 'html', 'http', 'json',
                  'logging', 'urllib', 'xml')
_STDLIB_MODULY = (
    # network and encryption (WebSocket, Sec-MS-GEC token, headers)
    'ssl', 'socket', 'selectors', 'ipaddress', 'hashlib', 'hmac', 'secrets',
    'uuid', 'base64', 'binascii', 'struct', 'zlib', 'random',
    # time (clock for the token, Date header)
    'datetime', 'time', 'calendar',
    # text and SSML
    're', 'string', 'textwrap', 'unicodedata', 'codecs',
    # language and types
    'abc', 'collections', 'contextlib', 'contextvars', 'copy', 'dataclasses',
    'enum', 'functools', 'inspect', 'itertools', 'math', 'numbers',
    'operator', 'types', 'typing', 'warnings', 'weakref',
    # files, processes and the edge-tts command line
    'argparse', 'io', 'mimetypes', 'pathlib', 'platform', 'queue', 'shlex',
    'shutil', 'signal', 'subprocess', 'tempfile', 'threading', 'traceback',
    'zipfile',
    # loading the package and finding out versions
    'importlib.abc', 'importlib.machinery', 'importlib.metadata',
    'importlib.resources', 'importlib.util',
)
stdlib_hidden = list(_STDLIB_MODULY)
for _balik in _STDLIB_BALIKY:
    stdlib_hidden += collect_submodules(_balik, filter=_bez_main)
# Size: not measured (the full Analysis takes minutes). The estimate is up to
# 2 MB extra on top of dist\Zanshin\ - the sources of everything in points 1
# and 2 total ~5 MB, a large part of that (asyncio, email, http.client, json,
# logging, ssl, the aiohttp client, yarl, multidict) the build already packed
# before, and the bytecode in the PYZ is compressed. New are mainly xml,
# http.server, the server part of aiohttp and email.mime. The build takes a
# few seconds longer (the submodule list).

extra_datas = []
if os.path.isdir('assets'):
    extra_datas.append(('assets', 'assets'))
# NOTE: a development file with the App ID for Steam used to be bundled here.
# Zanshin has no Steam integration at all (0.2), so the build bundles nothing
# of the kind.

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
        # Czech and Bulgarian (0.2) - i18n.py pulls them in with an import at
        # the end of the file; PyInstaller finds it on its own too, this is a
        # safety net so the build is never left without them (without the
        # module, the i18n import at start would fail with ImportError - the
        # app would not start at all).
        'i18n_cs_bg',
    ] + comtypes_hidden + edge_hidden + certifi_hidden + ctk_hidden + numpy_hidden + pygame_hidden + psutil_hidden
      # safety net for the downloaded edge-tts - see above
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
    # .exe metadata (name, author, description, version) - without this the
    # bundled .exe shows an empty "Details" tab. See version_info.txt.
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX OFF: a compressed .exe unpacks itself in memory at start, which is
    # the signature of packed malware - Defender/SmartScreen react to it with
    # a heuristic that changes with every definitions update (so a build that
    # worked at first suddenly starts landing in quarantine without a single
    # code change). The space saving is not worth it.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # ADMIN OFF (was True). An elevated process + an overlay over the game is
    # exactly the profile that anti-cheats (Vanguard, EAC, VAC) judge most
    # strictly (see SAFETY.md).
    # The app has no global hooks - the keyboard hook from non-public versions
    # was removed before the first public alpha. That is why the installer
    # (Dandurf.iss) installs into the user profile without UAC - which also
    # removes "Error 707" during installation.
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    # UPX OFF here too - the reason is at `upx=False` in the EXE above.
    upx=False,
    name='Zanshin',
)
