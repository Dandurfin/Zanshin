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


# Mena modifikatorov tak, ako ich ma klavesnica a Windows v danom jazyku
# (0.2.2 davka 4b). Nemecka klavesnica ma "Strg" a "Umschalt", nie "Ctrl" a
# "Shift" - nemecky hrac by "Ctrl + Alt + Z" hladal na klavesnici marne.
# Nastavenia aj registracia ostavaju v anglickom zapise ('ctrl+alt+z'); toto
# je LEN to, co sa ukaze. Jazyk, ktory tu nie je, ma anglicke mena.
_MENA_MODIFIKATOROV = {
    "de": {"ctrl": "Strg", "control": "Strg", "shift": "Umschalt"},
}


def _jazyk_appky():
    """Jazyk rozhrania appky - lenivy import, aby `hotkey` nezavisel od i18n
    (modul sa importuje aj samostatne, napr. v testoch)."""
    try:
        import i18n
        return i18n._lang["code"]
    except Exception:
        return "en"


def format_combo(text, lang=None, oddelovac=" + "):
    """Pekny zapis pre rozhranie: 'ctrl+alt+z' -> 'Ctrl + Alt + Z'.

    `lang` (predvolene jazyk appky) vyberie mena modifikatorov - po nemecky
    'Strg + Alt + Z'. Pre app.log (`lang="en"`) ostava anglicky zapis."""
    if not is_valid(text):
        return ""
    mena = _MENA_MODIFIKATOROV.get(_jazyk_appky() if lang is None else lang, {})
    kusy = [c.strip() for c in str(text).split("+") if c.strip()]
    return oddelovac.join(
        mena.get(k.lower()) or (k.upper() if len(k) == 1 else k.capitalize())
        for k in kusy)


# --------------------------------------------------------------------------
# Zrazka s rozlozenim klavesnice (0.2.2)
# --------------------------------------------------------------------------
#
# PRECO: na Windows je AltGr to iste co Ctrl+Alt. Na polskom rozlozeni
# AltGr+Z pise "ż" - globalne zaregistrovane Ctrl+Alt+Z by hracovi to
# pismeno zhltlo v kazdom okne (chat, prehliadac, dokument), aj ked je appka
# len v liste. Pred registraciou sa preto opyta kazdeho NAINSTALOVANEHO
# rozlozenia, ci z tej kombinacie nevznikne znak.
#
# Detekcia je cista funkcia s vlozitelnymi zavislostami (`rozlozenia`,
# `znak`): testy ju overia na vymyslenom polskom rozlozeni bez toho, aby
# sa v systeme cokolvek menilo. Ked sa Windowsu opytat neda (iny OS, chyba
# ctypes), zrazka sa NEHLASI - appka sa sprava ako doteraz.

# Predvolby v Nastaveniach -> Vseobecne. Prva je predvolena skratka appky,
# dalsie su zaloha: F-klavesy nepise ziadne rozlozenie ako znak, takze s
# AltGr sa nebiju nikde.
PRESETS = ("ctrl+alt+z", "ctrl+alt+f9", "ctrl+alt+f12", "ctrl+shift+f12")

_VK_SHIFT, _VK_CONTROL, _VK_MENU = 0x10, 0x11, 0x12
_VK_LSHIFT, _VK_LCONTROL, _VK_RMENU = 0xA0, 0xA2, 0xA5
# ToUnicodeEx: bit 2 = "nemen stav klavesnice" (Windows 10 1607+). Bez neho
# by mrtvy klaves (diakritika) ostal visiet a pokazil dalsie pismeno.
_TU_NEMEN_STAV = 0x4


def _rozlozenia():
    """Handle (HKL) vsetkych nainstalovanych rozlozeni; [] ked sa neda."""
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
    """Co napise rozlozenie `hkl` na klaves `vk` s AltGr (Ctrl+Alt) a
    pripadne Shiftom. "" = nic. Vynimka von nejde."""
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
            # Mrtvy klaves (napr. ˇ alebo ´): aj ten je pismo. Druhe volanie
            # ho zo stavu vycisti aj na starsom Windowse, ktory bit 2 nepozna.
            znak = buf.value[:1]
            user32.ToUnicodeEx(vk, sken, stav, buf, 8, _TU_NEMEN_STAV, hkl)
            return znak
        return buf.value[:n] if n > 0 else ""
    except Exception:
        return ""


def _tlacitelny(text):
    """Je v `text` znak, ktory by sa napisal (nie riadiaci znak)?"""
    return any(ch.isprintable() and ord(ch) >= 0x20 for ch in str(text or ""))


def znak_kolizie(text, rozlozenia=None, znak=None):
    """Znak, ktory by kombinacia `text` napisala na niektorom nainstalovanom
    rozlozeni (AltGr = Ctrl+Alt), alebo "" ked sa s pismom nebije.

    Plati len pre kombinacie s Ctrl AJ Alt a bez Win - ine modifikatory
    znak nepisu. `rozlozenia` (zoznam HKL) a `znak(hkl, vk, shift)` sa daju
    vlozit (testy); predvolene sa pyta Windowsu. Ziadna chyba von nejde."""
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
    """Prva platna predvolba, ktora sa s pismom nebije; "" ked ziadna.

    `kolizia(text) -> znak` (predvolene `znak_kolizie`) sa da vlozit."""
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

    `on_result(ok)` (0.2.2 davka 4b) sa zavola z toho isteho vlakna RAZ, ked
    Windows registraciu naozaj dokonci - uspesne aj neuspesne. `start()` caka
    na vysledok najviac 2 s; ked je Windows pri starte pomaly, vrati False a
    `caka` je True: skratka nie je obsadena, len este nie je hotova.
    Pravdivy vysledok potom povie az `on_result`.
    """

    # Kolko `start()` caka na vysledok registracie (s). Atribut triedy, aby
    # test s pomalou falosnou registraciou nemusel cakat cele 2 s.
    CAKAJ_NA_REGISTRACIU_S = 2.0

    def __init__(self, combo, on_press, log=None, on_result=None):
        self.combo = combo
        self._on_press = on_press
        # Verejny atribut: da sa nastavit aj po vytvoreni (appka ho tak
        # nastavuje, aby fungovali aj zjednodusene atrapy v testoch).
        self.on_result = on_result
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
        # registracia podarila, a nemal by co napisat do logu. Ked nestaci
        # (pomaly start Windows), `caka` ostane True a vysledok pride cez
        # `on_result` - volajuci nesmie False brat ako "obsadene".
        self._ready.wait(timeout=self.CAKAJ_NA_REGISTRACIU_S)
        return self.registered

    @property
    def caka(self):
        """Registracia este nedobehla (vlakno bezi, vysledok neprisiel)."""
        return self._thread is not None and not self._ready.is_set()

    def _hotovo(self, ok):
        """Vysledok registracie: najprv `_ready` (to cita `start`), potom
        `on_result`. Vynimka z callbacku nesmie zabit vlakno."""
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
            # Najcastejsie 1409 ERROR_HOTKEY_ALREADY_REGISTERED - kombinaciu
            # drzi ina appka. Nie je to chyba appky a nesmie ju zhodit.
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
        # app.log je po anglicky bez ohladu na jazyk appky
        self._zaloguj("hotkey: %s zaregistrovany" % format_combo(self.combo, lang="en"))
        self._hotovo(True)

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
