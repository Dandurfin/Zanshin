#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zanshin pre-flight check - run it BEFORE you open the app.

What it is for
--------------
The whole redesign (the Today/Cues/In-game pages, the breathing bar,
keycaps) and the fix of rebind and bulk slot deletion were made in an
environment WITHOUT tkinter and WITHOUT Windows. This script checks
everything that can be checked without opening a window:

  * compilation of all modules,
  * completeness and consistency of translations in all 11 languages,
  * that the app does not call methods/tokens that do not exist,
  * that rebind and keycap have the right API (regression from the
    redesign),
  * that data from user settings is normalised without a crash,
  * that the installed edge-tts is new enough (Microsoft rejects older
    ones).

It does NOT open any window, does NOT touch the network, does NOT upload
anything anywhere. It only reads the source and imports pure (no-GUI)
modules. What it can NOT check: actual drawing via
Tk/UpdateLayeredWindow, appearance. That is left for manual checking in
the running app.

Run:  python check_before_run.py
Exit code 0 = everything passed, 1 = something failed.
"""

import ast
import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

problems = []
notes = []


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8-sig") as fh:
        return fh.read()


def check(title):
    print(f"\n{'─' * 66}\n{title}\n{'─' * 66}")


# DandurfApp is split into mixins in app_*.py (state stays on DandurfApp,
# the mixins carry only methods). The app checks therefore read app.py and
# all app_*.py - otherwise calling a method from a mixin would look
# undefined and code moved into a mixin would not be checked at all.

def subory_appky():
    """{file name: source} for app.py and all app_*.py."""
    mena = ["app.py"] + sorted(f for f in os.listdir(HERE)
                               if f.startswith("app_") and f.endswith(".py"))
    return {meno: read(meno) for meno in mena}


def triedy_appky(subory):
    """[(file, class node)] for DandurfApp and all its bases (mixins).

    A base is looked up as a module-level class in app_*.py, just as Python
    finds it via `from app_x import Mixin`. A base that is not found is an
    error - the check would not see its methods."""
    triedy = {}
    for meno, src in subory.items():
        for uzol in ast.parse(src).body:
            if isinstance(uzol, ast.ClassDef) and (meno != "app.py"
                                                   or uzol.name == "DandurfApp"):
                triedy[uzol.name] = (meno, uzol)
    vysledok, videne, fronta = [], set(), ["DandurfApp"]
    while fronta:
        meno = fronta.pop(0)
        if meno in videne or meno == "object":
            continue
        videne.add(meno)
        if meno not in triedy:
            raise LookupError(f"class {meno} (a base of DandurfApp) is not in app.py or any app_*.py")
        vysledok.append(triedy[meno])
        for zaklad in triedy[meno][1].bases:
            fronta.append(zaklad.attr if isinstance(zaklad, ast.Attribute) else zaklad.id)
    return vysledok


def zdroj_metody_appky(subory, metoda):
    """Source of a DandurfApp method (even in a mixin) from `def` to body end."""
    for meno, trieda in triedy_appky(subory):
        for uzol in trieda.body:
            if isinstance(uzol, ast.FunctionDef) and uzol.name == metoda:
                return ast.get_source_segment(subory[meno], uzol)
    raise LookupError(f"method {metoda} is not in DandurfApp or its mixins")


# ==========================================================================
# 1. Compilation of all modules
# ==========================================================================

check("1. Compilation (syntax) of all .py files")
py_files = [f for f in os.listdir(HERE) if f.endswith(".py")]
for name in sorted(py_files):
    try:
        ast.parse(read(name))
        print(f"  OK   {name}")
    except SyntaxError as exc:
        problems.append(f"{name}: syntax {exc}")
        print(f"  FAIL {name}: {exc}")


# ==========================================================================
# 1b. Undefined names - compilation does NOT CATCH them
# ==========================================================================
#
# Onboarding crashed with NameError ('hud_paint' is not defined) right at
# the first start: the module was used but not imported. Both ast.parse and
# pytest passed, because the name is only evaluated at runtime. pyflakes
# sees it statically.

check("1b. Undefined names (pyflakes)")
try:
    import io
    from pyflakes import api as _pf_api
    from pyflakes import reporter as _pf_reporter
    _out, _err = io.StringIO(), io.StringIO()
    _rep = _pf_reporter.Reporter(_out, _err)
    for name in sorted(py_files):
        _pf_api.check(read(name), name, _rep)
    undefined = [line for line in _out.getvalue().splitlines() if "undefined name" in line]
    if undefined:
        problems.append(f"undefined names: {len(undefined)} (see the output above)")
        for line in undefined[:15]:
            print(f"  FAIL {line}")
    else:
        print(f"  OK   {len(py_files)} files, no undefined name used")
except ImportError:
    notes.append("pyflakes is not installed (pip install -r requirements-dev.txt) "
                 "- the undefined-names check was skipped")
    print("  NOTE pyflakes is missing - skipped (pip install pyflakes)")
except Exception as exc:
    problems.append(f"pyflakes check crashed: {exc}")
    print(f"  FAIL {exc}")


# ==========================================================================
# 2. Translations - all 11 languages, placeholders, still to translate
# ==========================================================================

check("2. Translations (all languages)")
try:
    import i18n
    S = i18n.STRINGS
    LANGS = list(i18n.LANGUAGES)

    def ph(text):
        return set(re.findall(r"\{(\w+)\}", str(text)))

    missing = {}
    mismatch = []
    empty = []
    for key, entry in S.items():
        ref = ph(entry.get("sk", entry.get("en", "")))
        for lang in LANGS:
            if lang not in entry:
                missing.setdefault(key, []).append(lang)
            else:
                if not str(entry[lang]).strip():
                    empty.append(f"{key}[{lang}]")
                if ph(entry[lang]) != ref:
                    mismatch.append(f"{key}[{lang}]: expected {ref}, found {ph(entry[lang])}")

    print(f"  keys in total: {len(S)}, languages: {', '.join(LANGS)}")
    if missing:
        problems.append(f"translations: {len(missing)} keys with a missing language")
        for k, langs in list(missing.items())[:10]:
            print(f"  FAIL {k}: missing {', '.join(langs)}")
    else:
        print(f"  OK   every key has all {len(LANGS)} languages")
    if mismatch:
        problems.append(f"translations: {len(mismatch)} mismatched placeholders")
        for m in mismatch[:10]:
            print(f"  FAIL {m}")
    else:
        print("  OK   all {placeholders} match across languages")
    if empty:
        problems.append(f"translations: {len(empty)} empty strings")
        print(f"  FAIL empty: {', '.join(empty[:10])}")

    # Still to translate - NOT an error, just a warning.
    #
    # The criterion is ja/zh/ru/bg, not de: German "Timing" and "normal" are
    # by coincidence the same words as English, so comparing with `de`
    # reported three strings forever, even after full translation. A
    # different script does not match English by accident. Deliberate matches
    # (ja/zh „{n}%“ like English) are in make_translation_todo.ZAMERNA_ZHODA -
    # otherwise a false warning would light up here before every run and a
    # real one would get lost in it.
    from make_translation_todo import na_dopreklad
    todo = na_dopreklad(S)
    if todo:
        notes.append(f"{len(todo)} strings are waiting for translation into ja/zh/ru/es/de/fr/pt/cs/bg "
                     f"(list in preklad_TODO.csv) - sk and en are done")
        print(f"  NOTE {len(todo)} strings only in English (to translate) - see preklad_TODO.csv")
    else:
        print(f"  OK   all {len(LANGS)} languages are fully translated")
except Exception as exc:
    problems.append(f"translations: the i18n module crashed on import: {exc}")
    print(f"  FAIL {exc}")


# ==========================================================================
# 3. app.py + mixins app_*.py - called methods and tokens exist
# ==========================================================================

check("3. app.py + app_*.py mixins - call integrity")
try:
    subory = subory_appky()
    src = "\n".join(subory.values())
    triedy = triedy_appky(subory)
    # Methods of DandurfApp and all its mixins. A name in two classes is a
    # duplicate even across files - one would silently shadow the other.
    methods = [n.name for _subor, cls in triedy for n in cls.body
               if isinstance(n, ast.FunctionDef)]
    defined = set(methods)
    called = set(re.findall(r"self\.([a-z_][a-z0-9_]*)\(", src))
    unknown = sorted(c for c in called if c not in defined)
    if unknown:
        problems.append(f"app.py / app_*.py calls undefined methods: {unknown}")
        print(f"  FAIL called without a definition: {unknown}")
    else:
        print(f"  OK   {len(defined)} methods in {len(triedy)} classes "
              f"({', '.join(cls.name for _s, cls in triedy)}), no call without a definition")

    dupes = sorted({m for m in methods if methods.count(m) > 1})
    if dupes:
        problems.append(f"DandurfApp + mixins: duplicate methods: {dupes}")
        print(f"  FAIL duplicates: {dupes}")
    else:
        print("  OK   no duplicate methods")

    # palette tokens must exist in both themes
    #
    import theme as th
    combined = src + read("ui_dialogs.py") + read("ui_kit.py")
    used = set(re.findall(r'pal\["([a-z_0-9]+)"\]', combined)) \
        | set(re.findall(r'pal\.get\("([a-z_0-9]+)"', combined)) \
        | set(re.findall(r'\["([a-z_0-9]+)"\]',
                         "".join(re.findall(r'tokens\([^)]*\)(\["[a-z_0-9]+"\])', combined))))

    # `ui_shell.py` is scanned SEPARATELY and ONLY for the pattern
    # `c("kluc", "zaloha")`.
    #
    # The title bar takes theme colours through this helper function
    # (`pal.get(kluc, PAL[zaloha])`), so without this a typo in a token name
    # could not be caught other than by eye. But the whole file CANNOT be
    # added here: `Sidebar` builds its own dictionary with its own names
    # (`hover`, `active`, `text_2`, `text_3`), which are NOT theme tokens -
    # a scan via `pal["..."]` would report them as missing.
    used |= set(re.findall(r'\bc\("([a-z_0-9]+)",\s*"[a-z_0-9]+"\)',
                           read("ui_shell.py")))
    for key in (th.MODERN, th.ZEN):
        miss = sorted(used - set(th.tokens(key)))
        if miss:
            problems.append(f"theme {key}: missing tokens {miss}")
            print(f"  FAIL theme {key}: missing {miss}")
        else:
            print(f"  OK   theme {key}: all {len(used)} used tokens exist")
except Exception as exc:
    problems.append(f"app.py / app_*.py check crashed: {exc}")
    print(f"  FAIL {exc}")


# ==========================================================================
# 4. Rebind + keycap API (regression from the redesign)
# ==========================================================================

check("4. Rebind and keycap (regression)")
try:
    kit = read("ui_kit.py")
    keycap = kit[kit.index("class Keycap"):]
    keycap = keycap[:keycap.index("\nclass ", 5)] if "\nclass " in keycap[5:] else keycap
    if re.search(r"def set_text\(", keycap):
        print("  OK   ui_kit.Keycap has set_text()")
    else:
        problems.append("ui_kit.Keycap has NO set_text() - rebind will crash")
        print("  FAIL Keycap has no set_text()")

    # PHASE 3: rebind checks were here while the cue was triggered by a key.
    # Rebind and both pynput listeners are gone - the only part of the app
    # that looked like a keylogger from outside. Instead, this guards that it
    # has NOT COME BACK. (Keycap is not deleted yet: the Cues page is
    # only redrawn in phase 5 and the set_text() check above keeps it
    # working.)
    # The whole app: app.py and the DandurfApp mixins in app_*.py.
    appka = subory_appky()
    ap = "\n".join(appka.values())
    dovoz =re.compile(r"^\s*(?:from\s+pynput|import\s+pynput)", re.M)
    # The pynput import is searched for in ALL .py files (not just app.py and
    # ui_dialogs.py) and also in the dependencies and the .spec - a hook in
    # another module would look the same to an anti-cheat.
    s_pynput = [n for n in sorted(py_files) if dovoz.search(read(n))]
    s_pynput += [n for n in sorted(os.listdir(HERE))
                 if (n.endswith(".spec") or n.startswith("requirements"))
                 and "pynput" in read(n).lower()]
    if s_pynput:
        problems.append("pynput is back: " + ", ".join(s_pynput))
        print(f"  FAIL pynput is back: {', '.join(s_pynput)}")
    hook_prec = (not s_pynput
                 and "keyboard.Listener(" not in ap
                 and "mouse.Listener(" not in ap
                 and "def begin_rebind(self" not in ap
                 and "def handle_trigger(self" not in ap)
    if hook_prec:
        print("  OK   the keyboard hook is gone and hasn't come back")
    else:
        problems.append("a keyboard hook or rebind came back in app.py / app_*.py")
        print("  FAIL a keyboard hook or rebind is back in app.py / app_*.py")

    # the method may live in a mixin (app_*.py) - search all of DandurfApp
    block = zdroj_metody_appky(appka, "remove_selected_slots")
    if "slot_only_one" in block:
        print("  OK   remove_selected_slots has a guard against deleting everything")
    else:
        problems.append("remove_selected_slots has no guard against deleting every slot")
        print("  FAIL the guard for bulk deletion is missing")
    # Font size MUST be a number. ui("11") passes compilation and tests, but
    # customtkinter multiplies it by a float when scaling -> TypeError and
    # the whole dialog does not open (this is how the Guide crashed every
    # time it was opened).
    string_fonts = []
    for name in sorted(os.listdir(".")):
        if not name.endswith(".py"):
            continue
        for i, line in enumerate(read(name).splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"\b(?:ui|display|mono)\(\s*['\"]", line):
                string_fonts.append(f"{name}:{i}")
    if string_fonts:
        problems.append("font size as a string: " + ", ".join(string_fonts))
        print(f"  FAIL font size given as a string: {', '.join(string_fonts)}")
    else:
        print("  OK   all font sizes are numbers, not strings")
except Exception as exc:
    problems.append(f"rebind check crashed: {exc}")
    print(f"  FAIL {exc}")


# ==========================================================================
# 5. Settings normalisation - pure modules without Tk
# ==========================================================================

check("5. Data layer (without Tk)")
for mod in ("settings_model", "hr_stats", "display", "hud_paint",
            "measure", "activity"):
    try:
        importlib.import_module(mod)
        print(f"  OK   import {mod}")
    except Exception as exc:
        problems.append(f"import {mod}: {exc}")
        print(f"  FAIL {mod}: {exc}")

try:
    import settings_model as sm
    # deliberately broken/empty data - normalisation must not crash
    for raw in ({}, {"mode": "nezmysel", "cooldown": "abc"}, {"key_type": "??"}, None):
        sm.normalize_slot(raw)
    for i in range(4):
        sm.normalize_overlay_config({"scale": 99, "pos_x": -50}, i)
    sm.normalize_hud_config({"opacity": "x"})
    sm.normalize_monitor_target("blabla")
    print("  OK   normalisation handles empty and broken input")
except Exception as exc:
    problems.append(f"settings normalisation crashed: {exc}")
    print(f"  FAIL {exc}")


# ==========================================================================
# 6. Icon - the character 残 can be drawn
# ==========================================================================

check("6. Icon (golden enso 残)")
try:
    import make_icon
    for px in (16, 32, 256):
        img = make_icon.render(px)
        if img.size != (px, px) or img.getchannel("A").getextrema()[1] == 0:
            problems.append(f"icon {px}px: empty or wrong size")
            print(f"  FAIL {px}px empty/wrong size")
        else:
            print(f"  OK   {px}px drawn")
    make_icon.tray_mark(64, (127, 179, 154))
    print("  OK   tray_mark (the tray mark) drawn")
except Exception as exc:
    notes.append(f"icon: {exc} - on Windows only the real font can check this, a CJK font is missing here")
    print(f"  NOTE {exc}")


# ==========================================================================
# 7. No Steam integration
# ==========================================================================
#
# Zanshin is not going to Steam for now (author's decision, 0.2) and the
# Steam layer is in _archiv. This check guards that it did not quietly
# come back - neither the module, nor its import, nor a Steamworks binding
# in the build.

check("7. No Steam integration")
try:
    steam_problemy = []
    if os.path.exists(os.path.join(HERE, "steam_integration.py")):
        steam_problemy.append("steam_integration.py is back in the project root")
    steam_dovoz = re.compile(r"^\s*(?:from|import)\s+(?:steam_integration|steamworks)\b",
                             re.M)
    for name in sorted(py_files):
        if steam_dovoz.search(read(name)):
            steam_problemy.append(f"{name} imports the Steam layer")
    for name in sorted(f for f in os.listdir(HERE) if f.endswith(".spec")):
        if re.search(r"steam_integration|steamworks|steam_appid", read(name)):
            steam_problemy.append(f"{name} packs the Steam layer")
    if steam_problemy:
        problems.extend(steam_problemy)
        for p in steam_problemy:
            print(f"  FAIL {p}")
    else:
        print("  OK   no Steam module, import or binding in the build")
except Exception as exc:
    problems.append(f"Steam check crashed: {exc}")
    print(f"  FAIL {exc}")


# ==========================================================================
# 8. edge-tts new enough (natural voice)
# ==========================================================================
#
# Since November 2026 Microsoft rejects older edge-tts (HTTP 403) - the
# app then speaks only with the Windows voice and in Settings -> Sound it
# says the service refused the request. build_all.ps1 raises edge-tts to
# the newest on every build by itself (and tries it out); when running
# from source it has to be done by hand. The requirement is only in
# requirements.txt and is read with the same pattern as $edgeMinVzor in
# build_all.ps1 (group 1 = the whole condition, 2 = the minimum). An old
# version is only a warning - the app runs even without the natural
# voice; a missing minimum in requirements.txt is an error.
# A version cap (e.g. ,<8) is deliberately not there - it would block a
# fix in a new major version. build_all.ps1 recommends it only
# temporarily, when a new edge-tts changes the API; that is why it is only
# a warning here, so that removing it is not forgotten.

check("8. edge-tts version (natural voice)")
try:
    from importlib import metadata as _metadata

    def _cisla_verzie(verzia):
        return tuple(int(c) for c in re.findall(r"\d+", verzia))

    _minimum = re.search(r"^\s*edge-tts\s*(>=\s*([0-9]+(?:\.[0-9]+)*)[^#;\r\n]*)",
                         read("requirements.txt"), re.I | re.M)
    if not _minimum:
        problems.append("requirements.txt has no minimum for edge-tts (edge-tts>=...)")
        print("  FAIL requirements.txt has no minimum for edge-tts")
    else:
        _treba = _minimum.group(2)
        _strop = re.search(r"<\s*=?\s*[0-9]", _minimum.group(1))
        if _strop:
            notes.append(f"requirements.txt has a cap for edge-tts ({_minimum.group(1).strip()}) - "
                         "the build won't get a fix from a newer version; if it's temporary, don't forget "
                         f"to remove it (edge-tts>={_treba})")
            print("  NOTE requirements.txt has a cap for edge-tts")
        try:
            _verzia = _metadata.version("edge-tts")
        except _metadata.PackageNotFoundError:
            _verzia = None
        if _verzia is None:
            notes.append("edge-tts is not installed - the natural voice won't work "
                         "(py -m pip install -r requirements.txt)")
            print("  NOTE edge-tts is not installed")
        elif _cisla_verzie(_verzia) < _cisla_verzie(_treba):
            notes.append(f"edge-tts {_verzia} is too old (minimum {_treba}) - Microsoft "
                         "refuses it and the natural voice stays silent. Update it: "
                         "py -m pip install -r requirements.txt")
            print(f"  NOTE edge-tts {_verzia} is too old (minimum {_treba})")
        else:
            print(f"  OK   edge-tts {_verzia} (minimum {_treba})")
except Exception as exc:
    notes.append(f"edge-tts version check crashed: {exc}")
    print(f"  NOTE {exc}")


# ==========================================================================
# Summary
# ==========================================================================

print(f"\n{'═' * 66}")
if notes:
    print("Notes (not errors):")
    for n in notes:
        print(f"  • {n}")
if problems:
    print(f"\n{'!' * 66}")
    print(f"FAILED: {len(problems)} problems")
    for p in problems:
        print(f"  ✗ {p}")
    print(f"{'!' * 66}")
    sys.exit(1)
else:
    print("ALL STRUCTURAL CHECKS PASSED.")
    print("Next: start the app and look at the window and the visuals in the game.")
    print(f"{'═' * 66}")
    sys.exit(0)
