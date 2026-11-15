# -*- coding: utf-8 -*-
"""One app copy (0.3, UX audit: "a second copy disables the sensor for good").

× only hides the app to the tray, and on Windows 11 the icon is under the
^ arrow. Whoever did not find it started Zanshin.exe again: a second
window, Ctrl+Alt+Z "held by another app", the heart rate port taken - and
after ~24 s the second copy SAVED a switched-off sensor into the shared
settings. Now main.py creates a named mutex before importing app; the
second copy gives the first one the signal "show the window" (a named
event) and exits with code 0. When the signal does not work, it shows a
native little window saying where to look for the app.

The tests run with a fake kernel32/user32 (no window, no real mutex),
except one that checks the real calls on Windows under its own name -
never under the name of a running Zanshin.
"""
import ast
import importlib.util
import json
import os
import sys
import threading
import types
import uuid

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402


@pytest.fixture
def mm(monkeypatch):
    """main.py loaded without a GUI: display and customtkinter are empty
    modules, so that the test does not change the process DPI mode
    (main.py sets it on import)."""
    displej = types.ModuleType("display")
    displej.enable_dpi_awareness = lambda: None
    monkeypatch.setitem(sys.modules, "display", displej)
    ctk = types.ModuleType("customtkinter")
    ctk.CTk = lambda: types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "customtkinter", ctk)
    spec = importlib.util.spec_from_file_location(
        "zanshin_main_022b", os.path.join(ROOT, "main.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class _Kernel:
    """Fake kernel32: named objects are just names in a set."""

    def __init__(self, existuje=(), set_ok=True, cakania=()):
        self.objekty = set(existuje)
        self.set_ok = set_ok
        self.cakania = list(cakania)
        self.posledna = 0
        self.volania = []
        self.nastavene = []
        self.zatvorene = []

    def CreateMutexW(self, attrs, vlastnik, meno):
        self.volania.append(("CreateMutexW", vlastnik, meno))
        self.posledna = 183 if meno in self.objekty else 0
        self.objekty.add(meno)
        return 101

    def CreateEventW(self, attrs, manual, zapnuta, meno):
        self.volania.append(("CreateEventW", manual, zapnuta, meno))
        self.objekty.add(meno)
        self.posledna = 0
        return 202

    def OpenEventW(self, pristup, dedit, meno):
        self.volania.append(("OpenEventW", pristup, meno))
        return 303 if meno in self.objekty else 0

    def SetEvent(self, handle):
        self.nastavene.append(handle)
        return 1 if self.set_ok else 0

    def CloseHandle(self, handle):
        self.zatvorene.append(handle)
        return 1

    def WaitForSingleObject(self, handle, ms):
        self.volania.append(("Wait", handle, ms))
        return self.cakania.pop(0) if self.cakania else 0x102


class _User:
    def __init__(self):
        self.spravy = []
        self.popredie = []

    def MessageBoxW(self, hwnd, text, titul, styl):
        self.spravy.append((text, titul, styl))
        return 1

    def AllowSetForegroundWindow(self, kto):
        self.popredie.append(kto)
        return 1


def _api(k32):
    return types.SimpleNamespace(k32=k32, u32=_User(),
                                 posledna_chyba=lambda: k32.posledna)


# --------------------------------------------------------------------------
# first copy
# --------------------------------------------------------------------------

def test_prva_kopia_drzi_mutex_a_vytvori_udalost(mm):
    k32 = _Kernel()
    api = _api(k32)
    kopia = mm._straz_jednej_kopie(api=api, environ={}, platforma="win32")
    assert kopia is not None and kopia.mutex == 101 and kopia.udalost == 202
    assert ("CreateMutexW", False, "Local\\Zanshin-single") in k32.volania
    # auto-reset (manual=False), not set at the start
    assert ("CreateEventW", False, False, "Local\\Zanshin-show") in k32.volania
    assert api.u32.spravy == [] and k32.nastavene == []
    # the mutex is not closed - it is held until the process ends
    assert 101 not in k32.zatvorene


# --------------------------------------------------------------------------
# second copy
# --------------------------------------------------------------------------

def test_druha_kopia_da_znamenie_a_ticho_skonci(mm):
    k32 = _Kernel(existuje={"Local\\Zanshin-single", "Local\\Zanshin-show"})
    api = _api(k32)
    with pytest.raises(SystemExit) as koniec:
        mm._straz_jednej_kopie(api=api, environ={}, platforma="win32")
    assert koniec.value.code == 0, "druhy start nie je chyba"
    assert ("OpenEventW", 0x0002, "Local\\Zanshin-show") in k32.volania
    assert k32.nastavene == [303]
    assert 303 in k32.zatvorene, "handle udalosti sa ma zatvorit"
    assert api.u32.spravy == [], "okno sa ukaze samo - okienko netreba"
    # the first copy may bring its window to the foreground
    assert api.u32.popredie == [0xFFFFFFFF]
    # the second copy does not create its own event
    assert not any(v[0] == "CreateEventW" for v in k32.volania)


@pytest.mark.parametrize("udalost_je, set_ok", [(False, True), (True, False)])
def test_ked_znamenie_zlyha_ukaze_okienko(mm, udalost_je, set_ok):
    existuje = {"Local\\Zanshin-single"}
    if udalost_je:
        existuje.add("Local\\Zanshin-show")
    k32 = _Kernel(existuje=existuje, set_ok=set_ok)
    api = _api(k32)
    with pytest.raises(SystemExit) as koniec:
        mm._straz_jednej_kopie(api=api, environ={}, platforma="win32")
    assert koniec.value.code == 0
    assert len(api.u32.spravy) == 1
    text, titul, styl = api.u32.spravy[0]
    assert titul == "Zanshin"
    assert "^" in text and "Zanshin" in text
    assert styl & 0x40, "informacia, nie chyba"


def test_mutex_vyssich_prav_sa_rata_ako_beziaca_kopia(mm):
    """Zanshin started as administrator: CreateMutexW returns NULL with
    ACCESS_DENIED - the mutex exists, the second copy must not start."""
    k32 = _Kernel(existuje={"Local\\Zanshin-show"})
    k32.CreateMutexW = lambda *a: setattr(k32, "posledna", 5) or 0
    api = _api(k32)
    with pytest.raises(SystemExit) as koniec:
        mm._straz_jednej_kopie(api=api, environ={}, platforma="win32")
    assert koniec.value.code == 0 and k32.nastavene == [303]


def test_okienko_v_ulozenom_jazyku_inak_anglicky_a_slovensky(mm):
    for jazyk in ("de", "sk", "bg"):
        assert mm._text_uz_bezi(jazyk) == i18n.tr_lang(jazyk, "tray.already_running")
    obe = mm._text_uz_bezi(None)
    assert i18n.tr_lang("en", "tray.already_running") in obe
    assert i18n.tr_lang("sk", "tray.already_running") in obe
    assert mm._text_uz_bezi("xx") == obe


def test_text_zo_zadania_a_vo_vsetkych_jazykoch():
    assert i18n.STRINGS["tray.already_running"]["sk"] == (
        "Zanshin už beží — nájdeš ho v lište pri hodinách (ak ikonu nevidíš, "
        "klikni na šípku ^).")
    for jazyk in i18n.LANGUAGES:
        text = i18n.tr_lang(jazyk, "tray.already_running")
        assert "Zanshin" in text and "^" in text, jazyk


def test_ulozeny_jazyk_sa_cita_bezpecne(mm, tmp_path, monkeypatch):
    import paths
    subor = tmp_path / "dandurf_settings.json"
    monkeypatch.setattr(paths, "SETTINGS_PATH", str(subor))
    assert mm._ulozeny_jazyk() is None, "chybajuci subor"
    subor.write_text(json.dumps({"lang": "fr"}), encoding="utf-8")
    assert mm._ulozeny_jazyk() == "fr"
    for zle in ("{", "[1, 2]", json.dumps({"lang": 7}), "\x00\x01"):
        subor.write_text(zle, encoding="utf-8")
        assert mm._ulozeny_jazyk() is None, zle


# --------------------------------------------------------------------------
# when the guard is skipped
# --------------------------------------------------------------------------

@pytest.mark.parametrize("environ, platforma", [
    ({"ZANSHIN_ALLOW_MULTI": "1"}, "win32"),
    ({"PYTEST_CURRENT_TEST": "x"}, "win32"),
    ({}, "linux"),
    ({}, "darwin"),
])
def test_obchadzka_a_iny_os_mutex_nevytvaraju(mm, environ, platforma):
    k32 = _Kernel(existuje={"Local\\Zanshin-single", "Local\\Zanshin-show"})
    api = _api(k32)
    assert mm._straz_jednej_kopie(api=api, environ=environ, platforma=platforma) is None
    assert k32.volania == [] and api.u32.spravy == []


def test_obchadzka_ma_verejne_meno_a_readme_ju_menuje(mm):
    # Since 0.3d running from source is in DEVELOPMENT.md, not in the README.
    assert mm.POVOL_VIAC_KOPII == "ZANSHIN_ALLOW_MULTI"
    with open(os.path.join(ROOT, "DEVELOPMENT.md"), encoding="utf-8-sig") as fh:
        readme = " ".join(fh.read().split())
    assert "`%s=1`" % mm.POVOL_VIAC_KOPII in readme
    assert "only one copy runs at a time" in readme


def test_zlyhanie_windows_api_nezabrani_startu(mm):
    def _pad(*_a):
        raise OSError("ctypes nejde")
    k32 = _Kernel()
    k32.CreateMutexW = _pad
    assert mm._straz_jednej_kopie(api=_api(k32), environ={}, platforma="win32") is None
    # NULL with a different error (not "already exists") - the app starts
    k32 = _Kernel()
    k32.CreateMutexW = lambda *a: setattr(k32, "posledna", 87) or 0
    assert mm._straz_jednej_kopie(api=_api(k32), environ={}, platforma="win32") is None


# --------------------------------------------------------------------------
# the first copy waits for the signal and shows the window
# --------------------------------------------------------------------------

def test_znamenie_ukaze_okno_kazdy_raz(mm):
    stop = threading.Event()
    k32 = _Kernel(cakania=[0x102, 0x0, 0x102, 0x0])
    ukazane = []

    def ukaz():
        ukazane.append(1)
        if len(ukazane) == 2:
            stop.set()

    kopia = types.SimpleNamespace(api=_api(k32), udalost=202)
    mm._cakaj_na_dalsi_start(kopia, ukaz, stop, krok_ms=5)
    assert ukazane == [1, 1]
    assert all(v[1] == 202 and v[2] == 5 for v in k32.volania if v[0] == "Wait")


def test_chyba_cakania_vlakno_ukonci(mm):
    k32 = _Kernel(cakania=[0xFFFFFFFF, 0x0])
    ukazane = []
    kopia = types.SimpleNamespace(api=_api(k32), udalost=202)
    mm._cakaj_na_dalsi_start(kopia, lambda: ukazane.append(1), threading.Event())
    assert ukazane == [] and len(k32.cakania) == 1


def test_pad_pri_ukazani_vlakno_nezabije(mm):
    stop = threading.Event()
    k32 = _Kernel(cakania=[0x0, 0x0])
    pokusy = []

    def ukaz():
        pokusy.append(1)
        if len(pokusy) == 2:
            stop.set()
        raise RuntimeError("Tk uz nebezi")

    kopia = types.SimpleNamespace(api=_api(k32), udalost=202)
    mm._cakaj_na_dalsi_start(kopia, ukaz, stop, krok_ms=1)
    assert pokusy == [1, 1]


def test_vlakno_sa_pri_ukonceni_zastavi(mm):
    stop = threading.Event()
    kopia = types.SimpleNamespace(api=_api(_Kernel()), udalost=202)
    vlakno = mm._spusti_cakanie_na_dalsi_start(kopia, lambda: None, stop)
    assert vlakno is not None and vlakno.daemon
    stop.set()
    vlakno.join(timeout=5)
    assert not vlakno.is_alive()
    # no guard (bypass, other OS) or no event: nothing is started
    assert mm._spusti_cakanie_na_dalsi_start(None, lambda: None, stop) is None
    bez = types.SimpleNamespace(api=None, udalost=None)
    assert mm._spusti_cakanie_na_dalsi_start(bez, lambda: None, stop) is None


# --------------------------------------------------------------------------
# the order in main()
# --------------------------------------------------------------------------

def _main_telo():
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as fh:
        strom = ast.parse(fh.read())
    return next(u for u in strom.body
                if isinstance(u, ast.FunctionDef) and u.name == "main").body


def _index(telo, podmienka):
    return next(i for i, u in enumerate(telo) if podmienka(u))


def test_straz_je_za_hookmi_a_pred_importom_app():
    telo = _main_telo()
    hooky = _index(telo, lambda u: "_install_crash_hooks" in ast.dump(u))
    straz = _index(telo, lambda u: "_straz_jednej_kopie" in ast.dump(u))
    app = _index(telo, lambda u: isinstance(u, ast.ImportFrom) and u.module == "app")
    assert hooky < straz < app


def test_druhy_start_ukaze_okno_cez_existujucu_cestu_listy():
    """The window is shown by `show_window` - the same method as "Show" in
    the tray (it goes through ui_call itself, so it is safe from another
    thread)."""
    telo = _main_telo()
    kod = "\n".join(ast.unparse(u) for u in telo)
    assert "_spusti_cakanie_na_dalsi_start(_JEDNA_KOPIA, app.show_window, stop)" in kod
    pokus = next(u for u in telo if isinstance(u, ast.Try))
    assert "root.mainloop()" in ast.unparse(pokus.body)
    assert "stop.set()" in ast.unparse(pokus.finalbody)
    from _zdroj_appky import zdroj_metody
    assert "self.ui_call(self._show_window)" in zdroj_metody("show_window")


# --------------------------------------------------------------------------
# the real Windows API (own names - a running Zanshin is not touched)
# --------------------------------------------------------------------------

@pytest.mark.skipif(not sys.platform.startswith("win"), reason="len Windows")
def test_skutocny_mutex_a_udalost(mm, monkeypatch):
    znacka = uuid.uuid4().hex
    monkeypatch.setattr(mm, "_MUTEX_MENO", "Local\\Zanshin-test-%s" % znacka)
    monkeypatch.setattr(mm, "_UDALOST_MENO", "Local\\Zanshin-test-show-%s" % znacka)
    okienka = []
    monkeypatch.setattr(mm, "_ukaz_uz_bezi", lambda api: okienka.append(api))
    prva = mm._straz_jednej_kopie(environ={}, platforma="win32")
    assert prva is not None and prva.mutex and prva.udalost
    k32 = prva.api.k32
    try:
        assert k32.WaitForSingleObject(prva.udalost, 0) == 0x102, "este nic"
        with pytest.raises(SystemExit) as koniec:
            mm._straz_jednej_kopie(environ={}, platforma="win32")
        assert koniec.value.code == 0
        assert okienka == [], "znamenie malo prejst"
        assert k32.WaitForSingleObject(prva.udalost, 0) == 0x0, "znamenie prislo"
        # auto-reset: one signal = one showing of the window
        assert k32.WaitForSingleObject(prva.udalost, 0) == 0x102
    finally:
        k32.CloseHandle(prva.udalost)
        k32.CloseHandle(prva.mutex)
