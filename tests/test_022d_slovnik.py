# -*- coding: utf-8 -*-
"""0.2.2 (UX audit, časť 3): jeden slovník a texty, ktoré nesľubujú viac než kód.

Čo sa stalo a prečo to stráži test:
  * Hlavný vypínač mal tri mená a „odpočúvať“ po slovensky znamená špehovať -
    pre appku, ktorá číta časovanie vstupov a názvy procesov, najhoršie
    možné slovo. Teraz: hlavný vypínač = „sledovať“ (en "watching"),
    prepínač tepu = „Prijímať tep z telefónu“ (en "Receive heart rate from
    the phone"), to, čo appka pošle = „pripomienka“ (en "cue").
  * Jedna pripomienka mala päť mien (hláška, spúšťač, slot, line, reminder)
    a každá zo štyroch 3-4 mená v dvoch jazykoch.
  * „Hranica“ boli dve rôzne čísla: BPM aj záťaž 0-100. Teraz hranica /
    limit = len tep v BPM, prah / threshold = len záťaž.
  * „0× som naschvál mlčala“ pri nule a porovnanie, ktoré sa nestalo: tiché
    kontrolné rameno je SÚČASŤOU počtu (ukázal sa len obrázok).
  * Bodka v bočnom paneli: tip opisuje tvar, ktorý kód naozaj kreslí.

Starý test, ktorý by tu niečo opakoval, ostal - tento stráži len nové veci.
"""
import ast
import os
import re
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = i18n.STRINGS
JAZYKY = i18n.LANGUAGES

# Kluce, ktore appka uz nepouziva (zvysky z 0.1 - prekryvanie hlasok, prisny
# zamok, oneskorenie, QR poznamka). Hrac ich nikdy neuvidi, slovnik v nich
# nestrazime. Keby sa niektory vratil do kodu, test_mrtve_kluce_su_naozaj_mrtve
# to chyti.
MRTVE = {"hr.qr_note", "log.listener_error", "settings.overlap", "settings.overlap_sub",
         "log.overlap_on", "log.overlap_off", "settings.strict_global_lock",
         "settings.strict_global_lock_short", "settings.strict_global_lock_sub",
         "log.strict_lock_on", "log.strict_lock_off", "dialog.delay", "dialog.jitter_note",
         "settings.cooldown", "log.slot_settings_saved", "log.slot_key_bound",
         "app.tagline", "onboarding.diag.subtitle"}

# "pocuvat" v prirodzenom zmysle, nie ako vypinac appky.
PRIRODZENE_POCUVAT = {"about.between_lines"}


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _zive():
    return [(k, e) for k, e in S.items() if k not in MRTVE]


def test_mrtve_kluce_su_naozaj_mrtve():
    """Výnimka platí len pre kľúč, ktorý žiadny modul appky nevolá."""
    zdroje = "".join(_read(m) for m in os.listdir(KOREN)
                     if m.endswith(".py") and not m.startswith("i18n"))
    for kluc in MRTVE:
        assert kluc in S, kluc
        assert f'"{kluc}"' not in zdroje and f"'{kluc}'" not in zdroje, kluc


# --------------------------------------------------------------------------
# Hlavny vypinac = sledovat, prepinac tepu = prijimat tep
# --------------------------------------------------------------------------

def test_hlavny_vypinac_sa_vola_sledovat():
    zle = [(k, j) for k, e in _zive() for j in ("sk", "cs")
           if k not in PRIRODZENE_POCUVAT
           and re.search(r"po[čc]úv|poslouch", e[j], re.I)]
    assert not zle, zle
    zle_en = [k for k, e in _zive() if re.search(r"\blisten", e["en"], re.I)]
    assert not zle_en, zle_en
    assert S["status.running"]["sk"].endswith("Sledujem")
    assert S["status.running"]["en"].endswith("Watching")
    assert S["kamae.running"]["sk"] == "Sledujem" and S["kamae.running"]["en"] == "Watching"
    assert S["log.listening_on"]["sk"].startswith("Sledovanie")
    assert "watching" in S["dock.start_tip"]["en"].lower()


def test_prepinac_tepu_sa_vola_prijimat_tep_a_texty_ho_cituju_presne():
    assert S["settings.hr_enable_switch"]["sk"] == "Prijímať tep z telefónu"
    assert S["settings.hr_enable_switch"]["en"] == "Receive heart rate from the phone"
    for jazyk in JAZYKY:
        meno = S["settings.hr_enable_switch"][jazyk]
        # veta v denniku radi ten prepinac vypnut a zapnut - musi ho volat
        # presne tak, ako je napisany pri prepinaci
        assert meno in S["log.hr_udp_busy"][jazyk], jazyk
    assert "príjem tepu" in S["tray.close_first"]["sk"]
    assert "heart-rate receiving" in S["tray.close_first"]["en"]


# --------------------------------------------------------------------------
# Pripomienka / cue - jedno slovo
# --------------------------------------------------------------------------

def test_pripomienka_ma_jedno_meno():
    assert not [k for k, e in S.items() if re.search(r"hl[áa][šs]k|hlášok", e["sk"], re.I)]
    assert not [k for k, e in S.items() if re.search(r"hlášk|hlášek|hlášce", e["cs"], re.I)]
    zle_en = [k for k, e in _zive()
              if re.search(r"\breminders?\b|\bTriggers\b|\bvoice lines?\b|\bSlot \{n\}", e["en"])]
    assert not zle_en, zle_en
    for jazyk in JAZYKY:
        stranka = S["nav.spustace"][jazyk]
        assert S["nav.nastavenia_tabs.spustace"][jazyk] == stranka, jazyk
        assert S["tour.triggers.title"][jazyk] == stranka, jazyk
    assert S["nav.spustace"]["sk"] == "Pripomienky" and S["nav.spustace"]["en"] == "Cues"


def test_styri_pripomienky_maju_v_kazdom_jazyku_jedno_meno():
    sprievodca = ("guide.grounding.title", "guide.jaw.title", "guide.periphery.title",
                  "guide.breath.title")
    for jazyk in JAZYKY:
        for index, kluc in enumerate(sprievodca):
            meno = S[f"overlay.slot.{index}"][jazyk]
            assert S[kluc][jazyk] == meno, (jazyk, kluc)
            # bez emoji a bez zatvoriek z 0.1 (pripomienky uz nespustaju klavesy)
            assert "(" not in meno and "（" not in meno, (jazyk, meno)
            assert all(ch.isalpha() or ch in " &" for ch in meno), (jazyk, meno)
        assert S["cue.category.release"][jazyk].lower() == S["overlay.slot.2"][jazyk].lower(), jazyk
        # popisy v uvode = presne to, co hrac uvidi pod obrazkom v hre
        for cap, popis in (("grounding", "grounding"), ("jaw", "jaw"), ("release", "release")):
            assert (S[f"ob.step1.cap_{cap}"][jazyk].upper()
                    == S[f"overlay.caption.{popis}"][jazyk].upper()), (jazyk, cap)


def test_hranica_je_tep_prah_je_zataz():
    assert "Hranica" in S["settings.hr_critical_learning"]["sk"]
    assert "BPM" in S["settings.hr_critical_learning"]["sk"]
    for kluc in ("cue_rate.learning", "cue_rate.computed", "session.end.none_never",
                 "insight.cue_never_above", "insight.cue_far"):
        assert "prah" in S[kluc]["sk"] and "hranic" not in S[kluc]["sk"], kluc
        assert "threshold" in S[kluc]["en"], kluc
        assert "limit" not in S[kluc]["en"] and " line " not in S[kluc]["en"], kluc
    for kluc in ("settings.hr_critical_learning", "settings.hr_critical_computed",
                 "metric.over.title", "metric.zones.title"):
        assert "limit" in S[kluc]["en"] and "threshold" not in S[kluc]["en"], kluc
    # zataz sa ukazuje na stupnici 0-100, nie ako hole cislo
    assert "{prah} zo 100" in S["cue_rate.learning"]["sk"]
    assert "{prah}/100" in S["cue_rate.learning"]["en"]


# --------------------------------------------------------------------------
# Dotaznik: "0× som naschval mlcala"
# --------------------------------------------------------------------------

def test_tiche_pripomienky_su_sucastou_poctu():
    for jazyk in JAZYKY:
        assert "{silent}" not in S["session.end.cues"][jazyk], jazyk
        assert "{n}" in S["session.end.cues_silent"][jazyk], jazyk
        assert "{silent}" in S["session.end.cues_silent"][jazyk], jazyk
    assert "z toho" in S["session.end.cues_silent"]["sk"]
    assert "of those" in S["session.end.cues_silent"]["en"]
    # veta s tichymi ide LEN pri nenulovom pocte
    strom = ast.parse(_read("ui_dialogs.py"))
    init = next(f for t in ast.walk(strom) if isinstance(t, ast.ClassDef)
                and t.name == "SessionEndDialog" for f in t.body
                if isinstance(f, ast.FunctionDef) and f.name == "__init__")
    kod = ast.unparse(init)
    assert "elif cues and silent:" in kod
    assert kod.index("elif cues and silent:") < kod.index("tr('session.end.cues_silent'")
    assert "tr('session.end.cues', n=cues)" in kod


def test_uvod_povie_o_pripomienkach_len_obrazkom():
    """Kto zvolil hlas, nemá si myslieť, že hlas nefunguje - asi štvrtina
    pripomienok je zo začiatku zámerne len obrázkom (trigger.silent_share_for)."""
    import trigger
    assert trigger.silent_share_for(0) == 0.25
    assert "každú štvrtú" in S["ob.cue.note"]["sk"]
    assert "one cue in four" in S["ob.cue.note"]["en"]


# --------------------------------------------------------------------------
# Lista, styl v Nastaveniach, bodka
# --------------------------------------------------------------------------

class _Ikona:
    def __init__(self, name, image, title, menu):
        self.menu = menu
        self.aktualizacie = 0

    def run(self):
        pass

    def update_menu(self):
        self.aktualizacie += 1


class _Vlakno:
    def __init__(self, target=None, daemon=None, **_kw):
        self.target = target

    def start(self):
        pass


def test_polozka_listy_povie_co_sa_po_kliku_stane(monkeypatch):
    pystray = pytest.importorskip("pystray")
    import app as app_mod
    monkeypatch.setattr(app_mod, "pystray", types.SimpleNamespace(
        Menu=pystray.Menu, MenuItem=pystray.MenuItem, Icon=_Ikona), raising=False)
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.fronta = []
    a.ui_call = a.fronta.append
    a.make_tray_image = lambda: None
    a._apply_window_icon = lambda: None
    a._snooze_job = None
    a.listening = False
    app_mod.DandurfApp.setup_tray(a)
    texty = [p.text for p in a.tray_icon.menu.items]
    assert i18n.tr("tray.start") in texty and i18n.tr("tray.stop") not in texty
    a.listening = True
    texty = [p.text for p in a.tray_icon.menu.items]
    assert i18n.tr("tray.stop") in texty and i18n.tr("tray.start") not in texty
    # po zmene stavu sa menu prestavia - inak by pystray ukazoval stary text
    pred = a.tray_icon.aktualizacie
    app_mod.DandurfApp.update_tray_icon(a)
    assert a.tray_icon.aktualizacie == pred + 1


def test_styl_v_nastaveniach_ma_vlastne_mena():
    """V Nastaveniach nie je otázka „keď ťa hra vytočí…“ - riadok nesmie
    ukazovať odpovede na ňu."""
    import app as app_mod
    D = app_mod.DandurfApp
    mena = D._cue_style_labels(None)
    assert mena == [i18n.tr("cue_style.voice"), i18n.tr("cue_style.sound"),
                    i18n.tr("cue_style.visual")]
    for jazyk in JAZYKY:
        for styl in ("voice", "sound", "visual"):
            assert S[f"cue_style.{styl}"][jazyk] != S[f"ob.cue.{styl}"][jazyk], (jazyk, styl)


def test_tip_bodky_opisuje_to_co_bodka_kresli():
    """Zastavená appka = dutý krúžok (`text_faint`), sledujúca = plná zelená
    (`success`). Tip pri bodke to musí povedať - nie „červená“, ktorú už
    nekreslí, ani farbu ensō, ktoré má vždy farbu accent."""
    tip = S["sidebar.state_tip"]
    assert "zelená" in tip["sk"].lower() and "krúžok" in tip["sk"]
    assert "green" in tip["en"].lower() and "ring" in tip["en"].lower()
    for jazyk in JAZYKY:
        assert "▶" in tip[jazyk], jazyk
        assert "červen" not in tip[jazyk].lower() and "red" not in tip[jazyk].lower(), jazyk
    strom = ast.parse(_read("ui_shell.py"))
    kresli = next(ast.unparse(f) for t in ast.walk(strom) if isinstance(t, ast.ClassDef)
                  and t.name == "_StateDot" for f in t.body
                  if isinstance(f, ast.FunctionDef) and f.name == "_redraw")
    assert "text_faint" in kresli and "success" in kresli
    assert "'danger'" not in kresli and '"danger"' not in kresli


# --------------------------------------------------------------------------
# Texty bez zargonu a bez slubov, ktore kod nedrzi
# --------------------------------------------------------------------------

def test_hracske_texty_bez_zargonu():
    for jazyk in JAZYKY:
        assert "Edge" not in S["engine.edge"][jazyk], jazyk
        for kluc in ("log.sapi_ready", "log.edge_not_cached", "log.edge_not_cached_later",
                     "log.edge_cache_ready", "log.edge_gen_failed", "settings.engine_sub"):
            assert "SAPI" not in S[kluc][jazyk] and "TTS" not in S[kluc][jazyk], (kluc, jazyk)
        assert "TCP" not in S["settings.hr_status_udp_off"][jazyk], jazyk
        for kluc in ("metric.hrpi.title", "dnes.stat_hrpi", "history.col_hrpi",
                     "history.detail_hrpi", "metric.hrr.title", "dnes.stat_hrr", "history.col_hrr"):
            assert "HRPI" not in S[kluc][jazyk] and "HRR" not in S[kluc][jazyk], (kluc, jazyk)
    assert S["common.log"]["sk"] == "Denník"
    assert "pasívne" not in S["log.safe_mode"]["sk"]


def test_uvod_nesluby_co_kod_nerobi():
    for jazyk in JAZYKY:
        assert "killfeed" not in S["ob.step2.body"][jazyk].lower(), jazyk
    assert "roh" not in S["ob.step2.title"]["sk"].lower()
    assert "corner" not in S["ob.step2.title"]["en"].lower()
    assert "nepovinn" not in S["ob.step3.kicker"]["sk"]
    assert "optional" not in S["ob.step3.kicker"]["en"]
    # "neviem" sa ulozi ako hlas - neslubuje rezim, ktory by si appka zistovala
    assert "zistí sama" not in S["ob.cue.unsure"]["sk"]
    assert "figure it out" not in S["ob.cue.unsure"]["en"]


def test_relacia_nie_vecer():
    assert "večer" not in S["session.end.trace_hint"]["sk"]
    assert "evening" not in S["session.end.trace_hint"]["en"]
    assert "na reláciu" in S["insight.cue_dropouts"]["sk"]
    assert "per session" in S["insight.cue_dropouts"]["en"]


def test_obrazok_ma_jedno_meno_a_tlacidlo_sa_cituje_presne():
    assert S["overlay.dialog_title"]["sk"] == "Obrázky v hre"
    assert S["overlay.dialog_title"]["en"] == "In-game pictures"
    for jazyk in JAZYKY:
        tlacidlo = S["overlay.test"][jazyk].replace("▶", "").strip()
        for kluc in ("overlay.drag_hint", "overlay.dialog_hint", "ob.step2.body"):
            assert tlacidlo in S[kluc][jazyk], (kluc, jazyk)
        assert "🎮" not in S["settings.overlay_button"][jazyk], jazyk


def test_zvuky_maju_jedno_meno_a_sady_mena_tem():
    for jazyk in JAZYKY:
        assert S["pack.zen"][jazyk] == "Sumi" and S["pack.modern"][jazyk] == "Aizome"
        for kluc in [k for k in S if k.startswith(("sfx.zen.", "sfx.modern."))]:
            assert "(" not in S[kluc][jazyk] and "（" not in S[kluc][jazyk], (kluc, jazyk)


def test_sprievodca_bez_odvolavania_na_autority():
    for jazyk in JAZYKY:
        for kluc in ("guide.breath.tech1.name", "guide.breath.tech2.name"):
            text = S[kluc][jazyk]
            assert "Huberman" not in text and "ヒューバーマン" not in text, (kluc, jazyk)
            assert "SEAL" not in text and "シールズ" not in text and "海豹" not in text, (kluc, jazyk)
    assert "nezosýpaj" in S["guide.grounding.instruction"]["sk"]


def test_zmazane_mrtve_napovedy_z_uvodu_01():
    for n in range(1, 5):
        assert f"onboarding.diag.item{n}_hint" not in S
    import i18n_cs_bg
    for slovnik in (i18n_cs_bg.CS, i18n_cs_bg.BG):
        assert not [k for k in slovnik if k.endswith("_hint") and k.startswith("onboarding.diag")]


def test_nastavenia_zvuk_pouzivaju_nove_mena_stylu():
    kod = zdroj_metody("_cue_style_label")
    assert "CUE_STYLE_SETTINGS_LABELS" in kod
