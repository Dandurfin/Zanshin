# -*- coding: utf-8 -*-
"""One global key - "not now" (spec §1.9).

WHY THIS IS NOT THE HOOK COMING BACK
------------------------------------
Phase 3 removed the global keyboard hook (`pynput`, `WH_KEYBOARD_LL`) and it
was one of the main reasons for the whole rebuild: a hook sees EVERY pressed
key and from the outside cannot be told apart from a keylogger.

`RegisterHotKey` is something completely different. The app announces a
single combination to Windows IN ADVANCE and the system sends it a message
only when someone presses it. It learns about no other key - technically it
cannot even, no stream of input flows through it. When the combination is
already taken by another app, the registration simply fails and
`RegisterHotKey` returns zero.

The difference in one sentence: a hook ASKS about everything and filters for
itself; a hotkey SAYS what it wants to be woken up for, and gets nothing
else.

It does not need admin rights (spec §5: `uac_admin=False` must not come
back).

WHY ITS OWN THREAD
------------------
`RegisterHotKey(NULL, ...)` binds the combination to the THREAD that
registered it, and `WM_HOTKEY` arrives in that thread's queue, not in a
window. Tk manages its queue itself and does not pull windowless messages
from it, so registering it in the Tk thread would mean the hotkey never
fires. The module therefore has its own thread with its own `GetMessageW`
loop.

The callback is called from THAT thread - the app must hand it over via
`ui_call`, the same as the callbacks from the smartwatch.

MOD_NOREPEAT
------------
Without it, holding the combination generates a flood of messages and "not
now" would turn on and off ten times a second.

The module must be importable even where there is no user32 (CI, another
OS) - otherwise the import of the whole app would fail. The same discipline
as `activity.py`.
"""

import threading

# --------------------------------------------------------------------------
# Key combinations
# --------------------------------------------------------------------------

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
# Without this, holding the key fires a flood of messages.
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_MODY = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN, "super": MOD_WIN,
}

# Virtual key codes that make sense to use. A deliberately NARROW list: the
# app does not need the whole VK table and every extra row is another
# combination that may clash with a game.
_VK = {}
for _i in range(26):                       # A-Z
    _VK[chr(ord("a") + _i)] = 0x41 + _i
for _i in range(10):                       # 0-9
    _VK[str(_i)] = 0x30 + _i
for _i in range(1, 13):                    # F1-F12
    _VK["f%d" % _i] = 0x6F + _i
_VK.update({"space": 0x20, "pause": 0x13, "insert": 0x2D, "delete": 0x2E,
            "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22})


class BadCombo(ValueError):
    """Invalid combination string."""


def parse_combo(text):
    """'ctrl+alt+z' -> (mods, vk). Raises `BadCombo` on nonsense.

    At least one modifier is REQUIRED. A bare key as a global hotkey would
    take a letter from the player in every game and every chat - and they
    would have no idea why their "z" does not work.
    """
    if text is None or not str(text).strip():
        raise BadCombo("prazdna kombinacia")
    casti = [c.strip().lower() for c in str(text).split("+") if c.strip()]
    if not casti:
        raise BadCombo("prazdna kombinacia")
    mody = 0
    klaves = None
    for cast in casti:
        if cast in _MODY:
            mody |= _MODY[cast]
        elif klaves is None:
            klaves = cast
        else:
            raise BadCombo("dva klavesy naraz: %s + %s" % (klaves, cast))
    if klaves is None:
        raise BadCombo("chyba klaves")
    if klaves not in _VK:
        raise BadCombo("neznamy klaves: %s" % klaves)
    if not mody:
        raise BadCombo("treba aspon jeden modifikator (ctrl/alt/shift/win)")
    return mody | MOD_NOREPEAT, _VK[klaves]


def is_valid(text):
    """Is this combination usable? No exception, for normalising settings."""
    try:
        parse_combo(text)
        return True
    except BadCombo:
        return False


# Modifier names as the keyboard and Windows show them in the given language
# (0.3 batch 4b). A German keyboard has "Strg" and "Umschalt", not "Ctrl" and
# "Shift" - a German player would look for "Ctrl + Alt + Z" on the keyboard
# in vain. Settings and registration stay in the English form
# ('ctrl+alt+z'); this is ONLY what is shown. A language that is not here
# gets the English names.
_MENA_MODIFIKATOROV = {
    "de": {"ctrl": "Strg", "control": "Strg", "shift": "Umschalt"},
}


def _jazyk_appky():
    """App UI language - a lazy import, so `hotkey` does not depend on i18n
    (the module is also imported on its own, e.g. in tests)."""
    try:
        import i18n
        return i18n._lang["code"]
    except Exception:
        return "en"


def format_combo(text, lang=None, oddelovac=" + "):
    """Display form for the interface: 'ctrl+alt+z' -> 'Ctrl + Alt + Z'.

    `lang` (default: the app language) picks the modifier names - in German
    'Strg + Alt + Z'. For app.log (`lang="en"`) the English form stays."""
    if not is_valid(text):
        return ""
    mena = _MENA_MODIFIKATOROV.get(_jazyk_appky() if lang is None else lang, {})
    kusy = [c.strip() for c in str(text).split("+") if c.strip()]
    return oddelovac.join(
        mena.get(k.lower()) or (k.upper() if len(k) == 1 else k.capitalize())
        for k in kusy)


# --------------------------------------------------------------------------
# Clash with the keyboard layout (0.3)
# --------------------------------------------------------------------------
#
# WHY: on Windows AltGr is the same as Ctrl+Alt. On the Polish layout
# AltGr+Z types "ż" - a globally registered Ctrl+Alt+Z would swallow that
# letter from the player in every window (chat, browser, document), even
# when the app is only in the tray. So before registering, it asks every
# INSTALLED layout whether that combination produces a character.
#
# Detection is a pure function with injectable dependencies (`rozlozenia`,
# `znak`): tests check it on a made-up Polish layout without changing
# anything in the system. When Windows cannot be asked (another OS, ctypes
# missing), no clash is REPORTED - the app behaves as before.

# Presets in Settings -> General. The first is the app's default shortcut,
# the others are fallbacks: no layout types F-keys as a character, so they
# do not clash with AltGr anywhere.
PRESETS = ("ctrl+alt+z", "ctrl+alt+f9", "ctrl+alt+f12", "ctrl+shift+f12")

_VK_SHIFT, _VK_CONTROL, _VK_MENU = 0x10, 0x11, 0x12
_VK_LSHIFT, _VK_LCONTROL, _VK_RMENU = 0xA0, 0xA2, 0xA5
# ToUnicodeEx: bit 2 = "do not change keyboard state" (Windows 10 1607+).
# Without it a dead key (diacritics) would stay hanging and spoil the next
# letter.
_TU_NEMEN_STAV = 0x4


def _rozlozenia():
    """Handles (HKL) of all installed layouts; [] when not possible."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetKeyboardLayoutList.argtypes = [ctypes.c_int,
                                                 ctypes.POINTER(wintypes.HKL)]
        user32.GetKeyboardLayoutList.restype = ctypes.c_int
        pocet = user32.GetKeyboardLayoutList(0, None)
        if pocet <= 0:
            return []
        pole = (wintypes.HKL * pocet)()
        pocet = user32.GetKeyboardLayoutList(pocet, pole)
        return [pole[i] for i in range(max(0, pocet)) if pole[i]]
    except Exception:
        return []


def _znak_rozlozenia(hkl, vk, shift):
    """What layout `hkl` types for key `vk` with AltGr (Ctrl+Alt) and
    possibly Shift. "" = nothing. No exception gets out."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT,
                                       ctypes.POINTER(ctypes.c_ubyte),
                                       wintypes.LPWSTR, ctypes.c_int,
                                       wintypes.UINT, wintypes.HKL]
        user32.ToUnicodeEx.restype = ctypes.c_int
        user32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT,
                                            wintypes.HKL]
        user32.MapVirtualKeyExW.restype = wintypes.UINT
        stav = (ctypes.c_ubyte * 256)()
        for klaves in (_VK_CONTROL, _VK_MENU, _VK_LCONTROL, _VK_RMENU):
            stav[klaves] = 0x80
        if shift:
            stav[_VK_SHIFT] = stav[_VK_LSHIFT] = 0x80
        sken = user32.MapVirtualKeyExW(vk, 0, hkl)       # MAPVK_VK_TO_VSC
        buf = ctypes.create_unicode_buffer(8)
        n = user32.ToUnicodeEx(vk, sken, stav, buf, 8, _TU_NEMEN_STAV, hkl)
        if n < 0:
            # A dead key (e.g. ˇ or ´) also counts as typing. A second call
            # clears it from the state even on older Windows that does not know
            # bit 2.
            znak = buf.value[:1]
            user32.ToUnicodeEx(vk, sken, stav, buf, 8, _TU_NEMEN_STAV, hkl)
            return znak
        return buf.value[:n] if n > 0 else ""
    except Exception:
        return ""


def _tlacitelny(text):
    """Does `text` contain a typeable character (not a control character)?"""
    return any(ch.isprintable() and ord(ch) >= 0x20 for ch in str(text or ""))


def znak_kolizie(text, rozlozenia=None, znak=None):
    """The character the combination `text` would type on some installed
    layout (AltGr = Ctrl+Alt), or "" when it does not clash with typing.

    Applies only to combinations with Ctrl AND Alt and without Win - other
    modifiers do not type characters. `rozlozenia` (list of HKL) and
    `znak(hkl, vk, shift)` can be injected (tests); by default Windows is
    asked. No error gets out."""
    try:
        mody, vk = parse_combo(text)
    except BadCombo:
        return ""
    if not (mody & MOD_CONTROL and mody & MOD_ALT) or mody & MOD_WIN:
        return ""
    shift = bool(mody & MOD_SHIFT)
    try:
        zoznam = _rozlozenia() if rozlozenia is None else list(rozlozenia)
    except Exception:
        return ""
    zisti = _znak_rozlozenia if znak is None else znak
    for hkl in zoznam:
        try:
            vysledok = zisti(hkl, vk, shift)
        except Exception:
            continue
        if _tlacitelny(vysledok):
            return next(ch for ch in str(vysledok) if ch.isprintable() and ord(ch) >= 0x20)
    return ""


def prva_volna(predvolby=PRESETS, preskoc=(), kolizia=None):
    """The first valid preset that does not clash with typing; "" if none.

    `kolizia(text) -> znak` (default `znak_kolizie`) can be injected."""
    zisti = znak_kolizie if kolizia is None else kolizia
    for combo in predvolby or ():
        if combo in (preskoc or ()) or not is_valid(combo):
            continue
        try:
            if zisti(combo):
                continue
        except Exception:
            continue
        return combo
    return ""


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

def _win32():
    """(ctypes, user32), or (None, None) when this system cannot do it."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                          wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        return ctypes, user32
    except Exception:
        return None, None


AVAILABLE = _win32()[1] is not None

_HOTKEY_ID = 1


class GlobalHotkey:
    """One combination, one callback. No hook.

    `on_press()` is called from this module's OWN thread - the caller must
    hand it over to Tk via `ui_call`.

    `on_result(ok)` (0.3 batch 4b) is called from that same thread ONCE,
    when Windows really finishes the registration - successfully or not.
    `start()` waits for the result at most 2 s; when Windows is slow at
    start, it returns False and `caka` is True: the shortcut is not taken,
    just not ready yet. The true result is then told only by `on_result`.
    """

    # How long `start()` waits for the registration result (s). A class
    # attribute, so a test with a slow fake registration does not have to wait
    # the full 2 s.
    CAKAJ_NA_REGISTRACIU_S = 2.0

    def __init__(self, combo, on_press, log=None, on_result=None):
        self.combo = combo
        self._on_press = on_press
        # Public attribute: it can also be set after creation (the app sets
        # it this way so that simplified fakes in tests work too).
        self.on_result = on_result
        self._log = log
        self._thread = None
        self._tid = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self.registered = False
        self.error = None

    # ---- lifecycle ----

    def start(self):
        """Returns True when the combination was registered successfully."""
        if self._thread is not None:
            return self.registered
        try:
            parse_combo(self.combo)
        except BadCombo as exc:
            self.error = str(exc)
            self._zaloguj("hotkey: %s" % exc)
            return False
        if not AVAILABLE:
            self.error = "win32 nie je k dispozicii"
            return False
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._slucka, daemon=True,
                                        name="hotkey")
        self._thread.start()
        # The wait is short and bounded: without it the caller would not know
        # whether the registration succeeded and would have nothing to write to
        # the log. When it is not enough (slow Windows start), `caka` stays
        # True and the result comes via `on_result` - the caller must not take
        # False as "taken".
        self._ready.wait(timeout=self.CAKAJ_NA_REGISTRACIU_S)
        return self.registered

    @property
    def caka(self):
        """Registration has not finished yet (thread runs, no result yet)."""
        return self._thread is not None and not self._ready.is_set()

    def _hotovo(self, ok):
        """Registration result: first `_ready` (read by `start`), then
        `on_result`. An exception from the callback must not kill the
        thread."""
        self._ready.set()
        if callable(self.on_result):
            try:
                self.on_result(bool(ok))
            except Exception:
                self._zaloguj("hotkey: on_result vyhodil vynimku")

    def stop(self):
        if self._thread is None:
            return
        self._stop.set()
        ctypes, _user32 = _win32()
        if ctypes is not None and self._tid:
            try:
                # Wakes `GetMessageW` so the loop can end. Without it the
                # thread would hang on the queue until the process ends.
                ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            except Exception:
                pass
        self._thread.join(timeout=2.0)
        self._thread = None
        self._tid = None
        self.registered = False

    # ---- internals ----

    def _zaloguj(self, sprava):
        if callable(self._log):
            try:
                self._log(sprava)
            except Exception:
                pass

    def _slucka(self):
        ctypes, user32 = _win32()
        if user32 is None:
            self._hotovo(False)
            return
        from ctypes import wintypes
        try:
            mody, vk = parse_combo(self.combo)
        except BadCombo as exc:
            self.error = str(exc)
            self._hotovo(False)
            return

        if not user32.RegisterHotKey(None, _HOTKEY_ID, mody, vk):
            # Most often 1409 ERROR_HOTKEY_ALREADY_REGISTERED - the
            # combination is held by another app. It is not an app error and
            # must not crash it.
            self.error = ("kombinaciu sa nepodarilo zaregistrovat (%d)"
                          % ctypes.get_last_error())
            self._zaloguj("hotkey: %s" % self.error)
            self._hotovo(False)
            return

        try:
            self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        except Exception:
            self._tid = None
        self.registered = True
        self.error = None
        # app.log is in English regardless of the app language
        self._zaloguj("hotkey: %s zaregistrovany" % format_combo(self.combo, lang="en"))
        self._hotovo(True)

        msg = wintypes.MSG()
        try:
            while not self._stop.is_set():
                # 0 = WM_QUIT arrived, -1 = error
                vysledok = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if vysledok in (0, -1):
                    break
                if msg.message == WM_HOTKEY and callable(self._on_press):
                    try:
                        self._on_press()
                    except Exception:
                        # An exception from the callback must not kill
                        # the loop - otherwise the hotkey would silently
                        # stop working after the first error.
                        self._zaloguj("hotkey: callback vyhodil vynimku")
        finally:
            try:
                user32.UnregisterHotKey(None, _HOTKEY_ID)
            except Exception:
                pass
            self.registered = False
