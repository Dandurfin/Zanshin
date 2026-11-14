# -*- coding: utf-8 -*-
"""Jedna kopia appky (0.2.2, audit UX: "druha kopia natrvalo vypne senzor").

× appku len schova do listy a na Windowse 11 je ikona pod sipkou ^. Kto ju
nenasiel, spustil Zanshin.exe znova: druhe okno, Ctrl+Alt+Z "drzi ina
appka", port tepu obsadeny - a druha kopia po ~24 s ULOZILA vypnuty senzor do
spolocnych nastaveni. Teraz main.py pred importom app vytvori pomenovany
mutex; druha kopia da prvej znamenie "ukaz okno" (pomenovana udalost) a
skonci s kodom 0. Ked znamenie nejde, ukaze nativne okienko, kde appku
hladat.

Testy bezia s falosnym kernel32/user32 (ziadne okno, ziadny skutocny
mutex), okrem jedneho, ktory na Windowse overi skutocne volania pod vlastnym
menom - nikdy nie pod menom beziaceho Zanshinu.
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
    """main.py nacitany bez GUI: display a customtkinter su prazdne moduly,
    aby test nemenil DPI rezim procesu (main.py ho nastavuje pri importe)."""
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
    """Falosny kernel32: pomenovane objekty su len mena v mnozine."""

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
# prva kopia
# --------------------------------------------------------------------------

def test_prva_kopia_drzi_mutex_a_vytvori_udalost(mm):
    k32 = _Kernel()
    api = _api(k32)
    kopia = mm._straz_jednej_kopie(api=api, environ={}, platforma="win32")
    assert kopia is not None and kopia.mutex == 101 and kopia.udalost == 202
    assert ("CreateMutexW", False, "Local\\Zanshin-single") in k32.volania
    # auto-reset (manual=False), na zaciatku nenastavena
    assert ("CreateEventW", False, False, "Local\\Zanshin-show") in k32.volania
    assert api.u32.spravy == [] and k32.nastavene == []
    # mutex sa nezatvara - drzi sa do konca procesu
    assert 101 not in k32.zatvorene


# --------------------------------------------------------------------------
# druha kopia
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
    # prva kopia smie dat svoje okno do popredia
    assert api.u32.popredie == [0xFFFFFFFF]
    # druha kopia si nevytvara vlastnu udalost
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
    """Zanshin spusteny ako spravca: CreateMutexW vrati NULL s ACCESS_DENIED -
    mutex existuje, druha kopia sa nema spustit."""
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
# kedy sa straz preskakuje
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
    assert mm.POVOL_VIAC_KOPII == "ZANSHIN_ALLOW_MULTI"
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8-sig") as fh:
        readme = " ".join(fh.read().split())
    assert "`%s=1`" % mm.POVOL_VIAC_KOPII in readme
    assert "only one copy runs at a time" in readme


def test_zlyhanie_windows_api_nezabrani_startu(mm):
    def _pad(*_a):
        raise OSError("ctypes nejde")
    k32 = _Kernel()
    k32.CreateMutexW = _pad
    assert mm._straz_jednej_kopie(api=_api(k32), environ={}, platforma="win32") is None
    # NULL s inou chybou (nie "uz existuje") - appka sa spusti
    k32 = _Kernel()
    k32.CreateMutexW = lambda *a: setattr(k32, "posledna", 87) or 0
    assert mm._straz_jednej_kopie(api=_api(k32), environ={}, platforma="win32") is None


# --------------------------------------------------------------------------
# prva kopia caka na znamenie a ukaze okno
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
    # bez strazi (obchadzka, iny OS) ani bez udalosti sa nic nespusta
    assert mm._spusti_cakanie_na_dalsi_start(None, lambda: None, stop) is None
    bez = types.SimpleNamespace(api=None, udalost=None)
    assert mm._spusti_cakanie_na_dalsi_start(bez, lambda: None, stop) is None


# --------------------------------------------------------------------------
# poradie v main()
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
    """Okno ukazuje `show_window` - ta ista metoda ako "Zobrazit" v liste
    (sama ide cez ui_call, takze je bezpecna z cudzieho vlakna)."""
    telo = _main_telo()
    kod = "\n".join(ast.unparse(u) for u in telo)
    assert "_spusti_cakanie_na_dalsi_start(_JEDNA_KOPIA, app.show_window, stop)" in kod
    pokus = next(u for u in telo if isinstance(u, ast.Try))
    assert "root.mainloop()" in ast.unparse(pokus.body)
    assert "stop.set()" in ast.unparse(pokus.finalbody)
    from _zdroj_appky import zdroj_metody
    assert "self.ui_call(self._show_window)" in zdroj_metody("show_window")


# --------------------------------------------------------------------------
# skutocne Windows API (vlastne mena - beziaci Zanshin sa netkne)
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
        # auto-reset: jedno znamenie = jedno ukazanie okna
        assert k32.WaitForSingleObject(prva.udalost, 0) == 0x102
    finally:
        k32.CloseHandle(prva.udalost)
        k32.CloseHandle(prva.mutex)
