# -*- coding: utf-8 -*-
"""Dokumenty po davke 4b (0.2.2) hovoria to, co robi kod.

  * README "You need" a uvod (`ob.step1.need`) hovoria to iste: chytre
    hodinky, ich appka v telefone, ktora posiela tep do PC, a ta ista
    domaca siet (Wi-Fi),
  * PRIVACY: cakajuca relacia sa doplni pri dalsom starte ALEBO hned po
    dalsom uspesnom ulozeni a subor sa potom zmaze; necitatelny sa nezmaze,
    odlozi sa ako `.corrupt-<cas>`. Zoznam lokalnych suborov sedi s kodom
    (`data_io.MAZATELNE`, nastavenia a ich zaloha, cache hlasu, logy),
  * SAFETY a HOW-IT-WORKS: stitky "(VPN/virtualna)" a "(hotspot)", externy
    prepinac Hyper-V,
  * HOW-IT-WORKS a CHANGELOG: datumy v jazyku appky, "1 h 15 min" od hodiny,
    dotaznik pri ukonceni z listy a pri vypnuti Windows, "phone connected",
    nemecke Strg/Umschalt,
  * DEVELOPMENT: tests/conftest.py presmeruje data a log testov.

Zamerne sa nepinuju cele odstavce - len nazvy z UI, cisla a tvary z kodu a
vety, ktore po zmene kodu prestanu platit. Data su vymyslene.
"""
import os
import re
import sys
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import data_io  # noqa: E402
import hotkey  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
import logging_setup  # noqa: E402
import netinfo  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody, zdroj_suboru  # noqa: E402

ZMENY = "CHANGELOG.md"
AKO = "docs/HOW-IT-WORKS.md"


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain_text(text):
    return " ".join(text.split())


def _plain(meno):
    return _plain_text(_read(meno))


def _en(kluc, **kw):
    text = i18n.STRINGS[kluc]["en"]
    return text.format(**kw) if kw else text


def _sk(kluc):
    return i18n.STRINGS[kluc]["sk"]


def _lokalne():
    """PRIVACY: cast o lokalnych suboroch (pred sietou)."""
    p = _read("PRIVACY.md")
    return _plain_text(p[:p.index("## The few things that can use the network")])


def _davka4():
    c = _read(ZMENY)
    s022 = c[c.index("## What 0.3 changes"):c.index("## What 0.2.1 fixes")]
    return _plain_text(s022[s022.index("### Fewer dead ends"):])


# 12. novembra 2026 o 20:05 miestneho casu - priklad z dokumentov
_PRIKLAD = time.mktime((2026, 11, 12, 20, 5, 0, 0, 0, -1))


# --------------------------------------------------------------------------
# README "You need" == uvod, krok 1
# --------------------------------------------------------------------------

def test_readme_you_need_hovori_to_iste_co_uvod():
    readme = _read("README.md")
    potrebujes = _plain_text(readme[readme.index("**You need:**"):
                                    readme.index("[Download]")])
    uvod = _en("ob.step1.need")
    for fraza in ("a smartwatch that measures heart rate",
                  "companion phone app that sends the heart rate to this PC",
                  "the phone and the PC on the same home network (Wi‑Fi)"):
        assert fraza in potrebujes, fraza
        assert fraza in uvod, fraza
    # testovana cesta a Windows su len v README (uvod uz bezi na Windows)
    assert "Windows 10 untested" in potrebujes
    assert "*HeartRateOnStream for OBS*" in potrebujes
    # stara veta "phone or watch app" ani hrudny pas sa nevracaju
    assert "phone or watch app" not in potrebujes
    assert "chest" not in uvod.lower()


# --------------------------------------------------------------------------
# PRIVACY: cakajuca relacia a uplny zoznam lokalnych suborov
# --------------------------------------------------------------------------

def _relacia(started):
    return {"started": started, "duration_s": 900.0, "samples": 900,
            "avg_bpm": 80, "max_bpm": 110, "baseline_bpm": 70}


def test_privacy_cakajuca_relacia_presne(tmp_path):
    lokalne = _lokalne()
    assert ("Zanshin adds them to your history at the next start, or right "
            "after the next session that saves, and then deletes the file") in lokalne
    assert "`%s.corrupt-<time>`" % hr_stats.CAKAJUCA_MENO in lokalne
    # kod: doplnenie pri starte aj po uspesnom ulozeni (nie pri vypinani)
    assert '_ak_vies(self, "_dopln_cakajuce_relacie")' in zdroj_metody(
        "_obnov_rozpracovanu_relaciu")
    zatvor = zdroj_appky()
    assert re.search(r"if not pri_vypnuti:\s*\n\s*_ak_vies\(self, "
                     r"\"_dopln_cakajuce_relacie\"\)", zatvor)
    # spravanie: doplnena -> subor zmizne
    cesta = str(tmp_path / "hr_sessions.json")
    teraz = time.time()
    assert hr_stats.zapis_cakajucu(cesta, _relacia(teraz - 7200))
    assert os.path.exists(hr_stats.cesta_cakajucej(cesta))
    assert len(hr_stats.obnov_cakajuce(cesta, now=teraz)) == 1
    assert not os.path.exists(hr_stats.cesta_cakajucej(cesta))
    # necitatelny sa nezmaze - odlozi sa ako .corrupt-<cas>
    with open(hr_stats.cesta_cakajucej(cesta), "w", encoding="utf-8") as fh:
        fh.write("{pokazene")
    assert hr_stats.obnov_cakajuce(cesta, now=teraz) == []
    odlozene = [f for f in os.listdir(tmp_path)
                if f.startswith(hr_stats.CAKAJUCA_MENO + ".corrupt-")]
    assert len(odlozene) == 1, os.listdir(tmp_path)
    assert not os.path.exists(hr_stats.cesta_cakajucej(cesta))


def test_privacy_kontrolny_bod_a_pokazena_historia():
    lokalne = _lokalne()
    assert "`%s`" % hr_stats.ROZPRACOVANA_MENO in lokalne
    assert "written every 5 minutes" in lokalne
    assert "It's deleted once the session is saved" in lokalne
    assert "`hr_sessions.json.corrupt-<time>`" in lokalne
    assert '"%s.corrupt-%d" % (path, int(time.time()))' in zdroj_suboru("hr_stats.py")


def test_privacy_zoznam_suborov_sedi_s_kodom():
    lokalne = _lokalne()
    # vsetko, co "Zmazat historiu" maze, je v zozname menom
    for _kluc, meno in data_io.MAZATELNE:
        assert "`%s`" % meno in lokalne, meno
    # nastavenia, ich zaloha a odlozeny pokazeny subor (app_prefs)
    prefs = zdroj_suboru("app_prefs.py")
    assert 'bak = cesta + ".bak"' in prefs
    assert '"%s.corrupt-%s" % (cesta, znacka)' in prefs
    assert "`dandurf_settings.json.bak`" in lokalne
    assert "`dandurf_settings.json.corrupt-<date>-<time>`" in lokalne
    # zalohy pred importom (data_io)
    assert '"%s.pred-importom-%s.bak" % (cesta, znacka)' in zdroj_suboru("data_io.py")
    assert "`<file>.pred-importom-<time>.bak`" in lokalne
    # pripraveny hlas a nahravky v audio/
    assert ("data.delete.tts", os.path.join("audio", "tts_cache")) in data_io.MAZATELNE_PRIECINKY
    assert "`audio/tts_cache`" in lokalne and "`audio/`" in lokalne
    # logy (logging_setup) - mena suborov, nie cesta (conftest ju presmeruje)
    assert os.path.basename(logging_setup.APP_LOG_PATH) == "app.log"
    assert os.path.basename(logging_setup.CRASH_LOG_PATH) == "crash.log"
    assert 'LOG_DIR = os.path.join(DATA_DIR, "logs")' in zdroj_suboru("logging_setup.py")
    assert "`logs/app.log`" in lokalne and "`logs/crash.log`" in lokalne


def test_privacy_ukazat_ip_je_tlacidlo_v_navode():
    p = _plain("PRIVACY.md")
    assert ("**%s** button in the pairing guide (a switch next to the *%s* field)"
            % (_en("hr.ip_show"), _en("settings.hr_ip_label"))) in p
    dialogy = zdroj_suboru("ui_dialogs.py")
    assert 'ui_kit.button(\n                addr_row, pal, tr("hr.ip_show")' in dialogy
    assert 'ui_kit.chip(addr_row, pal, tr("hr.ip_show")' not in dialogy
    assert 'text=tr("hr.ip_show"), variable=self.show_ip_var' in zdroj_suboru("app.py")


# --------------------------------------------------------------------------
# SAFETY a HOW-IT-WORKS: stitky adries
# --------------------------------------------------------------------------

def test_safety_a_how_it_works_stitky_adries():
    s = _plain("SAFETY.md")
    assert "„%s“" % _sk("hr.ip_virtual") in s
    assert "„%s“" % _sk("hr.ip_hotspot") in s
    assert "UDP socket sa len „pripojí“, nič sa neodošle" in s
    assert 'sock.connect(("10.255.255.255", 1))     # UDP connect = ziadny paket' in (
        zdroj_suboru("netinfo.py"))
    a = _plain(AKO)
    sekcia = a[a.index("## Which address the pairing guide shows"):]
    assert "*%s*" % _en("hr.ip_virtual") in sekcia
    assert "*%s*" % _en("hr.ip_hotspot") in sekcia
    assert "Hyper-V external switch" in sekcia
    # kod: hotspot ma vlastny druh, externy prepinac sa pocita ako fyzicky,
    # WSL / Default Switch / Docker nie
    assert netinfo.druh_adaptera("Local Area Connection* 10",
                                 "Microsoft Wi-Fi Direct Virtual Adapter #2") == netinfo.HOTSPOT
    assert netinfo._je_externy_prepinac("vEthernet (LAN)", "Hyper-V Virtual Ethernet Adapter")
    for meno in ("vEthernet (WSL)", "vEthernet (Default Switch)", "vEthernet (Docker)"):
        assert not netinfo._je_externy_prepinac(meno, "Hyper-V Virtual Ethernet Adapter"), meno
    for slovo in ("WSL", "*Default Switch*", "Docker"):
        assert slovo in sekcia, slovo


# --------------------------------------------------------------------------
# HOW-IT-WORKS a CHANGELOG: datumy, cas nad hranicou, dotaznik, texty
# --------------------------------------------------------------------------

def _hm_en(seconds):
    return ui_kit.cas_text(seconds, preklad=lambda k, **kw: i18n.tr_lang("en", k, **kw))


def test_datumy_a_cas_ako_v_kode():
    en = ui_kit.datum_text(_PRIKLAD, jazyk="en")
    sk = ui_kit.datum_text(_PRIKLAD, jazyk="sk")
    assert (en, sk) == ("12 Nov 2026", "12. 11. 2026")
    assert _hm_en(4500) == "1 h 15 min"
    assert ui_kit.DLZKA_OD_S == 3600 and _hm_en(3599) == "59:59"
    # nazov exportu ostava ISO
    assert 'time.strftime("zanshin-relacie-%Y-%m-%d.csv")' in zdroj_suboru("app_history.py")
    for meno, text in ((AKO, _plain(AKO)), (ZMENY, _davka4())):
        assert "*%s* in English, *%s* in Slovak" % (en, sk) in text, meno
        assert "*%s* from an hour up" % _hm_en(4500) in text, meno
    assert "keeps the `2026-11-12` form" in _plain(AKO)


def test_dotaznik_pri_ukonceni_z_listy_a_vypnuti():
    assert "self._dokonci_otvorene_dotazniky()" in zdroj_metody("_quit")
    assert "self._dokonci_otvorene_dotazniky()" in zdroj_metody("_pri_vypinani_windows")
    a = _plain(AKO)
    assert ("The same happens when the questions after an earlier stop are still "
            "open and you quit from the tray, or Windows shuts down, restarts or "
            "signs you out") in a
    assert ("The same happens when the questions after an earlier stop are still "
            "open and you quit from the tray or Windows shuts down") in _davka4()


def test_texty_z_davky_4b_su_v_changelogu():
    d4 = _davka4()
    for kluc in ("dnes.hr_connected", "settings.hr_status_waiting", "hr.ip_hotspot",
                 "nav.vhre_work_short", "ob.step3.pair_now", "hr.ip_show"):
        assert "*%s*" % _en(kluc) in d4, kluc
    # nemecke mena klaves
    assert hotkey.format_combo("ctrl+shift+f12", lang="de") == "Strg + Umschalt + F12"
    assert "*Strg* and *Umschalt*" in d4 and "*Strg* and *Umschalt*" in _plain(AKO)
    # pravidlo ulozenia relacie v logu = `hr_stats.je_ulozitelna`
    assert "at least a minute and have at least 10 readings" in _en("log.hr_session_no_data")
    assert "at least a minute and at least 10 heart-rate readings" in d4
    assert hr_stats.je_ulozitelna({"duration_s": 60.0, "samples": 10})
    assert not hr_stats.je_ulozitelna({"duration_s": 60.0, "samples": 9})
    # HOW-IT-WORKS: "phone connected" ked tep chodi, "waiting for watch" ked
    # je telefon pripojeny bez tepu
    a = _plain(AKO)
    for kluc in ("dnes.hr_connected", "dnes.hr_waiting", "settings.hr_status_waiting"):
        assert "*%s*" % _en(kluc) in a, kluc


def test_development_opisuje_conftest():
    d = _plain("DEVELOPMENT.md")
    assert "`tests/conftest.py`" in d
    conftest = _read("tests/conftest.py")
    assert "logging_setup.LOG_DIR = " in conftest and "paths.DATA_DIR = " in conftest
    assert "`stranka_vhre`" in d and "def stranka_vhre(" in zdroj_suboru("app_spolocne.py")
    assert "`datum_text`" in d and "`cas_text`" in d
