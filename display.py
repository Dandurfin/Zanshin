"""Screen and DPI detection - the single source of truth about WHERE and HOW
BIG the in-game overlay should be drawn.

Why this module exists
----------------------
The original overlay.py computed its position from
`tk.Toplevel.winfo_screenwidth()`. That has two flaws which fully show up on
modern setups:

  1) `winfo_screenwidth()` returns the size of the PRIMARY screen ONLY.
     Anyone with two monitors and the game on the second one never sees the
     visual there - on top of that the window was also clamped
     (`min(screen_w - w, ...)`) back onto the primary area.

  2) Without declaring DPI awareness, Windows lies to the process: on a 4K
     monitor with 150 % scaling it returns 2560x1440 instead of 3840x2160
     and also blurs the resulting window with bitmap upscaling (that is why
     the app was "blurry" on 4K and the overlay sat somewhere other than
     where it should).

Solution: `enable_dpi_awareness()` is called from main.py BEFORE the Tk
window is created, and position/size are computed relative to a specific
monitor from `monitors()`, not relative to the primary screen.

Visual size
-----------
A visual given in pixels is a different object on 1080p than on 4K (a
quarter of the size). So `scale_for(monitor)` returns a multiplier relative
to the reference height of 1080 px, which means a 240x160 visual takes up the
same PART of the screen at every resolution - that is what the player
perceives as "the same size".

The module is pure ctypes/stdlib; on non-Windows systems it has a safe
fallback (one virtual monitor), so the project can also be run during
development on Linux/macOS.
"""

import ctypes
import math
import sys

IS_WINDOWS = sys.platform == "win32"

# Reference screen height. All visual sizes in overlay.py are given in
# "1080p pixels" and are converted through scale_for().
REFERENCE_HEIGHT = 1080.0

# Sensible limits - on a 720p laptop we do not want to shrink the visuals
# until they are unreadable, and on an 8K wall we do not want to inflate them
# over half the screen.
MIN_SCALE = 0.65
MAX_SCALE = 3.0


class Monitor:
    """One physical screen in virtual desktop coordinates.

    `x/y` can also be negative (a monitor to the left of the primary one),
    so the position of a visual is ALWAYS computed as
    `x + width * percento`, never from `width` alone.
    """

    __slots__ = ("x", "y", "width", "height", "work_x", "work_y",
                 "work_width", "work_height", "primary", "name", "dpi")

    def __init__(self, x, y, width, height, primary=False, name="",
                 work=None, dpi=96):
        self.x, self.y = int(x), int(y)
        self.width, self.height = int(width), int(height)
        wx, wy, ww, wh = work if work else (x, y, width, height)
        self.work_x, self.work_y = int(wx), int(wy)
        self.work_width, self.work_height = int(ww), int(wh)
        self.primary = bool(primary)
        self.name = name or ""
        self.dpi = int(dpi)

    @property
    def rect(self):
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def scale(self):
        """Multiplier of visual sizes relative to the 1080p reference."""
        return max(MIN_SCALE, min(MAX_SCALE, self.height / REFERENCE_HEIGHT))

    def contains(self, px, py):
        return (self.x <= px < self.x + self.width
                and self.y <= py < self.y + self.height)

    def label(self, index):
        """Label for the dropdown - '1: 3840x2160 (primary)'."""
        suffix = " *" if self.primary else ""
        return f"{index + 1}: {self.width}x{self.height}{suffix}"

    def __repr__(self):  # pragma: no cover - only for debugging
        return (f"<Monitor {self.width}x{self.height}+{self.x}+{self.y} "
                f"dpi={self.dpi}{' primary' if self.primary else ''}>")


# --------------------------------------------------------------------------
# DPI awareness
# --------------------------------------------------------------------------

_dpi_state = {"done": False, "mode": "none"}


def enable_dpi_awareness():
    """Declares the process as per-monitor DPI aware (V2, if Windows can).

    It MUST be called BEFORE `import customtkinter` and before the first Tk
    window is created - once a window exists, Windows no longer changes the
    process mode.

    Tried from the best to the oldest:
      V2   (Win10 1703+) - correct DPI even when moving a window between monitors
      V1   (Win8.1+)     - per-monitor, but no auto-rescaling of the non-client area
      System (Vista+)    - at least no blurring on the primary monitor

    Returns the mode used as a string ('v2' / 'v1' / 'system' / 'none').
    """
    if _dpi_state["done"]:
        return _dpi_state["mode"]
    _dpi_state["done"] = True
    if not IS_WINDOWS:
        return _dpi_state["mode"]

    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 is a handle with the value -4;
    # it must be passed as a pointer-sized type, otherwise on 64-bit Windows it
    # gets truncated to 32 bits and the call silently fails.
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_int
        handle = ctypes.c_void_p(-4)
        if user32.SetProcessDpiAwarenessContext(handle):
            _dpi_state["mode"] = "v2"
            return "v2"
    except Exception:
        pass

    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2; customtkinter makes the same
        # call on import - if we succeed first, its call just returns
        # E_ACCESSDENIED and breaks nothing.
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            _dpi_state["mode"] = "v1"
            return "v1"
    except Exception:
        pass

    try:
        if ctypes.windll.user32.SetProcessDPIAware():
            _dpi_state["mode"] = "system"
            return "system"
    except Exception:
        pass
    return _dpi_state["mode"]


# --------------------------------------------------------------------------
# Monitor enumeration (Windows)
# --------------------------------------------------------------------------

if IS_WINDOWS:

    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong),
                    ("rcMonitor", _RECT),
                    ("rcWork", _RECT),
                    ("dwFlags", ctypes.c_ulong),
                    ("szDevice", ctypes.c_wchar * 32)]

    _MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(_RECT), ctypes.c_void_p)

    _MONITORINFOF_PRIMARY = 0x00000001
    _MONITOR_DEFAULTTONEAREST = 0x00000002


def _monitor_dpi(hmonitor):
    """Effective DPI of the monitor (96 = 100 %). Older Windows return 96."""
    try:
        x, y = ctypes.c_uint(), ctypes.c_uint()
        # MDT_EFFECTIVE_DPI = 0
        if ctypes.windll.shcore.GetDpiForMonitor(
                hmonitor, 0, ctypes.byref(x), ctypes.byref(y)) == 0:
            return int(x.value) or 96
    except Exception:
        pass
    return 96


def _from_handle(hmonitor):
    info = _MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(_MONITORINFOEXW)
    if not ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
        return None
    m, w = info.rcMonitor, info.rcWork
    return Monitor(
        m.left, m.top, m.right - m.left, m.bottom - m.top,
        primary=bool(info.dwFlags & _MONITORINFOF_PRIMARY),
        name=info.szDevice,
        work=(w.left, w.top, w.right - w.left, w.bottom - w.top),
        dpi=_monitor_dpi(hmonitor))


def _fallback_monitor(tk_widget=None):
    """Fallback when the Win32 API is not available (Linux/macOS development,
    or when enumeration fails) - one screen based on what Tk can tell."""
    width, height = 1920, 1080
    if tk_widget is not None:
        try:
            width = int(tk_widget.winfo_screenwidth())
            height = int(tk_widget.winfo_screenheight())
        except Exception:
            pass
    return Monitor(0, 0, width, height, primary=True, name="screen")


def monitors(tk_widget=None):
    """All connected screens, the primary one always first.

    The order is stable (primary, then left to right, top to bottom), so the
    player can pick "Monitor 2" in the settings and that choice keeps the
    same meaning after the app restarts.
    """
    if not IS_WINDOWS:
        return [_fallback_monitor(tk_widget)]
    found = []

    def _cb(hmonitor, _hdc, _rect, _lparam):
        mon = _from_handle(hmonitor)
        if mon is not None:
            found.append(mon)
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, _MONITORENUMPROC(_cb), 0)
    except Exception:
        found = []
    if not found:
        return [_fallback_monitor(tk_widget)]
    found.sort(key=lambda m: (not m.primary, m.x, m.y))
    return found


def primary_monitor(tk_widget=None):
    for mon in monitors(tk_widget):
        if mon.primary:
            return mon
    return monitors(tk_widget)[0]


def monitor_at_cursor(tk_widget=None):
    if IS_WINDOWS:
        try:
            pt = _POINT()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                for mon in monitors(tk_widget):
                    if mon.contains(pt.x, pt.y):
                        return mon
        except Exception:
            pass
    return primary_monitor(tk_widget)


def foreground_window_rect():
    """Rect of the focused window (typically the game). None if unavailable."""
    if not IS_WINDOWS:
        return None
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = _RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        return None


def monitor_of_foreground(tk_widget=None):
    """The monitor the active window is on - i.e. the one the player is
    playing on right now. This is the default target monitor for the
    overlay."""
    rect = foreground_window_rect()
    if rect is None:
        return monitor_at_cursor(tk_widget)
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    for mon in monitors(tk_widget):
        if mon.contains(cx, cy):
            return mon
    return monitor_at_cursor(tk_widget)


# Values for the settings: "auto" = monitor of the active window, "cursor" =
# monitor under the cursor, "primary" = the main one, "0".."3" = a specific
# index.
TARGET_AUTO = "auto"
TARGET_CURSOR = "cursor"
TARGET_PRIMARY = "primary"


def resolve_target(target=TARGET_AUTO, tk_widget=None):
    """Translates the saved monitor choice into a specific Monitor.

    Always returns a valid monitor - if the player unplugged the screen the
    overlay was set to, it falls back to the primary one instead of the
    visual ending up outside the visible area.
    """
    all_monitors = monitors(tk_widget)
    if target == TARGET_PRIMARY:
        return next((m for m in all_monitors if m.primary), all_monitors[0])
    if target == TARGET_CURSOR:
        return monitor_at_cursor(tk_widget)
    if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
        idx = int(target)
        if 0 <= idx < len(all_monitors):
            return all_monitors[idx]
        return next((m for m in all_monitors if m.primary), all_monitors[0])
    return monitor_of_foreground(tk_widget)


def place(monitor, width, height, pos_x_pct, pos_y_pct):
    """Top-left coordinate of a window of width `width` and height `height`
    such that its CENTRE sits at the given percentages of the `monitor` area.

    Clamping is to the bounds of THIS monitor (not the primary one), so the
    visual stays fully visible even on the second screen and even with
    negative virtual desktop coordinates.
    """
    cx = monitor.x + monitor.width * (pos_x_pct / 100.0)
    cy = monitor.y + monitor.height * (pos_y_pct / 100.0)
    x = int(round(cx - width / 2.0))
    y = int(round(cy - height / 2.0))
    x = max(monitor.x, min(monitor.x + monitor.width - width, x))
    y = max(monitor.y, min(monitor.y + monitor.height - height, y))
    return x, y


# --------------------------------------------------------------------------
# The app window on a monitor - whether it fits and where to put it
# --------------------------------------------------------------------------
#
# The main window has a FIXED logical size (DandurfApp.WINDOW_W/H) and CTk
# multiplies it by the display scale. On a typical gaming laptop (1920x1080
# at 150 %) that is ~1140 px of height against ~1008 px of work area, and the
# window can neither be shrunk nor maximised - the bottom of the side menu
# (Settings) ended up under the taskbar. These two functions are pure maths
# without Tk, so they can be checked for every setup without a real monitor.

# Physical px left between the window and the edge of the work area (in total
# for both sides). A window exactly on the edge of the taskbar looks like it
# is "under it", and with CTk rounding it could spill over by a pixel.
WINDOW_FIT_MARGIN_PX = 16
# We do not shrink the app below this fraction of the normal size - the font
# would be unreadable (size 10 would be only 7 px at 100 %). Better to let the
# window stick out at the bottom and keep the title bar up top within reach.
WINDOW_MIN_FIT = 0.7


def dpi_scale(monitor):
    """How many physical px one logical px is on this monitor (96 DPI = 1.0).

    The same value CTk multiplies window sizes by (`GetDpiForMonitor`,
    effective DPI), so the calculation below matches what CTk really draws."""
    try:
        dpi = int(getattr(monitor, "dpi", 96) or 96)
    except (TypeError, ValueError):
        dpi = 96
    return max(1, dpi) / 96.0


def window_fit_factor(width, height, scale, work_width, work_height,
                      margin=WINDOW_FIT_MARGIN_PX, minimum=WINDOW_MIN_FIT):
    """How much to shrink the window so that it fits whole into the work area.

    `width`/`height` are the window's LOGICAL px, `scale` is what CTk
    multiplies them by (monitor DPI times the already set window scaling),
    `work_*` is the monitor's work area in physical px (without the taskbar).

    Returns 1.0 when the window fits including the margin - then nothing
    should change. Otherwise a factor < 1 rounded DOWN to thousandths: CTk
    rounds the window size (`round`) and a factor rounded up would push the
    window a pixel over the edge. Never less than `minimum` - if the window
    does not fit even then, `center_in_work_area` sticks it to the top edge
    of the area.
    """
    try:
        scale = float(scale)
    except (TypeError, ValueError):
        scale = 1.0
    if not scale > 0:
        scale = 1.0
    phys_w = float(width) * scale
    phys_h = float(height) * scale
    if phys_w <= 0 or phys_h <= 0:
        return 1.0
    avail_w = float(work_width) - margin
    avail_h = float(work_height) - margin
    if phys_w <= avail_w and phys_h <= avail_h:
        return 1.0
    if avail_w <= 0 or avail_h <= 0:
        return float(minimum)
    factor = min(avail_w / phys_w, avail_h / phys_h)
    factor = math.floor(factor * 1000.0) / 1000.0
    return max(float(minimum), min(1.0, factor))


def center_in_work_area(monitor, px_width, px_height):
    """Top-left corner of a window `px_width` x `px_height` (PHYSICAL px) such
    that it sits in the centre of the work area of `monitor`.

    The work area, not the whole monitor: the taskbar can be at the bottom,
    top or on the side, and a window under it would be exactly where you do
    not see it. A window larger than the area is stuck to its top (left)
    edge - so the title bar the window is dragged by always stays on screen.
    """
    x = monitor.work_x + max(0, (monitor.work_width - int(px_width)) // 2)
    y = monitor.work_y + max(0, (monitor.work_height - int(px_height)) // 2)
    return int(x), int(y)


def is_fullscreen_foreground(tk_widget=None):
    """True if the active window exactly covers its whole monitor.

    A heuristic for recognising exclusive fullscreen: in it Windows does not
    draw any foreign layered windows, so the player would not see the
    overlay and would not know why. In that case the app advises them once
    to switch the game to "Borderless / Okno bez okrajov" mode.
    """
    rect = foreground_window_rect()
    if rect is None:
        return False
    for mon in monitors(tk_widget):
        if (abs(rect[0] - mon.x) <= 1 and abs(rect[1] - mon.y) <= 1
                and abs(rect[2] - (mon.x + mon.width)) <= 1
                and abs(rect[3] - (mon.y + mon.height)) <= 1):
            return True
    return False
