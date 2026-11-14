# -*- coding: utf-8 -*-
"""README, PRIVACY a KNOWN_ISSUES po davke 0.2.2c hovoria to, co robi kod.

Audit: parovanie v README nemalo postup (kde je adresa PC, ze 0.0.0.0 do
telefonu nepatri, Sukromna siet, Cancel vo firewalle, OBS na 4455). Davka
0.2.2c zmenila parovanie, uvod, prehliadku a prvy vecer - dokumenty to musia
povedat rovnako. Strazi sa:

  * README "Getting your heart rate in" zacina 5 krokmi, za nimi "Still
    waiting for the watch?" a "Streaming with OBS?"; nazvy ovladacov su
    presne tie z anglickeho UI a cisla (20 s, 4456) z kodu,
  * prvy start caka na hlas najviac 15 s - README aj PRIVACY uz netvrdia,
    ze appka zacne sledovat hned po uvode,
  * es/de/fr/pt dostanu hlas svojho jazyka, relacia "Len nastavovanie
    appky" sa z ucenia vyradi,
  * KNOWN_ISSUES ma v sekcii 0.2.2 body o uvode, prehliadke a parovani.

Zamerne sa nepinuju cele odstavce (audit: testy zamykali README v dlzke) -
len nazvy z UI, cisla z kodu a vety, ktore uz nesmu byt pravda. Od 0.2.2d
su pravidla hlasu a ucenia v docs/HOW-IT-WORKS.md - straze isli s nimi.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402
from settings_model import VOICE_HINTS  # noqa: E402


AKO = "docs/HOW-IT-WORKS.md"


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain(text):
    # vety v .md su zalomene kdekolvek; nedelitelny spojovnik (U+2011) z UI
    # aj z README sa porovnava ako obycajny
    return " ".join(text.split()).replace("‑", "-")


def _en(kluc):
    return i18n.STRINGS[kluc]["en"]


def _sekcia(text, nadpis, koniec=None):
    zaciatok = text.index("\n## " + nadpis)
    stop = text.index(koniec, zaciatok) if koniec else text.find("\n## ", zaciatok + 1)
    return text[zaciatok:stop if stop != -1 else len(text)]


def _konstanta(meno):
    """Cislo triedy DandurfApp zo zdroja app.py - bez importu Tk."""
    m = re.search(r"^\s+%s = ([\d.]+)\s*$" % meno, zdroj_suboru("app.py"), re.M)
    assert m, meno
    return float(m.group(1))


# --------------------------------------------------------------------------
# README: parovanie po krokoch
# --------------------------------------------------------------------------

def _parovanie():
    return _plain(_sekcia(_read("README.md"), "Getting your heart rate in"))


def test_readme_parovanie_zacina_krokmi():
    s = _parovanie()
    kroky = [s.index("%d. **" % n) for n in range(1, 6)]
    assert kroky == sorted(kroky)
    assert "6. **" not in s
    # kroky su navrchu sekcie, rady za nimi, technika portu az potom
    assert (kroky[-1] < s.index("**Still waiting for the watch?**")
            < s.index("**Streaming with OBS?**")
            < s.index("listens on port `4455`"))
    # stara veta, ktoru kroky nahradili
    assert "*Pairing* then means pointing the companion" not in s


def test_readme_kroky_menuju_ovladace_ako_appka():
    s = _parovanie()
    for kluc in ("hr.pair_button", "hr.ip_show", "hr.qr_show",
                 "settings.hr_ip_label", "hr.noconnect_title"):
        assert _plain(_en(kluc)) in s, kluc
    assert "**%s → %s**" % (_en("nav.vhre_short"),
                            _en("settings.hr_section_title")) in s
    # scena a zdroj su tie, ktore appka v telefone ponuka (krok 4 navodu)
    krok4 = _en("hr.step4_body")
    assert "“Zanshin”" in krok4 and "“Tep”" in krok4
    assert 'the scene "Zanshin" and the source "Tep"' in s
    # 0.0.0.0 do telefonu nepatri - README to hovori ako pole v appke
    assert "not the `0.0.0.0`" in s
    assert "0.0.0.0" in _en("settings.hr_ip_hint")


def test_readme_cesty_vo_windows_ako_v_navode():
    """Ponuky Windows v README su tie iste ako v boxe "Watch won't connect
    at all?" - inak by hrac hladal dve rozne cesty."""
    s = _parovanie()
    box = _plain(_en("hr.noconnect_body"))
    for cesta in ("Windows Security → Firewall & network protection → Allow "
                  "an app through firewall → Change settings",
                  "Network & internet → Wi-Fi (or Ethernet) → your network",
                  "Private network"):
        assert cesta in box, cesta
        assert cesta in s, cesta
    assert "tick **Private** next to Zanshin" in s


def test_readme_cisla_parovania_su_z_kodu():
    s = _parovanie()
    # "telefon sa nepripojil" po `HR_NO_CLIENT_AFTER_MS`
    assert _konstanta("HR_NO_CLIENT_AFTER_MS") == 20000
    assert "after about 20 seconds" in s
    # OBS drzi 4455: dennik radi ten isty nahradny port ako README
    assert "4456" in _en("log.hr_port_busy") and "OBS" in _en("log.hr_port_busy")
    assert "for example to `4456`" in s
    assert "You don't need OBS for Zanshin" in s
    # "Zanshin tries the new port right away": zmena portu prijem hned
    # znova spusti, aj ked ho predtym vypla chyba portu
    zmena = zdroj_metody("on_hr_config_change")
    assert "network_changed" in zmena
    assert "self.start_heart_rate_monitor()" in zmena
    assert "_hr_vypnute_chybou" in zmena


def test_navod_uz_neradi_prepnut_prijem():
    """Krok 5 navodu kedysi radil zapnut prepinac, ktory uz zaplo otvorenie
    navodu - kto posluchol, prijem si vypol. README kroky to nerobia tiez."""
    prepinac = _en("settings.hr_enable_switch")
    assert prepinac not in _en("hr.step5_body")
    assert "self._enable_hr_monitoring()" in zdroj_metody("open_watch_pairing")
    s = _parovanie()
    kroky = s[:s.index("**Still waiting for the watch?**")]
    assert prepinac not in kroky
    assert "This switches heart-rate receiving on" in kroky


# --------------------------------------------------------------------------
# Prvy start, hlasy jazykov, relacia nastavovania
# --------------------------------------------------------------------------

def test_prvy_start_caka_na_hlas_najviac_15_s():
    assert _konstanta("PRVY_START_MAX_S") == 15.0
    assert "self._zacni_sledovat_po_priprave_hlasu()" in zdroj_suboru("app.py")
    readme = _plain(_read("README.md"))
    privacy = _plain(_read("PRIVACY.md"))
    assert "begins listening by itself right after the introduction" not in readme
    assert "starts listening by itself right after the introduction" not in privacy
    assert "at most about 15 seconds" in readme
    assert "after about 15 seconds at most" in privacy
    assert "*%s*" % _en("kamae.voice_prep") in readme


def test_hlas_ukazky_v_uvode_je_z_windows():
    """README aj PRIVACY: ukazka hlasu v uvode nic neposiela - kod pouziva
    len hlas z Windows (`speak_sapi_isolated`)."""
    assert "speak_sapi_isolated(" in zdroj_suboru("ui_dialogs.py")
    assert "its voice preview there uses the Windows voice and sends nothing" in (
        _plain(_read(AKO)))
    assert "The voice preview in the introduction always uses it" in (
        _plain(_read("PRIVACY.md")))


def test_hlasy_jazykov_es_de_fr_pt():
    assert {"es", "de", "fr", "pt"} <= set(VOICE_HINTS)
    ako = _plain(_read(AKO))
    assert "also in Spanish, German, French or Portuguese" in ako
    k = _plain(_sekcia(_read("KNOWN_ISSUES.md"), "What 0.2.2 changes",
                       "\n## What 0.2.1 fixes"))
    # mena hlasov v KNOWN_ISSUES su tie z VOICE_HINTS
    for jazyk in ("es", "de", "fr", "pt"):
        meno = re.match(r"\w+-\w+-(\w+?)Neural$", VOICE_HINTS[jazyk]).group(1)
        assert meno in k, (jazyk, meno)


def test_relacia_nastavovania_sa_neuci():
    znacka = _en("session.context.setup")
    zaklad = {"duration_s": 900.0, "baseline_bpm": 70.0, "max_bpm": 95.0}
    assert hr_stats.ciste_relacie([dict(zaklad, setup=True)]) == []
    ako = _plain(_read(AKO))
    k = _plain(_read("KNOWN_ISSUES.md"))
    assert "*%s*" % znacka in ako
    assert "*%s*" % znacka in k


# --------------------------------------------------------------------------
# KNOWN_ISSUES: sekcia 0.2.2
# --------------------------------------------------------------------------

def _known_022():
    return _plain(_sekcia(_read("KNOWN_ISSUES.md"), "What 0.2.2 changes",
                          "\n## What 0.2.1 fixes"))


def test_known_issues_022_ma_uvod_a_parovanie():
    k = _known_022()
    assert k.index("### The first start") < k.index("### Pairing your watch")
    for nadpis in ('**"Pair a watch now" in the intro skipped the rest of it.**',
                   "**The intro couldn't be closed.**",
                   "**The tour described the ensō wrong.**",
                   "**The first evening spoke mostly in the Windows voice.**",
                   "**Setting the app up at the desk counted as play.**",
                   "**The pairing guide never showed whether pairing worked",
                   "**The English pairing guide showed `THIS PC\\u2019S` literally.**"):
        assert nadpis in k, nadpis


def test_known_issues_022_cituje_texty_z_appky():
    k = _known_022()
    for kluc in ("ob.skip", "ob.quit.title", "tour.sensor.pair",
                 "kamae.voice_prep", "kamae.no_client", "hr.noconnect_title",
                 "hr.trouble_title", "dnes.hr_title", "dnes.hr_off",
                 "dnes.hr_busy", "dnes.hr_no_client", "dnes.hr_waiting",
                 "settings.hr_ip_label", "hr.pair_button"):
        assert "*%s*" % _plain(_en(kluc)) in k, kluc
    assert '"%s"' % _en("hr.pair_this_pc") in k
    # zivy stav v navode - od cakania po tep
    assert "*%s*" % _en("hr.pair_status_waiting").lstrip("● ") in k


def test_known_issues_prehliadka_pat_miest():
    """Uvitanie + pat miest = 6 bubliniek; "five places" v texte prehliadky
    aj v KNOWN_ISSUES."""
    from guided_tour import GuidedTour
    assert GuidedTour.STEP_COUNT == 6
    assert "five places" in _en("tour.welcome.body")
    assert "five places in about a minute" in _known_022()
