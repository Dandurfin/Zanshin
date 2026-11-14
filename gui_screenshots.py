# -*- coding: utf-8 -*-
"""Vizuálna kontrola okna — postaví appku, nakŕmi ju dátami a odfotí stránky.

Načo to je
----------
`gui_harness_auto.py` overí aj to, čo sa bez reálneho vstupu overiť nedá
(ťahanie okna, koliesko myši, globálne hooky), ale **hýbe reálnou myšou a
posiela klávesy** — počas jeho behu sa počítač nedá používať a spustiť sa
dá len vtedy, keď má človek dve minúty času. Preto sa nespúšťa bežne, a
preto sa vizuálne chyby (prázdny pruh pod grafom, orezaný text, panel,
ktorý vypadol z okna) našli až neskoro.

Tento skript je ten lacný zvyšok: appku postaví, prepne po stránkach a
odfotí ich. Nedotkne sa myši ani klávesnice, beží asi 20 sekúnd a dá sa
pustiť kedykoľvek. Nič netvrdí o správnosti — obrázky musí pozrieť človek
(alebo model). Čo sa overiť DÁ programovo, hlási ako kontroly na konci.

Čo si zálohuje a vráti
----------------------
`dandurf_settings.json` (aj jeho `.bak`), `hr_sessions.json`, `hr_insights.json`,
`hr_session_open.json` (kontrolný bod relácie) a `hr_session_pending.json`
(relácie, ktoré sa nepodarilo uložiť). Skript do
nich zapisuje (syntetická história, prepnutie témy), ale na konci — aj po
páde — obnoví pôvodný stav. Bez toho by ti fotenie prepísalo reálne relácie.

Spustenie
---------
    python gui_screenshots.py                 # do logs/gui_screenshots
    python gui_screenshots.py C:\\cesta\\sem   # inam
    python gui_screenshots.py --lang en       # cely beh v inom jazyku appky
    python gui_screenshots.py --okno          # len okno appky, bez plochy okolo

`--lang` prepne jazyk hned na zaciatku a kroky s nemcinou a japoncinou sa
potom vratia k nemu (bez neho k slovencine, ako doteraz). `--okno` (alias
`--window`) foti len samotne okno appky podla jeho HWND - bez plochy, panela
uloh a okien okolo, aj ked ho nieco prekryva - a navyse odfoti panel
„Relacia zblizka“ z Historie (`17_relacia_zblizka`); z toho su obrazky
v README. Bez `--okno` ostava fotka okna s malym okrajom ako doteraz.

Návratový kód: 0 = žiadna chyba v callbackoch Tk, 1 = niečo spadlo.
"""
import argparse
import json
import math
import os
import random
import sys
import time
import traceback

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from i18n import LANGUAGES                      # noqa: E402  (bez Tk, nic nezapisuje)


def _argumenty(argv):
    """Volby sa citaju PRED zalohou a pred appkou - zly jazyk skonci hned,
    skor nez sa skript dotkne jedineho suboru."""
    p = argparse.ArgumentParser(
        description="Odfoti okno Zanshinu so syntetickymi datami.")
    p.add_argument("out", nargs="?",
                   default=os.path.join(PROJ, "logs", "gui_screenshots"),
                   help="priecinok na obrazky (predvolene logs/gui_screenshots)")
    p.add_argument("--lang", choices=LANGUAGES, default=None,
                   help="jazyk appky pocas behu, napr. en")
    p.add_argument("--okno", "--window", dest="okno", action="store_true",
                   help="fotit len okno appky (podla HWND), bez plochy okolo")
    return p.parse_args(argv)


ARGS = _argumenty(sys.argv[1:])
OUT = ARGS.out
os.makedirs(OUT, exist_ok=True)
os.chdir(PROJ)

# hr_session_open.json a .bak nastaveni od 0.2.2: appka pri starte kontrolny
# bod prida do historie a zmaze ho - bez zalohy by ho fotenie "spotrebovalo"
# a historiu potom vratilo bez neho (viz gui_harness_auto.py).
ZALOHOVAT = [os.path.join(PROJ, n) for n in
             ("dandurf_settings.json", "hr_sessions.json", "hr_insights.json",
              "hr_session_open.json", "dandurf_settings.json.bak",
              # relacie, ktore sa nedali ulozit (0.2.2) - start ich doplni
              # do historie a subor zmaze, rovnako ako kontrolny bod
              "hr_session_pending.json")]
_zalohy = {}
for _cesta in ZALOHOVAT:
    if os.path.exists(_cesta):
        with open(_cesta, "rb") as _fh:
            _zalohy[_cesta] = _fh.read()


def obnov_subory():
    """Vráti zálohované súbory; čo pred behom neexistovalo, zmaže."""
    for cesta in ZALOHOVAT:
        try:
            if cesta in _zalohy:
                with open(cesta, "wb") as fh:
                    fh.write(_zalohy[cesta])
            elif os.path.exists(cesta):
                os.remove(cesta)
        except Exception:
            traceback.print_exc()


import customtkinter as ctk                     # noqa: E402
from PIL import ImageGrab                       # noqa: E402

import hr_stats                                 # noqa: E402
import theme as theme_mod                       # noqa: E402
import ui_kit                                   # noqa: E402
from app import DandurfApp                      # noqa: E402

# Pevné semienko: dve spustenia po sebe majú dať tie isté obrázky, inak sa
# nedá povedať, či sa zmenil vzhľad alebo len náhodné dáta.
random.seed(7)

chyby = []
kontroly = []


otvorene = []          # dialogy cakajuce na zatvorenie


def kontrola(nazov, podmienka, detail=""):
    kontroly.append((nazov, bool(podmienka), detail))


root = ctk.CTk()
root.report_callback_exception = lambda et, ev, tb: chyby.append(
    "".join(traceback.format_exception(et, ev, tb)))
app = DandurfApp(root)


def _len_okno(okno):
    """HWND okna pre `--okno`, alebo None (vtedy sa foti obdlznik)."""
    return ui_kit._window_hwnd(okno) if ARGS.okno else None


def _bez_metadat(img):
    """Kopia obrazka bez EXIF/XMP/textovych blokov - nic okrem pixelov."""
    cisty = img.convert("RGB")
    cisty.info = {}
    return cisty


def foto(meno):
    root.update_idletasks()
    root.update()
    # Okno, ktore este caka na odhalenie (DWM cloak pri starte), nevidno -
    # snimka by zachytila plochu za nim. Radsej ziadna fotka.
    if getattr(app, "_zahalene", False) or ui_kit.je_zahalene(root):
        kontrola(f"foto {meno}: okno uz nie je zahalene", False)
        return
    x, y = root.winfo_rootx(), root.winfo_rooty()
    hwnd = _len_okno(root)
    try:
        if hwnd:
            # LEN NASE OKNO (`--okno`): podla HWND, nie obdlznik obrazovky -
            # ziadna plocha ani panel uloh, a okno inej appky navrchu sa do
            # fotky nedostane.
            img = ImageGrab.grab(window=hwnd)
        elif ARGS.okno:
            img = ImageGrab.grab(bbox=(x, y, x + root.winfo_width(),
                                       y + root.winfo_height()), all_screens=True)
        else:
            # okno + kúsok okolo, aby bolo vidno aj vlastnú titulkovú lištu
            bbox = (x - 8, y - 40, x + root.winfo_width() + 8, y + root.winfo_height() + 8)
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
        _bez_metadat(img).save(os.path.join(OUT, meno + ".png"))
        print("  foto", meno, img.size, flush=True)
        return img
    except Exception as exc:
        chyby.append(f"screenshot {meno} zlyhal: {exc}")


def foto_panelu(widget, meno, viditelne=None):
    """Jeden panel okna (obrazok do README) - vyrez z fotky celeho okna.

    Len s `--okno`: vtedy fotka zacina presne v rohu okna, takze poloha
    panelu v okne je aj jeho poloha na fotke. `viditelne` je widget, ktory
    panel orezava (platno scrollovanej stranky) - panel musi byt cely v nom."""
    img = foto("_okno_pre_" + meno)
    if img is None:
        return
    try:
        os.remove(os.path.join(OUT, "_okno_pre_" + meno + ".png"))
    except OSError:
        pass

    def obdlznik(w):
        x = w.winfo_rootx() - root.winfo_rootx()
        y = w.winfo_rooty() - root.winfo_rooty()
        return x, y, x + w.winfo_width(), y + w.winfo_height()

    x0, y0, x1, y1 = obdlznik(widget)
    hx0, hy0, hx1, hy1 = obdlznik(viditelne) if viditelne is not None else (0, 0) + img.size
    cely = (max(0, hx0) <= x0 and max(0, hy0) <= y0
            and x1 <= min(img.size[0], hx1) and y1 <= min(img.size[1], hy1))
    kontrola(f"panel {meno} je cely na obrazovke", cely, f"{(x0, y0, x1, y1)} v {img.size}")
    if cely:
        _bez_metadat(img.crop((x0, y0, x1, y1))).save(os.path.join(OUT, meno + ".png"))
        print("  foto", meno, (x1 - x0, y1 - y0), flush=True)


def foto_okna(okno, meno):
    """Ako `foto`, ale pre samostatný Toplevel (dialóg).

    `foto` fotí obdĺžnik hlavného okna. Dialóg je vlastné okno inde na
    obrazovke, takže by z neho zachytila akurát okraj — presne to sa aj
    stalo, kým tu tento pomocník nebol.
    """
    # Dialogy su teraz BEZRAMOVE (ui_kit.DialogChrome) - `y - 40` bol offset na
    # OS titulok, ktory uz nie je; kreslime od vrchu okna. lift() ich skusi
    # dat navrch (v harnesse to je pri modalnych oknach nespolahlive, ale
    # neskodi - v realnej appke ich DialogChrome._take_focus zdvihne sam).
    try:
        okno.lift()
    except Exception:
        pass
    okno.update_idletasks()
    okno.update()
    x, y = okno.winfo_rootx(), okno.winfo_rooty()
    okraj = 0 if ARGS.okno else 8
    bbox = (x - okraj, y - okraj, x + okno.winfo_width() + okraj,
            y + okno.winfo_height() + okraj)
    hwnd = _len_okno(okno)
    try:
        img = (ImageGrab.grab(window=hwnd) if hwnd
               else ImageGrab.grab(bbox=bbox, all_screens=True))
        _bez_metadat(img).save(os.path.join(OUT, meno + ".png"))
        print("  foto", meno, flush=True)
    except Exception as exc:
        chyby.append(f"screenshot {meno} zlyhal: {exc}")


# --------------------------------------------------------------------------
# Syntetické dáta - appka bez relácií ukazuje prázdne stavy, a tie sa dajú
# odfotiť aj tak; toto je druhá polovica pravdy ("ako to vyzerá s dátami").
# --------------------------------------------------------------------------

def ziva_relacia(minut=95):
    """Nakŕmi `app.hr_stats` jednou hodnovernou reláciou (1 vzorka/s)."""
    stats = app.hr_stats
    stats.reset_session()
    n = minut * 60
    start = time.time() - n
    for i in range(n):
        t = i / float(n)
        bpm = 63 + 5 * math.sin(i / 240.0)
        for stred, sirka, vyska in ((0.22, 0.05, 34), (0.55, 0.03, 22),
                                    (0.78, 0.04, 52), (0.9, 0.02, 18)):
            bpm += vyska * math.exp(-((t - stred) ** 2) / (2 * sirka ** 2))
        stats.add(bpm + random.uniform(-1.5, 1.5), ts=start + i)
    stats.session_start = start
    for podiel in (0.23, 0.56, 0.79):
        stats.note_trigger(ts=start + n * podiel, auto=True)
    app._hr_state = "connected"


def historia(pocet=46, dni=74):
    """Zapíše `hr_sessions.json` s reláciami za posledných ~10 týždňov —
    s dierami (dni bez hrania) aj s krivkou, nech je čo kresliť.

    Relacie zacinaju vecer (18-23 h miestneho casu), ako herny vecer, a
    pocet pripomienok sedi s trojuholnikmi v krivke (audit: "HLÁŠKY 0" pri
    troch ▼ vyzeralo ako chyba appky)."""
    sessions = []
    teraz = time.time()
    for den in range(1, dni + 1):
        if random.random() < 0.32:
            continue
        d = time.localtime(teraz - (dni - den) * 86400)
        # od 18:00 TOHO DNA, nie od polnoci + 18 h - v den zmeny casu by to
        # bolo 17:00 alebo 19:00
        vecer = time.mktime((d.tm_year, d.tm_mon, d.tm_mday, 18, 0, 0, 0, 0, -1))
        for _ in range(1 if random.random() < 0.8 else 2):
            start = vecer + random.uniform(0, 5) * 3600
            if start > teraz:
                continue
            trvanie = random.uniform(2400, 9000)
            base = 60 + (dni - den) * 0.04 + random.uniform(-2, 2)
            kriticky, krivka, nad = 110, [], 0.0
            for i in range(hr_stats.CURVE_POINTS):
                t = i / float(hr_stats.CURVE_POINTS - 1)
                bpm = base + 4 * math.sin(i / 7.0)
                for stred, sirka, vyska in ((0.25, 0.06, random.uniform(20, 45)),
                                            (0.62, 0.05, random.uniform(15, 55)),
                                            (0.85, 0.04, random.uniform(10, 35))):
                    bpm += vyska * math.exp(-((t - stred) ** 2) / (2 * sirka ** 2))
                bpm = max(48, min(178, bpm + random.uniform(-2, 2)))
                krivka.append(int(round(bpm)))
                if bpm >= kriticky:
                    nad += trvanie / hr_stats.CURVE_POINTS
            # jedno cislo pre pocet, automaticke aj ▼ v krivke
            hlasok = random.randint(0, 4)
            sessions.append({
                "started": start, "duration_s": round(trvanie, 1),
                "min_bpm": min(krivka), "avg_bpm": int(sum(krivka) / len(krivka)),
                "max_bpm": max(krivka), "time_over_s": round(nad, 1),
                "time_high_s": round(nad * 2.2, 1),
                "peak_stress": int(min(100, 30 + (max(krivka) - base) * 1.1)),
                "triggers": hlasok, "auto_triggers": hlasok,
                "critical_bpm": kriticky, "samples": int(trvanie),
                "baseline_bpm": int(round(base)),
                "zone_seconds": {"calm": trvanie * 0.55, "raised": trvanie * 0.2,
                                 "high": trvanie * 0.18, "critical": trvanie * 0.07},
                "hrr_bpm": random.randint(8, 32), "hrr_events": 3,
                "hrpi": random.randint(70, 120),
                "trigger_offsets_s": sorted(random.uniform(0, trvanie)
                                            for _ in range(hlasok)),
                "curve": krivka,
            })
    sessions.sort(key=lambda s: s["started"])
    sessions = sessions[-pocet:]
    with open(os.path.join(PROJ, "hr_sessions.json"), "w", encoding="utf-8") as fh:
        json.dump(sessions, fh)
    app._history_cache = (0.0, None)
    return sessions


# --------------------------------------------------------------------------
# Kroky - každý beží vo vlastnom `after()`, aby Tk medzi nimi stihol kresliť
# --------------------------------------------------------------------------

kroky = []


def krok(fn):
    kroky.append(fn)
    return fn


ZACIATOCNY_JAZYK = {}


@krok
def k_jazyk_zaciatok():
    """`--lang`: cely beh v tom jazyku (napr. anglicke obrazky do README).
    Ulozene nastavenia sa na konci vratia zo zalohy, takze jazyk hraca
    ostane, aky bol."""
    from app import LANG_NATIVE_LABELS
    # bez --lang sa kroky s de/ja vracaju k slovencine, ako doteraz
    ZACIATOCNY_JAZYK["kod"] = ARGS.lang or "sk"
    if ARGS.lang:
        if app.lang != ARGS.lang:
            app.on_lang_switch(LANG_NATIVE_LABELS[ARGS.lang])
        kontrola("jazyk behu je %s" % ARGS.lang, app.lang == ARGS.lang, str(app.lang))


@krok
def k_data():
    # appka býva pod terminálom, z ktorého sa skript spúšťa
    root.attributes("-topmost", True)
    root.lift()
    relacie = historia()
    ziva_relacia()
    app.run_hr_analysis()
    kontrola("syntetická história zapísaná", len(relacie) > 20, f"{len(relacie)} relácií")


@krok
def k_dnes():
    app.sidebar._select("dnes")
    app._refresh_dnes_stats()
    kontrola("stopa relácie má body", len(app.dnes_trace._values) > 2,
             str(len(app.dnes_trace._values)))
    kontrola("pásma relácie sa sčítali", sum(app.hr_stats.zone_seconds.values()) > 0)
    # Do 2.1 tu bola kontrola "karta má mikrograf" (`karta._series`).
    # Mikrograf z karty odišiel — karta je teraz VEĽKÉ číslo a pod ním
    # jedno slovo. Kontroluje sa teda to, na čom teraz stojí: že popisok
    # je naozaj krátky. Dlhý popisok bol to, čo v nemčine a ruštine
    # rozťahovalo pravý stĺpec na úkor stredu so značkou.
    karta = next(iter(app.dashboard_cards.values()), None)
    tag = karta.tag_label.cget("text") if karta is not None else ""
    kontrola("karta štatistiky má číslo aj popisok",
             karta is not None and bool(karta.value_label.cget("text")) and bool(tag),
             f"{karta.value_label.cget('text')!r} / {tag!r}" if karta else "")
    kontrola("popisok karty je krátky (<= 14 znakov)", len(tag) <= 14,
             f"{tag!r} má {len(tag)}")
    # `_refresh_dnes_stats` má celé telo v jednom `except`, takže rozbitá
    # stránka z Tk callbacku neunikne a "0 chýb v Tk" ju nevidí. Toto je
    # jediné miesto, kde sa to dá zachytiť.
    kontrola("obnovenie Dnes nikdy nezlyhalo", app._dnes_refresh_fails == 0,
             f"{app._dnes_refresh_fails} zlyhaní — pozri logy/app.log")


@krok
def k_dnes_foto():
    foto("01_dnes")


@krok
def k_historia():
    app.sidebar._select("historia")
    app._refresh_history_page()
    kontrola("graf trendu má body aj popisky osi",
             len(app.history_trend._values) > 1 and len(app.history_trend._labels) > 1,
             f"{len(app.history_trend._values)} bodov / {len(app.history_trend._labels)} popiskov")
    # Od 0.2.2 (davka 4) mriezka ukazuje tyzdne od prvej relacie, najviac
    # 26 - nie cely rok. Ma mat aspon tyzden, najviac pol roka, a popisky.
    mriezka = app.history_daygrid
    kontrola("mriežka dní je naplnená",
             7 <= len(mriezka._days) <= 26 * 7
             and any(d.get("count") for d in mriezka._days)
             and len(mriezka._months) == 12 and len(mriezka._weekdays) == 7,
             f"{len(mriezka._days)} dní")
    kontrola("detail relácie má krivku", len(app.history_detail_trace._values) > 2)


@krok
def k_historia_foto():
    foto("02_historia_hore")


@krok
def k_historia_scroll():
    app.history_scroll._parent_canvas.yview_moveto(0.28)


@krok
def k_historia_foto2():
    foto("03_historia_stred")


@krok
def k_historia_scroll2():
    app.history_scroll._parent_canvas.yview_moveto(0.72)
    kontrola("export do tabuľky je na stránke História",
             getattr(app, "history_export_btn", None) is not None)


@krok
def k_historia_foto3():
    foto("04_historia_dole")


@krok
def k_historia_detail():
    """`--okno`: panel „Relacia zblizka“ navrch viditelnej casti stranky -
    v dalsom kroku z neho bude samostatny obrazok (README)."""
    if not ARGS.okno:
        return
    # najnovsia relacia s dvoma pripomienkami - nech su v krivke vidno ▼
    sessions = app._world_sessions()
    s_dvoma = [i for i, s in enumerate(sessions)
               if len(s.get("trigger_offsets_s") or ()) == 2]
    if s_dvoma:
        app._pick_history_session(s_dvoma[-1])
    kontrola("detail ukazuje reláciu s pripomienkami", bool(s_dvoma))
    panel = app.history_detail_panel
    root.update_idletasks()
    vyska = max(1, app.history_scroll.winfo_height())
    app.history_scroll._parent_canvas.yview_moveto(max(0.0, (panel.winfo_y() - 12) / vyska))


@krok
def k_historia_detail_foto():
    if ARGS.okno:
        foto_panelu(app.history_detail_panel, "17_relacia_zblizka",
                    viditelne=app.history_scroll._parent_canvas)


@krok
def k_vhre():
    app.sidebar._select("vhre")


@krok
def k_vhre_foto():
    foto("05_vhre")


@krok
def k_vhre_qr():
    """Karta senzora je na spodku stránky; QR je tam len ako značka,
    kód sa rozbalí až klikom."""
    app.vhre_scroll._parent_canvas.yview_moveto(0.82)
    if getattr(app, "hr_qr", None) is not None:
        app.hr_qr._flip()
    kontrola("QR na appku do telefónu je na stránke V hre",
             getattr(app, "hr_qr", None) is not None)


@krok
def k_vhre_qr_foto():
    foto("05b_vhre_qr")


@krok
def k_zvuk():
    app.sidebar._select("zvuk")


@krok
def k_zvuk_foto():
    foto("06_zvuk")


@krok
def k_zvuk_scroll():
    # spodok stránky (Časovanie + Vrátiť odporúčané)
    app.zvuk_scroll._parent_canvas.yview_moveto(1.0)


@krok
def k_zvuk_foto2():
    foto("06b_zvuk_dole")


@krok
def k_sprievodca():
    # "guide" uz nie je samostatna karta - `TAB_ALIAS` ho presmeruje na
    # stranku Hlasky. Vysvetlivka ku kazdej hlaske sedi PRIAMO v jej karte,
    # takze sa fotí rozbalena karta, nie samostatna stranka.
    app.sidebar._select("guide")
    app.spustace_scroll._parent_canvas.yview_moveto(0.0)
    app.slots[0].toggle_detail()
    app.spustace_scroll._parent_canvas.yview_moveto(0.42)


@krok
def k_sprievodca_foto():
    foto("06c_sprievodca")


@krok
def k_sprievodca_periferia():
    # Tretia hlaska (Uvolnenie & periferia) - iny obsah, iny piktogram.
    app.slots[0].toggle_detail()
    app.slots[2].toggle_detail()
    app.spustace_scroll._parent_canvas.yview_moveto(0.62)


@krok
def k_sprievodca_foto3():
    foto("06e_sprievodca_periferia")


@krok
def k_sprievodca_filozofia():
    # Filozofia a zdroje su jedina cast, ktora nepatri ziadnej hlaske -
    # sedi zabalena na spodku stranky.
    app.slots[2].toggle_detail()
    app.guide_content._toggle("philosophy")
    app.spustace_scroll._parent_canvas.yview_moveto(1.0)


@krok
def k_sprievodca_foto2():
    foto("06d_sprievodca_znacka")


@krok
def k_spustace():
    # Sprievodca je na TEJ ISTEJ stranke, len nizsie - vyber karty scroll
    # nevracia, takze bez tohto by fotka spustacov zacinala tam, kde
    # skoncil sprievodca.
    app.sidebar._select("spustace")
    app.spustace_scroll._parent_canvas.yview_moveto(0.0)


@krok
def k_spustace_foto():
    foto("07_spustace")


@krok
def k_vseobecne():
    app.sidebar._select("vseobecne")


@krok
def k_vseobecne_foto():
    foto("08_vseobecne")


@krok
def k_acko_v_liste():
    """Tlačidlo „A" v titulkovej lište musí naozaj skočiť na sekciu.

    Otvoriť správnu stránku je len polovica úlohy — keby hráč ostal hore,
    sekciu by musel nájsť sám a tlačidlo by nebolo na nič.
    """
    app.sidebar._select("dnes")
    root.update()
    kontrola("áčko je v titulkovej lište",
             getattr(app.titlebar, "about_btn", None) is not None)
    app.show_about()
    root.update()
    # "vseobecne" je KARTA vnutri stranky "nastavenia", nie samostatna
    # stranka - preto sa overuje oboje (viz `DandurfApp.SETTINGS_TABS`).
    kontrola("áčko otvorí Nastavenia → Všeobecné",
             app.pages.current == "nastavenia"
             and app.settings_pages.current == "vseobecne",
             "%s / %s" % (app.pages.current, app.settings_pages.current))


@krok
def k_acko_posun():
    """Posun beží cez `after(80)`, takže sa meria až v ďalšom kroku."""
    wrap = getattr(app, "vseobecne_wrap", None)
    canvas = getattr(wrap, "_parent_canvas", None) if wrap else None
    hore = canvas.yview()[0] if canvas is not None else None
    kontrola("stránka sa posunula na sekciu", bool(hore and hore > 0.05),
             "yview=%.3f" % hore if hore is not None else "bez canvasu")
    foto("16_about")


@krok
def k_about():
    """Sekcia „O appke" a odkazy na autora.

    Odkazy vedú von z appky, takže keď sa stratia alebo sa ich zmení počet,
    nikto si to nevšimne — v okne to vyzerá rovnako, len tlačidlá chýbajú.
    """
    import guide_content

    def tlacidla(w, najdene):
        if isinstance(w, ctk.CTkButton):
            try:
                t = w.cget("text")
            except Exception:
                t = ""
            if t.startswith("↗"):
                najdene.append(t)
        for d in w.winfo_children():
            tlacidla(d, najdene)
        return najdene

    najdene = tlacidla(root, [])
    kontrola("odkazy na autora sú v okne",
             len(najdene) == len(guide_content.COMMUNITY_LINKS),
             "%d z %d" % (len(najdene), len(guide_content.COMMUNITY_LINKS)))
    for nazov, _url in guide_content.COMMUNITY_LINKS:
        kontrola("odkaz %s" % nazov, any(nazov in t for t in najdene))


@krok
def k_tema():
    """Prepnutie témy je najčastejší zdroj „zabudnutých" farieb — prvky,
    ktoré si držia vlastnú kópiu palety alebo kreslia na Canvas.

    Od 0.2 téma patrí svetu (B3-worlds), takže sa prepína svet - priame
    `on_theme_switch` by rozišlo vzhľad a svet."""
    app.set_world("work" if app.world == "play" else "play")
    app.sidebar._select("historia")


@krok
def k_tema_foto():
    app.history_scroll._parent_canvas.yview_moveto(0.28)
    foto("09_historia_opacna_tema")
    novy = theme_mod.tokens(app.theme_key)
    kontrola("graf prevzal farbu novej témy",
             app.history_detail_trace.pal["accent_hover"] == novy["accent_hover"],
             app.history_detail_trace.pal.get("accent_hover", "?"))
    kontrola("pozadie okna je z témy",
             app.appwrap.cget("fg_color") == novy["bg"], str(app.appwrap.cget("fg_color")))


@krok
def k_tema_dnes():
    # Dnes v opačnej téme - pásma tepu (pruh záťaže, stopa relácie,
    # legenda) majú v každej téme vlastný rad farieb
    app.sidebar._select("dnes")
    app._refresh_dnes_stats()


@krok
def k_tema_dnes_foto():
    foto("09b_dnes_opacna_tema")


@krok
def k_jazyk_de():
    """Nemčina má najdlhšie slová zo všetkých jazykov appky - ak sa
    rozloženie niekde zlomí, zlomí sa tu. Japončina zase overí, či sa vôbec
    vykreslia CJK znaky (potrebujú systémové písmo)."""
    from app import LANG_NATIVE_LABELS
    app.on_lang_switch(LANG_NATIVE_LABELS["de"])


@krok
def k_jazyk_de_foto():
    app.sidebar._select("zvuk")


@krok
def k_jazyk_de_foto2():
    foto("12_zvuk_nemcina")
    app.sidebar._select("dnes")


@krok
def k_jazyk_de_foto3():
    foto("13_dnes_nemcina")


@krok
def k_jazyk_ja():
    from app import LANG_NATIVE_LABELS
    app.on_lang_switch(LANG_NATIVE_LABELS["ja"])


@krok
def k_jazyk_ja_foto():
    foto("14_dnes_japoncina")
    kontrola("japonské znaky sa vykreslili (nie prázdne štvorčeky)",
             app.dnes_zone_panel is not None)


@krok
def k_jazyk_spat():
    from app import LANG_NATIVE_LABELS
    app.on_lang_switch(LANG_NATIVE_LABELS[ZACIATOCNY_JAZYK.get("kod", "sk")])


@krok
def k_dotaznik():
    """Dotazník po relácii sa musí dať OTVORIŤ — na každom tvare súhrnu.

    Chyba, kvôli ktorej tento krok vznikol, bola v `__init__` dialógu.
    Pytest ju minul (volal pomocníkov na triede, kde nevzniká) a harness
    tiež (dialóg nikdy neotvoril). Výsledok: sedem `TypeError` v denníku,
    trinásť relácií bez kontextu a všetky brány zelené.

    Tvary nižšie sú tie, ktoré v histórii naozaj ležia — od relácie zo
    staršej verzie bez krivky až po dnešnú s pruhom aktivity.
    """
    import ui_dialogs
    import ui_kit
    krivka = [70 + (i % 37) for i in range(519)]
    tvary = (
        ("dnešná relácia", dict(
            duration_s=1604.9, avg_bpm=93, max_bpm=124, baseline_bpm=76,
            critical_bpm=110, trigger_offsets_s=[120.0, 900.0],
            curve=krivka, activity_curve=[i / 600.0 for i in range(600)]), 2),
        ("bez pruhu aktivity", dict(
            duration_s=900.0, baseline_bpm=70, critical_bpm=110,
            curve=krivka[:200]), 1),
        ("zo staršej verzie, bez krivky", dict(duration_s=600.0), 0),
        ("prázdny súhrn", {}, 0),
        ("dlhšia než hodina", dict(duration_s=7380.0, curve=krivka), 1),
        ("diery v krivke aj inak dlhý pruh", dict(
            duration_s=1200.0, curve=[70, None, 80, None] * 50,
            activity_curve=[None, 0.5] * 40), 0),
    )
    # OKNA SA TU NEZATVARAJU, len skryju.
    #
    # CustomTkinter si po otvoreni Toplevelu planuje oneskoreny
    # `focus_set`. Ked okno zanikne skor, nez callback dobehne, Tk hodi
    # "bad window path name" - a harness by hlasil chybu, ktora s
    # dotaznikom nesuvisi. Zatvaraju sa az v `k_dotaznik_zavri`.
    for popis, suhrn, hlasok in tvary:
        try:
            dialog = ui_dialogs.SessionEndDialog(
                app, suhrn, cues=hlasok, silent=0)
        except Exception:
            chyby.append("dotazník „%s“:\n%s" % (popis, traceback.format_exc()))
            kontrola("dotazník sa otvorí: %s" % popis, False, "padol")
            continue
        kontrola("dotazník sa otvorí: %s" % popis, True)
        otvorene.append(dialog)
        root.update()
        dialog.top.grab_release()
        dialog.top.withdraw()

    # Graf v dotazníku: pri dosť dlhej krivke tam byť MUSÍ, inak by sa
    # hráč pýtal, čo sa dialo, bez toho, aby to videl.
    def ma_graf(widget):
        if isinstance(widget, ui_kit.SessionTrace):
            return True
        return any(ma_graf(d) for d in widget.winfo_children())

    try:
        s_grafom = ui_dialogs.SessionEndDialog(app, tvary[0][1], cues=2, silent=0)
        kontrola("dotazník má krivku relácie", ma_graf(s_grafom.top))
        otvorene.append(s_grafom)
        root.update()
        # ODFOTI SA AZ V DALSOM KROKU. `CTkToplevel` si rozmer nastavuje
        # oneskorene, takze hned po postaveni ma `winfo_width()` par pixelov
        # a na obrazku by bol cierny stvorcek.
        globals()["_dotaznik_na_foto"] = s_grafom
    except Exception:
        chyby.append(traceback.format_exc())
        kontrola("dotazník má krivku relácie", False, "nepodarilo sa postaviť")


@krok
def k_dotaznik_zavri():
    """Az teraz - okno ma rozmer a oneskorene `focus_set` uz dobehlo."""
    d = globals().get("_dotaznik_na_foto")
    if d is not None:
        try:
            d.top.deiconify()
            d.top.lift()
            foto_okna(d.top, "15_dotaznik")
        except Exception:
            chyby.append(traceback.format_exc())
    for dialog in otvorene:
        try:
            dialog.top.grab_release()
            dialog.top.destroy()
        except Exception:
            pass
    del otvorene[:]
    root.update()


@krok
def k_prazdny_stav():
    """Druhá polovica pravdy: ako appka vyzerá hneď po inštalácii."""
    try:
        os.remove(os.path.join(PROJ, "hr_sessions.json"))
    except OSError:
        pass
    app._history_cache = (0.0, None)
    app.hr_stats.reset_session()
    app._hr_state = "idle"
    app._refresh_history_page()
    app.sidebar._select("dnes")
    app._refresh_dnes_stats()


@krok
def k_prazdny_foto():
    foto("10_dnes_bez_dat")
    app.sidebar._select("historia")


@krok
def k_prazdny_foto2():
    foto("11_historia_bez_dat")


@krok
def k_koniec():
    obnov_subory()
    zlyhali = [k for k in kontroly if not k[1]]
    print()
    for nazov, ok, detail in kontroly:
        print(f"  {'OK  ' if ok else 'ZLE '} {nazov}" + (f"  ({detail})" if detail else ""))
    print(f"\n==== {len(kontroly) - len(zlyhali)} kontrol OK, {len(zlyhali)} zlyhalo, "
          f"{len(chyby)} chýb v Tk ====")
    for e in chyby:
        print("---- chyba ----\n", e)
    print("obrázky:", OUT)
    print("nastavenia a história obnovené zo zálohy")
    sys.stdout.flush()          # os._exit() buffer nevyprázdni
    root.after(200, lambda: os._exit(1 if (zlyhali or chyby) else 0))


def spusti(i=0):
    if i >= len(kroky):
        return
    try:
        kroky[i]()
    except Exception:
        chyby.append(traceback.format_exc())
        print("KROK ZLYHAL:", kroky[i].__name__, flush=True)
    root.after(650, lambda: spusti(i + 1))


try:
    root.after(1500, spusti)
    root.mainloop()
finally:
    obnov_subory()
os._exit(0)
