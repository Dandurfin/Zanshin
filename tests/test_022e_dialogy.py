# -*- coding: utf-8 -*-
"""Okna appky namiesto systemovych (0.2.2, davka 4 auditu UX).

  * ziadny `tkinter.messagebox` v appke - oznamy, otazky a volby idu cez
    `ui_kit.notify` / `confirm` / `choose` (tmave okno appky, tlacidla v
    jazyku appky, fokus na bezpecnom tlacidle, Enter / Escape),
  * systemove okno ostava len ZALOHA, ked sa okno appky postavit neda
    (ziadne / schovane hlavne okno, TclError) - a nikdy nevyhodi vynimku,
  * prvy × v titulkovej liste: dve jasne tlacidla "Nechat bezat v liste" /
    "Ukoncit Zanshin", Escape = nic sa nedeje a pyta sa znova.

Bez skutocneho okna - Tk triedy su atrapy, data synteticke.
"""
import ast
import glob
import os
import sys
import tkinter as tk
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import theme  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402

PAL = theme.tokens(theme.ZEN)


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


# --------------------------------------------------------------------------
# Ziadny systemovy messagebox v appke
# --------------------------------------------------------------------------

# Skripty mimo appky: harness (podstrkuje messagebox atrapou) a main.py, kde
# je systemove okno jedina moznost - customtkinter sa vtedy nenacital.
_MIMO_APPKY = {"gui_harness_auto.py", "gui_harness_onboarding.py", "main.py", "ui_kit.py"}


def test_appka_nevola_systemove_okna():
    subory = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*.py")))
    for meno in subory:
        if meno in _MIMO_APPKY:
            continue
        assert "messagebox" not in zdroj_suboru(meno), meno


def _volania_messagebox(strom):
    return [u for u in ast.walk(strom) if isinstance(u, ast.Attribute)
            and isinstance(u.value, ast.Name) and u.value.id == "messagebox"]


def test_v_ui_kit_je_messagebox_len_v_zalohe():
    strom = ast.parse(zdroj_suboru("ui_kit.py"))
    zaloha = next(u for u in strom.body
                  if isinstance(u, ast.FunctionDef) and u.name == "_systemove_okno")
    vsetky = _volania_messagebox(strom)
    assert vsetky and len(vsetky) == len(_volania_messagebox(zaloha))


def test_main_ma_systemove_okno_len_bez_customtkinter():
    src = zdroj_suboru("main.py")
    vynimka = src[src.index("import customtkinter as ctk"):src.index("sys.exit(1)")]
    assert src.count("messagebox.") == vynimka.count("messagebox.") == 1


# --------------------------------------------------------------------------
# Zaloha: systemove okno, ked sa okno appky postavit neda
# --------------------------------------------------------------------------

def _systemove(monkeypatch, ano=True):
    volania = []
    for meno in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(ui_kit.messagebox, meno,
                            lambda t, x, m=meno: volania.append((m, t, x)))
    monkeypatch.setattr(ui_kit.messagebox, "askyesno",
                        lambda t, x: volania.append(("askyesno", t, x)) or ano)
    return volania


def test_notify_bez_hlavneho_okna_ukaze_systemove_podla_druhu(monkeypatch):
    volania = _systemove(monkeypatch)
    ui_kit.notify(None, PAL, "Zanshin", "info")
    ui_kit.notify(None, PAL, "Zanshin", "pozor", kind="warning")
    ui_kit.notify(None, PAL, "Zanshin", "chyba", kind="error")
    # bez palety (atrapa appky) tiez - nie vynimka
    ui_kit.notify(types.SimpleNamespace(), None, "Zanshin", "bez palety")
    assert volania == [("showinfo", "Zanshin", "info"),
                       ("showwarning", "Zanshin", "pozor"),
                       ("showerror", "Zanshin", "chyba"),
                       ("showinfo", "Zanshin", "bez palety")]


@pytest.mark.parametrize("odpoved", [True, False])
def test_confirm_bez_okna_sa_opyta_systemovo(monkeypatch, odpoved):
    volania = _systemove(monkeypatch, ano=odpoved)
    assert ui_kit.confirm(None, PAL, "Zanshin", "Zmazat?", "Zmazat", "Zrusit",
                          danger=True) is odpoved
    assert volania == [("askyesno", "Zanshin", "Zmazat?")]


def test_choose_bez_okna_povie_text_a_vrati_bezpecnu_volbu(monkeypatch):
    volania = _systemove(monkeypatch)
    volba = ui_kit.choose(None, PAL, "Zanshin", "Co dalej?",
                          [("tray", "Do listy", "primary"), ("quit", "Koniec", "secondary")],
                          cancel=None, default="tray")
    assert volba == "tray"
    assert volania == [("showinfo", "Zanshin", "Co dalej?")]


@pytest.mark.parametrize("owner", [
    types.SimpleNamespace(winfo_exists=lambda: False),          # znicene
    types.SimpleNamespace(winfo_exists=lambda: True,            # schovane v liste
                          winfo_viewable=lambda: False),
])
def test_neviditelne_hlavne_okno_nedostane_modalny_dialog(monkeypatch, owner):
    """Dialog nad oknom schovanym v liste by ostal neviditelny s grabom -
    appka by cakala na odpoved, ktoru nikto nevidi."""
    volania = _systemove(monkeypatch)

    def nestavat(*a, **k):
        raise AssertionError("okno appky sa nema ani zacat stavat")

    monkeypatch.setattr(ui_kit.ctk, "CTkToplevel", nestavat)
    assert ui_kit.confirm(owner, PAL, "Z", "otazka", "Ano", "Nie") is True
    ui_kit.notify(owner, PAL, "Z", "oznam")
    assert [v[0] for v in volania] == ["askyesno", "showinfo"]


def test_tclerror_pri_stavbe_okna_padne_na_systemove(monkeypatch):
    volania = _systemove(monkeypatch)

    def zlyhaj(*a, **k):
        raise tk.TclError("can't open display")

    monkeypatch.setattr(ui_kit.ctk, "CTkToplevel", zlyhaj)
    owner = types.SimpleNamespace()
    assert ui_kit.confirm(owner, PAL, "Z", "otazka", "Ano", "Nie") is True
    ui_kit.notify(owner, PAL, "Z", "oznam", kind="error")
    assert ui_kit.choose(owner, PAL, "Z", "volba", [("a", "A", "primary")],
                         cancel=None, default="a") == "a"
    assert [v[0] for v in volania] == ["askyesno", "showerror", "showinfo"]


def test_tclerror_v_obsahu_zrusi_rozostavane_okno(monkeypatch):
    """Okno vzniklo, ale obsah nie - nesmie ostat visiet prazdne."""
    volania = _systemove(monkeypatch)
    okna = []

    class _Okno:
        def __init__(self, *a, **k):
            self.znicene = False
            okna.append(self)

        def title(self, *a):
            pass

        def configure(self, **k):
            pass

        def resizable(self, *a):
            pass

        def protocol(self, *a):
            pass

        def destroy(self):
            self.znicene = True

    def chrome(*a, **k):
        raise tk.TclError("bad window path name")

    monkeypatch.setattr(ui_kit.ctk, "CTkToplevel", _Okno)
    monkeypatch.setattr(ui_kit, "DialogChrome", chrome)
    ui_kit.notify(types.SimpleNamespace(), PAL, "Z", "oznam")
    assert okna and okna[0].znicene
    assert volania == [("showinfo", "Z", "oznam")]


def test_zlyhane_systemove_okno_nevyhodi_vynimku(monkeypatch):
    def zlyhaj(*a, **k):
        raise tk.TclError("no display")

    for meno in ("showinfo", "showwarning", "showerror", "askyesno"):
        monkeypatch.setattr(ui_kit.messagebox, meno, zlyhaj)
    assert ui_kit.confirm(None, PAL, "Z", "x", "Ano", "Nie") is False
    assert ui_kit.notify(None, PAL, "Z", "x") is None
    assert ui_kit.choose(None, PAL, "Z", "x", [("a", "A", "primary")],
                         default="a") == "a"


# --------------------------------------------------------------------------
# Okno appky: fokus a Enter na bezpecnom tlacidle, Escape = zrusit
# --------------------------------------------------------------------------

class _Tlacidlo:
    def __init__(self, okno, hodnota_popis, druh, command):
        self.okno, self.popis, self.druh, self.command = okno, hodnota_popis, druh, command
        self.cesta = f".dlg.b{len(okno.tlacidla)}"

    def __str__(self):
        return self.cesta

    def pack(self, *a, **k):
        pass

    def focus_set(self):
        self.okno.fokus = self


class _Okno:
    posledne = None

    def __init__(self, *a, **k):
        self.tlacidla, self.binds, self.after_fn = [], {}, []
        self.fokus, self.znicene, self.protokol = None, False, {}
        _Okno.posledne = self

    def title(self, *a):
        pass

    def configure(self, **k):
        pass

    def resizable(self, *a):
        pass

    def protocol(self, meno, fn):
        self.protokol[meno] = fn

    def bind(self, seq, fn):
        self.binds[seq] = fn

    def after(self, _ms, fn):
        self.after_fn.append(fn)

    def update_idletasks(self):
        pass

    def _get_window_scaling(self):
        return 1.0

    def winfo_reqwidth(self):
        return 300

    def winfo_reqheight(self):
        return 160

    def transient(self, *a):
        pass

    def grab_set(self):
        pass

    def grab_release(self):
        pass

    def grab_current(self):
        return None

    def focus_get(self):
        return self.fokus

    def destroy(self):
        self.znicene = True


class _Kus:
    def __init__(self, *a, **kw):
        self.kw = kw
        _Kus.vsetky.append(self)

    def pack(self, *a, **k):
        pass


@pytest.fixture
def okno_appky(monkeypatch):
    """Atrapy Tk + zaznam: ktore tlacidla vznikli, kam ide fokus, kde stoji."""
    _Kus.vsetky = []
    stav = types.SimpleNamespace(umiestnenie=[], chrome=[])

    def button(master, pal, text, command=None, kind="secondary", **kw):
        okno = _Okno.posledne
        b = _Tlacidlo(okno, text, kind, command)
        okno.tlacidla.append(b)
        return b

    def chrome(top, pal, title, on_close=None, **kw):
        stav.chrome.append((title, on_close))
        return types.SimpleNamespace(body=None)

    monkeypatch.setattr(ui_kit.ctk, "CTkToplevel", _Okno)
    monkeypatch.setattr(ui_kit.ctk, "CTkFrame", _Kus)
    monkeypatch.setattr(ui_kit.ctk, "CTkLabel", _Kus)
    monkeypatch.setattr(ui_kit, "button", button)
    monkeypatch.setattr(ui_kit, "DialogChrome", chrome)
    monkeypatch.setattr(ui_kit, "umiestni_dialog",
                        lambda top, owner, w, h, **k: stav.umiestnenie.append((w, h)))
    return stav


def _owner(akcia):
    """Hlavne okno, ktore pocas cakania "klikne" - `akcia(okno)`."""
    def cakaj(top):
        for fn in list(top.after_fn):
            fn()                  # oneskorene `focus_set`
        akcia(top)
    return types.SimpleNamespace(wait_window=cakaj)


def test_confirm_fokus_aj_enter_na_zrusit(okno_appky):
    ok = ui_kit.confirm(_owner(lambda top: top.binds["<Return>"]()), PAL, "Z",
                        "Naozaj zmazat?", "Zmazat", "Zrusit", danger=True)
    top = _Okno.posledne
    assert ok is False, "Enter omylom nesmie zmazat"
    assert top.fokus.popis == "Zrusit"
    assert [(b.popis, b.druh) for b in top.tlacidla][::-1] == [
        ("Zmazat", "danger"), ("Zrusit", "secondary")]
    assert top.znicene


def test_confirm_enter_na_inom_tlacidle_stlaci_to(okno_appky):
    def klik(top):
        zmazat = next(b for b in top.tlacidla if b.popis == "Zmazat")
        zmazat.focus_set()        # Tab na "Zmazat", potom Enter
        top.binds["<Return>"]()

    assert ui_kit.confirm(_owner(klik), PAL, "Z", "x", "Zmazat", "Zrusit",
                          danger=True) is True


def test_escape_a_krizik_su_zrusit(okno_appky):
    def escape(top):
        _title, on_close = okno_appky.chrome[-1]
        on_close()                # DialogChrome: Escape aj ✕ volaju on_close

    volba = ui_kit.choose(_owner(escape), PAL, "Z", "x",
                          [("tray", "Do listy", "primary"), ("quit", "Koniec", "secondary")],
                          cancel=None, default="tray")
    assert volba is None
    top = _Okno.posledne
    assert top.protokol["WM_DELETE_WINDOW"] is not None
    assert ui_kit.confirm(_owner(lambda t: t.protokol["WM_DELETE_WINDOW"]()), PAL,
                          "Z", "x", "Ano", "Nie") is False


def test_choose_fokus_a_enter_na_predvolenej_volbe(okno_appky):
    volba = ui_kit.choose(_owner(lambda top: top.binds["<Return>"]()), PAL, "Z", "x",
                          [("tray", "Do listy", "primary"), ("quit", "Koniec", "secondary")],
                          cancel=None, default="tray")
    assert volba == "tray"
    assert _Okno.posledne.fokus.popis == "Do listy"
    assert "<KP_Enter>" in _Okno.posledne.binds


def test_notify_jedno_tlacidlo_ok_v_jazyku_appky(okno_appky, sk):
    assert ui_kit.notify(_owner(lambda top: top.binds["<Return>"]()), PAL, "Z",
                         "oznam") is None
    top = _Okno.posledne
    assert [(b.popis, b.druh) for b in top.tlacidla] == [(i18n.tr("dialog.ok"), "primary")]
    assert top.fokus is top.tlacidla[0] and top.znicene


def test_okno_ma_zalomeny_text_a_stoji_v_strede_plochy(okno_appky):
    dlhy = "slovo " * 200
    ui_kit.notify(_owner(lambda top: top.binds["<Return>"]()), PAL, "Z", dlhy)
    texty = [k for k in _Kus.vsetky if k.kw.get("text") == dlhy]
    assert texty and texty[0].kw["wraplength"] == ui_kit.DIALOG_TEXT_W
    (sirka, _vyska), = okno_appky.umiestnenie
    assert sirka >= ui_kit.DIALOG_MIN_W, "kratky oznam nema byt uzky pruzok"


def test_oznam_nad_inym_dialogom_mu_vrati_grab(okno_appky):
    vratene = []
    dialog = types.SimpleNamespace(winfo_exists=lambda: True,
                                   grab_set=lambda: vratene.append(True))
    povodne = _Okno.grab_current
    _Okno.grab_current = lambda self: dialog
    try:
        ui_kit.notify(_owner(lambda top: top.binds["<Return>"]()), PAL, "Z", "x")
    finally:
        _Okno.grab_current = povodne
    assert vratene == [True]


# --------------------------------------------------------------------------
# Prvy × - dve jasne tlacidla
# --------------------------------------------------------------------------

def _app_na_zatvorenie():
    zaznam = []
    a = types.SimpleNamespace(
        tray_close_explained=False, hr_port=4455, root=None, pal=PAL,
        save_settings=lambda: zaznam.append("save"),
        minimize_to_tray=lambda: zaznam.append("tray"),
        quit_app=lambda: zaznam.append("quit"))
    return a, zaznam


def test_prvy_krizik_ponukne_listu_a_ukoncenie(monkeypatch, sk):
    import app as app_mod
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    otazky = []

    def choose(owner, pal, title, text, choices, cancel=None, default=None):
        otazky.append((text, choices, cancel, default))
        return "tray"

    monkeypatch.setattr(ui_kit, "choose", choose)
    a, zaznam = _app_na_zatvorenie()
    app_mod.DandurfApp.on_close(a)
    (text, choices, cancel, default), = otazky
    assert text == i18n.tr("tray.close_first", port=4455)
    assert choices == [("tray", i18n.tr("tray.keep_running"), "primary"),
                       ("quit", i18n.tr("tray.quit_app"), "secondary")]
    assert default == "tray", "Enter = bezpecne (appka bezi dalej)"
    assert cancel is None
    assert zaznam == ["save", "tray"]


def test_escape_pri_prvom_krizi_necha_okno_a_pyta_sa_znova(monkeypatch):
    import app as app_mod
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    otazky = []
    monkeypatch.setattr(ui_kit, "choose", lambda *a, **k: otazky.append(a) or None)
    a, zaznam = _app_na_zatvorenie()
    app_mod.DandurfApp.on_close(a)
    assert zaznam == [], "Escape / ✕ v dialogu: okno ostava, nic sa neulozi"
    assert a.tray_close_explained is False
    app_mod.DandurfApp.on_close(a)
    assert len(otazky) == 2, "este nevybral - pyta sa znova"


def test_ukoncit_z_dialogu_ukonci_appku(monkeypatch):
    import app as app_mod
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    monkeypatch.setattr(ui_kit, "choose", lambda *a, **k: "quit")
    a, zaznam = _app_na_zatvorenie()
    app_mod.DandurfApp.on_close(a)
    assert zaznam == ["save", "quit"] and a.tray_close_explained is True


def test_veta_pri_krizi_nespomina_ano_nie():
    zaznam = i18n.STRINGS["tray.close_first"]
    assert "(Nie" not in zaznam["sk"] and "Áno" not in zaznam["sk"]
    assert "(No" not in zaznam["en"] and "Yes" not in zaznam["en"]
    for jazyk in i18n.LANGUAGES:
        text = zaznam[jazyk]
        assert "=" not in text, jazyk          # "(Nie = ukoncit hned)"
        assert "^" in text and "▶" in text and "{port}" in text, jazyk
    assert "meriam a ukladám" in zaznam["sk"]


@pytest.mark.parametrize("kluc", ["tray.keep_running", "tray.quit_app",
                                  "profile.delete_btn", "dialog.ok"])
def test_nove_tlacidla_vo_vsetkych_jazykoch(kluc):
    zaznam = i18n.STRINGS[kluc]
    assert set(zaznam) == set(i18n.LANGUAGES)
    for jazyk in i18n.LANGUAGES:
        assert zaznam[jazyk].strip(), (kluc, jazyk)
        if kluc != "dialog.ok" and jazyk not in ("sk", "en"):
            assert zaznam[jazyk] != zaznam["en"], (kluc, jazyk)
    if kluc == "tray.quit_app":
        assert all("Zanshin" in zaznam[j] for j in i18n.LANGUAGES)


def test_tlacidla_dialogu_su_sloveso_nie_ano_nie():
    sk = {k: i18n.STRINGS[k]["sk"] for k in ("tray.keep_running", "tray.quit_app")}
    assert sk == {"tray.keep_running": "Nechať bežať v lište",
                  "tray.quit_app": "Ukončiť Zanshin"}
    assert i18n.STRINGS["tray.keep_running"]["en"] == "Keep running in the tray"
    assert i18n.STRINGS["tray.quit_app"]["en"] == "Quit Zanshin"


# --------------------------------------------------------------------------
# Kto co vola
# --------------------------------------------------------------------------

def test_zmazanie_profilu_v_okne_appky_so_slovesom():
    telo = zdroj_metody("delete_current_profile")
    assert "ui_kit.confirm(" in telo and "danger=True" in telo
    assert 'ok_label=tr("profile.delete_btn")' in telo
    assert 'ui_kit.notify(okno, pal, APP_NAME, tr("profile.cannot_delete_last"))' in telo


def test_on_close_pouziva_okno_appky():
    telo = zdroj_metody("on_close")
    assert "ui_kit.choose(" in telo
    assert 'tr("tray.keep_running")' in telo and 'tr("tray.quit_app")' in telo
    assert 'default="tray"' in telo and "cancel=None" in telo
