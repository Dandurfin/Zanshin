# -*- coding: utf-8 -*-
"""Heart-rate receiving state outside the pairing window (0.3, audit
"Waiting for heart rate all evening", "Waiting for the watch even when it
cannot come", "IP field 0.0.0.0").

  * both the bar and the centre of Today have their own "The phone didn't
    connect" state with advice,
  * the text on the right of the "Heart rate and load" header speaks by
    the receiving state,
  * the "Watch and heart rate" card: receiving -> state -> guide -> only
    then the network fields; the address field is "advanced" and "Show
    IP" is not shown at 0.0.0.0,
  * the QR descriptions and the hint under the field point to the guide,
    not to "IP of this PC".

The tests run without Tk: the real `DandurfApp` methods are called on a
dummy.
"""
import os
import re
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody, zdroj_suboru  # noqa: E402


@pytest.fixture(autouse=True)
def _slovencina():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _app():
    import app as app_mod
    return app_mod


def _nic(*_a, **_k):
    return None


# --------------------------------------------------------------------------
# The bar and the centre of Today: "The phone didn't connect"
# --------------------------------------------------------------------------

def _kamae(**kw):
    a = types.SimpleNamespace(listening=True, hr_monitoring_enabled=True,
                              _hr_state="connecting", _hr_last_bpm=None,
                              _cue_armed=False, _hr_lost=False,
                              _kamae_zastavene=lambda: ("stop", ""))
    a.__dict__.update(kw)
    return _app().DandurfApp._kamae_state_text(a)


def test_nikto_sa_nepripojil_ma_vlastny_stav_s_radou():
    titul, veta = _kamae(_hr_state="no_client")
    assert titul == "Telefón sa nepripojil"
    assert veta == i18n.tr("kamae.no_client_sub")
    for slovo in ("firewall", "Verejná", "reštarte routera", "ikonu hodiniek vľavo"):
        assert slovo in veta, slovo


def test_pripajanie_ostava_cakam_na_tep():
    assert _kamae(_hr_state="connecting") == (i18n.tr("kamae.no_hr"),
                                              i18n.tr("kamae.no_hr_sub"))
    assert _kamae(_hr_state="linked")[0] == i18n.tr("kamae.no_hr")


def test_vypadok_ma_prednost_pred_no_client():
    assert _kamae(_hr_state="no_client", _hr_lost=True)[1] == i18n.tr("kamae.lost_sub")


def test_bez_prijmu_posiela_na_ikonu_nie_na_prepinac():
    titul, veta = _kamae(hr_monitoring_enabled=False)
    assert titul == i18n.tr("kamae.no_watch")
    assert veta == ("Bez hodiniek neviem, kedy ti záťaž stúpa, tak mlčím. "
                    "Spáruj ich — ikona hodiniek vľavo.")
    for jazyk in i18n.LANGUAGES:
        text = i18n.tr_lang(jazyk, "kamae.no_watch_sub")
        assert i18n.tr_lang(jazyk, "settings.hr_enable_switch") not in text, jazyk


def test_ikona_hodiniek_vlavo_naozaj_existuje_a_otvara_navod():
    """The sentences point to "the watch icon on the left" - the side panel
    must have it, and a click must turn receiving on and open the guide."""
    src = zdroj_appky()
    assert "on_pair_watch=self.open_watch_pairing" in src
    shell = zdroj_suboru("ui_shell.py")
    assert "self.pair_btn = _WatchPulse(" in shell
    assert 'self.sidebar.pack(side="left"' in src
    telo = zdroj_metody("open_watch_pairing")
    assert "self._enable_hr_monitoring()" in telo and "WatchPairingDialog(" in telo


def test_no_client_prepise_pas_aj_dnes():
    volane = []
    a = types.SimpleNamespace(
        _hr_no_client_job="job", _hr_state="connecting", hr_monitoring_enabled=True,
        refresh_hr_status_label=lambda: volane.append("stitok"),
        _refresh_kamae_state_text=lambda: volane.append("pas"),
        _refresh_dnes_stats=lambda: volane.append("dnes"))
    _app().DandurfApp._hr_no_client(a)
    assert a._hr_state == "no_client" and a._hr_no_client_job is None
    assert volane == ["stitok", "pas", "dnes"]


def test_no_client_sa_nezapne_ked_uz_nieco_prislo():
    volane = []
    a = types.SimpleNamespace(
        _hr_no_client_job="job", _hr_state="linked", hr_monitoring_enabled=True,
        refresh_hr_status_label=lambda: volane.append(1),
        _refresh_kamae_state_text=lambda: volane.append(1),
        _refresh_dnes_stats=lambda: volane.append(1))
    _app().DandurfApp._hr_no_client(a)
    assert a._hr_state == "linked" and volane == []


def test_vypnutie_prijmu_prepise_dnes_aj_pas():
    volane = []
    a = types.SimpleNamespace(
        heart_rate_monitor=types.SimpleNamespace(stop=_nic),
        _cancel_no_client_check=_nic, _close_hr_session=_nic,
        hud=types.SimpleNamespace(set_connected=_nic),
        hr_stats=types.SimpleNamespace(clear_live=_nic),
        refresh_hr_status_label=_nic, log=_nic,
        _refresh_dnes_stats=lambda: volane.append("dnes"),
        _refresh_kamae_state_text=lambda: volane.append("pas"))
    _app().DandurfApp.stop_heart_rate_monitor(a)
    assert a._hr_state == "disconnected"
    assert volane == ["dnes", "pas"]


# --------------------------------------------------------------------------
# Today: the text on the right of the "Heart rate and load" header
# --------------------------------------------------------------------------

def _text(**kw):
    import app_today
    a = types.SimpleNamespace(_hr_state="connecting", hr_monitoring_enabled=True)
    a.__dict__.update(kw)
    return app_today._text_bez_tepu(a)


def test_cakam_na_hodinky_len_ked_mozu_prist():
    assert _text(_hr_state="connecting") == i18n.tr("dnes.hr_waiting")
    assert _text(_hr_state="linked") == i18n.tr("dnes.hr_waiting")


def test_text_podla_stavu_prijmu():
    assert _text(hr_monitoring_enabled=False, _hr_state="disconnected") == "príjem tepu vypnutý"
    assert _text(_hr_state="busy") == "port je obsadený"
    assert _text(hr_monitoring_enabled=False, _hr_state="busy_gave_up") == "port je obsadený"
    assert _text(_hr_state="no_client") == "telefón sa nepripojil"


def test_dnes_text_berie_z_funkcie_modulu():
    """A module function, not a method - `_refresh_dnes_stats` also runs on
    dummies in the tests, which would not have a new method."""
    telo = zdroj_metody("_refresh_dnes_stats")
    assert "_text_bez_tepu(self)" in telo
    assert 'tr("dnes.hr_waiting")' not in telo


# --------------------------------------------------------------------------
# The "Watch and heart rate" card
# --------------------------------------------------------------------------

def _riadok(karta, kotva):
    """Grid row number of the element that starts at `kotva`."""
    i = karta.index(kotva)
    m = re.search(r"row=(\d+)", karta[i:])
    return int(m.group(1))


def test_poradie_karty_prijem_stav_navod_az_potom_siet():
    karta = zdroj_metody("_build_heart_rate_card")
    prijem = _riadok(karta, 'ui_kit.switch(inner, pal, text=tr("settings.hr_enable_switch")')
    stav = _riadok(karta, "self.hr_status_label.grid(")
    navod = _riadok(karta, 'ui_kit.button(inner, pal, tr("hr.pair_button")')
    adresa = int(re.search(r'_hr_entry\(inner, pal, (\d+), tr\("settings.hr_ip_label"\)',
                           karta).group(1))
    port = int(re.search(r'_hr_entry\(inner, pal, (\d+), tr\("settings.hr_port_label"\)',
                         karta).group(1))
    assert prijem < stav < navod < adresa < port
    # the creation order too (Tab goes in creation order)
    assert (karta.index('tr("settings.hr_enable_switch")') < karta.index('tr("hr.pair_button")')
            < karta.index('tr("settings.hr_ip_label")'))


def test_pole_adresy_je_pokrocile_a_rada_nepise_do_telefonu():
    assert i18n.tr("settings.hr_ip_label") == "Sieťová adresa (pokročilé)"
    assert i18n.tr("settings.hr_ip_hint") == (
        "Nechaj 0.0.0.0. Do telefónu toto číslo nepíš — správnu adresu nájdeš "
        "v „Ako spárovať hodinky…“.")


@pytest.mark.parametrize("kluc", ["settings.hr_ip_hint", "hr.qr_android", "hr.qr_ios"])
def test_rady_posielaju_do_navodu_v_kazdom_jazyku(kluc):
    for jazyk in i18n.LANGUAGES:
        text = i18n.tr_lang(jazyk, kluc)
        posledny = text.split("\n")[-1]
        assert i18n.tr_lang(jazyk, "hr.pair_button") in posledny, (jazyk, posledny)


def test_qr_uz_neradi_ip_tohto_pc():
    assert i18n.tr("hr.qr_android").split("\n")[-1] == \
        "Adresu a port nájdeš v „Ako spárovať hodinky…“."
    assert i18n.tr("hr.qr_ios").split("\n")[-1] == \
        "Adresu a port nájdeš v „Ako spárovať hodinky…“."
    for jazyk in ("sk", "cs"):
        for kluc in ("hr.qr_android", "hr.qr_ios"):
            assert "IP a port" not in i18n.tr_lang(jazyk, kluc), (jazyk, kluc)


# --------------------------------------------------------------------------
# "Show IP" by the address field - only when there is something to reveal
# --------------------------------------------------------------------------

class _Var:
    def __init__(self, hodnota):
        self.hodnota = hodnota

    def get(self):
        return self.hodnota

    def set(self, hodnota):
        self.hodnota = hodnota


class _Pole:
    def __init__(self):
        self.show = ""

    def cget(self, _meno):
        return self.show

    def configure(self, show):
        self.show = show


class _Prepinac:
    def __init__(self):
        self.manager = ""
        self.pakovania = 0

    def winfo_manager(self):
        return self.manager

    def pack(self, **_kw):
        self.manager = "pack"
        self.pakovania += 1

    def pack_forget(self):
        self.manager = ""


def _nastavenia(ip):
    D = _app().DandurfApp
    a = types.SimpleNamespace(show_ip=False, show_ip_var=_Var(False),
                              hr_ip_entry=_Pole(), hr_ip_var=_Var(ip),
                              hr_ip_show_switch=_Prepinac())
    a._apply_hr_ip_mask = lambda: D._apply_hr_ip_mask(a)
    a.set_show_ip = lambda v: D.set_show_ip(a, v)
    return a


def test_pri_0000_prepinac_nie_je():
    for hodnota in ("0.0.0.0", ""):
        a = _nastavenia(hodnota)
        a._apply_hr_ip_mask()
        assert a.hr_ip_show_switch.manager == "", hodnota
        assert a.hr_ip_entry.show == ""


def test_pri_skutocnej_adrese_sa_ukaze_a_maska_plati_dalej():
    a = _nastavenia("192.168.1.20")
    a._apply_hr_ip_mask()
    assert a.hr_ip_show_switch.manager == "pack"
    assert a.hr_ip_entry.show == "•"
    a.set_show_ip(True)
    assert a.hr_ip_entry.show == "" and a.hr_ip_show_switch.manager == "pack"
    assert a.hr_ip_show_switch.pakovania == 1, "uz zobrazeny sa znova nepakuje"
    # the player sets 0.0.0.0 back - the toggle disappears
    a.hr_ip_var.set("0.0.0.0")
    a._apply_hr_ip_mask()
    assert a.hr_ip_show_switch.manager == ""


def test_karta_prepinac_nepakuje_sama():
    """Only `_apply_hr_ip_mask` shows/hides it - the card just creates it."""
    karta = zdroj_metody("_build_heart_rate_card")
    vytvorenie = karta[karta.index("def _prepinac_ip"):karta.index("self.hr_ip_entry =")]
    # the app's one switch widget (`ui_kit.switch`, 0.3 UX audit)
    assert "self.hr_ip_show_switch = ui_kit.switch(" in vytvorenie
    assert ".pack(" not in vytvorenie
    assert "self.hr_ip_show_switch = None" in zdroj_metody("__init__")
