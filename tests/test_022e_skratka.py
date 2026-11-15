# -*- coding: utf-8 -*-
"""The "not now" shortcut (0.3, batch 4): clash with the keyboard layout
(AltGr = Ctrl+Alt), choice in Settings -> General, the sentence in the bar
and in the tour. All on dummies - no real layout and no registration."""
import types

import app as app_mod
import guided_tour
import hotkey
import i18n
from i18n import tr
from app_spolocne import DEFAULT_SNOOZE_HOTKEY, SNOOZE_HOTKEY_MINUTES

import test_022c_uvod as uvod
import test_teraz_nie as teraz_nie

POLSKE = "pl-PL"
AMERICKE = "en-US"


def _znak(hkl, vk, shift):
    """Made-up layouts: Polish types AltGr+Z = "ż", AltGr+Shift+Z = "Ż"."""
    if hkl == POLSKE and vk == ord("Z"):
        return "Ż" if shift else "ż"
    if vk == ord("Z"):
        return "\x1a"          # Ctrl+Z without AltGr = a control character, not a letter
    return ""


def _kolizia_pl(combo):
    return hotkey.znak_kolizie(combo, rozlozenia=[AMERICKE, POLSKE], znak=_znak)


# --------------------------------------------------------------------------
# hotkey.znak_kolizie / prva_volna
# --------------------------------------------------------------------------

def test_ctrl_alt_z_na_polskom_rozlozeni_pise_z_s_bodkou():
    assert _kolizia_pl("ctrl+alt+z") == "ż"
    assert _kolizia_pl("ctrl+alt+shift+z") == "Ż"


def test_bez_polskeho_rozlozenia_ziadna_zrazka():
    assert hotkey.znak_kolizie("ctrl+alt+z", rozlozenia=[AMERICKE], znak=_znak) == ""


def test_kombinacie_bez_altgr_znak_nepisu():
    for combo in ("ctrl+shift+z", "alt+z", "win+ctrl+alt+z", "ctrl+alt+f9"):
        assert _kolizia_pl(combo) == "", combo


def test_chyba_rozlozenia_nehlasi_zrazku(monkeypatch):
    def zle(*_a):
        raise OSError("ctypes nejde")
    assert hotkey.znak_kolizie("ctrl+alt+z", rozlozenia=[POLSKE], znak=zle) == ""
    monkeypatch.setattr(hotkey, "_rozlozenia", lambda: [])
    assert hotkey.znak_kolizie("ctrl+alt+z") == ""
    assert hotkey.znak_kolizie("toto nie je skratka", rozlozenia=[POLSKE], znak=_znak) == ""


def test_predvolby_su_platne_a_prva_volna_preskoci_zrazku():
    assert hotkey.PRESETS[0] == DEFAULT_SNOOZE_HOTKEY
    assert all(hotkey.is_valid(c) for c in hotkey.PRESETS)
    assert hotkey.prva_volna(kolizia=_kolizia_pl) == "ctrl+alt+f9"
    assert hotkey.prva_volna(kolizia=lambda _c: "x") == ""


# --------------------------------------------------------------------------
# App start: the default shortcut would take a letter
# --------------------------------------------------------------------------

def _appka(combo=DEFAULT_SNOOZE_HOTKEY, vybrana=False):
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.snooze_hotkey = combo
    a.snooze_hotkey_chosen = vybrana
    a.denn = []
    a.log = a.denn.append
    a.ulozene = []
    a.save_settings = lambda: a.ulozene.append(a.snooze_hotkey)
    return a


def test_predvolena_skratka_sa_pri_zrazke_vymeni_a_povie_to_raz():
    a = _appka()
    assert a._vyber_skratku_pri_starte(kolizia=_kolizia_pl) == "ctrl+alt+f9"
    assert a.snooze_hotkey == "ctrl+alt+f9"
    assert a.ulozene == ["ctrl+alt+f9"], "nahrada sa ulozi - dalsi start uz nic nehlasi"
    assert a.denn == [tr("log.hotkey_layout_swapped", combo="Ctrl + Alt + Z",
                         char="ż", new="Ctrl + Alt + F9")]
    # second start: the shortcut is no longer the default, nothing changes and
    # nothing is reported
    assert a._vyber_skratku_pri_starte(kolizia=_kolizia_pl) is None
    assert len(a.denn) == 1


def test_ked_sa_bije_vsetko_skratka_ostane_vypnuta():
    a = _appka()
    assert a._vyber_skratku_pri_starte(kolizia=lambda c: "ż") == ""
    assert a.snooze_hotkey == ""
    assert a.denn == [tr("log.hotkey_layout_off", combo="Ctrl + Alt + Z", char="ż")]


def test_vlastnu_volbu_hraca_appka_nemeni():
    a = _appka(vybrana=True)
    assert a._vyber_skratku_pri_starte(kolizia=_kolizia_pl) is None
    assert a.snooze_hotkey == DEFAULT_SNOOZE_HOTKEY and not a.denn and not a.ulozene


def test_bez_zrazky_ani_pri_chybe_kontroly_sa_nic_nemeni():
    a = _appka()
    assert a._vyber_skratku_pri_starte(kolizia=lambda c: "") is None

    def zle(_c):
        raise RuntimeError("rozlozenia sa nedaju zistit")
    assert a._vyber_skratku_pri_starte(kolizia=zle) is None
    assert a.snooze_hotkey == DEFAULT_SNOOZE_HOTKEY and not a.denn


def test_start_vola_vyber_pred_registraciou():
    from _zdroj_appky import zdroj_metody
    init = zdroj_metody("__init__")
    assert init.index("self._vyber_skratku_pri_starte()") < init.index(
        "self.start_snooze_hotkey()")


# --------------------------------------------------------------------------
# Settings -> General
# --------------------------------------------------------------------------

def test_volby_oznacia_zrazku_a_koncia_vypnutou():
    a = _appka()
    volby = a._snooze_hotkey_volby(kolizia=_kolizia_pl)
    assert volby[-1] == (tr("settings.snooze_hotkey_none"), "")
    assert volby[0] == (tr("settings.snooze_hotkey_types", combo="Ctrl + Alt + Z",
                           char="ż"), "ctrl+alt+z")
    assert ("Ctrl + Alt + F9", "ctrl+alt+f9") in volby
    # a hand-written shortcut from the file is not lost in the menu
    a.snooze_hotkey = "ctrl+shift+f8"
    assert ("Ctrl + Shift + F8", "ctrl+shift+f8") in a._snooze_hotkey_volby(
        kolizia=lambda c: "")


class _FalosnaSkratka:
    vytvorene = []

    def __init__(self, combo, callback, log=None):
        self.combo, self.registered, self.zastavena = combo, False, False
        _FalosnaSkratka.vytvorene.append(self)

    def start(self):
        self.registered = self.combo != "ctrl+alt+f12"     # F12 "is held by another program"
        return self.registered

    def stop(self):
        self.zastavena = True


def test_zmena_skratky_odregistruje_staru_a_zaregistruje_novu(monkeypatch):
    monkeypatch.setattr(hotkey, "GlobalHotkey", _FalosnaSkratka)
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    _FalosnaSkratka.vytvorene = []
    a = _appka()
    a._hotkey = None
    assert a.start_snooze_hotkey() is True
    stara = a._hotkey
    volby = a._snooze_hotkey_volby(kolizia=lambda c: "")
    a._snooze_hotkey_podla_popisu = dict(volby)
    a.on_snooze_hotkey_pick("Ctrl + Alt + F9")
    assert stara.zastavena, "stara skratka sa najprv odregistruje"
    assert a._hotkey.combo == "ctrl+alt+f9" and a._hotkey.registered
    assert a.snooze_hotkey_chosen is True and a.ulozene[-1] == "ctrl+alt+f9"
    assert a.denn[-1] == tr("log.hotkey_on", combo="Ctrl + Alt + F9")
    assert a._snooze_hotkey_sub() == tr("settings.snooze_hotkey_sub",
                                        combo="Ctrl + Alt + F9",
                                        minutes=SNOOZE_HOTKEY_MINUTES)
    assert a._skratka_teraz_nie() == "Ctrl + Alt + F9"


def test_obsadena_skratka_ostane_vybrana_a_riadok_to_povie(monkeypatch):
    monkeypatch.setattr(hotkey, "GlobalHotkey", _FalosnaSkratka)
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    a = _appka()
    a._hotkey = None
    a._snooze_hotkey_podla_popisu = dict(a._snooze_hotkey_volby(kolizia=lambda c: ""))
    a.on_snooze_hotkey_pick("Ctrl + Alt + F12")
    assert a.snooze_hotkey == "ctrl+alt+f12", "volba ostava aj ked ju drzi iny program"
    assert a.denn[-1] == tr("log.hotkey_failed_tray", combo="Ctrl + Alt + F12")
    assert a._snooze_hotkey_sub() == tr("settings.snooze_hotkey_taken",
                                        combo="Ctrl + Alt + F12")
    assert a._skratka_teraz_nie() == "", "nefunkcnu skratku pas neslubuje"


def test_vypnuta_skratka(monkeypatch):
    monkeypatch.setattr(hotkey, "GlobalHotkey", _FalosnaSkratka)
    a = _appka()
    a._hotkey = _FalosnaSkratka("ctrl+alt+z", None)
    a._hotkey.registered = True
    a._snooze_hotkey_podla_popisu = dict(a._snooze_hotkey_volby(kolizia=lambda c: ""))
    stara = a._hotkey
    a.on_snooze_hotkey_pick(tr("settings.snooze_hotkey_none"))
    assert stara.zastavena and a._hotkey is None and a.snooze_hotkey == ""
    assert a.denn[-1] == tr("log.hotkey_off")
    assert a._snooze_hotkey_sub() == tr("settings.snooze_hotkey_off_sub")


def test_riadok_je_v_nastaveniach_vseobecne():
    from _zdroj_appky import zdroj_metody
    assert "self._build_snooze_hotkey_row(wrap, pal)" in zdroj_metody(
        "_build_nastavenia_page")


# --------------------------------------------------------------------------
# The bar on Today and the tour name the real shortcut
# --------------------------------------------------------------------------

def test_pas_pri_stiseni_menuje_skutocnu_skratku(monkeypatch):
    import time as _time
    h = teraz_nie._Hodiny(_time.mktime((2026, 9, 24, 21, 15, 0, 0, 0, -1)))
    a = teraz_nie._appka(monkeypatch, h)
    a.snooze_hotkey = "ctrl+alt+f9"
    a._hotkey = types.SimpleNamespace(registered=True)
    a._start_snooze(30)
    _titul, veta = a._kamae_state_text()
    assert veta == tr("kamae.snoozed_sub", until="21:45", combo="Ctrl + Alt + F9")
    a._hotkey.registered = False
    assert a._kamae_state_text()[1] == tr("kamae.snoozed_sub_tray", until="21:45")


def test_veta_v_pase_slubuje_aj_ponuku_v_liste():
    s = i18n.STRINGS
    for jazyk in ("sk", "en", "cs"):
        assert "{combo}" in s["kamae.snoozed_sub"][jazyk]
    assert "tou istou skratkou" not in s["kamae.snoozed_sub"]["sk"]
    assert "lište" in s["kamae.snoozed_sub"]["sk"]
    assert "lište" in s["kamae.snoozed_sub_tray"]["sk"]


def test_prehliadka_spomenie_skratku_raz_pri_pripomienkach():
    app = uvod._app(tep=72)
    app._skratka_teraz_nie = lambda: "Ctrl + Alt + F9"
    tour = guided_tour.GuidedTour(app)
    kroky = {k.key: tour._body(k) for k in tour.steps}
    veta = tr("tour.triggers.snooze", combo="Ctrl + Alt + F9")
    assert kroky["triggers"] == tr("tour.triggers.body") + " " + veta
    assert sum(veta in text for text in kroky.values()) == 1
    # without a valid shortcut it points to the menu in the tray
    app._skratka_teraz_nie = lambda: ""
    tour = guided_tour.GuidedTour(app)
    krok = next(k for k in tour.steps if k.key == "triggers")
    assert tour._body(krok).endswith(tr("tour.triggers.snooze_tray"))
