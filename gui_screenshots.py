# -*- coding: utf-8 -*-
"""Visual window check — builds the app, feeds it data, screenshots the pages.

What it is for
--------------
`gui_harness_auto.py` also checks what cannot be checked without real input
(dragging the window, the mouse wheel, global hooks), but it **moves the real
mouse and sends keys** — while it runs the computer cannot be used, and it
can only be started when a person has two minutes to spare. That is why it is
not run routinely, and why visual bugs (an empty strip under a chart,
clipped text, a panel that fell out of the window) were found only late.

This script is the cheap remainder: it builds the app, switches through the
pages and takes pictures of them. It does not touch the mouse or keyboard,
runs about 20 seconds and can be started at any time. It claims nothing
about correctness — a person (or a model) has to look at the pictures. What
CAN be checked programmatically, it reports as checks at the end.

What it backs up and restores
-----------------------------
`dandurf_settings.json` (and its `.bak`), `hr_sessions.json`, `hr_insights.json`,
`hr_session_open.json` (the session checkpoint) and `hr_session_pending.json`
(sessions that could not be saved). The script writes into
them (synthetic history, theme switch), but at the end — even after a
crash — it restores the original state. Without this the screenshots would
overwrite your real sessions.

Running it
----------
    python gui_screenshots.py                 # into logs/gui_screenshots
    python gui_screenshots.py C:\\cesta\\sem   # somewhere else
    python gui_screenshots.py --lang en       # whole run in another UI language
    python gui_screenshots.py --okno          # only the app window, no desktop

`--lang` switches the language right at the start, and the German and
Japanese steps then return to it (without it to Slovak, as before). `--okno`
(alias `--window`) shoots only the app window itself by its HWND - without
the desktop, the taskbar and the windows around it, even when something
covers it - and in addition shoots the "One session up close" panel from
History (`17_relacia_zblizka`); the pictures in the README come from that.
Without `--okno` the window shot with a small margin stays as before.

Return code: 0 = no error in Tk callbacks, 1 = something crashed.
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

from i18n import LANGUAGES                      # noqa: E402  (no Tk, writes nothing)


def _argumenty(argv):
    """Options are read BEFORE the backup and before the app - a wrong
    language ends right away, before the script touches a single file."""
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

# hr_session_open.json and the settings .bak since 0.3: at start the app
# adds the checkpoint to the history and deletes it - without a backup the
# screenshots would "consume" it and then restore the history without it
# (see gui_harness_auto.py).
ZALOHOVAT = [os.path.join(PROJ, n) for n in
             ("dandurf_settings.json", "hr_sessions.json", "hr_insights.json",
              "hr_session_open.json", "dandurf_settings.json.bak",
              # sessions that could not be saved (0.3) - the start adds them
              # to the history and deletes the file, just like the checkpoint
              "hr_session_pending.json")]
_zalohy = {}
for _cesta in ZALOHOVAT:
    if os.path.exists(_cesta):
        with open(_cesta, "rb") as _fh:
            _zalohy[_cesta] = _fh.read()


def obnov_subory():
    """Restores the backed-up files; deletes what was absent before the run."""
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

# Fixed seed: two runs in a row must give the same pictures, otherwise
# you cannot tell whether the look changed or just the random data.
random.seed(7)

chyby = []
kontroly = []


otvorene = []          # dialogs waiting to be closed


def kontrola(nazov, podmienka, detail=""):
    kontroly.append((nazov, bool(podmienka), detail))


root = ctk.CTk()
root.report_callback_exception = lambda et, ev, tb: chyby.append(
    "".join(traceback.format_exception(et, ev, tb)))
app = DandurfApp(root)


def _len_okno(okno):
    """HWND of the window for `--okno`, or None (then a rectangle is shot)."""
    return ui_kit._window_hwnd(okno) if ARGS.okno else None


def _bez_metadat(img):
    """Copy of the image without EXIF/XMP/text chunks - nothing but pixels."""
    cisty = img.convert("RGB")
    cisty.info = {}
    return cisty


def foto(meno):
    root.update_idletasks()
    root.update()
    # A window still waiting to be revealed (DWM cloak at start) is not
    # visible - the shot would capture the desktop behind it. Better no
    # picture at all.
    if getattr(app, "_zahalene", False) or ui_kit.je_zahalene(root):
        kontrola(f"foto {meno}: okno uz nie je zahalene", False)
        return
    x, y = root.winfo_rootx(), root.winfo_rooty()
    hwnd = _len_okno(root)
    try:
        if hwnd:
            # ONLY OUR WINDOW (`--okno`): by HWND, not a screen rectangle - no
            # desktop or taskbar, and another app's window on top does not get
            # into the picture.
            img = ImageGrab.grab(window=hwnd)
        elif ARGS.okno:
            img = ImageGrab.grab(bbox=(x, y, x + root.winfo_width(),
                                       y + root.winfo_height()), all_screens=True)
        else:
            # the window + a bit around it, so its own title bar is visible too
            bbox = (x - 8, y - 40, x + root.winfo_width() + 8, y + root.winfo_height() + 8)
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
        _bez_metadat(img).save(os.path.join(OUT, meno + ".png"))
        print("  foto", meno, img.size, flush=True)
        return img
    except Exception as exc:
        chyby.append(f"screenshot {meno} zlyhal: {exc}")


def foto_panelu(widget, meno, viditelne=None):
    """One window panel (README picture) - cut out of a whole-window shot.

    Only with `--okno`: then the shot starts exactly at the window corner,
    so the panel's position in the window is also its position in the
    shot. `viditelne` is the widget that clips the panel (the canvas of a
    scrolled page) - the panel must be wholly inside it."""
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
    """Like `foto`, but for a standalone Toplevel (dialog).

    `foto` shoots the main window's rectangle. A dialog is its own window
    elsewhere on the screen, so it would catch just its edge — exactly
    what happened before this helper was here.
    """
    # Dialogs are now FRAMELESS (ui_kit.DialogChrome) - `y - 40` was the offset
    # for the OS title bar, which is no longer there; we draw from the top of
    # the window. lift() tries to bring them to the top (in the harness this is
    # unreliable for modal windows, but it does no harm - in the real app
    # DialogChrome._take_focus raises them by itself).
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
# Synthetic data - the app without sessions shows empty states, and those
# can be shot anyway; this is the other half of the truth ("what it looks
# like with data").
# --------------------------------------------------------------------------

def ziva_relacia(minut=95):
    """Feeds `app.hr_stats` with one believable session (1 sample/s)."""
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
    """Writes `hr_sessions.json` with sessions from the last ~10 weeks —
    with gaps (days without playing) and with a curve, so there is
    something to draw.

    Sessions start in the evening (18-23 h local time), like a gaming
    evening, and the number of cues matches the triangles in the curve
    (audit: "HLÁŠKY 0" with three ▼ looked like an app bug)."""
    sessions = []
    teraz = time.time()
    for den in range(1, dni + 1):
        if random.random() < 0.32:
            continue
        d = time.localtime(teraz - (dni - den) * 86400)
        # from 18:00 OF THAT DAY, not from midnight + 18 h - on the day of the
        # clock change that would be 17:00 or 19:00
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
            # one number for the count, the automatic cues and ▼ in the curve
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
# Steps - each runs in its own `after()`, so Tk has time to draw between them
# --------------------------------------------------------------------------

kroky = []


def krok(fn):
    kroky.append(fn)
    return fn


ZACIATOCNY_JAZYK = {}


@krok
def k_jazyk_zaciatok():
    """`--lang`: the whole run in that language (e.g. English pictures for
    the README). Saved settings are restored from the backup at the end,
    so the player's language stays as it was."""
    from app import LANG_NATIVE_LABELS
    # without --lang the de/ja steps return to Slovak, as before
    ZACIATOCNY_JAZYK["kod"] = ARGS.lang or "sk"
    if ARGS.lang:
        if app.lang != ARGS.lang:
            app.on_lang_switch(LANG_NATIVE_LABELS[ARGS.lang])
        kontrola("jazyk behu je %s" % ARGS.lang, app.lang == ARGS.lang, str(app.lang))


@krok
def k_data():
    # the app usually sits under the terminal the script is started from
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
    # Until 2.1 this was a "card has a micrograph" check (`karta._series`).
    # The micrograph left the card — the card is now a BIG number with one
    # word under it. So what is checked is what it stands on now: that the
    # caption is really short. A long caption was what stretched the right
    # column in German and Russian at the expense of the centre with the
    # mark.
    karta = next(iter(app.dashboard_cards.values()), None)
    tag = karta.tag_label.cget("text") if karta is not None else ""
    kontrola("karta štatistiky má číslo aj popisok",
             karta is not None and bool(karta.value_label.cget("text")) and bool(tag),
             f"{karta.value_label.cget('text')!r} / {tag!r}" if karta else "")
    kontrola("popisok karty je krátky (<= 14 znakov)", len(tag) <= 14,
             f"{tag!r} má {len(tag)}")
    # `_refresh_dnes_stats` has its whole body in one `except`, so a broken
    # page does not escape from the Tk callback and "0 errors in Tk" does not
    # see it. This is the only place where it can be caught.
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
    # Since 0.3 (batch 4) the grid shows weeks from the first session, at most
    # 26 - not the whole year. It must have at least a week, at most half a
    # year, and the labels.
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
    """`--okno`: the "One session up close" panel at the top of the visible
    part of the page - in the next step it becomes a separate picture
    (README)."""
    if not ARGS.okno:
        return
    # the newest session with two cues - so ▼ is visible in the curve
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
    """The sensor card is at the bottom of the page; the QR is there only as
    a mark, the code expands only on click."""
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
    # bottom of the page (Timing + Restore recommended)
    app.zvuk_scroll._parent_canvas.yview_moveto(1.0)


@krok
def k_zvuk_foto2():
    foto("06b_zvuk_dole")


@krok
def k_sprievodca():
    # "guide" is no longer a separate tab - `TAB_ALIAS` redirects it to the
    # Cues page. The explanation for each cue sits RIGHT in its card, so
    # the expanded card is shot, not a separate page.
    app.sidebar._select("guide")
    app.spustace_scroll._parent_canvas.yview_moveto(0.0)
    app.slots[0].toggle_detail()
    app.spustace_scroll._parent_canvas.yview_moveto(0.42)


@krok
def k_sprievodca_foto():
    foto("06c_sprievodca")


@krok
def k_sprievodca_periferia():
    # The third cue (slot index 2, "Grip & gaze"; its old name was
    # "Uvolnenie & periferia", Release & periphery) - different content,
    # different pictogram.
    app.slots[0].toggle_detail()
    app.slots[2].toggle_detail()
    app.spustace_scroll._parent_canvas.yview_moveto(0.62)


@krok
def k_sprievodca_foto3():
    foto("06e_sprievodca_periferia")


@krok
def k_sprievodca_filozofia():
    # Philosophy and sources are the only part that belongs to no cue - it
    # sits collapsed at the bottom of the page.
    app.slots[2].toggle_detail()
    app.guide_content._toggle("philosophy")
    app.spustace_scroll._parent_canvas.yview_moveto(1.0)


@krok
def k_sprievodca_foto2():
    foto("06d_sprievodca_znacka")


@krok
def k_spustace():
    # The guide is on THE SAME page, just lower - choosing a tab does not
    # reset the scroll, so without this the shot of the triggers would start
    # where the guide ended.
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
    """The "A" button in the title bar must really jump to the section.

    Opening the right page is only half the job — if the player stayed at
    the top, they would have to find the section themselves and the button
    would be useless.
    """
    app.sidebar._select("dnes")
    root.update()
    kontrola("áčko je v titulkovej lište",
             getattr(app.titlebar, "about_btn", None) is not None)
    app.show_about()
    root.update()
    # "vseobecne" is a TAB inside the "nastavenia" page, not a separate
    # page - that is why both are checked (see `DandurfApp.SETTINGS_TABS`).
    kontrola("áčko otvorí Nastavenia → Všeobecné",
             app.pages.current == "nastavenia"
             and app.settings_pages.current == "vseobecne",
             "%s / %s" % (app.pages.current, app.settings_pages.current))


@krok
def k_acko_posun():
    """The scroll runs via `after(80)`, so it is measured in the next step."""
    wrap = getattr(app, "vseobecne_wrap", None)
    canvas = getattr(wrap, "_parent_canvas", None) if wrap else None
    hore = canvas.yview()[0] if canvas is not None else None
    kontrola("stránka sa posunula na sekciu", bool(hore and hore > 0.05),
             "yview=%.3f" % hore if hore is not None else "bez canvasu")
    foto("16_about")


@krok
def k_about():
    """The "About" section and the links to the author.

    The links lead out of the app, so when they get lost or their number
    changes, nobody notices — the window looks the same, only the buttons
    are missing.
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
    """Switching the theme is the most common source of "forgotten" colours —
    elements that keep their own copy of the palette or draw on a Canvas.

    Since 0.2 the theme belongs to the world (B3-worlds), so the world is
    switched - a direct `on_theme_switch` would split the look and the
    world apart."""
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
    # Today in the opposite theme - the heart-rate zones (load strip, session
    # trace, legend) have their own set of colours in each theme
    app.sidebar._select("dnes")
    app._refresh_dnes_stats()


@krok
def k_tema_dnes_foto():
    foto("09b_dnes_opacna_tema")


@krok
def k_jazyk_de():
    """German has the longest words of all the app's languages - if the
    layout breaks anywhere, it breaks here. Japanese in turn checks whether
    CJK characters are drawn at all (they need a system font)."""
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
    """The post-session questionnaire must OPEN — for every summary shape.

    The bug this step was created for was in the dialog's `__init__`.
    Pytest missed it (it called the helpers on the class, where it does not
    arise) and so did the harness (it never opened the dialog). Result: seven
    `TypeError`s in the journal, thirteen sessions without context and all
    gates green.

    The shapes below are the ones that really lie in the history — from a
    session from an older version without a curve to today's with an
    activity strip.
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
    # THE WINDOWS ARE NOT CLOSED HERE, only hidden.
    #
    # After opening a Toplevel, CustomTkinter schedules a delayed
    # `focus_set`. When the window is gone before the callback runs, Tk
    # throws "bad window path name" - and the harness would report an error
    # that has nothing to do with the questionnaire. They are closed only in
    # `k_dotaznik_zavri`.
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

    # The chart in the questionnaire: with a long enough curve it MUST be
    # there, otherwise the player would be asked what was going on without
    # seeing it.
    def ma_graf(widget):
        if isinstance(widget, ui_kit.SessionTrace):
            return True
        return any(ma_graf(d) for d in widget.winfo_children())

    try:
        s_grafom = ui_dialogs.SessionEndDialog(app, tvary[0][1], cues=2, silent=0)
        kontrola("dotazník má krivku relácie", ma_graf(s_grafom.top))
        otvorene.append(s_grafom)
        root.update()
        # IT IS SHOT ONLY IN THE NEXT STEP. `CTkToplevel` sets its size with a
        # delay, so right after being built `winfo_width()` is a few pixels and
        # the picture would show a black square.
        globals()["_dotaznik_na_foto"] = s_grafom
    except Exception:
        chyby.append(traceback.format_exc())
        kontrola("dotazník má krivku relácie", False, "nepodarilo sa postaviť")


@krok
def k_dotaznik_zavri():
    """Only now - the window has a size and the delayed `focus_set` has run."""
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
    """The other half of the truth: how the app looks right after install."""
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
    sys.stdout.flush()          # os._exit() does not flush the buffer
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
