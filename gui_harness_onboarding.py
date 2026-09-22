# -*- coding: utf-8 -*-
"""Automaticky GUI harness pre ONBOARDING + GUIDED TOUR (Windows).

Doplnok ku gui_harness_auto.py (ten testuje bezne stranky). Tento:
  * zalohuje dandurf_settings.json a ZMAZE ho -> appka ide ako pri prvom
    starte (onboarding + tour); na konci subor obnovi;
  * onboarding: 4 kroky Dalej/Spat, "Preskocit uvod" -> krok 4, popisy tem
    na 2 riadky (ziadne doslovne '\\n'), realny klik mysou na Dalej;
  * guided tour: auto-start po onboardingu, pri kazdom z 8 krokov zmeria
    polohu bubliny a zvyraznenia voci cielovemu widgetu (right/below/above/
    center), realny klik na Dalej v bubline, Preskocit, cleanup okien,
    tour_seen ulozene, opakovane spustenie cez start_tour (= Nastavenia);
  * rezim --pair: v kroku 3 "Sparovat hodinky teraz" -> parovaci dialog na
    stranke V hre, tour sa NEspusti sam.

Spustenie:  python gui_harness_onboarding.py [--pair]   (appka nesmie bezat)
Hybe realnou mysou; screenshoty a JSON idu do logs/gui_harness/.
"""
import ctypes, json, os, shutil, sys, traceback

PAIR_MODE = "--pair" in sys.argv
PROJ = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PROJ, "logs", "gui_harness")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, PROJ)
os.chdir(PROJ)

SETTINGS = os.path.join(PROJ, "dandurf_settings.json")
SETTINGS_BAK = os.path.join(OUT, "dandurf_settings.pred_onboarding_harnessom.json")
if os.path.exists(SETTINGS):
    shutil.copy2(SETTINGS, SETTINGS_BAK)
    os.remove(SETTINGS)          # prvy start = ziadne nastavenia


def restore_settings():
    if os.path.exists(SETTINGS_BAK):
        shutil.copy2(SETTINGS_BAK, SETTINGS)


import display
display.enable_dpi_awareness()
import tkinter as tk
import customtkinter as ctk
from PIL import ImageGrab

import app as app_mod
from app import DandurfApp
from i18n import tr
import ui_dialogs

user32 = ctypes.windll.user32
user32.GetParent.restype = ctypes.c_void_p
user32.GetParent.argtypes = [ctypes.c_void_p]
LEFTDOWN, LEFTUP, MOVE = 0x0002, 0x0004, 0x0001

results, errors, state = [], [], {}
PFX = "pair" if PAIR_MODE else "tour"


def rec(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + (f"  -- {detail}" if detail else ""), flush=True)


def shot(name, bbox=None, widget=None, margin=0):
    try:
        root.update_idletasks()
        if bbox is None:
            w = widget or root
            x, y = w.winfo_rootx() - margin, w.winfo_rooty() - margin
            bbox = (x, y, x + w.winfo_width() + 2 * margin, y + w.winfo_height() + 2 * margin)
        img = ImageGrab.grab(bbox=bbox, include_layered_windows=True, all_screens=True)
        img.save(os.path.join(OUT, f"{PFX}_{name}.png"))
    except Exception as exc:
        print("shot failed", name, exc)


def mouse_click_at(x, y):
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOVE, 0, 0, 0, 0)
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)


def center_of(widget):
    widget.update_idletasks()
    return (widget.winfo_rootx() + widget.winfo_width() // 2,
            widget.winfo_rooty() + widget.winfo_height() // 2)


def wrect(widget):
    widget.update_idletasks()
    return (widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height())


def find_widgets(w, cls, acc):
    for c in w.winfo_children():
        if isinstance(c, cls):
            acc.append(c)
        find_widgets(c, cls, acc)
    return acc


# --------------------------------------------------------------------------
root = ctk.CTk()


def _cb_exc(et, ev, tb):
    errors.append("".join(traceback.format_exception(et, ev, tb)))
    print("TK CALLBACK EXCEPTION:", errors[-1], flush=True)


root.report_callback_exception = _cb_exc


class SpyWizard(ui_dialogs.OnboardingWizard):
    """Zachyti instanciu wizardu, ktoru DandurfApp vytvori vo svojom __init__."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        state["wizard"] = self
        state.setdefault("wizards", []).append(self)


app_mod.OnboardingWizard = SpyWizard

steps = []


def step(delay):
    def deco(f):
        steps.append((delay, f))
        return f
    return deco


def run_steps(i=0):
    if i >= len(steps):
        finish()
        return
    delay, fn = steps[i]

    def go():
        try:
            fn()
        except Exception as exc:
            errors.append(traceback.format_exc())
            rec(f"step {fn.__name__} raised", False, repr(exc))
        run_steps(i + 1)
    root.after(delay, go)


# ============================ ONBOARDING ============================
@step(2500)
def ob_start():
    wz = state.get("wizard")
    rec("onboarding wizard opened on first run", wz is not None and wz.top.winfo_exists())
    if wz is None:
        return
    wz.top.attributes("-topmost", True)      # harness bezi spod okna Claude
    rec("wizard has 4 steps", wz.STEP_COUNT == 4 and wz._step == 0, f"step={wz._step}")
    rec("step 1: Back disabled, Skip visible",
        wz.back_btn.cget("state") == "disabled" and wz.skip_btn.winfo_ismapped())
    rec("wizard cannot be closed by X (protocol swallowed)",
        wz.top.protocol("WM_DELETE_WINDOW") not in ("", None))
    # vlastna lista namiesto Windows ramu
    chrome = getattr(wz, "chrome", None)
    rec("wizard is frameless (own DialogChrome bar, no OS title)",
        bool(wz.top.overrideredirect()) and chrome is not None and chrome.bar.winfo_ismapped())
    rec("wizard bar has NO close button", chrome is not None and chrome.close_btn is None)
    rec("wizard has modal grab", root.grab_current() is not None and root.grab_current().winfo_toplevel() is wz.top,
        str(root.grab_current()))
    shot("ob_step1", widget=wz.top)
    # realne tahanie za listu
    state["wz_xy0"] = (wz.top.winfo_x(), wz.top.winfo_y())
    bx, by = chrome.bar.winfo_rootx() + 150, chrome.bar.winfo_rooty() + chrome.bar.winfo_height() // 2
    state["wz_bar"] = (bx, by)


@step(300)
def ob_drag_down():
    x, y = state["wz_bar"]
    user32.SetCursorPos(int(x), int(y)); user32.mouse_event(MOVE, 0, 0, 0, 0)
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)


for _i in range(1, 7):
    def _wd(i=_i):
        x, y = state["wz_bar"]
        user32.SetCursorPos(int(x + 90 * i // 6), int(y + 60 * i // 6))
        user32.mouse_event(MOVE, 0, 0, 0, 0)
    _wd.__name__ = f"ob_drag_move_{_i}"
    # prvy pohyb az po pauze: Tk berie pri ButtonPress AKTUALNU polohu
    # kurzora v case spracovania, nie v case stlacenia - ak je zaneprazdneny
    # (assets thread, kreslenie), pohyb hned po stlaceni posunie pociatok
    step(200 if _i == 1 else 35)(_wd)


@step(60)
def ob_drag_up():
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(300)
def ob_drag_check():
    wz = state["wizard"]
    x1, y1 = wz.top.winfo_x(), wz.top.winfo_y()
    x0, y0 = state["wz_xy0"]
    rec("wizard can be dragged by its own bar (REAL mouse)",
        abs((x1 - x0) - 90) <= 6 and abs((y1 - y0) - 60) <= 6, f"{(x0, y0)} -> {(x1, y1)}")
    rec("wizard still has grab after drag", root.grab_current() is not None
        and root.grab_current().winfo_toplevel() is wz.top)
    # Escape nesmie nic urobit
    user32.keybd_event(0x1B, 0, 0, 0); user32.keybd_event(0x1B, 0, 2, 0)


@step(400)
def ob_escape_check():
    wz = state["wizard"]
    rec("Escape does NOT close the wizard", wz.top.winfo_exists() and not wz.confirmed)


@step(400)
def ob_click_next():
    # realny klik na Dalej - az PO tom, co Tk spracoval topmost (inak klik
    # trafi okno, ktore wizard prekryvalo)
    wz = state["wizard"]
    mouse_click_at(*center_of(wz.next_btn))


@step(700)
def ob_step2():
    wz = state["wizard"]
    rec("REAL click on Next -> step 2", wz._step == 1, f"step={wz._step}")
    rec("step 2: Back enabled", wz.back_btn.cget("state") == "normal")
    shot("ob_step2", widget=wz.top)
    wz._on_next()


@step(500)
def ob_step3():
    wz = state["wizard"]
    rec("Next -> step 3 (watch)", wz._step == 2, f"step={wz._step}")
    # druhy dovod pre hodinky (historia) - tlmeny riadok pod hlavnym textom
    body2 = getattr(wz, "step3_body2", None)
    rec("step 3: second reason (history) shown under main text",
        body2 is not None and body2.winfo_ismapped() and body2.cget("text") == tr("ob.step3.body2"))
    root.update_idletasks()
    labels = find_widgets(wz.body, ctk.CTkLabel, [])
    lowest = max(l.winfo_rooty() + l.winfo_height() for l in labels if l.winfo_ismapped())
    footer_top = wz.footer.winfo_rooty()
    rec("step 3: content does not overflow into the footer",
        lowest <= footer_top, f"content bottom={lowest} footer top={footer_top}")
    shot("ob_step3", widget=wz.top)
    if PAIR_MODE:
        # "Sparovat hodinky teraz" - najdi tlacidlo podla textu a klikni realne
        btns = [b for b in find_widgets(wz.body, ctk.CTkButton, [])
                if tr("ob.step3.pair_now") in str(b.cget("text"))]
        rec("step 3 has 'Pair now' button", len(btns) == 1)
        if btns:
            mouse_click_at(*center_of(btns[0]))
        return
    wz._on_back()
    state["_back_ok"] = wz._step == 1


@step(400)
def ob_back_then_skip():
    if PAIR_MODE:
        return
    wz = state["wizard"]
    rec("Back from step 3 -> step 2", state.get("_back_ok"), f"step={wz._step}")
    # Preskocit uvod -> rovno krok 4
    mouse_click_at(*center_of(wz.skip_btn))


@step(600)
def ob_step4():
    if PAIR_MODE:
        return
    wz = state["wizard"]
    rec("REAL click on 'Skip intro' -> step 4", wz._step == 3, f"step={wz._step}")
    rec("step 4: Skip hidden, Next says confirm",
        not wz.skip_btn.winfo_ismapped() and wz.next_btn.cget("text") == tr("onboarding.confirm"),
        wz.next_btn.cget("text"))
    # popisy tem: 2 riadky, ziadne doslovne '\n'
    labels = find_widgets(wz.body, ctk.CTkLabel, [])
    descs = [str(l.cget("text")) for l in labels
             if str(l.cget("text")) in (tr("onboarding.zen.desc"), tr("onboarding.modern.desc"))]
    rec("theme descriptions rendered (2 cards)", len(descs) == 2, str(descs))
    rec("theme descriptions have a real line break, no literal backslash-n",
        all("\n" in d and "\\n" not in d for d in descs), repr(descs))
    shot("ob_step4", widget=wz.top)
    # Spat na krok 3 a znova na 4 (Dalej/Spat funguje aj tu)
    wz._on_back()
    state["_back3"] = wz._step == 2
    wz._on_next()
    state["_fwd4"] = wz._step == 3


@step(400)
def ob_confirm():
    if PAIR_MODE:
        return
    wz = state["wizard"]
    rec("Back/Next between step 3 and 4", state.get("_back3") and state.get("_fwd4"))
    mouse_click_at(*center_of(wz.next_btn))      # realny klik na "Vstupit"


@step(2500)
def ob_after():
    wz = state["wizard"]
    rec("wizard closed after confirm", not wz.top.winfo_exists() and wz.confirmed)
    rec("main window visible after onboarding", root.winfo_viewable() and app_ref()[0] is not None,
        f"state={root.state()} mapped={root.winfo_ismapped()} viewable={root.winfo_viewable()}")
    shot("main_after_onboarding", widget=root, margin=20)
    app = state.get("app")
    if app is not None:
        # Tour krok 7 uz neukazuje na QuickDock.stop_btn (redizajn "Sumi noc"
        # ho zrusil) ANI na widget enso: znacka je od 2.1 kresba na strede
        # Dnes (`_EnsoHero` na `app.dnes_canvas`), takze bublina miery na
        # canvas (viz guided_tour._target "enso").
        rec("dnes canvas has real size (tour step 7 target)",
            wrect(app.dnes_canvas)[2] > 10,
            f"canvas={wrect(app.dnes_canvas)}")
    if PAIR_MODE:
        rec("wizard.wants_pairing set", bool(wz.wants_pairing))


def app_ref():
    return (state.get("app"),)


# ============================ PAIR MODE ============================
@step(1200)
def pair_check():
    if not PAIR_MODE:
        return
    app = state["app"]
    tops = [c for c in root.winfo_children() if isinstance(c, tk.Toplevel) and c.winfo_viewable()]
    titles = [t.title() for t in tops]
    rec("pairing dialog opened automatically after onboarding",
        any(t == tr("hr.pair_title") for t in titles), str(titles))
    rec("page 'V hre' selected for pairing (Settings > In game tab)",
        app.sidebar.rows["nastavenia"].active and app.settings_nav.active == "vhre")
    rec("tour did NOT auto-start (pairing path)", getattr(app, "_tour", None) is None)
    for t in tops:
        shot("pairing_dialog", widget=t)
        try:
            t.destroy()
        except Exception:
            pass
    root.attributes("-topmost", True)


# ============================ GUIDED TOUR ============================
SIDES = ["center", "below", "below", "below", "below", "below", "right", "center"]
GAP, PAD = 14, 4


def tour():
    return getattr(state["app"], "_tour", None)


def visible_tops():
    return [c for c in root.winfo_children() if isinstance(c, tk.Toplevel) and c.winfo_viewable()]


def check_tour_step(expected_index, tag):
    t = tour()
    if t is None:
        rec(f"tour step {expected_index + 1} ({tag}): tour object exists", False)
        return
    rec(f"tour step {expected_index + 1} ({tag}): index", t._index == expected_index, f"index={t._index}")
    step_def = t.steps[t._index]
    side = SIDES[t._index]
    bubble = t._bubble
    rec(f"tour step {t._index + 1}: bubble exists and is visible",
        bubble is not None and bubble.winfo_exists() and bubble.winfo_viewable())
    if bubble is None:
        return
    root.update_idletasks()
    bx, by, bw, bh = wrect(bubble)
    mon = next((m for m in display.monitors(root)
                if m.contains(root.winfo_rootx() + 10, root.winfo_rooty() + 10)), None)
    on_mon = mon is not None and mon.contains(bx, by) and mon.contains(bx + bw - 1, by + bh - 1)
    rec(f"tour step {t._index + 1}: bubble fully on the app's monitor", on_mon, f"bubble={(bx, by, bw, bh)} mon={mon}")
    target = step_def.target_fn() if step_def.target_fn else None
    if target is None:
        rx, ry, rw, rh = wrect(root)
        dx = abs((bx + bw / 2) - (rx + rw / 2))
        dy = abs((by + bh / 2) - (ry + rh / 2))
        rec(f"tour step {t._index + 1}: centered bubble ({side})", dx <= 2 and dy <= 2, f"dx={dx} dy={dy}")
        rec(f"tour step {t._index + 1}: no highlight for center step", t._highlight is None)
    else:
        tx, ty, tw, th = wrect(target)
        hl = t._highlight
        ok_hl = hl is not None and hl.winfo_exists()
        if ok_hl:
            hx, hy, hw, hh = wrect(hl)
            ok_hl = (abs(hx - (tx - PAD)) <= 1 and abs(hy - (ty - PAD)) <= 1
                     and abs(hw - (tw + 2 * PAD)) <= 1 and abs(hh - (th + 2 * PAD)) <= 1)
            detail = f"target={(tx, ty, tw, th)} highlight={(hx, hy, hw, hh)}"
        else:
            detail = "no highlight window"
        rec(f"tour step {t._index + 1}: highlight frame sits on target widget", ok_hl, detail)
        if side == "right":
            ok = abs(bx - (tx + tw + GAP)) <= 2 and abs((by + bh / 2) - (ty + th / 2)) <= 2
        elif side == "below":
            ok = abs((bx + bw / 2) - (tx + tw / 2)) <= 2 and abs(by - (ty + th + GAP)) <= 2
        elif side == "above":
            ok = abs((bx + bw / 2) - (tx + tw / 2)) <= 2 and abs((by + bh) - (ty - GAP)) <= 2
        else:
            ok = True
        rec(f"tour step {t._index + 1}: bubble placed '{side}' of target", ok,
            f"target={(tx, ty, tw, th)} bubble={(bx, by, bw, bh)}")
        overlap = not (bx >= tx + tw or bx + bw <= tx or by >= ty + th or by + bh <= ty)
        rec(f"tour step {t._index + 1}: bubble does not cover the target", not overlap)
    # screenshot: okno + okolie (bubliny mozu trcat von)
    rx, ry, rw, rh = wrect(root)
    shot(f"tour_step{t._index + 1}", bbox=(rx - 40, ry - 40, rx + rw + 360, ry + rh + 40))


def next_button(bubble):
    for b in find_widgets(bubble, ctk.CTkButton, []):
        if str(b.cget("text")) in (tr("tour.next"), tr("tour.done_btn")):
            return b
    return None


def skip_button(bubble):
    for b in find_widgets(bubble, ctk.CTkButton, []):
        if str(b.cget("text")) == tr("tour.skip"):
            return b
    return None


@step(1500)
def tour_autostart():
    if PAIR_MODE:
        state["app"].start_tour()          # rucne ako z Nastaveni
        return
    rec("tour auto-started after onboarding", tour() is not None and tour()._bubble is not None)


@step(900)
def tour_s1():
    root.attributes("-topmost", False)      # bubliny su topmost, root nesmie byt nad nimi
    check_tour_step(0, "welcome")
    t = tour()
    if t and t._bubble:
        b = next_button(t._bubble)
        rec("bubble has Next button", b is not None)
        if b:
            mouse_click_at(*center_of(b))    # realny klik


def make_tour_steps():
    for idx in range(1, 8):
        def chk(i=idx):
            check_tour_step(i, SIDES[i])
            t = tour()
            if t and t._bubble and i < 7:
                t._next()
        chk.__name__ = f"tour_s{idx + 1}"
        step(700)(chk)


make_tour_steps()


@step(500)
def tour_finish_by_done():
    t = tour()
    if t and t._bubble:
        b = next_button(t._bubble)
        rec("last bubble button says 'Done'", b is not None and str(b.cget("text")) == tr("tour.done_btn"),
            str(b.cget("text")) if b else None)
        if b:
            mouse_click_at(*center_of(b))


@step(800)
def tour_after_done():
    app = state["app"]
    rec("tour finished: no bubble/highlight windows left", not visible_tops(), str([t.title() for t in visible_tops()]))
    rec("tour finished: app._tour cleared and tour_seen True", getattr(app, "_tour", None) is None and app.tour_seen)
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            on_disk = json.load(fh).get("tour_seen")
    except Exception as exc:
        on_disk = repr(exc)
    rec("tour_seen persisted to settings file", on_disk is True, str(on_disk))
    # tlacidlo v Nastaveniach (chip s textom settings.tour_btn)
    page = app.pages.pages.get("nastavenia")
    btns = [b for b in find_widgets(page, ctk.CTkButton, [])
            if str(b.cget("text")) == tr("settings.tour_btn")] if page is not None else []
    rec("Settings has 'Start tour' button", len(btns) == 1, f"found={len(btns)}")
    # znovu spustit (ako z Nastaveni) a preskocit v strede
    app.start_tour()


@step(900)
def tour_replay_skip():
    t = tour()
    rec("tour replay starts at step 1", t is not None and t._index == 0 and t._bubble is not None)
    if t:
        # dvojite Dalej v jednom ticku = to, co robi rychly dvojklik; stary
        # odlozeny _place() nesmie nakreslit bublinu naviac
        t._next()
        t._next()


@step(700)
def tour_replay_double_next_check():
    rec("double Next in one tick leaves exactly one bubble + one highlight",
        len(visible_tops()) == 2, f"toplevels={len(visible_tops())}")


@step(700)
def tour_replay_skip2():
    t = tour()
    rec("replay advanced to step 3", t is not None and t._index == 2)
    if t and t._bubble:
        s = skip_button(t._bubble)
        rec("bubble has Skip button", s is not None)
        if s:
            mouse_click_at(*center_of(s))


@step(800)
def tour_replay_after_skip():
    app = state["app"]
    rec("Skip in the middle: no windows left", not visible_tops())
    rec("Skip in the middle: tour cleared", getattr(app, "_tour", None) is None)
    # kontrola, ze pri dalsom starte sa tour sam nespusti: rovnaka podmienka ako v app
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            d = json.load(fh)
        rec("next start would NOT auto-run tour (theme saved + tour_seen)",
            d.get("theme") in ("zen", "modern") and d.get("tour_seen") is True,
            f"theme={d.get('theme')} tour_seen={d.get('tour_seen')}")
    except Exception as exc:
        rec("settings readable", False, repr(exc))


def finish():
    rec("no Tk callback exceptions during run", not errors, f"{len(errors)} errors")
    with open(os.path.join(OUT, f"harness_{PFX}_results.json"), "w", encoding="utf-8") as fh:
        json.dump({"results": results, "errors": errors}, fh, indent=1, ensure_ascii=False)
    failed = [r for r in results if not r["ok"]]
    print(f"\n==== {len(results) - len(failed)} passed, {len(failed)} failed ====", flush=True)
    for r in failed:
        print("  FAIL", r["name"], "--", r["detail"], flush=True)
    for e in errors:
        print("---- error ----\n", e, flush=True)
    try:
        state["app"].overlay_manager.stop_all()
        state["app"].hud.stop()
    except Exception:
        pass
    restore_settings()
    print("nastavenia obnovene zo zalohy:", SETTINGS_BAK, flush=True)
    sys.stdout.flush()
    root.after(200, lambda: os._exit(1 if failed else 0))


try:
    root.after(300, run_steps)
    # DandurfApp blokuje vo wait_window(wizard) - after-retazec bezi aj vtedy
    state["app"] = DandurfApp(root)
    root.mainloop()
finally:
    restore_settings()
os._exit(0)
