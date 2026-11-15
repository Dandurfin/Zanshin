#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Predbezna kontrola Zanshin - spusti PRED tym, nez otvoris appku.

Na co to je
-----------
Cely redizajn (stranky Dnes/Spustace/V hre, dychajuci pas, keycapy) aj
oprava rebindu a hromadneho odstranenia slotov vznikli v prostredi BEZ
tkinter a BEZ Windows. Tento skript overi vsetko, co sa overit da bez
otvorenia okna:

  * kompilaciu vsetkych modulov,
  * uplnost a konzistenciu prekladov vo vsetkych 11 jazykoch,
  * ze appka nevola metody/tokeny, ktore neexistuju,
  * ze rebind a keycap maju spravne API (regresia z redizajnu),
  * ze data z uzivatelskych nastaveni sa normalizuju bez pada,
  * ze nainstalovany edge-tts je dost novy (starsi Microsoft odmieta).

NEotvara ziadne okno, NEsahat na siet, NEnahrava nikam. Len cita zdroj a
importuje ciste (bez GUI) moduly. Co NEvie overit: skutocne kreslenie cez
Tk/UpdateLayeredWindow, vzhlad. To ostava na rucne overenie v bezaciej
appke.

Spustenie:  python check_before_run.py
Navratovy kod 0 = vsetko preslo, 1 = nieco padlo.
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


# DandurfApp je rozdelena do mixinov v app_*.py (stav ostava na DandurfApp,
# mixiny nesu len metody). Kontroly appky preto citaju app.py aj vsetky
# app_*.py - inak by volanie metody z mixinu vyzeralo ako nedefinovane a
# kod presunuty do mixinu by sa nekontroloval vobec.

def subory_appky():
    """{meno suboru: zdrojak} pre app.py a vsetky app_*.py."""
    mena = ["app.py"] + sorted(f for f in os.listdir(HERE)
                               if f.startswith("app_") and f.endswith(".py"))
    return {meno: read(meno) for meno in mena}


def triedy_appky(subory):
    """[(subor, uzol triedy)] pre DandurfApp a vsetky jej zaklady (mixiny).

    Zaklad sa hlada ako trieda na urovni modulu v app_*.py, tak ako ju
    najde Python cez `from app_x import Mixin`. Zaklad, ktory sa nenajde,
    je chyba - jeho metody by kontrola nevidela."""
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
    """Zdrojak metody DandurfApp (aj ked byva v mixine) od `def` po koniec tela."""
    for meno, trieda in triedy_appky(subory):
        for uzol in trieda.body:
            if isinstance(uzol, ast.FunctionDef) and uzol.name == metoda:
                return ast.get_source_segment(subory[meno], uzol)
    raise LookupError(f"method {metoda} is not in DandurfApp or its mixins")


# ==========================================================================
# 1. Kompilacia vsetkych modulov
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
# 1b. Nedefinovane mena - kompilacia ich NEODCHYTI
# ==========================================================================
#
# Onboarding padal na NameError ('hud_paint' is not defined) hned pri
# prvom starte: modul sa pouzival, ale neimportoval. ast.parse aj pytest
# presli, lebo meno sa vyhodnocuje az za behu. pyflakes to vidi staticky.

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
# 2. Preklady - vsetkych 11 jazykov, placeholdery, dopreklad
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

    # Dopreklad - NIE je chyba, len upozornenie.
    #
    # Kriterium je ja/zh/ru/bg, nie de: nemecke "Timing" a "normal" su zhodou
    # okolnosti rovnake slova ako anglicke, takze porovnanie s `de` hlasilo
    # tri retazce navzdy aj po uplnom doprelozeni. Ine pismo sa s anglictinou
    # nahodou netrafi. Zamerne zhody (ja/zh „{n}%“ ako anglictina) su v
    # make_translation_todo.ZAMERNA_ZHODA - inak by tu pred kazdym spustenim
    # svietilo falosne upozornenie a skutocne by sa v nom stratilo.
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
# 3. app.py + mixiny app_*.py - volane metody a tokeny existuju
# ==========================================================================

check("3. app.py + app_*.py mixins - call integrity")
try:
    subory = subory_appky()
    src = "\n".join(subory.values())
    triedy = triedy_appky(subory)
    # Metody DandurfApp aj vsetkych jej mixinov. Meno v dvoch triedach je
    # duplicita aj napriec subormi - jedna by ticho zatienila druhu.
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

    # tokeny palety musia existovat v oboch temach
    #
    import theme as th
    combined = src + read("ui_dialogs.py") + read("ui_kit.py")
    used = set(re.findall(r'pal\["([a-z_0-9]+)"\]', combined)) \
        | set(re.findall(r'pal\.get\("([a-z_0-9]+)"', combined)) \
        | set(re.findall(r'\["([a-z_0-9]+)"\]',
                         "".join(re.findall(r'tokens\([^)]*\)(\["[a-z_0-9]+"\])', combined))))

    # `ui_shell.py` sa scanuje ZVLAST a LEN na vzor `c("kluc", "zaloha")`.
    #
    # Titulkova lista berie farby temy cez tuto pomocnu funkciu
    # (`pal.get(kluc, PAL[zaloha])`), takze bez toho by sa jej preklep v
    # nazve tokenu nedal odhalit inak nez okom. Cely subor sem ale pridat
    # NEMOZNO: `Sidebar` si stavia vlastny slovnik s vlastnymi menami
    # (`hover`, `active`, `text_2`, `text_3`), ktore NIE su tokeny temy -
    # scan cez `pal["..."]` by ich nahlasil ako chybajuce.
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
# 4. Rebind + keycap API (regresia z redizajnu)
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

    # FAZA 3: kontroly rebindu tu boli, kym sa hlaska spustala klavesou.
    # Rebind aj obe pynput listenery su prec - jediny kus appky, ktory
    # navonok vyzeral ako keylogger. Namiesto toho sa stráži, ze sa
    # NEVRATIL. (Keycap sa zatial nemaze: stranka Spustace sa prekresluje
    # az vo faze 5 a kontrola set_text() vyssie ho drzi funkcny.)
    # Cela appka: app.py aj mixiny DandurfApp v app_*.py.
    appka = subory_appky()
    ap = "\n".join(appka.values())
    dovoz =re.compile(r"^\s*(?:from\s+pynput|import\s+pynput)", re.M)
    # Import pynput sa hlada vo VSETKYCH .py (nie len v app.py a
    # ui_dialogs.py) a navyse v zavislostiach a v .spec - hook v inom module
    # by pre anti-cheat vyzeral rovnako.
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

    # metoda moze byvat v mixine (app_*.py) - hlada sa v celej DandurfApp
    block = zdroj_metody_appky(appka, "remove_selected_slots")
    if "slot_only_one" in block:
        print("  OK   remove_selected_slots has a guard against deleting everything")
    else:
        problems.append("remove_selected_slots has no guard against deleting every slot")
        print("  FAIL the guard for bulk deletion is missing")
    # Velkost pisma MUSI byt cislo. ui("11") prejde kompilaciou aj testami,
    # ale customtkinter ju pri skalovani nasobi floatom -> TypeError a cely
    # dialog sa neotvori (takto padal Sprievodca pri kazdom otvoreni).
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
# 5. Normalizacia nastaveni - ciste moduly bez Tk
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
    # zamerne rozbite/prazdne data - normalizacia nesmie padnut
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
# 6. Ikona - znak 残 sa da vykreslit
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
# 7. Ziadna integracia so Steamom
# ==========================================================================
#
# Zanshin na Steam zatial nejde (rozhodnutie autora, 0.2) a Steam vrstva
# je v _archiv. Tato kontrola strazi, ze sa nevratila potichu - ani modul,
# ani jeho import, ani Steamworks binding v builde.

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
# 8. edge-tts dost novy (prirodzeny hlas)
# ==========================================================================
#
# Microsoft od novembra 2026 odmieta starsie edge-tts (HTTP 403) - appka
# potom hovori len hlasom z Windows a v Nastaveniach -> Zvuk pise, ze
# sluzba poziadavku odmietla. build_all.ps1 edge-tts pri kazdom builde
# zdvihne na najnovsi sam (a vyskusa ho), pri behu zo zdrojakov to treba
# urobit rucne. Poziadavka je len v requirements.txt a cita sa tym istym
# vzorom ako $edgeMinVzor v build_all.ps1 (skupina 1 = cela podmienka,
# 2 = minimum). Stara verzia je len upozornenie - appka bezi aj bez
# prirodzeneho hlasu; chybajuce minimum v requirements.txt je chyba.
# Strop verzie (napr. ,<8) tam zamerne nie je - zablokoval by opravu v novej
# hlavnej verzii. build_all.ps1 ho odporuci len docasne, ked novy edge-tts
# zmeni API; preto tu len upozornenie, nech sa na jeho odstranenie nezabudne.

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
# Zaver
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
