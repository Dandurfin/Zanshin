# -*- coding: utf-8 -*-
"""0.3 (UX audit, batch 4): texts of existing keys in all 11 languages.

What this test guards:
  * one word for what the app sends (zh 提示, ja 合図, ru подсказка,
    de Hinweis, pt aviso, fr rappel) and for the in-game picture (sk/cs
    "obrázkom"),
  * hranica / limit = heart rate in BPM only, prah / threshold = load
    only - also in Japanese, Chinese, Russian and French,
  * addressing the player without gender (ru "ты включил", bg "Добре
    дошъл", es "Bienvenido", pt "Bem-vindo"),
  * pairing step 2 does not send an iPhone owner past step 3 (address and
    port),
  * the texts of metrics and insights speak in the first person like the
    others,
  * the introduction says what the player needs for the first heart rate
    (`ob.step1.need`),
  * the CSV export columns are grammatical (sk "verdikt pripomienky"),
  * the session counter names the four cues the same way as the game,
  * the journal talks about receiving the heart rate and about the phone,
    not about "monitorovani" and watches.

Synthetic data: none - the test reads only the dictionary and the sources.
"""
import ast
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = i18n.STRINGS
JAZYKY = i18n.LANGUAGES


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _vsetky(jazyk):
    return [(k, e[jazyk]) for k, e in S.items()]


# --------------------------------------------------------------------------
# One word for the cue and for the picture
# --------------------------------------------------------------------------

def test_obrazok_sa_vola_obrazok_aj_v_cestine_a_japoncine():
    for kluc in ("world.tip", "settings.world_sub", "history.world_note",
                 "ob.world.work.desc", "session.end.cues_work", "session.end.cues_visual",
                 "history.rebrik.visual", "history.rebrik.pause", "data.import.flagged"):
        assert re.search(r"[Oo]brázkom", S[kluc]["sk"]), kluc
        assert re.search(r"[Oo]brázkem", S[kluc]["cs"]), kluc
    assert not [k for k, v in _vsetky("sk") if re.search(r"\b[Oo]brazom\b", v)]
    assert not [k for k, v in _vsetky("cs") if re.search(r"\b[Oo]brazem\b", v)]
    assert not [k for k, v in _vsetky("ja") if "ビジュアル" in v]


def test_pripomienka_ma_v_kazdom_jazyku_jedno_slovo():
    # zh: 提醒 stays only as a verb ("我提醒了你"), the noun is 提示
    for kluc in ("dev.param.min_gap_s", "history.effect_empty", "session.context.why",
                 "palette.slot", "slots.unnamed", "dev.silent"):
        assert "提示" in S[kluc]["zh"], kluc
    for zle in ("提醒间隔", "提醒响起", "提醒没用", "提醒之间"):
        assert not [k for k, v in _vsetky("zh") if zle in v], zle
    # Chinese dash "——" without spaces as in all zh texts (0.3 batch 4b)
    assert S["palette.slot"]["zh"] == "提示——{label}"
    assert not [k for k, v in _vsetky("de") if "Erinnerung" in v]
    assert not [k for k, v in _vsetky("ru") if re.search(r"[Рр]еплик", v)]
    assert not [k for k, v in _vsetky("ja") if "セリフ" in v or "リマインダー" in v]
    assert not [k for k, v in _vsetky("pt") if re.search(r"[Ll]embrete", v)]
    assert not [k for k, v in _vsetky("es") if re.search(r"[Rr]ecordatorio", v)]
    for kluc, slovo in (("palette.slot", "合図"), ("slots.unnamed", "合図")):
        assert slovo in S[kluc]["ja"], kluc
    assert S["slots.unnamed"]["ru"] == "Подсказка {n}"
    assert "rappel" in S["guide.panel_subtitle"]["fr"]
    assert "signal" not in S["guide.panel_subtitle"]["fr"]


def test_francuzstina_ma_pre_relaciu_jedno_slovo():
    for kluc in ("session.context.save_failed", "session.context.setup_hint",
                 "session.context.setup_hint_first", "session.summary"):
        assert "séance" in S[kluc]["fr"].lower(), kluc
        assert not re.search(r"\bsession", S[kluc]["fr"], re.I), kluc


# --------------------------------------------------------------------------
# Limit = heart rate (BPM), threshold = load - in other languages too
# --------------------------------------------------------------------------

HRANICA = {"ja": "上限", "zh": "上限", "ru": "границ", "fr": "limite"}
PRAH = {"ja": "しきい値", "zh": "阈值", "ru": "порог", "fr": "seuil"}


def test_hranica_tepu_nie_je_prah_ani_v_dalsich_jazykoch():
    for kluc in ("metric.over.more", "metric.zones.more", "insight.over_up",
                 "history.export_col.over_min"):
        for jazyk, slovo in HRANICA.items():
            text = S[kluc][jazyk]
            assert slovo in text, (kluc, jazyk)
            assert PRAH[jazyk] not in text, (kluc, jazyk)
    # texts that name both name each with its own word
    for kluc in ("data.import.flagged", "settings.world_sub"):
        for jazyk in HRANICA:
            assert HRANICA[jazyk] in S[kluc][jazyk], (kluc, jazyk)
            assert PRAH[jazyk] in S[kluc][jazyk], (kluc, jazyk)


def test_stlpce_o_zatazi_nad_prahom_hovoria_o_prahu():
    """`above_runs` and `longest_above_s` are about load above the cue
    threshold (`trigger`), not about heart rate above the limit."""
    for kluc in ("history.export_col.above_runs", "history.export_col.longest_above_s"):
        assert "prahom" in S[kluc]["sk"] and "hranic" not in S[kluc]["sk"], kluc
        assert "prahem" in S[kluc]["cs"] and "hranic" not in S[kluc]["cs"], kluc
        assert "прага" in S[kluc]["bg"] and "границ" not in S[kluc]["bg"], kluc


# --------------------------------------------------------------------------
# Addressing without gender
# --------------------------------------------------------------------------

def test_oslovenie_hraca_bez_rodu():
    # ru: "ты ...л" (masculine past tense) when addressing the player
    assert not [k for k, v in _vsetky("ru")
                if re.search(r"\b[Тт]ы\s+(?:уже\s+)?[а-яё]+л(?:ся)?\b", v)]
    # bg: "си ...л" / "...л си" (masculine) and the masculine "Добре дошъл"
    assert not [k for k, v in _vsetky("bg")
                if re.search(r"\bси\s+[а-я]+л\b|\b[а-я]+л\s+си\b|дошъл", v)]
    assert "Bienvenido" not in S["onboarding.welcome"]["es"]
    assert "Bem-vindo" not in S["onboarding.welcome"]["pt"]
    for jazyk in JAZYKY:
        assert "{app}" in S["onboarding.welcome"][jazyk], jazyk
    # chips in the questionnaire: nouns, not adjectives about the player
    assert S["session.context.chill"]["es"] != "relajado"
    assert S["session.context.chill"]["pt"] != "tranquilo"
    # es "agitarse" means getting worked up, not exercise before playing
    assert "agit" not in S["session.context.exercise_before"]["es"]
    # Guide: "tazko byt uvolneny" (hard to be relaxed) was masculine - the
    # sentence is now about the body
    filozofia = S["guide.philosophy.block3_text"]
    assert "uvoľnené" in filozofia["sk"] and "uvoľnený a" not in filozofia["sk"]
    assert "uvolněné" in filozofia["cs"] and "uvolněný a" not in filozofia["cs"]
    assert "да си наистина отпуснат" not in filozofia["bg"]
    for jazyk, zle in (("es", "estar de verdad relajado"), ("pt", "estar realmente relaxado"),
                       ("fr", "d’être vraiment détendu"), ("ru", "быть по-настоящему")):
        assert zle not in filozofia[jazyk], jazyk


# --------------------------------------------------------------------------
# Pairing step 2: an iPhone does not skip the address and port
# --------------------------------------------------------------------------

def test_krok_2_neposle_iphone_okolo_adresy_a_portu():
    for jazyk in JAZYKY:
        text = S["hr.step2_body"][jazyk]
        assert "3–4" not in text and "3-4" not in text, jazyk
        assert "3" in text and "4" in text, jazyk
        assert "PulseOSC" in text and "HeartRateOnStream" in text, jazyk
    sk, en = S["hr.step2_body"]["sk"], S["hr.step2_body"]["en"]
    assert "Adresu a port (krok 3) zadáš v oboch appkách" in sk
    assert "krok 4 preskoč" in sk
    assert "Both apps need the address and port (step 3)" in en
    assert "skip step 4" in en
    # the steps the sentence refers to really are these
    assert "adresu a port" in S["hr.step3_body"]["sk"]
    assert "scénu" in S["hr.step4_body"]["sk"]


# --------------------------------------------------------------------------
# First person in metrics and insights
# --------------------------------------------------------------------------

APPKA = {"sk": "appka", "cs": "appka", "en": "the app", "ja": "アプリ", "zh": "应用",
         "ru": "приложени", "es": "la app", "de": "die App", "fr": "l’app", "pt": "o app",
         "bg": "приложението"}


def test_metriky_a_postrehy_hovoria_v_prvej_osobe():
    for jazyk, slovo in APPKA.items():
        assert slovo not in S["metric.load.more"][jazyk].lower(), jazyk
    assert "mlčím" in S["metric.load.more"]["sk"]
    assert "I stay quiet" in S["metric.load.more"]["en"]
    assert "som si" in S["insight.steady"]["sk"]
    assert S["insight.steady"]["en"].startswith("I haven")
    for kluc in ("insight.triggers_early", "insight.triggers_late"):
        assert "the app" not in S[kluc]["en"], kluc
        assert "my cues" in S[kluc]["en"], kluc


# --------------------------------------------------------------------------
# Introduction: what the player needs
# --------------------------------------------------------------------------

def test_uvod_povie_co_hrac_na_prvy_tep_potrebuje():
    zaznam = S["ob.step1.need"]
    assert set(zaznam) == set(JAZYKY)
    for jazyk in JAZYKY:
        text = zaznam[jazyk]
        assert text.strip() and "{" not in text, jazyk
        assert "Wi‑Fi" in text or "WLAN" in text, jazyk
        if jazyk != "en":
            assert text != zaznam["en"], jazyk
    # 0.3 batch 4b: a watch with an app on the phone, like the README ("Getting
    # your heart rate in"); nobody has verified a chest strap, so the
    # introduction does not promise it
    assert "hodinky" in zaznam["sk"] and "telefóne" in zaznam["sk"]
    assert "domácej sieti" in zaznam["sk"]
    assert "smartwatch" in zaznam["en"] and "phone app" in zaznam["en"]
    assert "same home network" in zaznam["en"]
    for jazyk, slovo in (("sk", "hrudn"), ("cs", "hrudn"), ("en", "chest"),
                         ("de", "Brustgurt"), ("fr", "ceinture"), ("es", "banda"),
                         ("pt", "cinta"), ("ru", "нагрудн"), ("bg", "гръден"),
                         ("ja", "胸"), ("zh", "胸")):
        assert slovo not in zaznam[jazyk], jazyk


def test_krok_1_uvodu_ukaze_co_treba_pod_uvodom():
    strom = ast.parse(_read("ui_dialogs.py"))
    krok1 = next(f for t in ast.walk(strom) if isinstance(t, ast.ClassDef)
                 and t.name == "OnboardingWizard" for f in t.body
                 if isinstance(f, ast.FunctionDef) and f.name == "_step1")
    kod = ast.unparse(krok1)
    assert "tr('ob.step1.need')" in kod
    assert kod.index("tr('ob.step1.body')") < kod.index("tr('ob.step1.need')")


# --------------------------------------------------------------------------
# Export, session counter, journal
# --------------------------------------------------------------------------

def test_stlpce_exportu_su_gramaticky():
    verdikt = S["history.export_col.cue_verdict"]
    assert verdikt["sk"] == "verdikt pripomienky"
    assert verdikt["cs"] == "verdikt připomínky"
    assert verdikt["es"] == "veredicto del aviso"
    assert verdikt["pt"] == "veredito do aviso"
    assert verdikt["fr"] == "verdict du rappel"
    assert S["history.export_col.confounded"]["es"].startswith("¿")
    for jazyk in JAZYKY:
        assert "." not in S["history.export_col.felt_load"][jazyk], jazyk


def test_pocitadlo_relacie_menuje_pripomienky_ako_hra():
    for jazyk in JAZYKY:
        text = S["session.summary"][jazyk]
        for index in range(4):
            assert S[f"overlay.slot.{index}"][jazyk] in text, (jazyk, index)
        for meno in ("{g}", "{j}", "{r}", "{b}"):
            assert meno in text, (jazyk, meno)
    assert "Uvoľnenie" not in S["session.summary"]["sk"]
    assert "Release" not in S["session.summary"]["en"]


def test_dennik_hovori_o_prijme_tepu_a_telefone():
    assert S["log.hr_disabled"]["sk"].startswith("Príjem tepu")
    assert "receiving" in S["log.hr_disabled"]["en"]
    assert S["log.hr_socket_error"]["sk"].startswith("Príjem tepu")
    assert not [k for k, v in _vsetky("sk") if re.search(r"[Mm]onitorovan", v)]
    assert not [k for k, v in _vsetky("en") if re.search(r"[Mm]onitoring", v)]
    # the client that disconnects is the app on the phone - same as the one
    # that connected
    for jazyk in ("sk", "en", "cs"):
        assert ("Telef" in S["log.hr_client_gone"][jazyk]
                or "phone" in S["log.hr_client_gone"][jazyk]), jazyk
        assert ("Telef" in S["log.hr_client_connected"][jazyk]
                or "phone" in S["log.hr_client_connected"][jazyk]), jazyk


def test_cestina_bez_preklepov_z_davky_4():
    assert "Když sleduju" in S["tour.dock.body"]["cs"]
    assert "co se v ty večery změnilo" in S["metric.over.more"]["cs"]
    assert "v liště" in S["tray.already_running"]["cs"]


def test_build_skript_posiela_vyvojara_do_development():
    skript = _read("build_all.ps1")
    assert "knows from DEVELOPMENT.md" in skript
    assert "knows from README" not in skript
    assert "Inno Setup" in _read("DEVELOPMENT.md")
