# -*- coding: utf-8 -*-
"""Check of the 0.3 visual batch on fresh screenshots - what was found.

  * the divider line (`ui_kit.linka`) disappeared after switching the
    world Play <-> Work: on recolouring, the parent sends its background
    to its children and the 1 px line is visible only thanks to
    `bg_color` in its own colour (screenshots 09/09b),
  * the confirmation in the app window (`ui_kit.confirm`) must not return
    before the person answers - not even when `grab_set` itself fails,
  * the cue card stands on the same left edge as the panels around it.

No real window - the Tk classes are fakes.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import theme  # noqa: E402
import theme_recolor  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import zdroj_suboru  # noqa: E402


class _Ram:
    """CTkFrame fake: remembers fill and background like CTk (`_fg_color`)."""

    def __init__(self, master=None, **kw):
        self.kw = dict(kw)
        self._fg_color = kw.get("fg_color")
        self._bg_color = kw.get("bg_color")

    def configure(self, require_redraw=False, **kw):
        if "fg_color" in kw:
            self._fg_color = kw["fg_color"]
        if "bg_color" in kw:
            self._bg_color = kw["bg_color"]

    def cget(self, volba):
        return {"fg_color": self._fg_color, "bg_color": self._bg_color}[volba]


def test_linka_po_zmene_temy_neprevezme_pozadie_rodica(monkeypatch):
    monkeypatch.setattr(ui_kit.ctk, "CTkFrame", _Ram)
    sumi, aizome = theme.tokens(theme.ZEN), theme.tokens(theme.MODERN)
    linka = ui_kit.linka(None, sumi)
    assert linka.cget("bg_color") == sumi["rule"]

    # 1) the parent (Panel) gets a new fill and sends it to its children -
    #    exactly like `CTkFrame.configure(fg_color=...)` in CTk
    linka.configure(bg_color=aizome["surface"])
    assert linka.cget("bg_color") == sumi["rule"], "pozadie panela linku skryje"
    # a transparent parent sends "transparent"
    linka.configure(bg_color="transparent")
    assert linka.cget("bg_color") == sumi["rule"]

    # 2) then `theme_recolor` recolours the line itself
    mapa = theme_recolor.build_color_map(sumi, aizome)
    theme_recolor.recolor_widget(linka, mapa)
    assert linka.cget("fg_color").lower() == aizome["rule"].lower()
    assert linka.cget("bg_color").lower() == aizome["rule"].lower()


def test_linka_bez_configure_nespadne(monkeypatch):
    """No `configure` on the fake (old test in test_022d_vizual): no crash."""

    class _Holy:
        def __init__(self, *a, **kw):
            self.kw = kw

    monkeypatch.setattr(ui_kit.ctk, "CTkFrame", _Holy)
    linka = ui_kit.linka(None, theme.tokens(theme.ZEN))
    assert linka.kw["height"] == 1


class _Kus:
    """CTkFrame/CTkLabel/button fake: pack only."""

    def __init__(self, *a, **kw):
        pass

    def pack(self, *a, **kw):
        return None

    def focus_set(self):
        return None


class _Okno:
    def __init__(self, *a, **kw):
        self.znicene = False

    def title(self, *a):
        pass

    def configure(self, **kw):
        pass

    def resizable(self, *a):
        pass

    def protocol(self, *a):
        pass

    def transient(self, *a):
        pass

    def grab_set(self):
        raise RuntimeError("grab failed: window not viewable")

    def grab_release(self):
        pass

    def after(self, *a):
        pass

    def destroy(self):
        self.znicene = True


def _priprav_confirm(monkeypatch):
    tlacidla = {}

    def button(master, pal, text, command=None, kind="secondary", **kw):
        tlacidla[kind] = command
        return _Kus()

    monkeypatch.setattr(ui_kit.ctk, "CTkToplevel", _Okno)
    monkeypatch.setattr(ui_kit.ctk, "CTkFrame", _Kus)
    monkeypatch.setattr(ui_kit.ctk, "CTkLabel", _Kus)
    monkeypatch.setattr(ui_kit, "button", button)
    monkeypatch.setattr(ui_kit, "DialogChrome",
                        lambda top, pal, title, on_close=None: types.SimpleNamespace(body=None))
    return tlacidla


def test_potvrdenie_caka_na_odpoved_aj_ked_grab_zlyha(monkeypatch):
    tlacidla = _priprav_confirm(monkeypatch)
    # wait_window = the person clicks "Delete" (danger)
    owner = types.SimpleNamespace(wait_window=lambda top: tlacidla["danger"]())
    ok = ui_kit.confirm(owner, theme.tokens(theme.ZEN), "Zmazat?", "text",
                        ok_label="Zmazat", cancel_label="Zrusit", danger=True)
    assert ok is True, "zlyhany grab nesmie z dialogu spravit mrtve tlacidlo"


def test_potvrdenie_bez_cakania_zavrie_okno_a_vrati_nie(monkeypatch):
    _priprav_confirm(monkeypatch)
    okna = []
    povodne = ui_kit.ctk.CTkToplevel

    def okno(*a, **kw):
        o = povodne(*a, **kw)
        okna.append(o)
        return o

    monkeypatch.setattr(ui_kit.ctk, "CTkToplevel", okno)

    def zlyhaj(_top):
        raise RuntimeError("wait_window zlyhal")

    ok = ui_kit.confirm(types.SimpleNamespace(wait_window=zlyhaj), theme.tokens(theme.ZEN),
                        "Zmazat?", "text", ok_label="Zmazat", cancel_label="Zrusit",
                        danger=True)
    assert ok is False
    assert okna[0].znicene, "dialog nesmie ostat otvoreny bez niekoho, kto caka"


def test_karta_pripomienky_na_lavej_hrane_stranky():
    src = zdroj_suboru("ui_dialogs.py")
    i = src.index("class SlotCard")
    karta = src[i:src.index("\nclass ", i + 1)]
    assert 'self.frame.pack(fill="x", pady=5)' in karta
    assert 'self.frame.pack(fill="x", padx=2' not in karta
