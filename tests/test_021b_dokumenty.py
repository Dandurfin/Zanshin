# -*- coding: utf-8 -*-
"""Dokumenty po opravach 0.2.1 (druha kontrola) hovoria to, co robi kod.

  * README / PRIVACY: prirodzeny hlas posiela Microsoftu len hlasky, ktore
    moze naozaj povedat (jedna zo styroch, zapnuta, so zapnutym obrazkom v
    hre, s hlasom, bez vlastnej nahravky). Uz netvrdia, ze ide aj vypnuta
    alebo nahrata hlaska, ani ze po prepnuti na hlas z Windows sa
    rozbehnuta priprava este dopossle.
  * Hlaska s vypnutym obrazkom v hre sa od 0.2.1c nepripravuje - PRIVACY a
    KNOWN_ISSUES uz nepriznavaju, ze jej text ide Microsoftu.
  * UDP, ktore sa neotvorilo: dokumenty citaju stitok a prepinac presne
    tak, ako ich ukazuje appka; do app.log ide len port a chyba.
  * KNOWN_ISSUES: hra Ctrl+Alt+Z "nemusi dostat", chodza sa z ucenia
    nevyraduje (kroky len stisia hlasky), terminy ako v README, licencia
    "GPLv3 or later".
  * SOUL: hranica vysokeho tepu je do naucenia zaloha 110.
  * SAFETY: gui_harness_auto.py zalohuje nastavenia a historiu tepu na
    disk vedla originalov a po prerusenom behu ich vrati (od 0.2.1c; do
    vtedy historiu drzal len v pamati a SAFETY to priznaval).

Kazda veta je naviazana na kod: ked sa kod zmeni, test povie, ktory
dokument treba prepisat - nie naopak.
"""
import ast
import inspect
import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import heart_rate  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain(meno):
    """Text bez zalomeni a bez znakov citatu ">" na zaciatku riadkov -
    vety v .md su zalomene kdekolvek, aj v ramceku README."""
    return " ".join(" ".join(r.lstrip(">") for r in _read(meno).splitlines())
                    .split())


def _en(kluc):
    return i18n.STRINGS[kluc]["en"]


def _sekcia(text, nadpis):
    zaciatok = text.index("\n## " + nadpis)
    koniec = text.find("\n## ", zaciatok + 1)
    return text[zaciatok:koniec if koniec != -1 else len(text)]


def _metoda_triedy(subor, trieda, metoda):
    src = _read(subor)
    for uzol in ast.parse(src).body:
        if isinstance(uzol, ast.ClassDef) and uzol.name == trieda:
            for f in uzol.body:
                if isinstance(f, ast.FunctionDef) and f.name == metoda:
                    return ast.get_source_segment(src, f)
    raise AssertionError(f"{trieda}.{metoda} nie je v {subor}")


# --------------------------------------------------------------------------
# Priprava hlasu: co sa posiela
# --------------------------------------------------------------------------

def test_priprava_posiela_len_hlasky_ktore_moze_povedat():
    # Kod: vypnuta hlaska, hlaska s vypnutym obrazkom v hre (0.2.1c),
    # vlastna nahravka a slot navyse z 0.1 (index 4+) sa nepripravuju - ani
    # pri Teste (`_speak_text`).
    telo = zdroj_metody("_slot_na_pripravu")
    for podmienka in ("je_kategoria(slot.index)", "slot.enabled_value",
                      "self._ma_obrazok_v_hre(slot)",
                      "MODE_TTS", "self._slot_voice_clip(slot)"):
        assert podmienka in telo, podmienka
    assert "self._slot_na_pripravu(slot)" in zdroj_metody("pregen_jobs")
    assert "self._slot_na_pripravu(slot)" in zdroj_metody("_speak_text")

    readme = _plain("README.md")
    assert "including ones you've switched off" not in readme
    assert ("that are switched on, with their in-game picture on, and set to "
            "speak (not ones that play your own recording)") in readme
    assert ("one of the four, switched on with its in-game picture on, set to "
            "speak and not playing your own recording") in readme
    assert ("testing a reminder that is switched off or has its picture off, "
            "or an extra one kept from 0.1, plays the Windows voice and sends "
            "nothing") in readme

    privacy = _plain("PRIVACY.md")
    assert "**Which reminders:** only those of the four" in privacy
    assert ("that are switched on, have their in-game picture on, are set to "
            "speak and don't play your own recording") in privacy
    assert "extra reminder kept from a 0.1 profile are never sent" in privacy
    # Co pripravu spusti (zapnutie hlasky ci obrazka, zmazanie nahravky,
    # novy profil).
    assert ("switch it or its picture on, switch it to speak or remove its "
            "own recording") in readme
    assert ("switch a reminder or its picture on, switch it to speak or "
            "remove its own recording") in privacy
    for meno, text in (("README.md", readme), ("PRIVACY.md", privacy)):
        assert "profile (or create one)" in text, meno


def test_zapnutie_hlasky_a_novy_profil_pripravu_spustia():
    """README aj PRIVACY menuju zapnutie hlasky a novy profil medzi tym, co
    pripravu spusti - kod to od tejto opravy naozaj robi."""
    assert "schedule_pregenerate" in _metoda_triedy(
        "ui_dialogs.py", "SlotCard", "on_enabled_change")
    assert "schedule_pregenerate" in zdroj_metody("create_profile")
    assert "schedule_pregenerate" in _metoda_triedy(
        "ui_dialogs.py", "SlotSettingsDialog", "_commit_voice")
    # Zapnutie obrazka v hre tiez (0.2.1c) - oba prepinace obrazka idu cez
    # `on_overlay_config_change` (test_021c_pregen_obrazok.py).
    assert "self.schedule_pregenerate(200)" in zdroj_metody("on_overlay_config_change")


def test_prepnutie_prec_zastavi_rozbehnutu_pripravu():
    # Kod: kazde planovanie aj prazdna priprava zvysi `_pregen_seq`, prepnutie
    # na hlas z Windows tiez - vlakno dalsiu hlasku nezacne.
    for metoda in ("on_engine_change", "schedule_pregenerate", "pregenerate"):
        assert "self._zrus_rozbehnutu_pripravu()" in zdroj_metody(metoda), metoda
    assert "self._pregen_seq += 1" in zdroj_metody("_zrus_rozbehnutu_pripravu")

    readme = _plain("README.md")
    assert "lines already being prepared at that moment are still sent" not in readme
    assert "that stops any preparing at once, except a line already on its way" in readme
    assert ("to Work or to the Windows voice stops any preparing already "
            "running at once; only a line already on its way is finished") in readme

    privacy = _plain("PRIVACY.md")
    assert "**Switching away stops it.**" in privacy
    assert ("to *Work* or to the Windows voice while lines are being prepared, "
            "preparing stops at once; only the line already on its way is "
            "finished") in privacy

    k = _plain("KNOWN_ISSUES.md")
    assert "**Switching to the Windows voice didn't stop preparing" in k


def test_hlaska_s_vypnutym_obrazkom_dokumenty_hovoria_pravdu():
    """`_dalsi_cue_slot` hlasku s vypnutym obrazkom v hre sam nespusti. Do
    0.2.1b ju priprava nevyradovala (jej text isiel Microsoftu) a PRIVACY s
    KNOWN_ISSUES to poctivo priznavali. Od 0.2.1c ju `_slot_na_pripravu`
    vyraduje - priznanie je prec a KNOWN_ISSUES to vedie medzi opravami.
    Keby podmienka na obrazok z kodu zmizla, test povie, ze vety o nej
    uz nie su pravda."""
    kod = zdroj_metody("_slot_na_pripravu").split('"""')[-1]   # bez docstringu
    vyraduje = "overlay_configs" in kod or "_ma_obrazok" in kod
    assert vyraduje
    privacy = _plain("PRIVACY.md")
    k = _plain("KNOWN_ISSUES.md")
    assert "still counts as switched on, so its line is prepared" not in privacy
    assert ("**A reminder whose in-game picture you've switched off** still "
            "has its line prepared") not in k
    opravy = " ".join(_sekcia(_read("KNOWN_ISSUES.md"), "What 0.2.1 fixes").split())
    assert "of ones whose in-game picture is off" in opravy
    assert "Switching one or its picture on" in opravy


# --------------------------------------------------------------------------
# Port tepu a UDP
# --------------------------------------------------------------------------

def test_privacy_port_menuje_ovladanie_ako_appka():
    p = _plain("PRIVACY.md")
    for kluc in ("settings.hr_enable_switch", "dnes.empty_btn",
                 "hr.pair_button", "settings.hr_ip_label"):
        assert _en(kluc) in p, kluc
    assert "*%s → %s*" % (_en("nav.vhre_short"),
                          _en("settings.hr_section_title")) in p
    assert "heart-rate sensor settings" not in p
    # Parovaci sprievodca senzor zapne - PRIVACY to hovori.
    assert "self._enable_hr_monitoring()" in zdroj_metody("open_watch_pairing")
    # Na UDP appka neodpoveda nicim, na TCP sa tvari ako OBS.
    assert "on UDP it replies nothing" in p
    assert "sendto" not in inspect.getsource(heart_rate)


def test_udp_stitok_a_log_v_dokumentoch_ako_v_kode():
    stitok = _en("settings.hr_status_udp_off")
    for meno in ("README.md", "KNOWN_ISSUES.md"):
        assert "*%s*" % stitok in _plain(meno), meno
    prepinac = _en("settings.hr_enable_switch")
    for meno in ("README.md", "KNOWN_ISSUES.md"):
        assert "switch *%s* off and on" % prepinac in _plain(meno), meno
    assert "**If UDP won't open**" in _plain("PRIVACY.md")
    assert "not your PC's address" in _plain("PRIVACY.md")

    # Kod: vlastne druhy stavu (TCP bezi dalej) a do app.log len port a
    # chyba - adresa `host` nie.
    src = inspect.getsource(heart_rate.HeartRateMonitor._udp_loop)
    assert '"udp_busy"' in src and '"udp_error"' in src
    volania = [u for u in ast.walk(ast.parse(textwrap.dedent(src)))
               if isinstance(u, ast.Call) and getattr(u.func, "attr", "") == "warning"]
    assert len(volania) == 1
    mena = {n.id for a in volania[0].args for n in ast.walk(a)
            if isinstance(n, ast.Name)}
    assert mena == {"port", "exc"}, mena


def test_readme_check_sources_offline_ako_skript():
    import check_sources
    readme = _plain("README.md")
    assert ("it says you're offline, checks nothing and exits with 0 instead "
            "of reporting the links as dead") in readme
    main = inspect.getsource(check_sources.main)
    assert "if unreachable and not answered:" in main
    assert "sys.exit(0)" in main


# --------------------------------------------------------------------------
# KNOWN_ISSUES, SOUL, SAFETY
# --------------------------------------------------------------------------

def test_known_issues_bez_rozporov():
    k = _plain("KNOWN_ISSUES.md")
    assert "the game doesn't receive that one key combination" not in k
    assert "a game that uses that one key combination may not receive it" in k
    assert "walking isn't filtered out yet" not in k
    for stare in ("high-HR line", "strain threshold", "high heart-rate line",
                  "plain GPLv3", "your own high heart-rate limit"):
        assert stare not in k, stare
    assert _read("KNOWN_ISSUES.md").rstrip().endswith("· GPLv3 or later")
    opravy = _sekcia(_read("KNOWN_ISSUES.md"), "What 0.2.1 fixes")
    for nadpis in ("### The online voice", "### Smaller fixes"):
        assert nadpis in opravy, nadpis
    # Jazykovy riadok: KNOWN_ISSUES hovori, ze uz netvrdi preklad hlasok.
    assert _en("settings.language_sub") == "Cues you already have keep their wording."
    assert "reminders you already have keep their wording" in k


def test_chodza_len_stisi_hlasky_ucenie_ju_nevyraduje():
    """KNOWN_ISSUES: kroky len stisia hlasky, cas chodze sa uci dalej. Keby
    ucenie kroky niekedy vyradovalo, veta v KNOWN_ISSUES musi ist prec."""
    k = _plain("KNOWN_ISSUES.md")
    assert "Steps from the watch only keep cues quiet" in k
    for f in (hr_stats.dynamicky_kriticky, hr_stats.dynamicky_prah_zataze,
              hr_stats.dlhodoba_zakladna, hr_stats.ciste_relacie,
              hr_stats.HeartStats.summary):
        src = inspect.getsource(f)
        for slovo in ("steps", "_steps", "kroky", "note_metrics"):
            assert slovo not in src, (f.__name__, slovo)
    assert "steps_per_min" in zdroj_metody("_cue_can_fire")


def test_soul_hranica_a_licencia():
    s = _plain("SOUL.md")
    assert "your own high heart-rate limit" not in s
    assert hr_stats.KRITICKY_ZALOHA == 110.0
    assert "(at or above your high heart-rate limit — 110 BPM until the app has learned yours)" in s
    assert "under the GPLv3 or later." in s
    assert "under the GPLv3." not in s


def test_safety_harness_odklada_nastavenia_a_historiu_ako_skript():
    skript = _read("gui_harness_auto.py")
    safety = _plain("SAFETY.md")
    for subor in ("hr_sessions.json", "hr_insights.json"):
        assert '"%s"' % subor in skript, subor
        assert "`%s`" % subor in safety, subor
    assert 'os.path.join(PROJ, "logs", "gui_harness")' in skript
    # Od 0.2.1c je zaloha na disku vedla originalov, nie v pamati ani v
    # logs\gui_harness\ - a po tvrdom zabiti ju vrati dalsi beh
    # (test_021c_harness_zaloha.py overuje spravanie).
    assert "_hr_backups" not in skript
    assert 'ZALOHA = ".pred-harnessom"' in skript
    assert "def obnov_po_prerusenom_behu" in skript
    assert '"%s.pred-obnovou-%s"' in skript
    assert "drží len v pamäti" not in safety
    assert "(zálohu dá do `logs\\gui_harness\\`)" not in safety
    assert "skopíruje na disk vedľa originálu (`*.pred-harnessom`)" in safety
    assert "vráti ich aj po prerušení (Ctrl+C, zavreté okno, pád)" in safety
    assert "`*.pred-obnovou-<čas>`" in safety
