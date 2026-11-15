# -*- coding: utf-8 -*-
"""Kopia existujucich textov (0.2.2 davka 4b).

  * "hodinky pripojene" tam, kde je pripojeny TELEFON (appka, ktora posiela
    tep z hodiniek): `dnes.hr_connected`, `settings.hr_status_waiting`,
  * nemecka klavesnica ma "Strg", nie "Ctrl" - zapis skratky podla jazyka,
    nastavenia ostavaju v anglickom zapise,
  * stopa relacie v dotazniku nehovori v Praci "hralo sa", bulharsky titulok
    nema sloveso v mnoznom cisle pri kratkom case,
  * neulozena relacia povie skutocne pravidlo (`hr_stats.je_ulozitelna`),
  * zlyhana priprava hlasu menuje Nastavenia → Zvuk a tlacidlo neopakuje,
  * veta pri prvom × hovori, co plati, KED appka ostane v liste,
  * cinstina ma jednu pomlcku "——",
  * uvod sluby len hodinky s appkou v telefone (ako README),
  * stitok "(VPN/virtualna)" sa zhoduje s adresou (zensky rod).

Vsetko bez okna, data vymyslene.
"""
import ast
import os
import re
import types

import pytest

import app as app_mod
import app_audio
import hotkey
import hr_stats
import i18n
from _zdroj_appky import zdroj_metody, zdroj_suboru

S = i18n.STRINGS
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TELEFON = {"sk": "telefón", "en": "phone", "ja": "電話", "zh": "手机", "ru": "телефон",
           "es": "móvil", "de": "handy", "fr": "téléphone", "pt": "celular",
           "cs": "telefon", "bg": "телефон"}
HODINKY = {"sk": "hodink", "en": "watch", "ja": "時計", "zh": "手表", "ru": "часы",
           "es": "reloj", "de": "uhr", "fr": "montre", "pt": "relógio",
           "cs": "hodink", "bg": "часовник"}


@pytest.fixture
def jazyk():
    povodny = i18n._lang["code"]
    yield i18n.set_lang
    i18n.set_lang(povodny)


# --------------------------------------------------------------------------
# Telefon, nie hodinky
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kluc", ["dnes.hr_connected", "settings.hr_status_waiting"])
def test_pripojeny_je_telefon(kluc):
    for j in i18n.LANGUAGES:
        text = S[kluc][j].lower()
        assert TELEFON[j] in text, (kluc, j, text)
        assert HODINKY[j] not in text, (kluc, j, text)


def test_stav_linked_hovori_o_telefone():
    a = types.SimpleNamespace(_hr_state="linked", _hr_last_bpm=None, pal={"warn": "#f80"})
    text, _farba = app_mod.DandurfApp._hr_status_display(a)
    assert text == i18n.tr("settings.hr_status_waiting")


def test_signal_v_historii_caka_na_tep_nie_na_hodinky():
    assert "kým sa hodinky pripojili" not in S["metric.signal.more"]["sk"]
    assert "wait for the watch to connect" not in S["metric.signal.more"]["en"]
    assert "until your heart rate started coming in" in S["metric.signal.more"]["en"]


# --------------------------------------------------------------------------
# Skratka: "Strg" po nemecky
# --------------------------------------------------------------------------

def test_nemecky_zapis_skratky():
    assert hotkey.format_combo("ctrl+alt+z", lang="de") == "Strg + Alt + Z"
    assert hotkey.format_combo("ctrl+shift+f12", lang="de") == "Strg + Umschalt + F12"
    for j in ("en", "sk", "ja", "bg"):
        assert hotkey.format_combo("ctrl+alt+z", lang=j) == "Ctrl + Alt + Z", j
    assert hotkey.format_combo("ctrl+k", lang="de", oddelovac=" ") == "Strg K"
    assert hotkey.format_combo("toto nie", lang="de") == ""


def test_predvoleny_jazyk_je_jazyk_appky(jazyk):
    jazyk("de")
    assert hotkey.format_combo("ctrl+alt+z") == "Strg + Alt + Z"
    jazyk("en")
    assert hotkey.format_combo("ctrl+alt+z") == "Ctrl + Alt + Z"


def test_nemecke_texty_nemaju_ctrl():
    assert not [k for k, v in S.items() if re.search(r"\bCtrl\b", v["de"])]
    assert "Strg+Alt+Z" in S["log.safe_mode"]["de"]
    for kluc in ("log.edge_failed_offline", "log.edge_failed_refused", "log.edge_failed_other"):
        assert "Strg+K" in S[kluc]["de"], kluc


def test_volba_v_nemcine_uklada_anglicky_zapis(jazyk):
    jazyk("de")
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.snooze_hotkey = "ctrl+alt+f9"
    a._hotkey_zlyhala = False
    volby = a._snooze_hotkey_volby(kolizia=lambda _c: "")
    assert ("Strg + Alt + Z", "ctrl+alt+z") in volby
    a._snooze_hotkey_podla_popisu = dict(volby)
    a.ulozene = []
    a.save_settings = lambda: a.ulozene.append(a.snooze_hotkey)
    a.start_snooze_hotkey = lambda po_zmene=False: True
    a._refresh_snooze_hotkey_row = lambda: None
    a._refresh_kamae_state_text = lambda: None
    a.log = lambda _m: None
    a.on_snooze_hotkey_pick("Strg + Alt + Z")
    assert a.snooze_hotkey == "ctrl+alt+z" and a.ulozene == ["ctrl+alt+z"]


def test_app_log_ostava_anglicky():
    assert 'format_combo(self.combo, lang="en")' in zdroj_suboru("hotkey.py")


# --------------------------------------------------------------------------
# Dotaznik po relacii
# --------------------------------------------------------------------------

def _init_dotaznika():
    strom = ast.parse(zdroj_suboru("ui_dialogs.py"))
    trieda = next(u for u in strom.body
                  if isinstance(u, ast.ClassDef) and u.name == "SessionEndDialog")
    return ast.unparse(next(f for f in trieda.body
                            if isinstance(f, ast.FunctionDef) and f.name == "__init__"))


def test_stopa_relacie_v_praci_nehovori_o_hrani():
    kod = _init_dotaznika()
    assert "'session.end.trace_hint_work' if self._svet == 'work'" in kod
    hranie = {"sk": "hralo", "cs": "hrálo", "en": "playing", "de": "gespielt",
              "fr": "jouais", "es": "jugando", "pt": "jogando", "ru": "игра",
              "bg": "играло", "ja": "プレイ", "zh": "玩"}
    for j in i18n.LANGUAGES:
        text = S["session.end.trace_hint_work"][j]
        assert hranie[j] not in text, j
        # rovnaka stavba ako verzia pre Hru (trojuholniky, pruh, vstupy)
        assert text != S["session.end.trace_hint"][j], j


@pytest.mark.parametrize("minuty", [0, 1, 2, 59, 123])
def test_bulharsky_titulok_bez_mnozneho_cisla(jazyk, minuty):
    """"Зад гърба ти са 1 мин игра" - "са" je mnozne cislo, pri jednej
    minute (a pri "0 мин" kratkej relacie) nesedelo. Teraz "Играта ти
    продължи {time}." - sloveso patri k "Играта", nie k casu."""
    import ui_dialogs
    jazyk("bg")
    cas = ui_dialogs.SessionEndDialog._cas(minuty)
    for kluc in ("session.end.title", "session.end.title_work"):
        text = i18n.tr(kluc, time=cas)
        assert " са " not in text and cas in text, (kluc, text)
        assert "продължи" in text, (kluc, text)


# --------------------------------------------------------------------------
# Neulozena relacia: skutocne pravidlo
# --------------------------------------------------------------------------

def test_pravidlo_ulozenia_relacie():
    assert hr_stats.je_ulozitelna({"duration_s": 60, "samples": 10})
    assert not hr_stats.je_ulozitelna({"duration_s": 59.9, "samples": 500})
    assert not hr_stats.je_ulozitelna({"duration_s": 3600, "samples": 9})


def test_veta_o_neulozenej_relacii_povie_pravidlo():
    for j in i18n.LANGUAGES:
        text = S["log.hr_session_no_data"][j]
        assert text.count("10") == 2, j
        assert HODINKY[j] not in text.lower(), j
    en = S["log.hr_session_no_data"]["en"]
    assert "fewer than 10 heart-rate readings" in en and "at least a minute" in en
    assert "not even a minute" not in en


def test_riadok_ide_len_pri_minute_bez_hodnot():
    D = app_mod.DandurfApp
    denn = []
    a = types.SimpleNamespace(log=denn.append)
    D._kratka_relacia_bez_tepu(a, {"duration_s": 61.0, "samples": 9})
    D._kratka_relacia_bez_tepu(a, {"duration_s": 30.0, "samples": 2})
    D._kratka_relacia_bez_tepu(a, {"duration_s": 900.0, "samples": 300})
    assert denn == [i18n.tr("log.hr_session_no_data")]


# --------------------------------------------------------------------------
# Zlyhana priprava hlasu
# --------------------------------------------------------------------------

def test_hlas_posle_do_nastaveni_zvuk(jazyk):
    for j in i18n.LANGUAGES:
        jazyk(j)
        stranka = app_audio.stranka_zvuku()
        assert stranka == "%s → %s" % (i18n.tr("nav.nastavenia"),
                                       i18n.tr("nav.nastavenia_tabs.zvuk"))
        retry = i18n.tr("common.retry")
        for kluc in ("log.edge_failed_offline", "log.edge_failed_refused",
                     "log.edge_failed_other"):
            text = i18n.tr(kluc, page=stranka, retry=retry, err="x",
                           cmd=i18n.tr("common.prepare_voices"))
            assert stranka in text, (j, kluc)
            assert i18n.tr("nav.zvuk") not in text, (j, kluc)
            # "opitaj pak s „Opitaj pak“": meno tlacidla len raz
            assert text.lower().count(retry.lower()) == 1, (j, kluc, text)
    assert "page=stranka_zvuku()" in zdroj_metody("_edge_priprava_zlyhala")
    # {cmd} je presne polozka palety Ctrl+K
    assert 'tr("common.prepare_voices")' in zdroj_metody("_command_palette_items")


# --------------------------------------------------------------------------
# Prvy ×: veta pred volbou
# --------------------------------------------------------------------------

def test_veta_pri_krizi_nehovori_ze_uz_bezim_v_liste():
    z = S["tray.close_first"]
    assert z["sk"].startswith("Ak ma necháš bežať v lište")
    assert z["en"].startswith("If you keep me running in the tray")
    assert not z["sk"].startswith("Bežím") and not z["en"].startswith("I keep running")
    assert not z["cs"].startswith("Běžím") and not z["bg"].startswith("Продължавам")
    # tlacidlo "Nechat bezat v liste" je ta ista volba, o ktorej veta hovori
    assert i18n.tr_lang("en", "tray.keep_running") == "Keep running in the tray"


# --------------------------------------------------------------------------
# Cinstina: jedna pomlcka
# --------------------------------------------------------------------------

def test_cinstina_ma_jednu_pomlcku():
    zle = []
    for kluc, zaznam in S.items():
        text = zaznam["zh"]
        if text == zaznam["en"]:
            continue            # anglicka nahrada, nie cinsky text
        bez_ziadnej_hodnoty = text.replace("“—”", "")
        if re.search(r" —|— |(?<!—)—(?!—)|———", bez_ziadnej_hodnoty):
            zle.append(kluc)
    assert not zle, zle


# --------------------------------------------------------------------------
# Uvod a README: hodinky s appkou v telefone
# --------------------------------------------------------------------------

def test_uvod_hovori_o_hodinkach_ako_readme():
    en = S["ob.step1.need"]["en"]
    assert "smartwatch" in en and "companion phone app" in en
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    assert "smartwatch" in readme and "companion app" in readme
    assert "chest strap" not in readme.lower()


# --------------------------------------------------------------------------
# Stitok adresy a mrtve kluce
# --------------------------------------------------------------------------

def test_stitok_vpn_sa_zhoduje_s_adresou():
    assert S["hr.ip_virtual"]["sk"] == "(VPN/virtuálna)"
    assert S["hr.ip_virtual"]["fr"] == "(VPN/virtuelle)"
    assert S["hr.ip_virtual"]["cs"] == "(VPN/virtuální)"      # rovnake pre vsetky rody
    for j in i18n.LANGUAGES:
        assert "VPN" in S["hr.ip_virtual"][j], j


def test_paleta_uz_neodstranuje_emoji_zo_sprievodcu():
    kod = zdroj_metody("_command_palette_items")
    assert "📖" not in kod
    assert 'sprievodca = tr("guide.panel_title")' in kod
    for kluc in ("nav.guide", "dnes.stat_hrpi", "key.gamepad_prefix",
                 "onboarding.hero.symptom.jaw"):
        assert kluc not in S, kluc
