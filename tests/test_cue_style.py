# -*- coding: utf-8 -*-
"""Cue style (0.2): a question in onboarding and a row in Settings.

The author's decisions that these tests guard:
  * the question „Keď ťa hra poriadne vytočí, ako chceš, aby sa appka ozvala?“
    (When a game really winds you up, how do you want the app to speak up?)
    with four equal answers, nothing preselected,
  * „Neviem, nech si to appka zistí sama“ (I don't know, let the app find
    out by itself) = voice (the ladder goes down after the first objection),
  * settings["cue_style"] is "voice" | "sound" | "visual", missing = voice,
  * delivery: voice = sound and words; sound = the slot's sound and the
    picture, no TTS; picture = picture only. Work is always picture only.
  * the row „Ako sa ozývam“ (How I speak up) in Settings: the app may go
    quieter by itself, never louder than this - not even in the session that
    is running right now.
"""
import ast
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import rebrik  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import strom_appky, zdroj_appky  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _funkcia(subor, meno, trieda=None):
    # "app.py" = the whole app: app.py and the DandurfApp mixins in app_*.py
    koren = strom_appky() if subor == "app.py" else ast.parse(_read(subor))
    if trieda:
        koren = next(u for u in ast.walk(koren)
                     if isinstance(u, ast.ClassDef) and u.name == trieda)
    for f in ast.walk(koren):
        if isinstance(f, ast.FunctionDef) and f.name == meno:
            return f
    raise AssertionError(meno)


# --------------------------------------------------------------------------
# Settings: normalisation and migration
# --------------------------------------------------------------------------

@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    # `load_settings` lives in the app_prefs mixin (PrefsMixin) and reads
    # SETTINGS_PATH from its own module - it has to be redirected there.
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def nacitaj(obsah=None):
        if obsah is not None:
            with open(cesta, "w", encoding="utf-8") as fh:
                json.dump(obsah, fh)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield nacitaj
    i18n.set_lang(povodny)


def test_prvy_start_je_hlas(nastavenia):
    assert nastavenia()["cue_style"] == rebrik.STYL_HLAS


def test_migracia_bez_kluca_je_hlas(nastavenia):
    """Older-version settings have no style - the player stays on voice."""
    d = nastavenia({"lang": "sk", "theme": "zen"})
    assert d["cue_style"] == "voice" and d["first_run"] is False


@pytest.mark.parametrize("ulozeny, cakany", [
    ("voice", "voice"), ("sound", "sound"), ("visual", "visual"),
    ("unsure", "voice"), ("nezmysel", "voice"), (None, "voice"), (3, "voice"),
    (["visual"], "voice"), ("VISUAL", "voice"),
])
def test_ulozeny_styl_sa_normalizuje(nastavenia, ulozeny, cakany):
    d = nastavenia({"lang": "sk", "theme": "zen", "cue_style": ulozeny})
    assert d["cue_style"] == cakany


def test_styly_idu_od_najhlasnejsieho():
    assert rebrik.STYLY == ("voice", "sound", "visual")
    assert rebrik.je_tichsi("sound", "voice") and rebrik.je_tichsi("visual", "sound")
    assert not rebrik.je_tichsi("voice", "visual")
    assert not rebrik.je_tichsi("sound", "sound")
    assert rebrik.je_tichsi("visual", None), "chybajuci styl = hlas"


# --------------------------------------------------------------------------
# Delivery by style (the real app.py methods on a dummy)
# --------------------------------------------------------------------------

class _Vlakno:
    """Synchronous `threading.Thread` - so we can check what was started."""

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


def _relacia_so_stylom(monkeypatch, styl, svet="play"):
    """Opens a session like `_open_hr_session` (rung + state-machine voice) and
    delivers one cue from the voice arm. Returns (rung, fired _emit calls,
    drawn pictograms, cue record)."""
    import app as app_mod
    import app_today
    D = app_mod.DandurfApp
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    # `_fire_somatic_cue` lives in the app_today mixin (TodayMixin) and reads
    # `threading` from its own module - the synchronous thread goes there too.
    monkeypatch.setattr(app_today, "threading", types.SimpleNamespace(Thread=_Vlakno))
    spustene, vykreslene = [], []
    slot = types.SimpleNamespace(index=1, text_value="Teeth")
    a = types.SimpleNamespace(
        cue_style=styl, _session_world=svet, _history_sessions=lambda: [],
        slots=[slot], hr_stats=hr_stats.HeartStats(),
        overlay_manager=types.SimpleNamespace(
            trigger=lambda i: vykreslene.append(i) or True),
        last_global_trigger_time=0.0, log=lambda *x: None,
        _refresh_hud_session_text=lambda: None, _refresh_dnes_stats=lambda: None,
        _dalsi_cue_slot=lambda: 1, _slot_zaznie=lambda s, bez_slov=False: True,
        _emit=lambda s, bez_slov=False: spustene.append(bez_slov))
    D._urci_stupen_hlasky(a)
    # the same condition as `open_session(voice=...)` in `_open_hr_session`
    hlas = svet != "work" and a._cue_rung == rebrik.HLAS
    ev = {"typ": trigger.E_DELIVER, "ts": 1200.0, "arm": "voice",
          "delivery": "pause", "hlas": hlas, "load": 61.0,
          "load_peak": 74.0, "zone_at": "high"}
    assert D._fire_somatic_cue(a, ev) is True
    return a._cue_rung, spustene, vykreslene, a.hr_stats.cues[-1]


def test_styl_hlas_prehra_zvuk_aj_slova(monkeypatch):
    stupen, spustene, obraz, cue = _relacia_so_stylom(monkeypatch, "voice")
    assert stupen == rebrik.HLAS
    assert spustene == [False], "_emit bez `bez_slov` = zvuk aj slova"
    assert obraz == [1] and cue["audible"] is True


def test_styl_zvuk_prehra_len_zvuk_slotu_a_obrazok(monkeypatch):
    stupen, spustene, obraz, cue = _relacia_so_stylom(monkeypatch, "sound")
    assert stupen == rebrik.HLAS, "zvuk je stupen hlasu so stlmenymi slovami"
    assert spustene == [True], "bez_slov: ziadne TTS ani nahravka"
    assert obraz == [1]


def test_styl_obrazok_len_ukaze(monkeypatch):
    stupen, spustene, obraz, cue = _relacia_so_stylom(monkeypatch, "visual")
    assert stupen == rebrik.OBRAZ
    assert spustene == [] and obraz == [1]
    assert (cue["rung"], cue["audible"]) == ("visual", False)


@pytest.mark.parametrize("styl", ["voice", "sound", "visual"])
def test_praca_je_len_obrazok_pri_kazdom_style(monkeypatch, styl):
    stupen, spustene, obraz, _cue = _relacia_so_stylom(monkeypatch, styl, svet="work")
    assert stupen == rebrik.OBRAZ and spustene == [] and obraz == [1]


def test_styl_je_vrchol_rebrika_nikdy_nie_hlasnejsie():
    """Picture as style: not even three clean cue sessions bring voice back."""
    ciste = [{"started": 1_789_000_000.0 + i * 3600.0, "duration_s": 1800.0,
              "auto_triggers": 1} for i in range(6)]
    assert rebrik.stupen(ciste, styl="visual")["stupen"] == rebrik.OBRAZ
    assert rebrik.stupen(ciste, styl="sound")["stupen"] == rebrik.HLAS
    # and after an objection even "neviem" (= voice) drops a rung right away
    vyhrada = [dict(ciste[0], cue_verdict="disruptive")]
    assert rebrik.stupen(vyhrada, styl="voice")["stupen"] == rebrik.OBRAZ


# --------------------------------------------------------------------------
# Style change: quieter applies at once, louder from the next session
# --------------------------------------------------------------------------

def _beziaca(styl, stupen=rebrik.HLAS, svet="play"):
    return types.SimpleNamespace(
        cue_style=styl, _cue_style_rel=styl, _cue_rung=stupen,
        _session_world=svet, cue_trigger=types.SimpleNamespace(voice=True))


def test_tichsi_styl_plati_hned_aj_v_beziacej_relacii():
    import app as app_mod
    D = app_mod.DandurfApp
    a = _beziaca("voice")
    D._nastav_styl_hlasky(a, "visual")
    assert (a.cue_style, a._cue_style_rel, a._cue_rung) == ("visual", "visual", "visual")
    assert a.cue_trigger.voice is False, "automat uz hlas neohlasi"

    a = _beziaca("voice")
    D._nastav_styl_hlasky(a, "sound")
    assert (a._cue_style_rel, a._cue_rung, a.cue_trigger.voice) == ("sound", "voice", True)


def test_hlasnejsi_styl_pocka_na_dalsiu_relaciu():
    import app as app_mod
    D = app_mod.DandurfApp
    a = _beziaca("visual", stupen=rebrik.OBRAZ)
    a.cue_trigger.voice = False
    D._nastav_styl_hlasky(a, "voice")
    assert a.cue_style == "voice", "ulozi sa a plati od dalsej relacie"
    assert (a._cue_style_rel, a._cue_rung, a.cue_trigger.voice) == ("visual", "visual", False)
    # when the next session opens, the new style is already used
    a._history_sessions = lambda: []
    D._urci_stupen_hlasky(a)
    assert (a._cue_style_rel, a._cue_rung) == ("voice", "voice")


def test_zmena_stylu_nezrusi_pauzu_ani_nepokazi_nezmysel():
    import app as app_mod
    D = app_mod.DandurfApp
    a = _beziaca("voice", stupen=rebrik.PAUZA)
    D._nastav_styl_hlasky(a, "visual")
    assert a._cue_rung == rebrik.PAUZA, "pauza je tichsia nez obrazok"
    a = _beziaca("sound")
    D._nastav_styl_hlasky(a, "nezmysel")
    assert a.cue_style == "voice" and a._cue_style_rel == "sound"


# --------------------------------------------------------------------------
# Onboarding: step 5 saves the choice
# --------------------------------------------------------------------------

def test_onboarding_ma_styri_schvalene_odpovede_bez_predvolby():
    import ui_dialogs
    W = ui_dialogs.OnboardingWizard
    assert [v for v, _k in W.CUE_VOLBY] == ["voice", "sound", "visual", "unsure"]
    sk = [i18n.STRINGS[k]["sk"] for _v, k in W.CUE_VOLBY]
    # 0.3: "Neviem" no longer promises a "let the app find out" mode, which
    # does not exist - it is saved as voice and the ladder quiets down by
    # itself (UX audit).
    assert sk == ["Pokojne aj hlasom", "Radšej len zvuk a obrázok",
                  "Len obrázok, nič nehovor",
                  "Neviem — začni hlasom a stíš sa, keď budeš prekážať"]
    assert i18n.STRINGS["ob.cue.title"]["sk"] == (
        "Keď ťa hra poriadne vytočí, ako chceš, aby sa appka ozvala?")
    assert i18n.STRINGS["ob.cue.title"]["en"] == (
        "When a game really winds you up, how do you want the app to speak up?")
    # nothing is preselected and all four buttons are the same size
    init = ast.unparse(_funkcia("ui_dialogs.py", "__init__", "OnboardingWizard"))
    assert "self.cue_style = None" in init and "self._cue_volba = None" in init
    krok = _funkcia("ui_dialogs.py", "_step5", "OnboardingWizard")
    tlacidla = [u for u in ast.walk(krok) if isinstance(u, ast.Call)
                and ast.unparse(u.func) == "ctk.CTkButton"]
    assert len(tlacidla) == 1, "jedno tlacidlo v cykle cez vsetky styri odpovede"
    kw = {k.arg: ast.unparse(k.value) for k in tlacidla[0].keywords}
    assert kw["width"] == "460" and kw["height"] == "46"
    assert "for volba, kluc in self.CUE_VOLBY" in ast.unparse(krok)
    # no default and no "recommended" (the body without the docstring)
    telo = ast.unparse(ast.Module(body=krok.body[1:], type_ignores=[]))
    for zakazane in ("odporu", "recommend", "self._cue_volba =", "self.cue_style ="):
        assert zakazane not in telo, zakazane
    assert telo.count("_vyber_styl(") == telo.count("lambda v=volba: self._vyber_styl(v)") == 1, \
        "vyber len na klik, nie pri stavbe kroku"


@pytest.mark.parametrize("volba, ulozene", [
    ("voice", "voice"), ("sound", "sound"), ("visual", "visual"), ("unsure", "voice"),
])
def test_onboarding_ulozi_volbu(volba, ulozene):
    import ui_dialogs
    W = ui_dialogs.OnboardingWizard
    wz = types.SimpleNamespace(NEVIEM=W.NEVIEM, cue_style=None, _cue_volba=None,
                               _oznac_styl=lambda: None)
    W._vyber_styl(wz, volba)
    assert (wz.cue_style, wz._cue_volba) == (ulozene, volba)


def test_app_prevezme_styl_z_onboardingu():
    import app as app_mod
    D = app_mod.DandurfApp
    a = _beziaca("sound")
    a._nastav_styl_hlasky = lambda s: D._nastav_styl_hlasky(a, s)
    D._prevezmi_styl_z_onboardingu(a, types.SimpleNamespace(cue_style=None))
    assert a.cue_style == "sound", "bez odpovede ostava, co bolo"
    D._prevezmi_styl_z_onboardingu(a, types.SimpleNamespace(cue_style="visual"))
    assert a.cue_style == "visual"
    # first start and repeated onboarding; with the repeated one before saving
    src = zdroj_appky()
    assert src.count("self._prevezmi_styl_z_onboardingu(wizard)") == 2
    znova = ast.unparse(_funkcia("app.py", "replay_onboarding"))
    assert znova.index("self._prevezmi_styl_z_onboardingu(wizard)") < znova.index(
        "self.save_settings()")


def test_preskocit_uvod_neprekoci_otazku():
    """"Preskočiť" (Skip) on steps 1-2 goes to the watch step (0.3) - not to
    the world choice, which skipped it. The world and the question (step 5)
    come after it."""
    import ui_dialogs
    W = ui_dialogs.OnboardingWizard
    assert W.STEP_COUNT == 5 and W.KROK_HODINKY == 2
    ud = _read("ui_dialogs.py")
    assert "command=lambda: self._show_step(self.KROK_HODINKY))" in ud
    krok = ast.unparse(_funkcia("ui_dialogs.py", "_show_step", "OnboardingWizard"))
    assert "self._step5)[index]" in krok
    assert "index >= self.KROK_HODINKY" in krok


# --------------------------------------------------------------------------
# Settings -> Sound: the "Ako sa ozyvam" (How I speak up) row
# --------------------------------------------------------------------------

def test_riadok_v_nastaveniach_meni_styl_a_uklada():
    import app as app_mod
    D = app_mod.DandurfApp
    ulozene = []
    pripravy = []
    a = _beziaca("voice")
    a._nastav_styl_hlasky = lambda s: D._nastav_styl_hlasky(a, s)
    a.save_settings = lambda: ulozene.append(a.cue_style)
    # the style decides whether Edge cues get prepared (`_hlasky_hovoria`)
    a.schedule_pregenerate = lambda *_: pripravy.append(a.cue_style)
    # 0.3: the row has its own style names (cue_style.*), not the answers from
    # the introduction
    assert D._cue_style_label("sound") == i18n.tr("cue_style.sound")
    assert D._cue_style_label(None) == i18n.tr("cue_style.voice")
    assert D._cue_style_labels(a) == [i18n.tr("cue_style.voice"), i18n.tr("cue_style.sound"),
                                      i18n.tr("cue_style.visual")]
    D._on_cue_style_label(a, i18n.tr("ob.cue.visual"))
    assert ulozene == [], "odpoved z uvodu uz nie je meno stylu v Nastaveniach"
    D._on_cue_style_label(a, i18n.tr("cue_style.visual"))
    assert ulozene == ["visual"] and a._cue_rung == rebrik.OBRAZ
    assert pripravy == ["visual"], "po zmene stylu sa priprava hlasok prepocita"
    D._on_cue_style_label(a, "nieco ine")
    assert ulozene == ["visual"], "neznamy popisok nic nezmeni"
    stranka = ast.unparse(_funkcia("app.py", "_build_zvuk_page"))
    assert "tr('settings.cue_style')" in stranka
    assert "tr('settings.cue_style_sub')" in stranka
    assert "command=self._on_cue_style_label" in stranka
    # 0.3 batch 4: no longer its own panel above the voice, but the FIRST row
    # of the Volume panel (UX audit: a card for one sentence)
    hlasitost = stranka.index("settings.audio_volume_title")
    assert hlasitost < stranka.index("settings.cue_style") < stranka.index("settings.volume'")


def test_texty_su_vo_vsetkych_jazykoch_a_hovoria_pravdu():
    for kluc in ("ob.step5.kicker", "ob.cue.title", "ob.cue.voice", "ob.cue.sound",
                 "ob.cue.visual", "ob.cue.unsure", "ob.cue.note",
                 "settings.cue_style", "settings.cue_style_sub",
                 "cue_style.voice", "cue_style.sound", "cue_style.visual"):
        assert set(i18n.STRINGS[kluc]) == set(i18n.LANGUAGES), kluc
    sub = i18n.STRINGS["settings.cue_style_sub"]
    # the app speaks of itself in the feminine; quieter by itself, louder
    # never; work is picture (0.3: one word "obrazok" (picture) for what shows
    # in game)
    assert "stíšim sa aj sama" in sub["sk"] and "nikdy" in sub["sk"]
    assert "V práci" in sub["sk"] and "obrázkom" in sub["sk"]
    assert "never louder" in sub["en"] and "At work" in sub["en"]
    assert "never louder" in i18n.STRINGS["ob.cue.note"]["en"]
    assert i18n.STRINGS["settings.cue_style"]["sk"] == "Ako sa ozývam"


def test_onboarding_povie_co_posiela_prirodzeny_hlas():
    """Under the cue-style question there is a quiet line about the online
    voice: the cue texts (never the heart rate) go to Microsoft, the Windows
    voice sends nothing - and where to switch it (the Settings tab as it is
    really called in the given language)."""
    zaznam = i18n.STRINGS["ob.cue.online_note"]
    assert set(zaznam) == set(i18n.LANGUAGES)
    for jazyk in i18n.LANGUAGES:
        text = zaznam[jazyk]
        assert "Microsoft" in text, jazyk
        assert i18n.tr_lang(jazyk, "nav.nastavenia_tabs.zvuk") in text, jazyk
        if jazyk != "en":
            assert text != zaznam["en"], ("nepreložené", jazyk)
    assert "(nikdy nie tep)" in zaznam["sk"] and "Hlas z Windows neposiela nič" in zaznam["sk"]
    assert "(never your heart rate)" in zaznam["en"]
    assert "The Windows voice sends nothing" in zaznam["en"]
    # not „…, um ihn … umzuwandeln“ - the subject would be the text itself
    assert "und wird dort in Sprache umgewandelt" in zaznam["de"]
    krok = ast.unparse(_funkcia("ui_dialogs.py", "_step5", "OnboardingWizard"))
    assert "tr('ob.cue.online_note')" in krok
    # quiet style like the row above it, and placed only below the answers
    assert krok.index("tr('ob.cue.note')") < krok.index("tr('ob.cue.online_note')")
    riadok = krok[krok.index("tr('ob.cue.online_note')"):]
    assert "ui_kit.ui(11)" in riadok and "pal['text_faint']" in riadok
