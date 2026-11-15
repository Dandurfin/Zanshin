# -*- coding: utf-8 -*-
"""Automatic GUI harness (Windows) - checking the app in a real window.

What it does
------------
Starts DandurfApp IN THIS PROCESS (no pyautogui over someone else's window),
and then via a Tk `after()` chain:
  * clicks through all 6 pages and measures the geometry of the Today page
    (jump),
  * lets KamaeBar breathe and checks that it does not change height,
  * on every slider sends a REAL mouse wheel (user32.mouse_event) and
    event_generate and checks that the value stayed,
  * switches on the visual test, reads WS_EX_TRANSPARENT from the window,
    walks a WindowFromPoint grid (grabbability), checks the fleur cursor,
    drags the window with the REAL mouse, saves the position, reopens,
    switches to another slot,
  * opens the pairing dialog, checks override/focus/grab, drags it by the
    bar and closes it with a real Escape,
  * saves a pictogram colour and checks on a screenshot that the visual is
    red,
  * bulk-selects slots (refusing "all" + deleting two),
  * stats cards on Today: the picker has all rows whole (SK and DE) and is
    on screen, cap of 4 cards, the last one stays, ✕ <-> ✓, and swapping
    cards by dragging with the REAL mouse (a click, a gap or ⓘ do not
    change the order),
  * switches the language to EN and back, the theme Sumi/Aizome and back.

What you need to know
---------------------
  * IT MOVES THE REAL MOUSE and sends keys - leave the PC alone while it
    runs (~2 min).
  * It makes the main window temporarily `topmost`, otherwise the
    terminal/IDE covers it.
  * The settings (dandurf_settings.json and its .bak) and the heart-rate
    history (hr_sessions.json, hr_insights.json, the session checkpoint
    hr_session_open.json) are backed up at the start ON DISK next to the
    originals (`<subor>.pred-harnessom`) and RESTORED at the end - bulk
    deletion, drag and the history test would otherwise change them. After
    a run that someone killed hard, the next run restores them right at
    the start (see "Data backup").
  * Screenshots and harness_results.json go to logs/gui_harness/.
  * messagebox.showinfo/askyesno are replaced by a record during bulk
    deletion (otherwise a modal window would block the run).

Run:  python gui_harness_auto.py   (the app MUST NOT be running alongside)
"""
import atexit, ctypes, filecmp, json, os, shutil, sys, time, traceback
from ctypes import wintypes

PROJ = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PROJ, "logs", "gui_harness")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, PROJ)
os.chdir(PROJ)

# ---------------------------------------------------------------------------
# Data backup (settings + heart-rate history) - on disk, not in memory
# ---------------------------------------------------------------------------
# The harness runs on the Zanshin data of the source tree next to main.py,
# i.e. on the real heart-rate history. Up to 0.2.1c it put it aside only in
# MEMORY and the last `finally` did not even restore it: Ctrl+C, closing the
# window or a crash between setting aside and restoring deleted it forever.
# The settings backup was on disk, but the next run overwrote it with the
# settings the interrupted run had changed. So now:
#   * BEFORE the first touch every file is copied next to itself as
#     `<subor>.pred-harnessom`; a file that did not exist before the run
#     gets the marker `<subor>.pred-harnessom-nebol`. On disk it survives
#     even the process being killed.
#   * It is restored in `finish()`, in the `finally` around mainloop
#     (Ctrl+C, closed window) and via `atexit` (a crash even before
#     mainloop) - every way out.
#   * When someone killed the run hard (Task Manager, closing the console),
#     the backup stays on disk and the next run restores it BEFORE it
#     touches anything (`obnov_po_prerusenom_behu`). `zaloz_zalohy` does not
#     write a new backup over an unrestored old one - that was the loss of
#     settings.
# The names `.pred-harnessom*` and `.pred-obnovou-*` are already covered by
# .gitignore (`*.pred-*`; the history also by `hr_*.json*`), so they do not
# go to GitHub. The heart-rate history backups are siblings of its files,
# so "Delete history" deletes them too (`data_io._plan_priecinka`); that
# option does not delete the settings, nor their backup.
ZALOHA = ".pred-harnessom"
NEBOL = ".pred-harnessom-nebol"


def _zapis_kopiu(zdroj, ciel):
    """Copy via `.tmp` + `os.replace`: an interruption in the middle of
    copying does not leave a half backup that the next run would restore
    instead of the data."""
    tmp = ciel + ".tmp"
    shutil.copy2(zdroj, tmp)
    os.replace(tmp, ciel)


def obnov_po_prerusenom_behu(cesty, znacka=None):
    """Restores backups that an interrupted run left behind. Called first.

    Rule: the backup from before the harness is the player's real state and
    is restored. What is in its place now, however, is not blindly
    overwritten or deleted - the interrupted harness may have written it
    (synthetic data), but so may the app started in the meantime (a new
    real session), and the two cannot be told apart. If the file differs
    from the backup (or did not exist before the run), it is set aside next
    to it as `<subor>.pred-obnovou-<cas>` and it is printed where it is.
    That way nothing is lost; one identical to the backup need not be kept.
    Returns the list of restored files.
    """
    znacka = znacka or time.strftime("%Y%m%d-%H%M%S")
    vratene = []
    for p in cesty:
        zaloha, nebol = p + ZALOHA, p + NEBOL
        if not (os.path.exists(zaloha) or os.path.exists(nebol)):
            continue
        if os.path.exists(p) and not (os.path.exists(zaloha)
                                      and filecmp.cmp(p, zaloha, shallow=False)):
            bokom = "%s.pred-obnovou-%s" % (p, znacka)
            n = 2
            while os.path.exists(bokom):
                bokom = "%s.pred-obnovou-%s-%d" % (p, znacka, n)
                n += 1
            os.replace(p, bokom)
            print("harness: %s z preruseneho behu odlozeny ako %s"
                  % (os.path.basename(p), bokom), flush=True)
        if os.path.exists(zaloha):
            os.replace(zaloha, p)
            print("harness: %s vrateny zo zalohy preruseneho behu"
                  % os.path.basename(p), flush=True)
        if os.path.exists(nebol):
            os.remove(nebol)
        vratene.append(p)
    return vratene


def zaloz_zalohy(cesty):
    """Backs up every file to disk before the run touches it."""
    for p in cesty:
        if os.path.exists(p + ZALOHA) or os.path.exists(p + NEBOL):
            # A backup that `obnov_po_prerusenom_behu` did not restore (e.g. a
            # locked file). Overwriting it with the current file would be
            # exactly the data loss it protects against - the run would rather
            # not start.
            raise SystemExit("harness: %s ma nevratenu zalohu z preruseneho "
                             "behu - vrat ju rucne a spusti znova" % p)
    for p in cesty:
        if os.path.exists(p):
            _zapis_kopiu(p, p + ZALOHA)
        else:
            open(p + NEBOL, "w").close()


def vrat_zalohy(cesty, nechat_zalohy=False):
    """Restores the files from before the run; what did not exist before the
    run is deleted (this run wrote it). `nechat_zalohy=True` (mid-run)
    restores a copy and keeps the backup, because the app and the harness
    still write to the files; at the end the backup is restored by a move
    and disappears. A second call finds nothing - `finish()`, `finally` and
    `atexit` may call it one after another."""
    for p in cesty:
        try:
            if os.path.exists(p + ZALOHA):
                if nechat_zalohy:
                    _zapis_kopiu(p + ZALOHA, p)
                else:
                    os.replace(p + ZALOHA, p)
            elif os.path.exists(p + NEBOL):
                if os.path.exists(p):
                    os.remove(p)
                if not nechat_zalohy:
                    os.remove(p + NEBOL)
        except Exception as exc:
            # The backup stays on disk - the next run restores it.
            print("harness: subor sa nepodarilo vratit", p, exc, flush=True)


SETTINGS = os.path.join(PROJ, "dandurf_settings.json")
HR_SESSIONS = os.path.join(PROJ, "hr_sessions.json")
HR_INSIGHTS = os.path.join(PROJ, "hr_insights.json")
# Since 0.3 the app at start adds to history the checkpoint of a session
# that was not saved last time (hr_session_open.json), and deletes it.
# Without a backup the harness would "consume" it this way and then restore
# the history to the state before the run - the session from the crashed
# app would be gone forever. The same for the settings .bak: otherwise it
# would be left after the run with the settings the harness modified.
HR_SESSION_OPEN = os.path.join(PROJ, "hr_session_open.json")
# Sessions that could not be saved (0.3, hr_stats.CAKAJUCA_MENO) - start
# adds them to history and deletes the file, exactly like the checkpoint
# above.
HR_SESSION_PENDING = os.path.join(PROJ, "hr_session_pending.json")
SETTINGS_BAK = SETTINGS + ".bak"
ODLOZENE = (SETTINGS, HR_SESSIONS, HR_INSIGHTS, HR_SESSION_OPEN, SETTINGS_BAK,
            HR_SESSION_PENDING)
obnov_po_prerusenom_behu(ODLOZENE)
zaloz_zalohy(ODLOZENE)
atexit.register(vrat_zalohy, ODLOZENE)
if os.path.exists(SETTINGS):
    # This harness tests the ordinary pages, not the first start. If the
    # settings lacked the theme (= first_run) or tour_seen, the app would
    # open the onboarding/tour and the harness would hang in a modal
    # wait_window() forever. For the duration of the run we fill them in;
    # the original is restored at the end.
    # (Onboarding and the tour are tested by gui_harness_onboarding.py.)
    try:
        with open(SETTINGS, encoding="utf-8") as _fh:
            _d = json.load(_fh)
        if _d.get("theme") not in ("zen", "modern") or not _d.get("tour_seen"):
            _d.setdefault("theme", "zen")
            _d["tour_seen"] = True
            with open(SETTINGS, "w", encoding="utf-8") as _fh:
                json.dump(_d, _fh, ensure_ascii=False, indent=2)
            print("harness: docasne doplnena tema/tour_seen, aby nebezal onboarding", flush=True)
    except Exception as _exc:
        print("harness: nastavenia sa nepodarilo upravit:", _exc, flush=True)

import display
display.enable_dpi_awareness()
import tkinter as tk
import customtkinter as ctk
from PIL import ImageGrab

from app import DandurfApp
import ui_kit

user32 = ctypes.windll.user32
user32.WindowFromPoint.restype = ctypes.c_void_p
user32.GetAncestor.restype = ctypes.c_void_p
user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetParent.restype = ctypes.c_void_p
user32.GetParent.argtypes = [ctypes.c_void_p]
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
user32.LoadCursorW.restype = ctypes.c_void_p
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("hCursor", ctypes.c_void_p), ("pt", POINT)]


results, errors = [], []


def rec(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + (f"  -- {detail}" if detail else ""), flush=True)


# At start the main window only shows once it is fully drawn; until then
# it is cloaked (DWM cloak, see app._odhal_hotove_okno). A cloaked window
# still has winfo_viewable() True, a screenshot would capture the DESKTOP
# BEHIND IT (privacy!) and a real click would hit someone else's window.
# That is why every step first waits until the window shows, and `grab`
# refuses to take a picture while it is cloaked.
ODHALENIE_TIMEOUT_MS = 5000


def app_zahalena():
    return bool(getattr(globals().get("app"), "_zahalene", False)) or ui_kit.je_zahalene(root)


def grab(name, bbox):
    if app_zahalena():
        rec(f"screenshot {name}: app window not cloaked", False,
            "skipped - a grab now would capture the desktop behind the window")
        return None
    img = ImageGrab.grab(bbox=bbox, include_layered_windows=True, all_screens=True)
    img.save(os.path.join(OUT, name + ".png"))
    return img


def shot(name, bbox=None, widget=None):
    root.update_idletasks()
    if bbox is None:
        w = widget or root
        x, y = w.winfo_rootx(), w.winfo_rooty()
        bbox = (x, y, x + w.winfo_width(), y + w.winfo_height())
    try:
        grab(name, bbox)
    except Exception as exc:
        print("shot failed", name, exc)


def top_hwnd(widget):
    return user32.GetParent(ctypes.c_void_p(widget.winfo_id())) or widget.winfo_id()


def exstyle(hwnd):
    return user32.GetWindowLongW(ctypes.c_void_p(hwnd), -20)


def win_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def is_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def hit_root(x, y):
    h = user32.WindowFromPoint(POINT(x, y))
    if not h:
        return None
    return user32.GetAncestor(h, 2)  # GA_ROOT


MOUSEEVENTF_MOVE, LEFTDOWN, LEFTUP, WHEEL = 0x0001, 0x0002, 0x0004, 0x0800


def mouse_to(x, y):
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOUSEEVENTF_MOVE, 0, 0, 0, 0)


def cursor_handle():
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    user32.GetCursorInfo(ctypes.byref(ci))
    return ci.hCursor


IDC_SIZEALL = 32646

# ---------------------------------------------------------------------------
root = ctk.CTk()


def _cb_exc(et, ev, tb):
    errors.append("".join(traceback.format_exception(et, ev, tb)))
    print("TK CALLBACK EXCEPTION:", "".join(traceback.format_exception(et, ev, tb)), flush=True)


root.report_callback_exception = _cb_exc
app = DandurfApp(root)

steps = []
state = {}


def step(delay, fn=None):
    if fn is None:
        def deco(f):
            steps.append((delay, f))
            return f
        return deco
    steps.append((delay, fn))
    return fn


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


def kamae_geom():
    k = app.kamae
    anchor = k.master
    wrap = anchor.master
    return dict(kamae_y=k.winfo_y(), kamae_h=k.winfo_height(),
                canvas_h=k.canvas.winfo_height(), anchor_y=anchor.winfo_y(),
                anchor_h=anchor.winfo_height(), wrap_y=wrap.winfo_y(),
                wrap_h=wrap.winfo_height(), root_w=root.winfo_width(),
                root_h=root.winfo_height(), root_x=root.winfo_x(), root_y=root.winfo_y())


# ---------------- 1. start ----------------
@step(1800, )
def s_start():
    rec("app window opened",
        root.winfo_exists() and root.winfo_viewable() and not ui_kit.je_zahalene(root),
        f"geometry={root.geometry()} override={root.overrideredirect()} "
        f"cloaked={ui_kit.je_zahalene(root)}")
    rec("sidebar has 4 main pages + enso (rest are tabs in Settings)",
        len(app.sidebar.buttons) == 4, list(app.sidebar.buttons))
    rec("settings group has 4 tabs", list(app.settings_nav.buttons) == list(app.SETTINGS_TABS), list(app.settings_nav.buttons))
    hwnd = top_hwnd(root)
    root.attributes("-topmost", True)     # harness runs from a Claude window that covers the app
    user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    root.lift()
    state["g0"] = kamae_geom()
    print("kamae geom start:", state["g0"])
    shot("01_dnes")


# ---------------- 1b. side menu: fixed columns ----------------
def page_on_top():
    """Which page (main one or a Settings tab) is on top right now - by the
    widget under a point in the page area, via app.page_frames."""
    pages = app.pages
    root.update_idletasks()
    w = root.winfo_containing(pages.winfo_rootx() + 60, pages.winfo_rooty() + 120)
    found = None
    while w is not None:
        for key, frame in app.page_frames.items():
            if w is frame and found is None:
                found = key
        w = getattr(w, "master", None)
    return found


def check_sidebar_alignment(tag):
    root.update_idletasks()
    rows = app.sidebar.rows
    cx = {k: r.icon.winfo_rootx() + r.icon.winfo_width() / 2 for k, r in rows.items()}
    rec(f"sidebar: all 3 icons centered on the same x ({tag})", max(cx.values()) - min(cx.values()) <= 1, str(cx))
    lx = {k: r.label.winfo_rootx() + r.label.winfo_width() / 2 for k, r in rows.items()}
    rec(f"sidebar: all 3 labels centered on the same x ({tag})", max(lx.values()) - min(lx.values()) <= 1, str(lx))
    hs = {k: r.winfo_height() for k, r in rows.items()}
    rec(f"sidebar: rows same height ({tag})", len(set(hs.values())) == 1, str(hs))
    rec(f"sidebar: narrow icon menu (<= 110 px logical) ({tag})",
        app.sidebar.winfo_width() <= 110 * 1.6, str(app.sidebar.winfo_width()))
    # "In-game" is now a sidebar item (not a tab in Settings) - the badge
    # (a dot when the heart-rate sensor runs) goes directly on its
    # _NavRow.badge.
    app.sidebar.set_badge("vhre", "●")
    root.update_idletasks()
    rec(f"sidebar: badge appended to 'V hre' row ({tag})",
        app.sidebar.rows["vhre"].badge.cget("text").endswith("●"))
    app._refresh_nav_badges()
    root.update_idletasks()
    rec(f"sidebar: empty badge removed ({tag})",
        not app.sidebar.rows["vhre"].badge.cget("text").endswith("●"))


@step(100, )
def s_sidebar_alignment():
    check_sidebar_alignment("initial")
    shot("01b_sidebar", widget=app.sidebar)


@step(100, )
def s_sidebar_click_icon():
    app.sidebar._select("dnes")
    root.update_idletasks()
    # CTkLabel.bind() binds to the inner tk.Label - send the event there
    ic = app.sidebar.rows["historia"].icon
    getattr(ic, "_label", ic).event_generate("<Button-1>", x=3, y=3)


@step(300, )
def s_sidebar_click_icon_check():
    rec("sidebar: click on ICON switches page", page_on_top() == "historia" and app.sidebar.rows["historia"].active, str(page_on_top()))
    # Compact rows no longer have visible text under the icon (redesign
    # "Sumi noc" - "no text under the icons"), so self.label is no longer
    # .pack()-ed and a click on it would do nothing. The second click on the
    # navigation row now targets the icon again (idempotent with the first
    # click above).
    ic = app.sidebar.rows["nastavenia"].icon
    getattr(ic, "_label", ic).event_generate("<Button-1>", x=3, y=3)


@step(300, )
def s_sidebar_click_label_check():
    rec("sidebar: click on ICON opens Settings group (first tab = triggers)",
        page_on_top() == "spustace" and app.sidebar.rows["nastavenia"].active
        and app.settings_nav.active == "spustace", f"{page_on_top()} tab={app.settings_nav.active}")
    # navigation to a tab via sidebar._select (palette, onboarding, tour) -
    # "vhre" is NO LONGER a tab (redesign "Sumi noc"), it is its own
    # top-level page, so it is checked separately below.
    for key in ("zvuk", "guide", "vseobecne"):
        app.sidebar._select(key)
        root.update_idletasks()
        rec(f"navigate: _select('{key}') shows the tab and highlights Settings",
            page_on_top() == key and app.settings_nav.active == key
            and app.sidebar.rows["nastavenia"].active, f"top={page_on_top()}")
    app.sidebar._select("vhre")
    root.update_idletasks()
    rec("navigate: _select('vhre') shows the top-level page (not a Settings tab)",
        page_on_top() == "vhre" and app.sidebar.rows["vhre"].active
        and not app.sidebar.rows["nastavenia"].active, f"top={page_on_top()}")
    app.sidebar._select("dnes")
    root.update_idletasks()
    # real mouse click on the Settings icon
    ic = app.sidebar.rows["nastavenia"].icon
    mouse_to(ic.winfo_rootx() + ic.winfo_width() // 2, ic.winfo_rooty() + ic.winfo_height() // 2)


@step(150, )
def s_sidebar_real_click():
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(400, )
def s_sidebar_real_click_check():
    rec("sidebar: REAL mouse click on icon opens Settings (last tab remembered)",
        page_on_top() == "vseobecne", str(page_on_top()))
    box = app.sidebar.rows["nastavenia"].box
    rec("sidebar: active row has highlighted background", box.cget("fg_color") != "transparent", str(box.cget("fg_color")))
    # real click on the "Sound" tab in SubNav
    b = app.settings_nav.buttons["zvuk"]
    mouse_to(b.winfo_rootx() + b.winfo_width() // 2, b.winfo_rooty() + b.winfo_height() // 2)


@step(150, )
def s_tab_real_click():
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(400, )
def s_tab_real_click_check():
    rec("settings tabs: REAL click on 'Zvuk' tab switches tab", page_on_top() == "zvuk", str(page_on_top()))
    shot("01c_settings_tabs")
    app.sidebar._select("dnes")


# ---------------- 1c. fixed window (no dragging by edges), alignment, dock, hooks without admin ----------------
# Since the "fixed window" tweak (see app.py DandurfApp.WINDOW_W/H) the app
# no longer has manual resize grips - the window keeps one fixed size so
# the dashboard layouts do not fall apart (especially CommandPalette). This
# block therefore only checks that the size is exactly fixed and that an
# attempt to "drag" the corner (where the grip used to be) does not change
# the window.
def _window_scaling():
    """winfo_width()/height() return PHYSICAL pixels (e.g. 1770x1140 at
    150% DPI), while WINDOW_W/H are logical 1080p values - without
    rescaling the comparison would fail on every machine with
    scale != 100%."""
    try:
        from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
        return float(ScalingTracker.get_window_scaling(root) or 1.0)
    except Exception:
        return 1.0


@step(300, )
def s_resize_begin():
    root.update_idletasks()
    state["size0"] = (root.winfo_width(), root.winfo_height())
    scaling = _window_scaling()
    expected = (round(app.WINDOW_W * scaling), round(app.WINDOW_H * scaling))
    # +-1 px: CTk geometry() rounds, but minsize/maxsize truncates. On a
    # small screen (app scaled down, `ui_kit.umiestni_pevne_okno`) the window
    # is therefore a pixel smaller than round(...), e.g. 1539x991 vs
    # 1540x992.
    sedi = all(abs(a - b) <= 1 for a, b in zip(state["size0"], expected))
    rec("window opens at the fixed size (WINDOW_W x WINDOW_H, scaled)",
        sedi, f"{state['size0']} expected {expected} (scaling={scaling})")
    grips = getattr(root, "_resize_grips", [])
    rec("no manual resize grips (fixed window by design)", len(grips) == 0, str(len(grips)))
    x = root.winfo_rootx() + root.winfo_width() - 4
    y = root.winfo_rooty() + root.winfo_height() - 4
    state["grip_pt"] = (x, y)
    mouse_to(x, y)


@step(250, )
def s_resize_down():
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)


for _i in range(1, 7):
    def _rz(i=_i):
        x, y = state["grip_pt"]
        mouse_to(x + 120 * i // 6, y + 80 * i // 6)
    _rz.__name__ = f"resize_move_{_i}"
    step(200 if _i == 1 else 40)(_rz)


@step(80, )
def s_resize_up():
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(400, )
def s_resize_check():
    root.update_idletasks()
    w1, h1 = root.winfo_width(), root.winfo_height()
    w0, h0 = state["size0"]
    rec("dragging the SE corner does NOT resize the window (no grips left)",
        (w1, h1) == (w0, h0), f"{(w0, h0)} -> {(w1, h1)}")
    rec("window still frameless", bool(root.overrideredirect()))
    shot("01d_after_resize_attempt")


@step(400, )
def s_alignment_forms():
    root.update_idletasks()
    # IP / port / heart rate: fields and labels on one axis
    app.sidebar._select("vhre")
    root.update_idletasks()
    xs = [e.winfo_rootx() for e in (app.hr_ip_entry, app.hr_port_entry, app.hr_critical_bpm_entry)]
    rec("V hre: IP / port / BPM entries share one x axis", len(set(xs)) == 1, str(xs))
    # visuals: 4 names (with emoji in a fixed column) start at the same x
    rows = app.vhre_slot_rows
    tx = [r.title_label.winfo_rootx() for r in rows]
    cx = [r.control.winfo_rootx() + r.control.winfo_width() for r in rows]
    rec("V hre: 4 visual rows - titles start at the same x (emoji in fixed column)", len(set(tx)) == 1, str(tx))
    rec("V hre: 4 visual rows - switches end on the same x", len(set(cx)) == 1, str(cx))


@step(500, )
def s_alignment_shot():
    shot("01e_vhre_aligned")
    app.sidebar._select("dnes")


@step(300, )
def s_dock_and_hook():
    # Start/Stop is no longer a button in QuickDock (redesign "Sumi noc")
    # - the only control is the enso in the middle of the sidebar, the
    # state is carried by the colour (_live).
    rec("enso: idle color before listening starts", app.sidebar.enso._live is False)
    rec("Dnes: empty state (preview + pair button) visible without a watch", app.dnes_empty.winfo_ismapped())
    rec("Dnes: live chart/load hidden while no watch (replaced by empty state)", not app.dnes_live.winfo_ismapped())
    root.update()
    root.update_idletasks()
    # QuickDock (🔊 / 😴 / ⌘) is NO LONGER in the row - removed deliberately,
    # see `app.py` at `_build_ui`. This used to check whether its three icons
    # fit into the narrow panel. Now it checks what was left after it: that
    # nothing else sticks out of the narrow row, and that the snooze still
    # has somewhere to be visible (otherwise it could be switched on with a
    # shortcut and would show nowhere).
    sb_right = app.sidebar.winfo_rootx() + app.sidebar.winfo_width()
    prvky = [w for w in app.sidebar.winfo_children() if w.winfo_ismapped()]
    rights = [w.winfo_rootx() + w.winfo_width() for w in prvky]
    rec("sidebar: nothing sticks out of the narrow rail",
        bool(prvky) and max(rights) <= sb_right,
        f"max={max(rights) if rights else '?'} sidebar_right={sb_right}")
    rec("sidebar: state dot can show snoozed",
        hasattr(app.sidebar.state_dot, "set_snoozed"))
    rec("quick dock is gone", getattr(app, "quick_dock", None) is None)
    shot("01f_dnes_compact")
    # start listening. NOTE: here was also `state["counts0"] = dict(...)` -
    # the baseline for the keyboard hook check, which no longer exists (see
    # `s_stop_listening` below).
    app.toggle_listening()


@step(900, )
def s_enso_while_listening():
    rec("enso: live color while listening", app.sidebar.enso._live is True)
    # Arming ("body holding high, waiting for a pause") is an INNER ring, not
    # a third colour - that is why `_live` stays a bare bool and the flag is
    # next to it.
    #
    # CHANGE FROM THE PREVIOUS VERSION: the set is no longer rendered lazily
    # at the first arming, but is FILLED IN IN THE BACKGROUND right from
    # start. Lazy rendering meant over 280 ms of frozen window at 150 px
    # exactly at the moment the app armed. Now start costs ~20 ms and both
    # sets are done within ~1.2 s, while the player is still getting their
    # bearings.
    enso = app.sidebar.enso
    rec("enso: armed ring not armed yet", enso._armed is False)
    # CHANGE (2.1): the enso is no longer a widget with 80 precomputed Tk
    # frames, but a drawing on the Canvas of the Today centre (`_EnsoHero`) -
    # the box over the dojo disappeared with that. Frames are rendered ON
    # REQUEST and cached by phase, no `_build_queue`. We check that render
    # returns an image for both the live and the armed state (and that the
    # resampling threshold by size holds via BIG_PX).
    px = int(app.ENSO_SIZE)
    rec("enso: renders a live frame on demand", enso.render(px) is not None)
    enso.set_armed(True)
    root.update()
    rec("enso: armed ring shows instantly (on-demand render)",
        enso._armed is True and enso.render(px) is not None)
    enso.set_armed(False)
    root.update()
    rec("enso: armed ring clears again", enso._armed is False)
    rec("listening starts in a NON-elevated process", app.listening and not is_elevated())
    # NOTE: here a REAL key of slot 0 was sent (`VkKeyScanW` + two
    # `keybd_event`) and the next step checked that a cue popped up on it.
    # Removed in 2.1b/A2, because that check HAD NO WAY TO PASS:
    #   - `fired` counted the increment in `app.session_counts`
    #   - `session_counts` only increases at `source=="trigger"` (app.py)
    #   - and nobody calls `fire_slot` with such a source any more - phase 3
    #     removed the keyboard hook and the body triggers the cue
    # So the check always saw 0 and lit up green. A green colour that means
    # nothing is worse than a missing test.


@step(1200, )
def s_stop_listening():
    app.toggle_listening()
    root.update()
    rec("listening stops again", not app.listening)
    try:
        app.overlay_manager.stop_all()
    except Exception:
        pass


# ---------------- 2. pages + Today jump ----------------
def make_page_step(key, name):
    def fn():
        app.sidebar._select(key)
    fn.__name__ = f"page_{key}"
    step(120, fn)

    def snap():
        shot(name)
        if key == "dnes":
            g = kamae_geom()
            state.setdefault("g_dnes", []).append(g)
    snap.__name__ = f"snap_{key}"
    step(500, snap)


for _k, _n in (("historia", "02a_historia_empty"), ("spustace", "02_spustace"),
               ("zvuk", "03_zvuk"), ("vhre", "04_vhre"),
               ("guide", "05_guide"), ("nastavenia", "06_nastavenia"), ("dnes", "07_dnes_back")):
    make_page_step(_k, _n)


@step(50, )
def s_bounce():
    # quick switch there and back + measurements at several moments
    app.sidebar._select("spustace")


@step(250, )
def s_bounce_back():
    app.sidebar._select("dnes")
    state["g_ticks"] = [kamae_geom()]


for _d in (40, 120, 300, 600):
    def _m():
        state["g_ticks"].append(kamae_geom())
    _m.__name__ = f"measure_{_d}"
    step(_d, _m)


@step(50, )
def s_eval_jump():
    g0 = state["g0"]
    keys = [k for k in g0 if k not in ("root_x", "root_y")]
    diffs = []
    for g in state.get("g_dnes", []) + state.get("g_ticks", []):
        for k in keys:
            if g[k] != g0[k]:
                diffs.append(f"{k}: {g0[k]} -> {g[k]}")
    rec("Dnes layout stable after page switches (no jump)", not diffs, "; ".join(sorted(set(diffs))) or "all equal")
    print("ticks:", state["g_ticks"])


# ---------------- 3. KamaeBar breathing ----------------
@step(50, )
def s_live_on():
    app.kamae.set_live(True)
    state["live_geoms"] = []


for _d in (200, 400, 700, 1000, 1400):
    def _lm():
        state["live_geoms"].append(kamae_geom())
    _lm.__name__ = f"live_measure_{_d}"
    step(_d, _lm)
    if _d in (400, 1400):
        def _ls(d=_d):
            shot(f"08_kamae_live_{d}", widget=app.kamae)
        _ls.__name__ = f"live_shot_{_d}"
        step(10, _ls)


@step(50, )
def s_live_off():
    app.kamae.set_live(False)
    g0 = state["g0"]
    bad = [f"{k}:{g[k]}" for g in state["live_geoms"] for k in ("kamae_h", "canvas_h", "root_h", "wrap_h") if g[k] != g0[k]]
    rec("KamaeBar breathing keeps height constant", not bad, "; ".join(bad) or "stable")
    shot("09_kamae_idle", widget=app.kamae)


# ---------------- 4. sliders and the mouse wheel ----------------
def find_sliders(w, acc):
    for c in w.winfo_children():
        if isinstance(c, ctk.CTkSlider):
            acc.append(c)
        find_sliders(c, acc)
    return acc


def page_of(widget):
    w = widget
    while w is not None and w is not root:
        for key, frame in app.pages.pages.items():
            if w is frame:
                return key
        w = w.master
    return None


def scroll_frame_of(widget):
    w = widget.master
    while w is not None:
        if isinstance(w, ctk.CTkScrollableFrame):
            return w
        w = getattr(w, "master", None)
    return None


@step(100, )
def s_collect_sliders():
    sliders = find_sliders(root, [])
    state["sliders"] = sliders
    # 6 sliders on the pages: Sound has 4 (cooldown, volume, balance,
    # speech rate) and In-game 2 (size + opacity of the HUD panel).
    # NOTE: 7 were expected here - the seventh was "Dojo background" in
    # Settings, which disappeared along with the photo strip above the title
    # bar. Without this fix the harness reports a false FAIL and hides real
    # regressions.
    rec("sliders found on pages (4 more live in dialogs)", len(sliders) == 6, f"{len(sliders)} sliders: " + ", ".join(sorted(set(page_of(s) or '?' for s in sliders))))


def make_slider_steps(idx):
    def show():
        s = state["sliders"][idx]
        key = page_of(s)
        app.sidebar._select(key)
        state["cur_key"] = key
    show.__name__ = f"slider{idx}_show"
    step(60, show)

    def scroll_into_view():
        s = state["sliders"][idx]
        sf = scroll_frame_of(s)
        state["cur_sf"] = sf
        if sf is not None:
            root.update_idletasks()
            # move the scroll so that the slider is visible (approx)
            try:
                canvas = sf._parent_canvas
                inner_h = sf.winfo_height()
                cy = s.winfo_rooty() - sf.winfo_rooty()
                if cy > canvas.winfo_height() - 40 or cy < 0:
                    frac = max(0.0, min(1.0, (cy + canvas.yview()[0] * inner_h - 100) / max(1, inner_h)))
                    canvas.yview_moveto(frac)
            except Exception as exc:
                print("scroll into view failed", exc)
    scroll_into_view.__name__ = f"slider{idx}_scroll"
    step(60, scroll_into_view)

    def real_wheel():
        s = state["sliders"][idx]
        root.update_idletasks()
        x = s.winfo_rootx() + s.winfo_width() // 2
        y = s.winfo_rooty() + s.winfo_height() // 2
        state["v0"] = s.get()
        sf = state["cur_sf"]
        state["y0"] = sf._parent_canvas.yview()[0] if sf is not None else None
        mouse_to(x, y)
        state["cursor_pos"] = (x, y)
    real_wheel.__name__ = f"slider{idx}_move"
    step(80, real_wheel)

    def send_wheel():
        user32.mouse_event(WHEEL, 0, 0, -120, 0)
    send_wheel.__name__ = f"slider{idx}_wheel"
    step(120, send_wheel)
    step(120, send_wheel)

    def check():
        s = state["sliders"][idx]
        v1 = s.get()
        sf = state["cur_sf"]
        y1 = sf._parent_canvas.yview()[0] if sf is not None else None
        hit = hit_root(*state["cursor_pos"]) == top_hwnd(root)
        detail = f"page={state['cur_key']} value {state['v0']} -> {v1}; scroll {state['y0']} -> {y1}; cursor over app={hit}"
        rec(f"slider {idx} ({state['cur_key']}): REAL wheel does not change value", abs(v1 - state["v0"]) < 1e-9, detail)
        state.setdefault("scroll_moved", []).append((state["cur_key"], state["y0"], y1))
        # event_generate variant (independent of focus/foreground)
        s.set(state["v0"])
        v_before = s.get()
        s._canvas.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
        root.update()
        v_after = s.get()
        rec(f"slider {idx} ({state['cur_key']}): event_generate wheel does not change value", abs(v_after - v_before) < 1e-9, f"{v_before} -> {v_after}")
        s.set(state["v0"])
    check.__name__ = f"slider{idx}_check"
    step(150, check)


for _i in range(6):
    make_slider_steps(_i)


# ---------------- 5. drag & drop of the visual test ----------------
@step(100, )
def s_overlay_begin():
    app.sidebar._select("vhre")
    cfg = app.overlay_configs[0]
    state["pos0"] = (cfg["pos_x"], cfg["pos_y"])
    app.toggle_overlay_test(0)


@step(900, )
def s_overlay_inspect():
    slot = app.overlay_manager._slots[0]
    surf = slot.surface
    rec("test mode: overlay window exists", surf is not None and surf.top is not None, f"mode={getattr(surf, 'mode', None)}")
    hwnd = top_hwnd(surf.top)
    state["ov_hwnd"] = hwnd
    ex = exstyle(hwnd)
    rec("test mode: WS_EX_TRANSPARENT cleared", not (ex & 0x20), f"exstyle=0x{ex:08x} layered={bool(ex & 0x80000)} noactivate={bool(ex & 0x8000000)}")
    l, t, r, b = win_rect(hwnd)
    state["ov_rect"] = (l, t, r, b)
    print("overlay rect", (l, t, r, b), "tk:", surf.top.winfo_x(), surf.top.winfo_y(), slot.w, slot.h)
    hits, pts, first = 0, 0, None
    n = 9
    for iy in range(n):
        for ix in range(n):
            x = l + int((r - l) * (ix + 0.5) / n)
            y = t + int((b - t) * (iy + 0.5) / n)
            pts += 1
            if hit_root(x, y) == hwnd:
                hits += 1
                if first is None:
                    first = (x, y)
    state["ov_hit"] = (hits, pts, first)
    cx, cy = (l + r) // 2, (t + b) // 2
    center_hit = hit_root(cx, cy) == hwnd
    rec("test mode: overlay window is hit-testable on (almost) whole area", hits >= pts * 0.95, f"{hits}/{pts} grid points hit; center hit={center_hit}")
    state["drag_from"] = (cx, cy) if center_hit else first
    # drag direction: towards the monitor centre, so the cursor does not
    # hit the edge of the screen
    mon = app.overlay_manager.target_monitor()
    mcx, mcy = mon.x + mon.width / 2, mon.y + mon.height / 2
    global DX, DY
    DX = 180 if cx < mcx else -180
    DY = 120 if cy < mcy else -120
    from i18n import tr
    btn = app.vhre_test_buttons[0]
    rec("test button says 'Hotovo'", btn.cget("text") == tr("overlay.test_done"), btn.cget("text"))
    shot("10_overlay_test_before_drag", bbox=(l - 40, t - 40, r + 40, b + 40))


@step(100, )
def s_drag_hover():
    if state.get("drag_from"):
        mouse_to(*state["drag_from"])


@step(250, )
def s_drag_cursor():
    if not state.get("drag_from"):
        rec("cursor over overlay is fleur", False, "no hit point")
        return
    h = cursor_handle()
    fleur = user32.LoadCursorW(None, IDC_SIZEALL)
    rec("cursor over overlay is fleur (IDC_SIZEALL)", h == fleur, f"hCursor={h} fleur={fleur}")


@step(50, )
def s_drag_down():
    if state.get("drag_from"):
        slot = app.overlay_manager._slots[0]
        state["ov_xy0"] = (slot.surface.top.winfo_x(), slot.surface.top.winfo_y())
        user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)


DX, DY, N = 180, 120, 12
for _i in range(1, N + 1):
    def _mv(i=_i):
        if state.get("drag_from"):
            x0, y0 = state["drag_from"]
            mouse_to(x0 + DX * i // N, y0 + DY * i // N)
    _mv.__name__ = f"drag_move_{_i}"
    step(35, _mv)


@step(60, )
def s_drag_up():
    if state.get("drag_from"):
        user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(400, )
def s_drag_check():
    slot = app.overlay_manager._slots[0]
    if slot.surface is None or slot.surface.top is None:
        rec("overlay dragged by real mouse", False, "surface gone")
        return
    x1, y1 = slot.surface.top.winfo_x(), slot.surface.top.winfo_y()
    x0, y0 = state.get("ov_xy0", (None, None))
    ok = x0 is not None and abs((x1 - x0) - DX) <= 6 and abs((y1 - y0) - DY) <= 6
    rec("overlay dragged by real mouse (moved by DX,DY)", ok, f"from {(x0, y0)} to {(x1, y1)}; expected +({DX},{DY})")
    state["ov_xy1"] = (x1, y1)
    l, t, r, b = win_rect(state["ov_hwnd"])
    shot("11_overlay_test_after_drag", bbox=(l - 40, t - 40, r + 40, b + 40))
    rec("overlay still in test mode after drag", slot._test_mode and slot.surface is not None)


@step(100, )
def s_stop_test():
    app.toggle_overlay_test(0)


@step(400, )
def s_stop_check():
    slot = app.overlay_manager._slots[0]
    cfg = app.overlay_configs[0]
    rec("after 'Hotovo': overlay hidden, test mode off", slot.surface is None and not slot._test_mode)
    rec("after 'Hotovo': position saved to config", (cfg["pos_x"], cfg["pos_y"]) != state["pos0"], f"{state['pos0']} -> {(cfg['pos_x'], cfg['pos_y'])}")
    try:
        with open(os.path.join(PROJ, "dandurf_settings.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        disk = data.get("overlay_configs", data.get("overlay", {}))
        print("disk overlay cfg:", json.dumps(disk)[:300])
        d0 = disk[0] if isinstance(disk, list) else disk.get("0") or disk.get(0)
        rec("position persisted to dandurf_settings.json", d0 and (d0.get("pos_x"), d0.get("pos_y")) == (cfg["pos_x"], cfg["pos_y"]), str(d0))
    except Exception as exc:
        rec("position persisted to dandurf_settings.json", False, repr(exc))
    from i18n import tr
    btn = app.vhre_test_buttons[0]
    rec("test button back to 'Test'", btn.cget("text") == tr("overlay.test"), btn.cget("text"))
    # re-test: it should appear at the new position
    app.toggle_overlay_test(0)


@step(700, )
def s_retest_pos():
    slot = app.overlay_manager._slots[0]
    if slot.surface is None:
        rec("re-test opens at saved position", False, "no surface")
        return
    x, y = slot.surface.top.winfo_x(), slot.surface.top.winfo_y()
    x1, y1 = state["ov_xy1"]
    rec("re-test opens at saved (dragged) position", abs(x - x1) <= 3 and abs(y - y1) <= 3, f"{(x, y)} vs {(x1, y1)}")
    # testing another slot switches off the first
    app.toggle_overlay_test(1)


@step(700, )
def s_other_slot():
    s0, s1 = app.overlay_manager._slots[0], app.overlay_manager._slots[1]
    rec("starting test on slot 1 stops slot 0 test", (not s0._test_mode) and s0.surface is None and s1._test_mode and s1.surface is not None)
    from i18n import tr
    rec("slot 0 button back to 'Test', slot 1 says 'Hotovo'",
        app.vhre_test_buttons[0].cget("text") == tr("overlay.test")
        and app.vhre_test_buttons[1].cget("text") == tr("overlay.test_done"))
    if s1.surface is not None:
        hwnd = top_hwnd(s1.surface.top)
        l, t, r, b = win_rect(hwnd)
        n = 9
        hits = sum(1 for iy in range(n) for ix in range(n)
                   if hit_root(l + int((r - l) * (ix + 0.5) / n), t + int((b - t) * (iy + 0.5) / n)) == hwnd)
        rec("slot 1 (jaw) test window hit-testable on whole area", hits >= n * n * 0.95, f"{hits}/{n*n}")
        shot("12_overlay_test_slot1", bbox=(l - 40, t - 40, r + 40, b + 40))
    app.toggle_overlay_test(1)


@step(400, )
def s_normal_play():
    # an ordinary run (not a test) must have click-through back
    slot = app.overlay_manager._slots[0]
    rec("slot 1 stopped", app.overlay_manager._slots[1].surface is None)
    slot.play()


@step(500, )
def s_normal_check():
    slot = app.overlay_manager._slots[0]
    if slot.surface is None:
        rec("normal play: window exists", False)
        return
    hwnd = top_hwnd(slot.surface.top)
    ex = exstyle(hwnd)
    rec("normal play: WS_EX_TRANSPARENT set (click-through)", bool(ex & 0x20), f"exstyle=0x{ex:08x}")
    slot.stop()
    # put the original position of slot 0 back into the config
    app.on_overlay_config_change(0, pos=state["pos0"])
    cfg = app.overlay_configs[0]
    rec("restored original slot 0 position", (cfg["pos_x"], cfg["pos_y"]) == state["pos0"], str(state["pos0"]))


# ---------------- 6. dialog with its own title bar ----------------
@step(200, )
def s_dialog_open():
    # a transient dialog is not topmost - if root stayed topmost, it would
    # cover it and a real click on the bar would go to root (a harness
    # artefact, not the app's)
    root.attributes("-topmost", False)
    import ui_dialogs
    state["pair_dlg"] = ui_dialogs.WatchPairingDialog(app)   # like open_watch_pairing, plus a reference
    d = state["pair_dlg"]
    ip = d._local_ip()
    ips = d._local_ips()
    rec("pairing: _local_ip() returns a real LAN IP (not 127.x, not empty)",
        bool(ip) and not str(ip).startswith("127.") and not str(ip).startswith("169.254."), str(ip))
    rec("pairing: candidates list has the preferred IP first", ips and ips[0] == ip, str(ips))
    # Hidden IP (0.2): the address is hidden until the player clicks "Show IP".
    rec("pairing: IP hidden until 'Show IP', port visible",
        ip and str(ip) not in d.ip_label.cget("text")
        and str(app.hr_port) in d.ip_label.cget("text"), d.ip_label.cget("text"))
    d._toggle_ip()
    rec("pairing: 'Show IP' reveals the IP and port", ip and str(ip) in d.ip_label.cget("text")
        and str(app.hr_port) in d.ip_label.cget("text"), d.ip_label.cget("text"))
    d._toggle_ip()          # back to hidden, so the harness does not leave the IP exposed


@step(800, )
def s_dialog_inspect():
    tops = [c for c in root.winfo_children() if isinstance(c, tk.Toplevel) and c.winfo_viewable()]
    state["dlg"] = None
    for t in tops:
        try:
            if t.title() and "hodink" in t.title().lower() or "spár" in t.title().lower() or "pair" in t.title().lower():
                state["dlg"] = t
        except Exception:
            pass
    if state["dlg"] is None and tops:
        state["dlg"] = tops[-1]
    dlg = state["dlg"]
    rec("pairing dialog opened", dlg is not None, f"toplevels={[t.title() for t in tops]}")
    if dlg is None:
        return
    rec("dialog is frameless (overrideredirect)", bool(dlg.overrideredirect()))
    f = root.focus_get()
    rec("dialog has keyboard focus", f is not None and f.winfo_toplevel() is dlg, f"focus={f}")
    rec("dialog has grab", root.grab_current() is not None and root.grab_current().winfo_toplevel() is dlg, f"grab={root.grab_current()}")
    shot("13_dialog", widget=dlg)
    state["dlg_xy0"] = (dlg.winfo_x(), dlg.winfo_y())
    # real drag by the bar (17 px from the top, left of the cross)
    state["dlg_bar"] = (dlg.winfo_rootx() + 200, dlg.winfo_rooty() + 17)
    rec("dialog bar is under the cursor point (not covered)", hit_root(*state["dlg_bar"]) == top_hwnd(dlg),
        f"hit={hit_root(*state['dlg_bar'])} dlg={top_hwnd(dlg)}")
    mouse_to(*state["dlg_bar"])


@step(120, )
def s_dialog_down():
    if state.get("dlg") is not None:
        user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)


for _i in range(1, 9):
    def _dm(i=_i):
        if state.get("dlg") is not None:
            x, y = state["dlg_bar"]
            mouse_to(x + 80 * i // 8, y + 60 * i // 8)
    _dm.__name__ = f"dlg_move_{_i}"
    step(35, _dm)


@step(60, )
def s_dialog_up():
    if state.get("dlg") is not None:
        user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(300, )
def s_dialog_drag_check():
    dlg = state.get("dlg")
    if dlg is None:
        return
    x1, y1 = dlg.winfo_x(), dlg.winfo_y()
    x0, y0 = state["dlg_xy0"]
    rec("dialog dragged by its own bar", abs((x1 - x0) - 80) <= 6 and abs((y1 - y0) - 60) <= 6, f"{(x0, y0)} -> {(x1, y1)}")
    # real Escape
    user32.keybd_event(0x1B, 0, 0, 0)
    user32.keybd_event(0x1B, 0, 2, 0)


@step(400, )
def s_dialog_escape_check():
    dlg = state.get("dlg")
    if dlg is None:
        return
    rec("dialog closes on real Escape key", not dlg.winfo_exists())
    if dlg.winfo_exists():
        try:
            dlg.destroy()
        except Exception:
            pass
    root.attributes("-topmost", True)


# ---------------- 6a. Session history, info panels, sources, analysis ---------------
# HR_SESSIONS / HR_INSIGHTS are at the top with the data backup - the copy
# from before the run is on disk from the start (`zaloz_zalohy`), nothing
# is put aside in memory here any more.


def _odloz_historiu_tepu():
    """Empty history test: the files disappear for a moment. Only a file
    whose copy from before the run is on disk (or that did not exist
    before the run) is deleted - without it, interrupting the run would
    delete the history forever."""
    for p in (HR_SESSIONS, HR_INSIGHTS):
        if not os.path.exists(p):
            continue
        if os.path.exists(p + ZALOHA) or os.path.exists(p + NEBOL):
            os.remove(p)
        else:
            rec("history: %s left in place - no backup on disk" % os.path.basename(p),
                False, "backup missing, not deleting real data")


def _vrat_historiu_tepu():
    """Puts the pre-run history back; the backup stays until the run ends."""
    vrat_zalohy((HR_SESSIONS, HR_INSIGHTS), nechat_zalohy=True)


@step(200, )
def s_history_empty():
    _odloz_historiu_tepu()
    app.sidebar._select("historia")
    app._refresh_history_page()


@step(400, )
def s_history_empty_check():
    from i18n import tr
    box = app.history_sessions_box
    labels = [w for w in box.winfo_children() if isinstance(w, ctk.CTkLabel)]
    rec("history: empty history shows the empty-state text (no crash)",
        len(labels) == 1 and labels[0].cget("text") == tr(
            "history.empty", page=app._nazov_vhre()))
    rec("history: trend chart drawn empty without error", app.history_trend.winfo_ismapped())
    shot("21_history_empty")
    # synthetic sessions via real HeartStats (the same fields as the app)
    import hr_stats, json, time as _t
    sessions = []
    now = _t.time()
    for i in range(8):
        st = hr_stats.HeartStats(110)
        base = 60 + i          # rising baseline
        t0 = now - (10 - i) * 86400
        vals = [base] * 300 + [base + 70] + [base + 70 - (25 * k / 60.0) for k in range(1, 61)] + [base + 5] * 600
        for k, v in enumerate(vals):
            st.add(v, ts=t0 + k)
        st.session_start = t0
        st.note_trigger(ts=t0 + 400)
        s = st.summary()
        s["duration_s"] = len(vals)
        s["started"] = t0
        sessions.append(s)
    with open(HR_SESSIONS, "w", encoding="utf-8") as fh:
        json.dump(sessions, fh)
    state["hr_synth"] = sessions
    app._refresh_history_page()


@step(500, )
def s_history_filled_check():
    box = app.history_sessions_box
    rows = [w for w in box.winfo_children() if isinstance(w, ctk.CTkFrame) and w.cget("height") != 1]
    rec("history: table shows 8 sessions (+ header)", len(rows) == 9, f"rows={len(rows)}")
    # Periods (redesign "Sumi noc"): the trend chart now filters to the
    # chosen period and buckets (day/month/year - see
    # hr_stats.aggregate_by_period). The test sessions are 3-10 days old, all
    # in the same calendar month - "Month" (bucket=day) gives exactly 8
    # separate points, "Week" would not necessarily catch them all.
    import hr_stats as _hrs
    app._set_history_period(_hrs.PERIOD_MONTH)
    root.update_idletasks()
    rec("history: trend series has 8 points (period=month, daily buckets)",
        len(app.history_trend._values) == 8, str(app.history_trend._values))
    rec("history: trend caption is baseline + delta text", "→" in app.history_trend_delta.cget("text"),
        app.history_trend_delta.cget("text"))
    synth = state["hr_synth"][-1]
    rec("history: synthetic sessions carry HRR/HRPI/baseline/zones",
        synth.get("hrr_bpm") is not None and synth.get("hrpi", 0) > 0 and synth.get("baseline_bpm")
        and sum(synth.get("zone_seconds", {}).values()) > 0,
        f"hrr={synth.get('hrr_bpm')} hrpi={synth.get('hrpi')} base={synth.get('baseline_bpm')}")
    # info rows: expanding
    info = app.history_info_hrr
    rec("history: HRR info row closed by default", not info.is_open)
    # CTkButton (ctk 6) calls command on <ButtonRelease-1> and only when
    # there was an <Enter> before (_mouse_inside) - we simulate the whole
    # mouse pass
    cv = getattr(info.toggle, "_canvas", info.toggle)
    cv.event_generate("<Enter>", x=5, y=5)
    cv.event_generate("<Button-1>", x=5, y=5)
    cv.event_generate("<ButtonRelease-1>", x=5, y=5)
    root.update()
    rec("history: click on 'ⓘ what it means' opens the explanation",
        info.is_open and info.more.winfo_ismapped())
    from i18n import tr
    rec("history: HRR explanation text is the exact wording",
        info.more.cget("text") == tr("metric.hrr.more"))
    # the load info lives in dnes_live, which is hidden without the watch
    # (an empty state is there instead) - it exists, it shows after
    # connecting
    rec("history: Dnes page has info rows for BPM (visible) and load (in live frame)",
        app.dnes_info_bpm.winfo_ismapped() and app.dnes_info_load.winfo_exists()
        and app.dnes_info_load.master is app.dnes_live)
    # the "How it came about" panel (the author's text + three examples)
    rec("history: science panel collapsed by default", not app.history_science_body.winfo_ismapped())
    app._toggle_history_science()
    root.update()
    rec("history: science panel expands with intro + links",
        app.history_science_body.winfo_ismapped() and len(app.history_source_links) == 3,
        f"links={len(app.history_source_links)}")
    shot("22_history_filled")


@step(300, )
def s_history_link():
    # The History page lives in the app_history mixin - `webbrowser` is
    # slipped in directly on the shared module (the same object as
    # `app.webbrowser` before).
    import webbrowser
    state["opened"] = []
    state["_wb"] = webbrowser.open
    webbrowser.open = lambda u, *a, **k: state["opened"].append(u) or True
    link, url = app.history_source_links[0]
    state["link_url"] = url
    root.update_idletasks()
    app.history_scroll._parent_canvas.yview_moveto(1.0)
    root.update_idletasks()
    mouse_to(*[link.winfo_rootx() + 30, link.winfo_rooty() + link.winfo_height() // 2])


@step(200, )
def s_history_link_click():
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(400, )
def s_history_link_check():
    import webbrowser
    rec("history: REAL click on '↗ source' opens the study URL in the browser",
        state["opened"] == [state["link_url"]], str(state["opened"]))
    webbrowser.open = state["_wb"]
    # background analysis: a slowed-down analysis must not block the UI
    import hr_insights as hi
    state["_analyze"] = hi.analyze

    def slow_analyze(sessions, now=None):
        time.sleep(2.0)
        return state["_analyze"](sessions, now)
    hi.analyze = slow_analyze
    state["ticks"] = []
    state["t_start"] = time.perf_counter()

    def tick():
        state["ticks"].append(time.perf_counter())
        if len(state["ticks"]) < 8:
            root.after(200, tick)
    root.after(200, tick)
    app.run_hr_analysis()
    app.sidebar._select("zvuk")
    root.update()
    state["switched"] = page_on_top() == "zvuk"
    app.sidebar._select("historia")


@step(2600, )
def s_history_analysis_check():
    import hr_insights as hi
    hi.analyze = state["_analyze"]
    gaps = [b - a for a, b in zip(state["ticks"], state["ticks"][1:])]
    rec("history: UI kept ticking while analysis ran in background (max gap < 0.6 s)",
        len(state["ticks"]) >= 8 and max(gaps) < 0.6, f"gaps={[round(g, 2) for g in gaps]}")
    rec("history: page switch worked during analysis", state["switched"])
    rec("history: analysis thread finished and insights rendered",
        not app._hr_analysis_thread.is_alive() and app._hr_insights
        and any(w.winfo_ismapped() for w in app.history_insights_box.winfo_children()),
        str([i.get("key") for i in app._hr_insights]))
    rec("history: insights persisted to hr_insights.json", os.path.exists(HR_INSIGHTS))
    keys = [i.get("key") for i in app._hr_insights]
    rec("history: rising synthetic baseline detected as 'resting_up'", "resting_up" in keys, str(keys))
    shot("23_history_insights")
    _vrat_historiu_tepu()
    app._refresh_history_page()
    app.sidebar._select("dnes")


# ---------------- 6b. pictogram colour (config + render) ----------------
@step(200, )
def s_color_set():
    app.sidebar._select("vhre")
    state["color0"] = app.overlay_configs[0].get("color")
    app.on_overlay_config_change(0, color="#ff2020")
    rec("color stored in config as #rrggbb", app.overlay_configs[0]["color"] == "#ff2020", str(app.overlay_configs[0]["color"]))
    with open(os.path.join(PROJ, "dandurf_settings.json"), encoding="utf-8") as fh:
        disk = json.load(fh)["overlay_configs"][0].get("color")
    rec("color persisted to settings file", disk == "#ff2020", str(disk))
    app.toggle_overlay_test(0)


@step(900, )
def s_color_check():
    slot = app.overlay_manager._slots[0]
    if slot.surface is None:
        rec("colored test visual rendered", False, "no surface")
        return
    hwnd = top_hwnd(slot.surface.top)
    l, t, r, b = win_rect(hwnd)
    img = grab("16_overlay_red", (l, t, r, b))
    if img is None:
        return
    px = img.load()
    red = sum(1 for y in range(0, img.height, 2) for x in range(0, img.width, 2)
              if px[x, y][0] > 150 and px[x, y][1] < 110 and px[x, y][2] < 110)
    rec("test visual uses the custom color (red pixels present)", red > 40, f"red-ish samples={red}")
    app.toggle_overlay_test(0)
    app.on_overlay_config_change(0, color=state["color0"] or "")
    rec("color reset to theme", app.overlay_configs[0].get("color") == (state["color0"] or None))


# ---------------- 6c. bulk slot selection ----------------
# 0.2: the four categories (slots 0-3) are fixed - they have no checkbox
# or ✕, they are switched off with a toggle. Only extra slots from 0.1
# (index 4+) can be bulk-removed, so we temporarily add two of them here.
# finish() restores the settings.
@step(300, )
def s_bulk_select_all():
    import app as app_mod
    from settings_model import normalize_slot
    app.sidebar._select("spustace")
    state["msgs"] = []
    app_mod.messagebox.showinfo = lambda *a, **k: state["msgs"].append(("info",) + a)
    app_mod.messagebox.askyesno = lambda *a, **k: (state["msgs"].append(("yesno",) + a) or True)
    app.rebuild_slots(app.slot_dicts() + [normalize_slot({"text": "extra A"}),
                                          normalize_slot({"text": "extra B"})])
    state["n_slots"] = len(app.slots)
    for slot in app.slots:
        slot.set_selected(True)
    app._on_slot_selection_change()


@step(300, )
def s_bulk_all_check():
    from i18n import tr
    bar = app.bulk_bar
    kategorie = app.slots[:4]
    rec("category slots have no checkbox and cannot be selected",
        all(s.select_check is None and not s.selected for s in kategorie),
        str([(s.select_check is None, s.selected) for s in kategorie]))
    rec("bulk bar visible when extra slots selected", bool(bar.winfo_ismapped()),
        f"label={app.bulk_label.cget('text')}")
    rec("bulk label counts only the extra slots",
        app.bulk_label.cget("text") == tr("slots.selected_count", n=state["n_slots"] - 4),
        app.bulk_label.cget("text"))
    shot("17_bulk_bar")
    app.remove_selected_slots()


@step(500, )
def s_bulk_two_check():
    rec("removing the extra slots asks once and keeps all four categories",
        len(app.slots) == 4 and [m[0] for m in state["msgs"]] == ["yesno"],
        f"slots={len(app.slots)} msgs={[m[0] for m in state['msgs']]}")
    app.remove_slot(0)
    rec("a category slot cannot be removed", len(app.slots) == 4, f"slots={len(app.slots)}")
    rec("bulk bar hidden after rebuild", not app.bulk_bar.winfo_ismapped())
    rec("nav badge updated (triggers tab)", app.settings_nav._badges.get("spustace") == str(len(app.slots)),
        str(app.settings_nav._badges.get("spustace")))
    shot("18_after_bulk_remove")


# ---------------- 6c2. Today: stats cards (picker, cap, dragging) ----------------
# At most 4 cards (2x2 grid), the last one stays, the order changes by
# dragging a card onto another (swapping places). Dragging is done with the
# REAL mouse: after a press Tk sends motion and release to the widget that
# got the press (implicit grab) - event_generate cannot verify that,
# because it sends straight to the widget.
# The selection is restored at the end of the block; finish() also
# restores all the settings.
DASH_PLNE = ["baseline", "hrr", "over", "breath"]
DASH_SWAP = ["breath", "hrr", "over", "baseline"]       # baseline <-> breath
DASH_N = 8


def _saved_dashboard():
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            return json.load(fh).get("dashboard_stats")
    except Exception as exc:
        return f"unreadable: {exc}"


def _dash_set(stats):
    app.dashboard_stats = list(stats)
    app.save_settings()
    app._rebuild_dashboard_stats_grid()
    root.update_idletasks()


def _dash_lit():
    """Cards with a non-default border (leftover highlight after a drag)."""
    soft = app.pal["line_soft"]
    return {k: c.cget("border_color") for k, c in app.dashboard_cards.items()
            if c.cget("border_color") != soft}


def _dash_order():
    def pos(k):
        info = app.dashboard_cards[k].grid_info()
        return int(info["row"]), int(info["column"])
    return sorted(app.dashboard_cards, key=pos)


def _center(widget):
    return (widget.winfo_rootx() + widget.winfo_width() // 2,
            widget.winfo_rooty() + widget.winfo_height() // 2)


def _hits(widget, x, y):
    w = root.winfo_containing(x, y)
    while w is not None:
        if w is widget:
            return True
        w = getattr(w, "master", None)
    return False


def _picker_rows():
    """[(stat_id, title_label, check_label)] in catalogue order."""
    out = []
    rows = app._dashboard_picker_rows.winfo_children()
    for (sid, _t, _c), row in zip(app._dashboard_stat_catalog(), rows):
        inner = row.winfo_children()[0]
        labels = [w for w in inner.winfo_children() if isinstance(w, ctk.CTkLabel)]
        out.append((sid, labels[0], labels[1]))
    return out


def _dash_picker_check(tag):
    from i18n import tr
    top = app._dashboard_picker
    root.update_idletasks()
    rows = app._dashboard_picker_rows.winfo_children()
    n = len(app._dashboard_stat_catalog())
    cut = [i for i, r in enumerate(rows) if r.winfo_height() < r.winfo_reqheight()]
    rec(f"stats picker: all {n} rows get their full height ({tag})",
        len(rows) == n and not cut, f"rows={len(rows)} cut={cut}")
    frame = top.winfo_children()[0]
    rec(f"stats picker: frame as tall as its content ({tag})",
        frame.winfo_height() >= frame.winfo_reqheight(),
        f"{frame.winfo_height()} vs req {frame.winfo_reqheight()}")
    x0, y0, x1, y1 = ui_kit.work_area(app.dashboard_edit_btn)
    px, py = top.winfo_rootx(), top.winfo_rooty()
    rec(f"stats picker: whole popup on screen ({tag})",
        x0 <= px and px + top.winfo_width() <= x1 and y0 <= py and py + top.winfo_height() <= y1,
        f"popup {px},{py} {top.winfo_width()}x{top.winfo_height()} area={(x0, y0, x1, y1)}")
    hint = [w for w in frame.winfo_children()
            if isinstance(w, ctk.CTkLabel) and w.cget("text") == tr("dashboard.picker_hint")]
    rec(f"stats picker: one quiet hint line ({tag})", len(hint) == 1)
    # full grid: unselected rows faded, clicking them does nothing
    faint = app.pal["text_faint"]
    off = [(sid, t) for sid, t, _c in _picker_rows() if sid not in app.dashboard_stats]
    rec(f"stats picker: with 4 cards the other rows are faint ({tag})",
        off and all(t.cget("text_color") == faint for _s, t in off),
        str([(s, t.cget("text_color")) for s, t in off]))
    before = list(app.dashboard_stats)
    off[0][1]._label.event_generate("<Button-1>", x=3, y=3)
    root.update_idletasks()
    rec(f"stats picker: clicking a faint row adds nothing ({tag})",
        app.dashboard_stats == before, str(app.dashboard_stats))


@step(300, )
def s_dash_setup():
    app.sidebar._select("dnes")
    state["dash0"] = list(app.dashboard_stats)
    _dash_set(DASH_PLNE)
    app._open_dashboard_picker()


@step(400, )
def s_dash_picker_check():
    from app import LANG_NATIVE_LABELS
    _dash_picker_check(app.lang)
    app._close_dashboard_picker()
    state["dash_lang0"] = app.lang
    app.on_lang_switch(LANG_NATIVE_LABELS["de"])


@step(900, )
def s_dash_picker_de():
    app.sidebar._select("dnes")
    root.update_idletasks()
    app._open_dashboard_picker()


@step(400, )
def s_dash_picker_de_check():
    from app import LANG_NATIVE_LABELS
    _dash_picker_check("de")
    app._close_dashboard_picker()
    app.on_lang_switch(LANG_NATIVE_LABELS[state["dash_lang0"]])


@step(900, )
def s_dash_drag_prep():
    app.sidebar._select("dnes")
    _dash_set(DASH_PLNE)
    root.update()                   # winfo_containing needs the windows shown
    cards = app.dashboard_cards
    a = _center(cards["baseline"].value_label)
    b = _center(cards["breath"])
    ok = _hits(cards["baseline"], *a) and _hits(cards["breath"], *b)
    rec("stats drag: held number and target card visible", ok, f"{a} -> {b}")
    state["dash_drag"] = (a, b) if ok else None
    if ok:
        mouse_to(*a)


@step(150, )
def s_dash_down():
    if state.get("dash_drag"):
        user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)


for _i in range(1, DASH_N + 1):
    def _dm(i=_i):
        if state.get("dash_drag"):
            (x0, y0), (x1, y1) = state["dash_drag"]
            mouse_to(x0 + (x1 - x0) * i // DASH_N, y0 + (y1 - y0) * i // DASH_N)
    _dm.__name__ = f"dash_drag_move_{_i}"
    step(200 if _i == 1 else 40)(_dm)


@step(150, )
def s_dash_mid_check():
    if not state.get("dash_drag"):
        return
    cards = app.dashboard_cards
    rec("stats drag: held card has the accent border",
        cards["baseline"].cget("border_color") == app.pal["accent"],
        cards["baseline"].cget("border_color"))
    rec("stats drag: card under the pointer has the accent_hover border",
        cards["breath"].cget("border_color") == app.pal["accent_hover"],
        cards["breath"].cget("border_color"))
    rec("stats drag: cursor is fleur while dragging",
        cursor_handle() == user32.LoadCursorW(None, IDC_SIZEALL))
    rec("stats drag: nothing changes before the release", app.dashboard_stats == DASH_PLNE)


@step(60, )
def s_dash_up():
    if state.get("dash_drag"):
        user32.mouse_event(LEFTUP, 0, 0, 0, 0)


@step(400, )
def s_dash_drag_check():
    rec("stats drag: dropping on another card swaps the two (real mouse)",
        app.dashboard_stats == DASH_SWAP, str(app.dashboard_stats))
    rec("stats drag: the new order is saved", _saved_dashboard() == DASH_SWAP, str(_saved_dashboard()))
    rec("stats drag: cards rebuilt in the new order", _dash_order() == DASH_SWAP, str(_dash_order()))
    rec("stats drag: all borders back to normal", not _dash_lit(), str(_dash_lit()))
    # an ordinary click (no movement) on the card's number
    mouse_to(*_center(app.dashboard_cards["hrr"].value_label))


@step(150, )
def s_dash_click():
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)


def _dash_real_drag(key, name):
    """Press at point state[key][0], drag to state[key][1], release."""
    def down():
        if state.get(key):
            mouse_to(*state[key][0])
            user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    down.__name__ = f"{name}_down"
    step(150, down)
    for _j in range(1, DASH_N + 1):
        def mv(i=_j):
            if state.get(key):
                (x0, y0), (x1, y1) = state[key]
                mouse_to(x0 + (x1 - x0) * i // DASH_N, y0 + (y1 - y0) * i // DASH_N)
        mv.__name__ = f"{name}_move_{_j}"
        step(200 if _j == 1 else 40, mv)

    def up():
        if state.get(key):
            user32.mouse_event(LEFTUP, 0, 0, 0, 0)
    up.__name__ = f"{name}_up"
    step(60, up)


@step(300, )
def s_dash_click_check():
    rec("stats drag: a plain click changes nothing", app.dashboard_stats == DASH_SWAP,
        str(app.dashboard_stats))
    # release into the gap between the columns
    cards = app.dashboard_cards
    left, right = cards[DASH_SWAP[0]], cards[DASH_SWAP[1]]
    gx = (left.winfo_rootx() + left.winfo_width() + right.winfo_rootx()) // 2
    gy = left.winfo_rooty() + left.winfo_height() // 2
    gap_ok = app._dashboard_card_at(gx, gy) is None
    rec("stats drag: there is a gap between the columns", gap_ok, f"{gx},{gy}")
    state["dash_gap"] = (_center(left.value_label), (gx, gy)) if gap_ok else None


_dash_real_drag("dash_gap", "dash_gap")


@step(400, )
def s_dash_gap_check():
    rec("stats drag: dropping into the gap changes nothing", app.dashboard_stats == DASH_SWAP,
        str(app.dashboard_stats))
    rec("stats drag: borders back to normal after the gap drop", not _dash_lit(), str(_dash_lit()))
    # press on ⓘ, drag onto another card: ⓘ is a button, no drag starts there
    cards = app.dashboard_cards
    state["dash_info"] = (_center(cards[DASH_SWAP[0]]._info_btn), _center(cards[DASH_SWAP[3]]))


_dash_real_drag("dash_info", "dash_info")


@step(400, )
def s_dash_info_check():
    rec("stats drag: pressing ⓘ and dragging does not reorder", app.dashboard_stats == DASH_SWAP,
        str(app.dashboard_stats))
    rec("stats drag: borders normal after the ⓘ press", not _dash_lit(), str(_dash_lit()))
    for card in app.dashboard_cards.values():
        card._close_info()
    # one variant via event_generate: drag by the card's border (its canvas)
    cards = app.dashboard_cards
    a, b = cards[DASH_SWAP[1]], cards[DASH_SWAP[2]]         # hrr -> over
    ax, ay = a.winfo_rootx() + 4, a.winfo_rooty() + a.winfo_height() // 2
    bx, by = _center(b)
    cv = a._canvas
    cv.event_generate("<ButtonPress-1>", x=4, y=ay - a.winfo_rooty(), rootx=ax, rooty=ay)
    cv.event_generate("<B1-Motion>", x=bx - a.winfo_rootx(), y=by - a.winfo_rooty(),
                      rootx=bx, rooty=by, state=0x100)
    cv.event_generate("<ButtonRelease-1>", x=bx - a.winfo_rootx(), y=by - a.winfo_rooty(),
                      rootx=bx, rooty=by, state=0x100)
    root.update()
    want = ["breath", "over", "hrr", "baseline"]
    rec("stats drag: dragging by the card's edge swaps too (event_generate)",
        app.dashboard_stats == want and _dash_order() == want, str(app.dashboard_stats))


@step(300, )
def s_dash_remove_check():
    # ✕ on the card <-> ✓ in the picker
    card = app.dashboard_cards["over"]
    card._on_enter()
    card._remove_btn.invoke()
    root.update_idletasks()
    saved = _saved_dashboard()
    rec("stats ✕: card removed and saved",
        "over" not in app.dashboard_stats and isinstance(saved, list) and "over" not in saved,
        f"{app.dashboard_stats} saved={saved}")
    app._open_dashboard_picker()


@step(400, )
def s_dash_last_card_check():
    marks = [(sid, c.cget("text") == "✓") for sid, _t, c in _picker_rows()]
    rec("stats picker: ✓ marks match the cards after ✕",
        all(on == (sid in app.dashboard_stats) for sid, on in marks), str(marks))
    app._close_dashboard_picker()
    # the last card stays
    last = app.dashboard_stats[0]
    _dash_set([last])
    rec("stats: the last card has no ✕", app.dashboard_cards[last]._remove_btn is None)
    app._toggle_dashboard_stat(last)
    rec("stats: the last card cannot be removed", app.dashboard_stats == [last],
        str(app.dashboard_stats))
    # cap of 4 cards
    _dash_set(DASH_PLNE)
    app._toggle_dashboard_stat("avg")
    rec("stats: a 5th card is refused", app.dashboard_stats == DASH_PLNE
        and len(app.dashboard_cards) == 4, str(app.dashboard_stats))
    _dash_set(state["dash0"])


# ---------------- 6d. language ----------------
@step(200, )
def s_lang_en():
    from app import LANG_NATIVE_LABELS
    state["lang0"] = app.lang
    app.on_lang_switch(LANG_NATIVE_LABELS["en"])


@step(900, )
def s_lang_en_check():
    rec("language switched to English without exception", app.lang == "en" and not errors,
        app.sidebar.rows["vhre"].text)
    app.sidebar._select("vhre")


@step(400, )
def s_lang_en_shot():
    shot("19_english_vhre")
    from app import LANG_NATIVE_LABELS
    app.on_lang_switch(LANG_NATIVE_LABELS[state["lang0"]])


@step(900, )
def s_lang_back():
    rec("language switched back", app.lang == state["lang0"])


# ---------------- 7. theme ----------------
@step(300, )
def s_theme():
    state["theme0"] = app.theme_key
    state["world0"] = app.world
    # Since 0.2 the theme belongs to the world (B3-worlds) - the world is
    # switched, not the theme.
    app.set_world("work" if app.world == "play" else "play")


@step(900, )
def s_theme_check():
    rec("theme switched without exception", app.theme_key != state["theme0"] and not errors, f"{state['theme0']} -> {app.theme_key}")
    shot("14_theme_other")
    check_sidebar_alignment("after theme switch")
    app.sidebar._select("vhre")


@step(500, )
def s_theme_vhre():
    shot("15_theme_other_vhre")
    app.set_world(state["world0"])


@step(800, )
def s_theme_back():
    rec("theme switched back", app.theme_key == state["theme0"])
    shot("20_final_dnes")


def finish():
    rec("no Tk callback exceptions during run", not errors, f"{len(errors)} errors")
    with open(os.path.join(OUT, "harness_results.json"), "w", encoding="utf-8") as fh:
        json.dump({"results": results, "errors": errors, "state": {k: str(v) for k, v in state.items() if k not in ("sliders", "dlg", "cur_sf")}}, fh, indent=1, ensure_ascii=False)
    failed = [r for r in results if not r["ok"]]
    print(f"\n==== {len(results) - len(failed)} passed, {len(failed)} failed ====")
    for r in failed:
        print("  FAIL", r["name"], "--", r["detail"])
    for e in errors:
        print("---- error ----\n", e)
    try:
        app.overlay_manager.stop_all()
        app.hud.stop()
    except Exception:
        pass

    def koniec():
        # Restored only just before the process ends: whatever the app wrote
        # in those 200 ms is overwritten by the backup - not the other way
        # round. `os._exit` skips `finally` and `atexit`, so it has to be
        # restored here.
        vrat_zalohy(ODLOZENE)
        print("nastavenia a historia tepu vratene zo zaloh", flush=True)
        os._exit(1 if failed else 0)
    sys.stdout.flush()      # os._exit() does not flush the buffer
    root.after(200, koniec)


try:
    root.after(300, run_steps)
    root.mainloop()
finally:
    # Ctrl+C, closed window, exception from mainloop: everything is restored
    # here too. A crash even before mainloop is covered by `atexit`, a hard
    # kill by the next run.
    vrat_zalohy(ODLOZENE)
os._exit(0)
