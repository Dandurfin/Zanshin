# -*- coding: utf-8 -*-
"""Watch pairing window is no longer blind (0.3, audit "Parovaci dialog").

Until now:
  * the window had no status - whether pairing was working could be seen only
    behind the modal window,
  * step 5 advised "switch the sensor on", although just opening the guide
    had already switched receiving on - whoever obeyed switched receiving OFF,
  * the firewall advice stood under "connects, but heart rate does not come",
    i.e. under the opposite case from where it belongs,
  * the English header literally showed "THIS PC\\u2019S",
  * the frameless window had no position.

Tests run without Tk: `stav_parovania` is a module function and the dialog's
methods are called on a stub.
"""
import ast
import os
import runpy
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n        # noqa: E402
import ui_dialogs  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402


@pytest.fixture(autouse=True)
def _slovencina():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _trieda(src, meno):
    for uzol in ast.parse(src).body:
        if isinstance(uzol, ast.ClassDef) and uzol.name == meno:
            return ast.get_source_segment(src, uzol)
    raise AssertionError(meno)


def _metoda_dialogu(meno):
    src = zdroj_suboru("ui_dialogs.py")
    for uzol in ast.parse(src).body:
        if isinstance(uzol, ast.ClassDef) and uzol.name == "WatchPairingDialog":
            for f in uzol.body:
                if isinstance(f, ast.FunctionDef) and f.name == meno:
                    return ast.get_source_segment(src, f)
    raise AssertionError(meno)


class _Stats:
    def __init__(self, zobraz):
        self.display_bpm = zobraz


def _app(**kw):
    a = types.SimpleNamespace(_hr_state="connecting", hr_monitoring_enabled=True,
                              _hr_last_bpm=None, hr_port=4455,
                              hr_stats=_Stats(None))
    a.__dict__.update(kw)
    return a


# --------------------------------------------------------------------------
# Status under the address - from the real receiving state
# --------------------------------------------------------------------------

def test_cakam_na_telefon():
    assert ui_dialogs.stav_parovania(_app()) == (
        "caka", i18n.tr("hr.pair_status_waiting"))
    assert i18n.tr("hr.pair_status_waiting") == "● Čakám, kým sa telefón pripojí…"


def test_telefon_pripojeny_cakam_na_tep():
    assert ui_dialogs.stav_parovania(_app(_hr_state="linked")) == (
        "caka", i18n.tr("hr.pair_status_linked"))
    assert i18n.tr("hr.pair_status_linked") == "● Telefón pripojený — čakám na tep…"


def test_tep_chodi_ukaze_vyhladene_cislo_nie_surove():
    a = _app(_hr_state="connected", _hr_last_bpm=97, hr_stats=_Stats(84))
    druh, text = ui_dialogs.stav_parovania(a)
    assert druh == "ok"
    assert text == "✓ Tep chodí: 84 BPM. Okno môžeš zavrieť."
    assert "97" not in text


def test_bez_hr_stats_aspon_surove_cislo():
    a = _app(_hr_state="connected", _hr_last_bpm=91, hr_stats=None)
    assert ui_dialogs.stav_parovania(a) == ("ok", i18n.tr("hr.pair_status_ok", bpm=91))


def test_connected_bez_vzorky_este_nie_je_ok():
    """The raw `_hr_last_bpm` decides if heart rate is coming (like the label).

    "connected" without a sample arises when `start_listening` opens a new
    session during pairing (the first start does that by itself) - but the
    phone is still connected, so not "waiting for the phone to connect"."""
    a = _app(_hr_state="connected", _hr_last_bpm=None, hr_stats=_Stats(80))
    assert ui_dialogs.stav_parovania(a) == ("caka", i18n.tr("hr.pair_status_linked"))


def test_nikto_sa_nepripojil_posle_k_radam_nizsie():
    druh, text = ui_dialogs.stav_parovania(_app(_hr_state="no_client"))
    assert druh == "pozor" and text == i18n.tr("hr.pair_status_no_client")
    assert "nižšie" in text


def test_obsadeny_port_skusa_znova_a_po_vzdani_povie_co_robit():
    druh, text = ui_dialogs.stav_parovania(_app(_hr_state="busy", hr_port=4456))
    assert druh == "pozor" and "4456" in text
    druh, text = ui_dialogs.stav_parovania(
        _app(_hr_state="busy_gave_up", hr_monitoring_enabled=False, hr_port=4456))
    assert druh == "chyba" and "4456" in text
    assert "V hre" in text and "telefóne" in text


def test_prijem_sa_nezapol():
    druh, text = ui_dialogs.stav_parovania(
        _app(_hr_state="disconnected", hr_monitoring_enabled=False))
    assert druh == "chyba" and text == i18n.tr("hr.pair_status_off")
    # reopening the guide = `open_watch_pairing` -> `_enable_hr_monitoring`
    assert "self._enable_hr_monitoring()" in zdroj_metody("open_watch_pairing")


def test_stav_sa_obnovuje_kazdu_sekundu_a_po_zavreti_prestane():
    naplanovane, stitok = [], {}

    class Top:
        def after(self, ms, fn):
            naplanovane.append((ms, fn))
            return "job"

    pal = {"success": "S", "warn": "W", "danger": "D", "text_dim": "T"}
    d = types.SimpleNamespace(
        _zavrete=False, _stav_job=None, top=Top(), STAV_OBNOVA_MS=1000,
        app=_app(_hr_state="connected", _hr_last_bpm=70, hr_stats=_Stats(70), pal=pal),
        status_label=types.SimpleNamespace(configure=lambda **kw: stitok.update(kw)))
    d._obnov_stav = lambda: ui_dialogs.WatchPairingDialog._obnov_stav(d)
    d._obnov_stav()
    assert stitok == {"text": i18n.tr("hr.pair_status_ok", bpm=70), "text_color": "S"}
    assert naplanovane[0][0] == 1000 and d._stav_job == "job"
    # the state change shows in the next round
    d.app._hr_state, d.app.hr_monitoring_enabled = "busy_gave_up", False
    naplanovane[0][1]()
    assert stitok["text_color"] == "D"
    # nothing after closing
    d._zavrete = True
    pocet = len(naplanovane)
    naplanovane[-1][1]()
    assert len(naplanovane) == pocet


def test_stav_je_pod_adresou_nad_krokmi():
    init = _metoda_dialogu("__init__")
    assert init.index("self._render_ips()") < init.index("self.status_label") \
        < init.index('tr("hr.step1_title")')
    assert "self._obnov_stav()" in init


# --------------------------------------------------------------------------
# on_close (the guide starts the tour after it) and closing
# --------------------------------------------------------------------------

def _zatvaratelny(on_close):
    zrusene, stav = [], {"typing": None, "destroy": 0}
    top = types.SimpleNamespace(
        after_cancel=zrusene.append, grab_release=lambda: None,
        destroy=lambda: stav.__setitem__("destroy", stav["destroy"] + 1))
    d = types.SimpleNamespace(
        _zavrete=False, _stav_job="job-1", top=top, _on_close=on_close,
        app=types.SimpleNamespace(set_typing=lambda v: stav.__setitem__("typing", v)))
    return d, zrusene, stav


def test_on_close_sa_zavola_raz_aj_pri_dvojitom_zavreti():
    volania = []
    d, zrusene, stav = _zatvaratelny(lambda: volania.append(1))
    ui_dialogs.WatchPairingDialog.close(d)
    ui_dialogs.WatchPairingDialog.close(d)       # Escape after a click on Close
    assert volania == [1]
    assert stav == {"typing": False, "destroy": 1}
    assert zrusene == ["job-1"] and d._stav_job is None


def test_bez_on_close_sa_zavrie_normalne():
    d, _zrusene, stav = _zatvaratelny(None)
    ui_dialogs.WatchPairingDialog.close(d)
    assert stav["destroy"] == 1


def test_chyba_v_on_close_nevyleti_a_zapise_sa(monkeypatch):
    zapisane = []
    monkeypatch.setattr(ui_dialogs.logging_setup, "get_logger",
                        lambda _m: types.SimpleNamespace(exception=zapisane.append))

    def zle():
        raise RuntimeError("prehliadka zlyhala")

    d, _zrusene, stav = _zatvaratelny(zle)
    ui_dialogs.WatchPairingDialog.close(d)
    assert stav["destroy"] == 1 and len(zapisane) == 1


def test_on_close_je_volitelny_parameter():
    init = ast.parse(_metoda_dialogu("__init__")).body[0]
    mena = [a.arg for a in init.args.args]
    assert mena == ["self", "app", "on_close"]
    assert isinstance(init.args.defaults[0], ast.Constant) and init.args.defaults[0].value is None


# --------------------------------------------------------------------------
# Window position
# --------------------------------------------------------------------------

def test_okno_je_vycentrovane_spolocnym_pomocnikom():
    init = _metoda_dialogu("__init__")
    # 0.3 (UX audit): the shared dialog helper - centred via
    # `vycentrovana_geometria` and the size shrunk to the work area
    assert "ui_kit.umiestni_dialog(self.top, app.root, 560, 640" in init
    assert 'self.top.geometry("560x640")' not in init


# --------------------------------------------------------------------------
# Step texts and advice
# --------------------------------------------------------------------------

def test_krok5_uz_nerada_prepinat():
    assert i18n.tr("hr.step5_title") == "Skontroluj stav pod adresou"
    telo = i18n.tr("hr.step5_body")
    assert "netreba nič prepínať" in telo and "zapni" not in telo.lower()
    for jazyk in i18n.LANGUAGES:
        text = i18n.tr_lang(jazyk, "hr.step5_body")
        # no language quotes the switch "Pocuvat tep z hodiniek" any more
        assert i18n.tr_lang(jazyk, "settings.hr_enable_switch") not in text, jazyk
        assert "BPM" in text, jazyk


def test_krok1_varuje_pred_otazkou_windowsu():
    assert i18n.tr("hr.step1_title") == "Rovnaká Wi‑Fi a povolenie siete"
    telo = i18n.tr("hr.step1_body")
    assert "Windows" in telo and "súkromné" in telo
    for jazyk in i18n.LANGUAGES:
        assert "Windows" in i18n.tr_lang(jazyk, "hr.step1_body"), jazyk


def test_box_vobec_sa_nepripoja_je_nad_trouble():
    trieda = _trieda(zdroj_suboru("ui_dialogs.py"), "WatchPairingDialog")
    assert trieda.index('tr("hr.noconnect_title")') < trieda.index('tr("hr.trouble_title")')
    assert 'tr("hr.noconnect_body")' in trieda
    assert 'tr("hr.trouble_pad")' in trieda


def test_kontrolny_zoznam_ma_styri_body_vo_vsetkych_jazykoch():
    for jazyk in i18n.LANGUAGES:
        text = i18n.tr_lang(jazyk, "hr.noconnect_body")
        riadky = text.split("\n")
        assert len(riadky) == 4, jazyk
        assert [r[:2] for r in riadky] == ["1)", "2)", "3)", "4)"], jazyk
        assert "Zanshin" in riadky[3], jazyk


def test_mena_ponuk_windowsu_su_skutocne():
    """sk verified in Slovak Windows 11 (Nastavenia, Windows Zabezpecenie),
    en according to English Windows 11."""
    sk = i18n.tr_lang("sk", "hr.noconnect_body")
    for meno in ("Nastavenia → Sieť a internet", "Typ profilu siete: Súkromná sieť",
                 "Windows Zabezpečenie → Firewall a ochrana siete",
                 "Povoliť aplikáciu v bráne firewall", "Zmeniť nastavenie",
                 "zaškrtni Súkromné", "hosťovská sieť", "VPN", "reštarte routera"):
        assert meno in sk, meno
    en = i18n.tr_lang("en", "hr.noconnect_body")
    for meno in ("Settings → Network & internet", "Network profile type: Private network",
                 "Windows Security → Firewall & network protection",
                 "Allow an app through firewall", "Change settings"):
        assert meno in en, meno


def test_firewall_presiel_z_trouble_do_noconnect():
    for jazyk in ("sk", "en"):
        assert "firewall" in i18n.tr_lang(jazyk, "hr.noconnect_body").lower()
    assert i18n.tr("hr.trouble_body") == (
        "Skontroluj scénu „Zanshin“ a zdroj „Tep“ v telefóne a či hodinky naozaj "
        "merajú. Ak port obsadil iný program, zmeň ho tu aj v telefóne.")
    for jazyk in i18n.LANGUAGES:
        text = i18n.tr_lang(jazyk, "hr.trouble_body").lower()
        assert "firewall" not in text and "windows" not in text, jazyk


# --------------------------------------------------------------------------
# THIS PC’S - a literal backslash in the text
# --------------------------------------------------------------------------

def test_hlavicka_adresy_bez_doslovneho_escape():
    assert i18n.STRINGS["hr.pair_this_pc"]["en"] == (
        "THIS PC’S ADDRESS AND PORT — enter it in the phone app")
    for jazyk in i18n.LANGUAGES:
        assert "\\" not in i18n.tr_lang(jazyk, "hr.pair_this_pc"), jazyk


def test_mrtve_kopie_su_prec():
    """There is no doubled backslash before u2019 in the source any more (the
    dead copies hr.pair_this_pc ja..pt and the old hr.step3_body were deleted
    too)."""
    src = zdroj_suboru("i18n.py")
    assert "\\\\u2019" not in src


def _spusti_kontrolu(monkeypatch, capsys):
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.chdir(ROOT)
    with pytest.raises(SystemExit) as koniec:
        runpy.run_path(os.path.join(ROOT, "check_translations.py"), run_name="__main__")
    return koniec.value.code, capsys.readouterr().out


def test_check_translations_prejde(monkeypatch, capsys):
    kod, vystup = _spusti_kontrolu(monkeypatch, capsys)
    assert kod == 0, vystup


def test_check_translations_chyti_doslovny_escape(monkeypatch, capsys):
    zly = {jazyk: "OK" for jazyk in i18n.LANGUAGES}
    zly["en"] = "THIS PC\\u2019S ADDRESS"          # literal backslash + u2019
    monkeypatch.setitem(i18n.STRINGS, "test.zly_escape", zly)
    kod, vystup = _spusti_kontrolu(monkeypatch, capsys)
    assert kod == 1
    assert "test.zly_escape [en]" in vystup and "\\u2019" in vystup


# --------------------------------------------------------------------------
# QR in the guide does not point to "How to pair your watch…" (same window)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kluc", ["hr.qr_android", "hr.qr_ios"])
def test_qr_v_navode_posiela_na_ramik_hore(kluc):
    for jazyk in i18n.LANGUAGES:
        i18n.set_lang(jazyk)
        karta = ui_dialogs._qr_popis(kluc)
        navod = ui_dialogs._qr_popis(kluc, v_navode=True)
        assert karta == i18n.tr(kluc), jazyk
        assert i18n.tr("hr.pair_button") not in navod, jazyk
        assert navod.split("\n")[-1] == i18n.tr("hr.qr_addr_above"), jazyk
        # the app name, price and "not tested yet" stay
        assert navod.split("\n")[:-1] == karta.split("\n")[:-1], jazyk


def test_navod_vola_qr_s_v_navode():
    init = _metoda_dialogu("__init__")
    assert "watch_app_qr(col, pal_, v_navode=True)" in init
    assert 'tr("hr.step2_body"), qr_v_navode)' in init


def test_skutocny_znak_escape_nie_je():
    """The ’ (U+2019) in a text is fine - the bug is only a literal \\uXXXX."""
    assert "’" in i18n.STRINGS["hr.pair_this_pc"]["en"]
