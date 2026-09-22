"""Zistovanie obrazoviek a DPI - jediny zdroj pravdy o tom, KDE a AKO VELKY
sa ma in-game overlay vykreslit.

Preco tento modul vznikol
-------------------------
Povodny overlay.py si polohu ratal z `tk.Toplevel.winfo_screenwidth()`.
To ma dve chyby, ktore sa naplno prejavia na modernych zostavach:

  1) `winfo_screenwidth()` vracia rozmer LEN PRIMARNEJ obrazovky. Kto ma
     dva monitory a hru na tom druhom, ten vizual na nom nikdy neuvidi -
     okno sa navyse este aj orezalo (`min(screen_w - w, ...)`) spat na
     primarnu plochu.

  2) Bez ohlasenia DPI-awareness Windows procesu klame: na 4K monitore so
     150 % skalovanim vrati 2560x1440 namiesto 3840x2160 a vysledne okno
     este aj rozmaze bitmapovym zvacsenim (preto bola appka na 4K
     "rozmazana" a overlay sedel inde, nez mal).

Riesenie: `enable_dpi_awareness()` sa vola z main.py EST PRED vytvorenim
Tk okna, a poloha/velkost sa rata voci konkretnemu monitoru zo
`monitors()`, nie voci primarnej obrazovke.

Velkost vizualov
----------------
Vizual zadany v pixeloch je na 1080p iny objekt nez na 4K (stvrtinovy).
`scale_for(monitor)` preto vracia nasobok voci referencnej vyske 1080 px,
takze 240x160 vizual zabera na kazdom rozliseni rovnaku CAST obrazovky -
to je to, co hrac vnima ako "rovnako velke".

Modul je cisty ctypes/stdlib, na ne-Windows systemoch ma bezpecnu
nahradu (jeden virtualny monitor), aby sa dal projekt spustat aj pri
vyvoji na Linuxe/macOS.
"""

import ctypes
import sys

IS_WINDOWS = sys.platform == "win32"

# Referencna vyska obrazovky. Vsetky rozmery vizualov v overlay.py su
# zadane v "1080p pixeloch" a prepocitavaju sa cez scale_for().
REFERENCE_HEIGHT = 1080.0

# Rozumne medze - na 720p notebooku nechceme vizualy zmensit na necitatelne
# a na 8K stene ich nechceme nafuknut cez pol obrazovky.
MIN_SCALE = 0.65
MAX_SCALE = 3.0


class Monitor:
    """Jedna fyzicka obrazovka v suradniciach virtualnej plochy.

    `x/y` mozu byt aj zaporne (monitor vlavo od primarneho), preto sa
    poloha vizualu VZDY rata ako `x + width * percento`, nikdy nie len
    z `width`.
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
        """Nasobok velkosti vizualov voci 1080p referencii."""
        return max(MIN_SCALE, min(MAX_SCALE, self.height / REFERENCE_HEIGHT))

    def contains(self, px, py):
        return (self.x <= px < self.x + self.width
                and self.y <= py < self.y + self.height)

    def label(self, index):
        """Popisok do dropdownu - '1: 3840x2160 (hlavny)'."""
        suffix = " *" if self.primary else ""
        return f"{index + 1}: {self.width}x{self.height}{suffix}"

    def __repr__(self):  # pragma: no cover - len na ladenie
        return (f"<Monitor {self.width}x{self.height}+{self.x}+{self.y} "
                f"dpi={self.dpi}{' primary' if self.primary else ''}>")


# --------------------------------------------------------------------------
# DPI awareness
# --------------------------------------------------------------------------

_dpi_state = {"done": False, "mode": "none"}


def enable_dpi_awareness():
    """Ohlasi proces ako per-monitor DPI aware (V2, ak to Windows vie).

    MUSI sa zavolat EST PRED `import customtkinter` a pred vytvorenim
    prveho Tk okna - po vytvoreni okna uz Windows rezim procesu nemeni.

    Skusa sa od najlepsieho po najstarsie:
      V2   (Win10 1703+) - spravne DPI aj pri presune okna medzi monitormi
      V1   (Win8.1+)     - per-monitor, ale bez auto-prepoctu neklientskej casti
      System (Vista+)    - aspon ziadne rozmazanie na primarnom monitore

    Vracia pouzity rezim ako retazec ('v2' / 'v1' / 'system' / 'none').
    """
    if _dpi_state["done"]:
        return _dpi_state["mode"]
    _dpi_state["done"] = True
    if not IS_WINDOWS:
        return _dpi_state["mode"]

    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 je handle s hodnotou -4;
    # musi sa odovzdat ako pointer-sized typ, inak na 64-bit Windows
    # prejde orezany na 32 bitov a volanie tíško zlyha.
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
        # PROCESS_PER_MONITOR_DPI_AWARE = 2; rovnake volanie robi aj
        # customtkinter pri importe - ak uspejeme my skor, jeho volanie
        # uz len vrati E_ACCESSDENIED a nic nepokazi.
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
# Enumeracia monitorov (Windows)
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
    """Efektivne DPI monitora (96 = 100 %). Na starsich Windows vrati 96."""
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
    """Nahrada, ked Win32 API nie je k dispozicii (Linux/macOS vyvoj, alebo
    ked enumeracia zlyha) - jedna obrazovka podla toho, co vie povedat Tk."""
    width, height = 1920, 1080
    if tk_widget is not None:
        try:
            width = int(tk_widget.winfo_screenwidth())
            height = int(tk_widget.winfo_screenheight())
        except Exception:
            pass
    return Monitor(0, 0, width, height, primary=True, name="screen")


def monitors(tk_widget=None):
    """Vsetky pripojene obrazovky, primarna vzdy prva.

    Poradie je stabilne (primarna, potom zlava doprava, zhora nadol), aby
    si hrac mohol v nastaveniach vybrat "Monitor 2" a ten vyber mal aj po
    restarte appky rovnaky vyznam.
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
    """Obdlznik okna, ktore ma prave focus (typicky hra). None ak sa neda."""
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
    """Monitor, na ktorom bezi aktivne okno - teda ten, na ktorom hrac
    prave hra. Toto je predvoleny cielovy monitor pre overlay."""
    rect = foreground_window_rect()
    if rect is None:
        return monitor_at_cursor(tk_widget)
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    for mon in monitors(tk_widget):
        if mon.contains(cx, cy):
            return mon
    return monitor_at_cursor(tk_widget)


# Hodnoty do nastaveni: "auto" = monitor aktivneho okna, "cursor" = monitor
# pod kurzorom, "primary" = hlavny, "0".."3" = konkretny index.
TARGET_AUTO = "auto"
TARGET_CURSOR = "cursor"
TARGET_PRIMARY = "primary"


def resolve_target(target=TARGET_AUTO, tk_widget=None):
    """Prelozi ulozenu volbu monitora na konkretny Monitor.

    Vzdy vrati platny monitor - ak hrac odpojil obrazovku, na ktorej mal
    overlay nastaveny, spadne sa na primarnu namiesto toho, aby vizual
    skoncil mimo viditelnej plochy.
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
    """Lava horna suradnica okna sirky `width` a vysky `height` tak, aby
    jeho STRED sedel na zadanych percentach plochy `monitor`.

    Orezanie je na hranice TOHTO monitora (nie primarneho), takze vizual
    ostava cely viditelny aj na druhej obrazovke a aj pri zapornych
    suradniciach virtualnej plochy.
    """
    cx = monitor.x + monitor.width * (pos_x_pct / 100.0)
    cy = monitor.y + monitor.height * (pos_y_pct / 100.0)
    x = int(round(cx - width / 2.0))
    y = int(round(cy - height / 2.0))
    x = max(monitor.x, min(monitor.x + monitor.width - width, x))
    y = max(monitor.y, min(monitor.y + monitor.height - height, y))
    return x, y


def is_fullscreen_foreground(tk_widget=None):
    """True, ak aktivne okno presne prekryva cely svoj monitor.

    Heuristika na rozpoznanie exkluzivneho fullscreenu: v nom Windows
    nekresli ziadne cudzie vrstvene okna, takze by hrac overlay nevidel a
    nevedel preco. Appka mu v takom pripade raz poradi prepnut hru do
    rezimu "Borderless / Okno bez okrajov".
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
