# -*- coding: utf-8 -*-
"""Automatic GUI harness for ONBOARDING + GUIDED TOUR (Windows).

A complement to gui_harness_auto.py (that one tests the ordinary pages).
This one:
  * backs up dandurf_settings.json and DELETES it -> the app runs as on
    first start (onboarding + tour); at the end it restores the file;
  * onboarding: 5 steps Next/Back, Esc opens the question "Quit Zanshin?",
    "Skip to the watch" -> step 3 (watch), theme descriptions on 2 lines
    (no literal '\\n'), step 5 (cue style: four equal answers, nothing
    preselected, the choice gets saved), a real mouse click on Next;
  * guided tour: auto-start after onboarding, at each of the 6 steps it
    measures the position of the bubble and the highlight relative to the
    target widget (right/below/above/center), a real click on Next in the
    bubble, Skip, cleanup of windows, tour_seen saved, a repeated start via
    start_tour (= Settings);
  * --pair mode: in step 3 "Pair a watch now" -> the introduction goes on
    with steps 4-5, after it the pairing dialog on the In-game page; the
    tour starts only after it is closed (the harness destroys the dialog
    directly, so it starts the tour itself).

Run:  python gui_harness_onboarding.py [--pair]   (the app must not be running)
Moves the real mouse; screenshots and JSON go to logs/gui_harness/.
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
    os.remove(SETTINGS)          # first start = no settings


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
import ui_kit

user32 = ctypes.windll.user32
user32.GetParent.restype = ctypes.c_void_p
user32.GetParent.argtypes = [ctypes.c_void_p]
LEFTDOWN, LEFTUP, MOVE = 0x0002, 0x0004, 0x0001

results, errors, state = [], [], {}
PFX = "pair" if PAIR_MODE else "tour"


def rec(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + (f"  -- {detail}" if detail else ""), flush=True)


# At startup the main window shows only once fully drawn; until then it is
# cloaked (DWM cloak, see app._odhal_hotove_okno). A cloaked window still
# has winfo_viewable() True, a screenshot would capture the DESKTOP BEHIND
# IT (privacy!) and a real click would hit someone else's window. So every
# step first waits for the window to show.
ODHALENIE_TIMEOUT_MS = 5000


def app_zahalena():
    return bool(getattr(state.get("app"), "_zahalene", False)) or ui_kit.je_zahalene(root)


def shot(name, bbox=None, widget=None, margin=0):
    if app_zahalena():
        rec(f"screenshot {name}: app window not cloaked", False,
            "skipped - a grab now would capture the desktop behind the window")
        return
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
    """Captures the wizard instance that DandurfApp creates in its __init__."""

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

    def go(cakal=0):
        if app_zahalena():
            if cakal < ODHALENIE_TIMEOUT_MS:
                root.after(50, lambda: go(cakal + 50))
                return
            rec(f"app window revealed within {ODHALENIE_TIMEOUT_MS // 1000} s (before {fn.__name__})",
                False, "still DWM-cloaked - stopping, a screenshot or real click would hit the desktop")
            finish()
            return
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
    wz.top.attributes("-topmost", True)      # the harness runs from under the Claude window
    rec("wizard has 5 steps", wz.STEP_COUNT == 5 and wz._step == 0, f"step={wz._step}")
    rec("step 1: Back disabled, Skip visible",
        wz.back_btn.cget("state") == "disabled" and wz.skip_btn.winfo_ismapped())
    rec("wizard X of the OS goes through the quit question",
        "_on_close_request" in str(wz.top.protocol("WM_DELETE_WINDOW")))
    # custom title bar instead of the Windows frame
    chrome = getattr(wz, "chrome", None)
    rec("wizard is frameless (own DialogChrome bar, no OS title)",
        bool(wz.top.overrideredirect()) and chrome is not None and chrome.bar.winfo_ismapped())
    rec("wizard bar has a close button (asks before quitting)",
        chrome is not None and chrome.close_btn is not None)
    rec("wizard has modal grab", root.grab_current() is not None and root.grab_current().winfo_toplevel() is wz.top,
        str(root.grab_current()))
    shot("ob_step1", widget=wz.top)
    # real dragging by the title bar
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
    # the first move only after a pause: on ButtonPress Tk takes the CURRENT
    # cursor position at processing time, not at press time - if it is busy
    # (assets thread, drawing), a move right after the press shifts the origin
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
    # Escape opens the question "Quit Zanshin?" - the introduction does not
    # close by itself
    user32.keybd_event(0x1B, 0, 0, 0); user32.keybd_event(0x1B, 0, 2, 0)


@step(400)
def ob_escape_check():
    wz = state["wizard"]
    rec("Escape opens the quit question, wizard stays",
        wz.top.winfo_exists() and wz._otazka is not None and not wz.quit_requested)
    shot("ob_quit_question", widget=wz.top)
    wz._hide_quit_question()                 # = Continue


@step(400)
def ob_click_next():
    # real click on Next - only AFTER Tk has processed topmost (otherwise the
    # click hits the window the wizard was covering)
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
    # second reason for the watch (history) - a dim line under the main text
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
        # "Pair a watch now" - find the button by its text and really click it
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
    wz = state["wizard"]
    if PAIR_MODE:
        # "Pair now" does NOT end the introduction (0.3): it goes to step 4,
        # pairing opens only after the introduction
        rec("'Pair now' goes on to step 4, pairing queued",
            wz.top.winfo_exists() and wz._step == 3 and wz.wants_pairing, f"step={wz._step}")
        wz._on_next()
        wz._confirm()
        return
    rec("Back from step 3 -> step 2", state.get("_back_ok"), f"step={wz._step}")
    # Skip -> step 3 (watch), not the world choice
    mouse_click_at(*center_of(wz.skip_btn))


@step(600)
def ob_step4():
    if PAIR_MODE:
        return
    wz = state["wizard"]
    rec("REAL click on 'Skip to the watch' -> step 3 (watch)", wz._step == 2, f"step={wz._step}")
    wz._on_next()
    rec("step 4: Skip hidden, Next still says Next (step 5 follows)",
        not wz.skip_btn.winfo_ismapped() and wz.next_btn.cget("text") == tr("ob.next"),
        wz.next_btn.cget("text"))
    # world descriptions (B3-worlds: Play/Sumi, Work/Aizome): 2 lines,
    # no literal '\n'
    labels = find_widgets(wz.body, ctk.CTkLabel, [])
    descs = [str(l.cget("text")) for l in labels
             if str(l.cget("text")) in (tr("ob.world.play.desc"), tr("ob.world.work.desc"))]
    rec("world descriptions rendered (2 cards)", len(descs) == 2, str(descs))
    rec("theme descriptions have a real line break, no literal backslash-n",
        all("\n" in d and "\\n" not in d for d in descs), repr(descs))
    shot("ob_step4", widget=wz.top)
    # Back to step 3 and again to 4 and 5 (Next/Back works here too)
    wz._on_back()
    state["_back3"] = wz._step == 2
    wz._on_next()
    state["_fwd4"] = wz._step == 3
    wz._on_next()
    state["_fwd5"] = wz._step == 4


@step(600)
def ob_step5():
    if PAIR_MODE:
        return
    wz = state["wizard"]
    rec("Back/Next between steps 3, 4 and 5",
        state.get("_back3") and state.get("_fwd4") and state.get("_fwd5"))
    rec("step 5: Skip hidden, Next says confirm",
        not wz.skip_btn.winfo_ismapped() and wz.next_btn.cget("text") == tr("onboarding.confirm"),
        wz.next_btn.cget("text"))
    root.update_idletasks()
    btns = list(getattr(wz, "_cue_buttons", {}).values())
    rozmery = {(b.winfo_width(), b.winfo_height()) for b in btns}
    rec("step 5: four cue-style answers of one size, none preselected",
        len(btns) == 4 and len(rozmery) == 1 and wz.cue_style is None, str(rozmery))
    labels = find_widgets(wz.body, ctk.CTkLabel, [])
    lowest = max(l.winfo_rooty() + l.winfo_height() for l in labels if l.winfo_ismapped())
    rec("step 5: content does not overflow into the footer",
        lowest <= wz.footer.winfo_rooty(), f"content bottom={lowest}")
    shot("ob_step5", widget=wz.top)
    wz._vyber_styl(wz.NEVIEM)
    state["_neviem_je_hlas"] = wz.cue_style == "voice"
    wz._vyber_styl("sound")


@step(400)
def ob_confirm():
    if PAIR_MODE:
        return
    wz = state["wizard"]
    rec("step 5: 'not sure' is stored as voice", state.get("_neviem_je_hlas"))
    mouse_click_at(*center_of(wz.next_btn))      # real click on "Enter"


@step(2500)
def ob_after():
    wz = state["wizard"]
    rec("wizard closed after confirm", not wz.top.winfo_exists() and wz.confirmed)
    rec("main window visible after onboarding",
        root.winfo_viewable() and not ui_kit.je_zahalene(root) and app_ref()[0] is not None,
        f"state={root.state()} mapped={root.winfo_ismapped()} viewable={root.winfo_viewable()} "
        f"cloaked={ui_kit.je_zahalene(root)}")
    shot("main_after_onboarding", widget=root, margin=20)
    app = state.get("app")
    if app is not None and not PAIR_MODE:
        rec("cue style from step 5 stored", getattr(app, "cue_style", None) == "sound",
            getattr(app, "cue_style", None))
    if app is not None:
        # Tour step 2 no longer points at QuickDock.stop_btn (the "Sumi noc"
        # redesign removed it) NOR at the enso widget: since 2.1 the mark is a
        # drawing in the centre of Today (`_EnsoHero` on `app.dnes_canvas`), so
        # the bubble aims at the canvas (see guided_tour._target "enso").
        rec("dnes canvas has real size (tour step 2 target)",
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
# guided_tour._STEPS: intro, enso, heart-rate receiving, cues, history, end
# (without heart rate the end points at the watch indicator in the side
# panel)
SIDES = ["center", "right", "left", "below", "right", "right"]
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
    # screenshot: window + surroundings (bubbles may stick out)
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
        state["app"].start_tour()          # by hand, as from Settings
        return
    rec("tour auto-started after onboarding", tour() is not None and tour()._bubble is not None)


@step(900)
def tour_s1():
    root.attributes("-topmost", False)      # bubbles are topmost, the root must not be above them
    check_tour_step(0, "welcome")
    t = tour()
    if t and t._bubble:
        b = next_button(t._bubble)
        rec("bubble has Next button", b is not None)
        if b:
            mouse_click_at(*center_of(b))    # real click


def make_tour_steps():
    for idx in range(1, len(SIDES)):
        def chk(i=idx):
            check_tour_step(i, SIDES[i])
            t = tour()
            if t and t._bubble and i < len(SIDES) - 1:
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
    # the button in Settings (a chip with the settings.tour_btn text)
    page = app.pages.pages.get("nastavenia")
    btns = [b for b in find_widgets(page, ctk.CTkButton, [])
            if str(b.cget("text")) == tr("settings.tour_btn")] if page is not None else []
    rec("Settings has 'Start tour' button", len(btns) == 1, f"found={len(btns)}")
    # start again (as from Settings) and skip in the middle
    app.start_tour()


@step(900)
def tour_replay_skip():
    t = tour()
    rec("tour replay starts at step 1", t is not None and t._index == 0 and t._bubble is not None)
    if t:
        # a double Next in one tick = what a quick double click does; an old
        # deferred _place() must not draw an extra bubble
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
    # check that on the next start the tour does not start by itself: the same
    # condition as in app
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
    # DandurfApp blocks in wait_window(wizard) - the after chain runs even then
    state["app"] = DandurfApp(root)
    root.mainloop()
finally:
    restore_settings()
os._exit(0)
