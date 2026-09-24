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
  * ze data z uzivatelskych nastaveni sa normalizuju bez pada.

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

problems = []
notes = []


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8-sig") as fh:
        return fh.read()


def check(title):
    print(f"\n{'─' * 66}\n{title}\n{'─' * 66}")


# ==========================================================================
# 1. Kompilacia vsetkych modulov
# ==========================================================================

check("1. Kompilacia (syntax) vsetkych .py")
py_files = [f for f in os.listdir(HERE) if f.endswith(".py")]
for name in sorted(py_files):
    try:
        ast.parse(read(name))
        print(f"  OK   {name}")
    except SyntaxError as exc:
        problems.append(f"{name}: syntax {exc}")
        print(f"  PAD  {name}: {exc}")


# ==========================================================================
# 1b. Nedefinovane mena - kompilacia ich NEODCHYTI
# ==========================================================================
#
# Onboarding padal na NameError ('hud_paint' is not defined) hned pri
# prvom starte: modul sa pouzival, ale neimportoval. ast.parse aj pytest
# presli, lebo meno sa vyhodnocuje az za behu. pyflakes to vidi staticky.

check("1b. Nedefinovane mena (pyflakes)")
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
        problems.append(f"nedefinovane mena: {len(undefined)} (viz vypis)")
        for line in undefined[:15]:
            print(f"  PAD  {line}")
    else:
        print(f"  OK   {len(py_files)} suborov, ziadne pouzite nedefinovane meno")
except ImportError:
    notes.append("pyflakes nie je nainstalovany (pip install -r requirements-dev.txt) "
                 "- kontrola nedefinovanych mien preskocena")
    print("  POZN pyflakes chyba - preskocene (pip install pyflakes)")
except Exception as exc:
    problems.append(f"pyflakes kontrola padla: {exc}")
    print(f"  PAD  {exc}")


# ==========================================================================
# 2. Preklady - vsetkych 11 jazykov, placeholdery, dopreklad
# ==========================================================================

check("2. Preklady (vsetky jazyky)")
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
                    mismatch.append(f"{key}[{lang}]: cakane {ref}, najdene {ph(entry[lang])}")

    print(f"  klucov spolu: {len(S)}, jazyky: {', '.join(LANGS)}")
    if missing:
        problems.append(f"preklady: {len(missing)} klucov s chybajucim jazykom")
        for k, langs in list(missing.items())[:10]:
            print(f"  PAD  {k}: chyba {', '.join(langs)}")
    else:
        print(f"  OK   kazdy kluc ma vsetkych {len(LANGS)} jazykov")
    if mismatch:
        problems.append(f"preklady: {len(mismatch)} nezhodnych placeholderov")
        for m in mismatch[:10]:
            print(f"  PAD  {m}")
    else:
        print("  OK   vsetky {placeholdery} sedia napric jazykmi")
    if empty:
        problems.append(f"preklady: {len(empty)} prazdnych retazcov")
        print(f"  PAD  prazdne: {', '.join(empty[:10])}")

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
        notes.append(f"{len(todo)} retazcov caka na dopreklad do ja/zh/ru/es/de/fr/pt/cs/bg "
                     f"(zoznam v preklad_TODO.csv) - sk a en su hotove")
        print(f"  POZN {len(todo)} retazcov len anglicky (na dopreklad) - viz preklad_TODO.csv")
    else:
        print(f"  OK   vsetkych {len(LANGS)} jazykov je doprelozenych")
except Exception as exc:
    problems.append(f"preklady: modul i18n padol pri importe: {exc}")
    print(f"  PAD  {exc}")


# ==========================================================================
# 3. app.py - volane metody a tokeny existuju
# ==========================================================================

check("3. app.py - integrita volani")
try:
    src = read("app.py")
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DandurfApp")
    methods = [n.name for n in cls.body if isinstance(n, ast.FunctionDef)]
    defined = set(methods)
    called = set(re.findall(r"self\.([a-z_][a-z0-9_]*)\(", src))
    unknown = sorted(c for c in called if c not in defined)
    if unknown:
        problems.append(f"app.py vola nedefinovane metody: {unknown}")
        print(f"  PAD  volane bez definicie: {unknown}")
    else:
        print(f"  OK   {len(defined)} metod, ziadne volanie bez definicie")

    dupes = sorted({m for m in methods if methods.count(m) > 1})
    if dupes:
        problems.append(f"app.py duplicitne metody: {dupes}")
        print(f"  PAD  duplicity: {dupes}")
    else:
        print("  OK   ziadne duplicitne metody")

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
            problems.append(f"tema {key}: chybajuce tokeny {miss}")
            print(f"  PAD  tema {key}: chyba {miss}")
        else:
            print(f"  OK   tema {key}: vsetkych {len(used)} pouzitych tokenov existuje")
except Exception as exc:
    problems.append(f"app.py kontrola padla: {exc}")
    print(f"  PAD  {exc}")


# ==========================================================================
# 4. Rebind + keycap API (regresia z redizajnu)
# ==========================================================================

check("4. Rebind a keycap (regresia)")
try:
    kit = read("ui_kit.py")
    keycap = kit[kit.index("class Keycap"):]
    keycap = keycap[:keycap.index("\nclass ", 5)] if "\nclass " in keycap[5:] else keycap
    if re.search(r"def set_text\(", keycap):
        print("  OK   ui_kit.Keycap ma set_text()")
    else:
        problems.append("ui_kit.Keycap NEMA set_text() - rebind padne")
        print("  PAD  Keycap nema set_text()")

    # FAZA 3: kontroly rebindu tu boli, kym sa hlaska spustala klavesou.
    # Rebind aj obe pynput listenery su prec - jediny kus appky, ktory
    # navonok vyzeral ako keylogger. Namiesto toho sa stráži, ze sa
    # NEVRATIL. (Keycap sa zatial nemaze: stranka Spustace sa prekresluje
    # az vo faze 5 a kontrola set_text() vyssie ho drzi funkcny.)
    ap = read("app.py")
    dovoz =re.compile(r"^\s*(?:from\s+pynput|import\s+pynput)", re.M)
    # Import pynput sa hlada vo VSETKYCH .py (nie len v app.py a
    # ui_dialogs.py) a navyse v zavislostiach a v .spec - hook v inom module
    # by pre anti-cheat vyzeral rovnako.
    s_pynput = [n for n in sorted(py_files) if dovoz.search(read(n))]
    s_pynput += [n for n in sorted(os.listdir(HERE))
                 if (n.endswith(".spec") or n.startswith("requirements"))
                 and "pynput" in read(n).lower()]
    if s_pynput:
        problems.append("pynput je spat: " + ", ".join(s_pynput))
        print(f"  PAD  pynput je spat: {', '.join(s_pynput)}")
    hook_prec = (not s_pynput
                 and "keyboard.Listener(" not in ap
                 and "mouse.Listener(" not in ap
                 and "def begin_rebind(self" not in ap
                 and "def handle_trigger(self" not in ap)
    if hook_prec:
        print("  OK   klavesovy hook je prec a nevratil sa")
    else:
        problems.append("v app.py sa vratil klavesovy hook alebo rebind")
        print("  PAD  klavesovy hook alebo rebind je spat v app.py")

    rss = read("app.py")
    block = rss[rss.index("def remove_selected_slots(self"):]
    block = block[:block.index("\n    def ", 5)]
    if "slot_only_one" in block:
        print("  OK   remove_selected_slots ma poistku proti zmazaniu vsetkeho")
    else:
        problems.append("remove_selected_slots bez poistky proti prazdnu")
        print("  PAD  chyba poistka pri hromadnom mazani")
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
        problems.append("velkost pisma ako retazec: " + ", ".join(string_fonts))
        print(f"  PAD  retazcova velkost pisma: {', '.join(string_fonts)}")
    else:
        print("  OK   vsetky velkosti pisma su cisla, nie retazce")
except Exception as exc:
    problems.append(f"kontrola rebindu padla: {exc}")
    print(f"  PAD  {exc}")


# ==========================================================================
# 5. Normalizacia nastaveni - ciste moduly bez Tk
# ==========================================================================

check("5. Datova vrstva (bez Tk)")
for mod in ("settings_model", "hr_stats", "display", "hud_paint",
            "measure", "activity"):
    try:
        importlib.import_module(mod)
        print(f"  OK   import {mod}")
    except Exception as exc:
        problems.append(f"import {mod}: {exc}")
        print(f"  PAD  {mod}: {exc}")

try:
    import settings_model as sm
    # zamerne rozbite/prazdne data - normalizacia nesmie padnut
    for raw in ({}, {"mode": "nezmysel", "cooldown": "abc"}, {"key_type": "??"}, None):
        sm.normalize_slot(raw)
    for i in range(4):
        sm.normalize_overlay_config({"scale": 99, "pos_x": -50}, i)
    sm.normalize_hud_config({"opacity": "x"})
    sm.normalize_monitor_target("blabla")
    print("  OK   normalizacia zvlada prazdne aj rozbite vstupy")
except Exception as exc:
    problems.append(f"normalizacia nastaveni padla: {exc}")
    print(f"  PAD  {exc}")


# ==========================================================================
# 6. Ikona - znak 残 sa da vykreslit
# ==========================================================================

check("6. Ikona (zlate enso 残)")
try:
    import make_icon
    for px in (16, 32, 256):
        img = make_icon.render(px)
        if img.size != (px, px) or img.getchannel("A").getextrema()[1] == 0:
            problems.append(f"ikona {px}px: prazdna alebo zly rozmer")
            print(f"  PAD  {px}px prazdna/zla velkost")
        else:
            print(f"  OK   {px}px vykreslene")
    make_icon.tray_mark(64, (127, 179, 154))
    print("  OK   tray_mark (znacka do listy) vykreslena")
except Exception as exc:
    notes.append(f"ikona: {exc} - na Windows to overi az realne pismo, tu chyba CJK font")
    print(f"  POZN {exc}")


# ==========================================================================
# 7. Ziadna integracia so Steamom
# ==========================================================================
#
# Zanshin na Steam zatial nejde (rozhodnutie autora, 0.2) a Steam vrstva
# je v _archiv. Tato kontrola strazi, ze sa nevratila potichu - ani modul,
# ani jeho import, ani Steamworks binding v builde.

check("7. Ziadna integracia so Steamom")
try:
    steam_problemy = []
    if os.path.exists(os.path.join(HERE, "steam_integration.py")):
        steam_problemy.append("steam_integration.py je spat v koreni projektu")
    steam_dovoz = re.compile(r"^\s*(?:from|import)\s+(?:steam_integration|steamworks)\b",
                             re.M)
    for name in sorted(py_files):
        if steam_dovoz.search(read(name)):
            steam_problemy.append(f"{name} importuje Steam vrstvu")
    for name in sorted(f for f in os.listdir(HERE) if f.endswith(".spec")):
        if re.search(r"steam_integration|steamworks|steam_appid", read(name)):
            steam_problemy.append(f"{name} bali Steam vrstvu")
    if steam_problemy:
        problems.extend(steam_problemy)
        for p in steam_problemy:
            print(f"  PAD  {p}")
    else:
        print("  OK   ziadny Steam modul, import ani binding v builde")
except Exception as exc:
    problems.append(f"kontrola Steamu padla: {exc}")
    print(f"  PAD  {exc}")


# ==========================================================================
# Zaver
# ==========================================================================

print(f"\n{'═' * 66}")
if notes:
    print("Upozornenia (nie chyby):")
    for n in notes:
        print(f"  • {n}")
if problems:
    print(f"\n{'!' * 66}")
    print(f"NEPRESLO: {len(problems)} problemov")
    for p in problems:
        print(f"  ✗ {p}")
    print(f"{'!' * 66}")
    sys.exit(1)
else:
    print("VSETKY STRUKTURALNE KONTROLY PRESLI.")
    print("Dalej: spusti appku a pozri sa na okno aj vizualy v hre.")
    print(f"{'═' * 66}")
    sys.exit(0)
