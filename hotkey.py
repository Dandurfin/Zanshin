# -*- coding: utf-8 -*-
"""Jeden globalny klaves - "teraz nie" (zadanie §1.9).

PRECO TO NIE JE NAVRAT HOOKU
----------------------------
Faza 3 zrusila globalny klavesovy hook (`pynput`, `WH_KEYBOARD_LL`) a bol to
jeden z hlavnych dovodov celej prestavby: hook vidi KAZDY stlaceny klaves a
navonok sa neda odlisit od keyloggera.

`RegisterHotKey` je nieco uplne ine. Appka Windowsu VOPRED ohlasi jedinu
kombinaciu a system jej posle spravu az vtedy, ked ju niekto stlaci. O ziadnom
inom klavese sa nedozvie - technicky ani nemoze, ziadny prud vstupu cez nu
netecie. Ked uz je kombinacia obsadena inou appkou, registracia jednoducho
zlyha a `RegisterHotKey` vrati nulu.

Rozdiel v jednej vete: hook sa PYTA na vsetko a filtruje si; hotkey POVIE, na
co chce byt zobudeny, a nic ine nedostane.

Admin prava nepotrebuje (zadanie §5: `uac_admin=False` sa nesmie vratit).

PRECO VLASTNE VLAKNO
--------------------
`RegisterHotKey(NULL, ...)` viaze kombinaciu na VLAKNO, ktore ju
zaregistrovalo, a `WM_HOTKEY` pride do fronty toho vlakna, nie do okna. Tk
svoju frontu spravuje sam a spravy bez okna z nej nevytiahne, takze
registrovat to v Tk vlakne by znamenalo, ze sa hotkey nikdy neozve. Modul ma
preto vlastne vlakno s vlastnou `GetMessageW` slucku.

Callback sa vola z TOHO vlakna - appka ho musi preniest cez `ui_call`, rovnako
ako callbacky z hodiniek.

MOD_NOREPEAT
------------
Bez neho drzanie kombinacie vygeneruje zaplavu sprav a "teraz nie" by sa
zaplo a vyplo desatkrat za sekundu.

Modul sa musi dat importovat aj tam, kde ziadny user32 nie je (CI, iny OS) -
inak by padol import celej appky. Rovnaka disciplina ako `activity.py`.
"""

import threading

# --------------------------------------------------------------------------
# Kombinacie klaves
# --------------------------------------------------------------------------

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
# Bez tohto drzanie klavesu spusti zaplavu sprav.
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_MODY = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN, "super": MOD_WIN,
}

# Virtualne kody klaves, ktore dava zmysel pouzit. Zamerne UZKY zoznam: celu
# tabulku VK appka nepotrebuje a kazdy dalsi riadok je dalsia kombinacia,
# ktora sa moze bit s hrou.
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
    """Neplatny zapis kombinacie."""


def parse_combo(text):
    """'ctrl+alt+z' -> (mody, vk). Vyhodi `BadCombo` pri nezmysle.

    Aspon jeden modifikator je POVINNY. Holy klaves ako globalny hotkey by
    hracovi zobral pismeno v kazdej hre aj v kazdom chate - a on by netusil,
    preco mu "z" nefunguje.
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
    """Da sa tato kombinacia pouzit? Bez vynimky, pre normalizaciu nastaveni."""
    try:
        parse_combo(text)
        return True
    except BadCombo:
        return False


def format_combo(text):
    """Pekny zapis pre rozhranie: 'ctrl+alt+z' -> 'Ctrl + Alt + Z'."""
    if not is_valid(text):
        return ""
    kusy = [c.strip() for c in str(text).split("+") if c.strip()]
    return " + ".join(k.upper() if len(k) == 1 else k.capitalize() for k in kusy)


# --------------------------------------------------------------------------
# Registracia
# --------------------------------------------------------------------------

def _win32():
    """(ctypes, user32), alebo (None, None) ked to na tomto systeme nejde."""
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
    """Jedna kombinacia, jeden callback. Ziadny hook.

    `on_press()` sa vola z VLASTNEHO vlakna tohto modulu - volajuci ho musi
    preniest do Tk cez `ui_call`.
    """

    def __init__(self, combo, on_press, log=None):
        self.combo = combo
        self._on_press = on_press
        self._log = log
        self._thread = None
        self._tid = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self.registered = False
        self.error = None

    # ---- zivotny cyklus ----

    def start(self):
        """Vrati True, ked sa kombinaciu podarilo zaregistrovat."""
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
        # Cakanie je kratke a ohranicene: bez neho by volajuci nevedel, ci sa
        # registracia podarila, a nemal by co napisat do logu.
        self._ready.wait(timeout=2.0)
        return self.registered

    def stop(self):
        if self._thread is None:
            return
        self._stop.set()
        ctypes, _user32 = _win32()
        if ctypes is not None and self._tid:
            try:
                # Zobudi `GetMessageW`, aby slucka mohla skoncit. Bez toho by
                # vlakno viselo na fronte az do konca procesu.
                ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            except Exception:
                pass
        self._thread.join(timeout=2.0)
        self._thread = None
        self._tid = None
        self.registered = False

    # ---- vnutro ----

    def _zaloguj(self, sprava):
        if callable(self._log):
            try:
                self._log(sprava)
            except Exception:
                pass

    def _slucka(self):
        ctypes, user32 = _win32()
        if user32 is None:
            self._ready.set()
            return
        from ctypes import wintypes
        try:
            mody, vk = parse_combo(self.combo)
        except BadCombo as exc:
            self.error = str(exc)
            self._ready.set()
            return

        if not user32.RegisterHotKey(None, _HOTKEY_ID, mody, vk):
            # Najcastejsie 1409 ERROR_HOTKEY_ALREADY_REGISTERED - kombinaciu
            # drzi ina appka. Nie je to chyba appky a nesmie ju zhodit.
            self.error = ("kombinaciu sa nepodarilo zaregistrovat (%d)"
                          % ctypes.get_last_error())
            self._zaloguj("hotkey: %s" % self.error)
            self._ready.set()
            return

        try:
            self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        except Exception:
            self._tid = None
        self.registered = True
        self.error = None
        self._ready.set()
        self._zaloguj("hotkey: %s zaregistrovany" % format_combo(self.combo))

        msg = wintypes.MSG()
        try:
            while not self._stop.is_set():
                # 0 = prisiel WM_QUIT, -1 = chyba
                vysledok = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if vysledok in (0, -1):
                    break
                if msg.message == WM_HOTKEY and callable(self._on_press):
                    try:
                        self._on_press()
                    except Exception:
                        # Vynimka z callbacku nesmie zabit slucku - inak by
                        # hotkey po prvej chybe ticho prestal fungovat.
                        self._zaloguj("hotkey: callback vyhodil vynimku")
        finally:
            try:
                user32.UnregisterHotKey(None, _HOTKEY_ID)
            except Exception:
                pass
            self.registered = False
