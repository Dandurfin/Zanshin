# -*- coding: utf-8 -*-
"""Skrytá IP (0.2) - adresa PC sa na obrazovke neukáže sama.

Okno appky býva na streame a tester posiela screenshoty. Lokálna IP tam
nemá čo robiť: okno párovania, pole IP v Nastaveniach aj riadky v denníku
ju ukazujú zamaskovanú, kým si ju hráč neodkryje tlačidlom „Ukázať IP“.
Odkrytie platí len do reštartu - `app.show_ip` sa do nastavení nezapisuje.

Testy bežia bez Tk: čisté funkcie z `netinfo` a skutočné metódy
`DandurfApp` na malej atrape.
"""
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import netinfo  # noqa: E402
from _zdroj_appky import subory_appky, zdroj_appky, zdroj_metody  # noqa: E402

IP = "192.168.1.20"


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8-sig") as fh:
        return fh.read()


def _trieda(src, nazov):
    start = src.index(f"class {nazov}")
    koniec = src.find("\nclass ", start + 1)
    return src[start:koniec if koniec > 0 else len(src)]


def _app():
    import app as app_mod
    return app_mod.DandurfApp


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


# --------------------------------------------------------------------------
# netinfo.mask_ip a spol.
# --------------------------------------------------------------------------

def test_prazdno_none_a_nuly_ostanu_bez_zmeny():
    """0.0.0.0 nie je adresa PC, len „počúvaj všade“ - a rada „nechaj
    0.0.0.0“ ju potrebuje ukázať."""
    assert netinfo.mask_ip("") == ""
    assert netinfo.mask_ip(None) is None
    assert netinfo.mask_ip("0.0.0.0") == "0.0.0.0"


def test_ipv4_sa_zamaskuje_v_tvare_adresy():
    assert netinfo.mask_ip(IP) == "•••.•••.•••.•••"
    assert netinfo.mask_ip(" 10.0.0.5 ") == "•••.•••.•••.•••"
    assert IP not in netinfo.mask_ip(IP)


def test_cokolvek_ine_su_len_bodky():
    for ine in ("fe80::1", "localhost", "moj-pc.lan", "300.1.1.1"):
        assert netinfo.mask_ip(ine) == "•••", ine


def test_adresa_na_obrazovku_je_cela_len_na_vyziadanie():
    assert netinfo.ip_for_screen(IP) == "•••.•••.•••.•••"
    assert netinfo.ip_for_screen(IP, show=True) == IP


def test_parovanie_skryje_adresu_ale_port_necha():
    """Port (4455) má každý rovnaký - v telefóne ho treba vidieť."""
    text = netinfo.pairing_address(IP, 4455)
    assert IP not in text and "4455" in text
    assert IP in netinfo.pairing_address(IP, 4455, show=True)


def test_dalsie_adresy_su_skryte_kazda():
    ips = ["10.0.0.5", "172.16.0.9"]
    text = netinfo.pairing_other_ips(ips)
    assert not any(ip in text for ip in ips)
    assert text.count("•••.•••.•••.•••") == 2
    assert all(ip in netinfo.pairing_other_ips(ips, show=True) for ip in ips)


def test_pole_ip_sa_maskuje_len_pri_skutocnej_adrese():
    assert netinfo.entry_mask(IP) == "•"
    assert netinfo.entry_mask(IP, show=True) == ""
    assert netinfo.entry_mask("") == ""
    assert netinfo.entry_mask("0.0.0.0") == ""
    assert netinfo.entry_mask(None) == ""


# --------------------------------------------------------------------------
# Denník appky (log.hr_enabled, log.hr_bind_fallback)
# --------------------------------------------------------------------------

def test_riadok_v_denniku_ukazuje_skrytu_ip(sk):
    D = _app()
    atrapa = types.SimpleNamespace(hr_ip=IP, show_ip=False)
    ip = D._hr_ip_display(atrapa)
    assert IP not in ip
    riadok = i18n.tr("log.hr_enabled", ip=ip, port=4455)
    assert IP not in riadok and "4455" in riadok
    atrapa.show_ip = True
    assert D._hr_ip_display(atrapa) == IP


def test_dennik_pri_prazdnej_ip_ukaze_nuly():
    D = _app()
    assert D._hr_ip_display(types.SimpleNamespace(hr_ip="  ", show_ip=False)) == "0.0.0.0"


def test_fallback_riadok_ide_cez_masku():
    telo = zdroj_metody("_apply_hr_status")
    blok = telo[telo.index('kind == "bound_any"'):]
    blok = blok[:blok.index("return")]
    assert "netinfo.ip_for_screen(payload, self.show_ip)" in blok
    assert "ip=payload)" not in blok


def test_do_suboru_logu_ip_pc_nejde():
    """Riadky `log.hr_*` idú len do panela v okne (`DandurfApp.log`), nie do
    logs/app.log - a do súboru sa adresa nezapisuje ani inde."""
    telo = zdroj_metody("log")
    assert "app_log" not in telo and "get_logger" not in telo
    for subor in (*subory_appky(), "heart_rate.py", "obs_websocket.py", "netinfo.py"):
        src = _read(subor)
        for riadok in src.splitlines():
            if "log." in riadok and ("app_log" in riadok or riadok.strip().startswith("log.")):
                assert "hr_ip" not in riadok and "local_ip" not in riadok, (subor, riadok)


# --------------------------------------------------------------------------
# Okno párovania
# --------------------------------------------------------------------------

def test_parovanie_sklada_adresy_cez_netinfo():
    trieda = _trieda(_read("ui_dialogs.py"), "WatchPairingDialog")
    assert "netinfo.pairing_address(" in trieda
    assert "netinfo.pairing_other_ips(" in trieda
    assert 'f"{ip}   :   {app.hr_port}"' not in trieda, "holá IP v texte"
    assert '",  ".join(candidates[1:])' not in trieda, "holé ďalšie adresy"
    # tlačidlo prepína stav celej appky, nie len dialógu
    assert "set_show_ip" in trieda
    assert 'tr("hr.ip_show")' in trieda and 'tr("hr.ip_hide")' in trieda


def test_texty_tlacidiel_su_vo_vsetkych_jazykoch():
    for kluc in ("hr.ip_show", "hr.ip_hide", "hr.ip_hidden_note"):
        assert set(i18n.STRINGS[kluc]) >= set(i18n.LANGUAGES), kluc
    assert i18n.STRINGS["hr.ip_show"]["sk"] == "Ukázať IP"
    assert i18n.STRINGS["hr.ip_hide"]["sk"] == "Skryť IP"


# --------------------------------------------------------------------------
# Pole IP v Nastaveniach
# --------------------------------------------------------------------------

class _Pole:
    def __init__(self):
        self.show = ""

    def cget(self, meno):
        assert meno == "show"
        return self.show

    def configure(self, show):
        self.show = show


class _Var:
    def __init__(self, hodnota):
        self.hodnota = hodnota

    def get(self):
        return self.hodnota

    def set(self, hodnota):
        self.hodnota = hodnota


def _atrapa_nastaveni(ip):
    D = _app()

    class Atrapa:
        set_show_ip = D.set_show_ip
        _apply_hr_ip_mask = D._apply_hr_ip_mask

    a = Atrapa()
    a.show_ip = False
    a.show_ip_var = _Var(False)
    a.hr_ip_entry = _Pole()
    a.hr_ip_var = _Var(ip)
    return a


def test_pole_ip_je_skryte_kym_ho_hrac_neodkryje():
    a = _atrapa_nastaveni(IP)
    a._apply_hr_ip_mask()
    assert a.hr_ip_entry.show == "•"
    a.set_show_ip(True)
    assert a.hr_ip_entry.show == "" and a.show_ip_var.get() is True
    a.set_show_ip(False)
    assert a.hr_ip_entry.show == "•"


def test_pole_s_nulami_ostava_citatelne():
    a = _atrapa_nastaveni("0.0.0.0")
    a._apply_hr_ip_mask()
    assert a.hr_ip_entry.show == ""


def test_karta_senzora_ma_prepinac_a_ukladanie_sa_nemeni():
    karta = zdroj_metody("_build_heart_rate_card")
    assert 'tr("hr.ip_show")' in karta
    assert "self._apply_hr_ip_mask()" in karta
    # hodnota sa ukladá rovnako ako predtým - maska je len kreslenie
    zmena = zdroj_metody("on_hr_config_change")
    assert "ip = self.hr_ip_var.get().strip() or ANY_INTERFACE" in zmena


# --------------------------------------------------------------------------
# show_ip sa neukladá - po reštarte je IP znova skrytá
# --------------------------------------------------------------------------

def test_show_ip_sa_neuklada_do_nastaveni():
    src = zdroj_appky()
    assert "self.show_ip = False" in src
    for metoda in ("save_settings", "load_settings"):
        assert "show_ip" not in zdroj_metody(metoda), metoda


def test_privacy_md_hovori_o_skrytej_ip():
    text = _read("PRIVACY.md")
    assert "Show IP" in text and "hides your PC's IP" in text
