# -*- coding: utf-8 -*-
"""UX skeptic's findings after batch 4 (0.3) - visible only in screenshots.

  * Pairing window with a VPN: the "(VPN/virtual)" tag at the end of the big
    address line (mono 20) did not fit - it got clipped and pushed out the
    "Show IP" button, so the address could not be revealed. Now the tag is
    its own line below the address and the button gets its place in the
    row first.
  * The sessions table in History wrote the length as "84:54" (looks like a
    time of day), while the detail of the same session above it said
    "1 h 24 min".
  * The sentence about a failed voice preparation was in `danger` (~3.7:1
    on `surface`), although small text should use `danger_text` (>= 4.5:1,
    the rule in theme.py).

Synthetic addresses from documentation ranges, no network.
"""
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_suboru  # noqa: E402


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _tk_root():
    if sys.platform != "win32":
        pytest.skip("len Windows")
    import tkinter as tk
    import customtkinter as ctk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("bez displeja")
    root.withdraw()
    return root


def _kontrast(a, b):
    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# --------------------------------------------------------------------------
# Pairing window: the VPN tag and "Show IP"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("jazyk", ["sk", "de", "ja"])
def test_parovanie_s_vpn_ukaze_stitok_aj_tlacidlo(monkeypatch, jazyk):
    import customtkinter as ctk
    import netinfo
    import ui_dialogs
    povodny = i18n._lang["code"]
    i18n.set_lang(jazyk)
    root = _tk_root()
    vpn = "192.0.2.50"
    monkeypatch.setattr(netinfo, "local_ip_candidates", lambda *a, **k: [vpn])
    monkeypatch.setattr(netinfo, "virtualne_adresy", lambda *a, **k: {vpn})
    # the window is unmapped under the hidden root - a grab would fail
    monkeypatch.setattr(ctk.CTkToplevel, "grab_set", lambda self: None)
    app = types.SimpleNamespace(
        pal=theme.tokens(theme.ZEN), root=root, set_typing=lambda _v: None,
        show_ip=False, hr_port=4455, hr_monitoring_enabled=True,
        _hr_state="disconnected", _hr_last_bpm=None)
    try:
        dlg = ui_dialogs.WatchPairingDialog(app)
        stitok = i18n.tr("hr.ip_virtual")
        # the big line carries only the address and port - the tag would get
        # clipped in it
        assert dlg.ip_label.cget("text") == netinfo.pairing_address(vpn, 4455, False)
        assert stitok not in dlg.ip_label.cget("text")
        # the tag is its own line RIGHT below the address, the hidden-address
        # sentence after it
        assert dlg.ip_virtual_label is not None
        assert dlg.ip_virtual_label.cget("text") == stitok
        rad = dlg.ip_label.master
        net_in = rad.master
        poradie = [str(w) for w in net_in.pack_slaves()]
        i = poradie.index(str(rad))
        assert poradie[i + 1] == str(dlg.ip_virtual_label)
        assert poradie[i + 2] == str(dlg.ip_hidden_label), "veta o skrytej adrese"
        # "Show IP" gets its place in the row FIRST - nothing pushes it out now
        assert [str(w) for w in rad.pack_slaves()][0] == str(dlg.ip_toggle)
        # revealing the address: still no tag in the line
        app.show_ip = True
        dlg._render_ips()
        assert dlg.ip_label.cget("text") == netinfo.pairing_address(vpn, 4455, True)
        dlg.close()
    finally:
        i18n.set_lang(povodny)
        root.destroy()


def test_parovanie_bez_vpn_nema_stitok(monkeypatch, sk):
    import customtkinter as ctk
    import netinfo
    import ui_dialogs
    root = _tk_root()
    monkeypatch.setattr(netinfo, "local_ip_candidates",
                        lambda *a, **k: ["198.51.100.7", "192.0.2.50"])
    monkeypatch.setattr(netinfo, "virtualne_adresy", lambda *a, **k: {"192.0.2.50"})
    monkeypatch.setattr(ctk.CTkToplevel, "grab_set", lambda self: None)
    app = types.SimpleNamespace(
        pal=theme.tokens(theme.MODERN), root=root, set_typing=lambda _v: None,
        show_ip=True, hr_port=4455, hr_monitoring_enabled=True,
        _hr_state="disconnected", _hr_last_bpm=None)
    try:
        dlg = ui_dialogs.WatchPairingDialog(app)
        assert dlg.ip_virtual_label is None, "fyzicka adresa stitok nema"
        assert dlg.ip_label.cget("text") == "198.51.100.7   :   4455"
        # the virtual one is in the "other addresses" line - that one wraps, so
        # the tag stays there
        assert i18n.tr("hr.ip_virtual") in dlg.other_ips_label.cget("text")
        dlg.close()
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# History: length in the table as in the detail
# --------------------------------------------------------------------------

def test_tabulka_relacii_pise_dlzku_ako_detail(sk):
    import app as app_mod
    D = app_mod.DandurfApp
    zdroj = zdroj_suboru("app_history.py")
    tabulka = zdroj[zdroj.index("cols = ((\"col_date\""):zdroj.index("bunky = [row]")]
    assert 'self._fmt_dlzka(dlzka) if dlzka else "-"' in tabulka
    assert 'self._fmt_minutes(s.get("duration_s"))' not in tabulka
    # the same session: table and detail "1 h 24 min", a short one "45 min"
    assert D._fmt_dlzka(5094.0) == "1 h 24 min"
    assert D._fmt_dlzka(2700.0) == "45 min"


# --------------------------------------------------------------------------
# Sound: the failed voice preparation sentence is readable
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tema", [theme.ZEN, theme.MODERN])
def test_chyba_pripravy_hlasu_v_danger_text(tema):
    import app as app_mod
    import audio_engine
    pal = theme.tokens(tema)
    farby = []
    a = types.SimpleNamespace(
        pal=pal, log=lambda *_a: None,
        set_edge_status=lambda text, color=None: farby.append(color),
        _ukaz_skusit_hlas_znova=lambda _ukaz: None)
    app_mod.DandurfApp._edge_priprava_zlyhala(
        a, audio_engine.EDGE_CHYBA_ODMIETNUTE, 12, 40)
    assert farby == [pal["danger_text"]]
    assert _kontrast(pal["danger_text"], pal["surface"]) >= 4.5
    assert _kontrast(pal["danger"], pal["surface"]) < 4.5, "preto nie danger"
