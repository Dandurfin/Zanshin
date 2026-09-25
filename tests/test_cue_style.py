# -*- coding: utf-8 -*-
"""Štýl hlášky (0.2): otázka v onboardingu a riadok v Nastaveniach.

Rozhodnutia zadávateľa, ktoré tieto testy strážia:
  * otázka „Keď ťa hra poriadne vytočí, ako chceš, aby sa appka ozvala?“
    so štyrmi rovnocennými odpoveďami, nič predvybrané,
  * „Neviem, nech si to appka zistí sama“ = hlas (rebrík ide dole po prvej
    výhrade),
  * settings["cue_style"] je "voice" | "sound" | "visual", chýbajúci = hlas,
  * doručenie: hlas = zvuk aj slová; zvuk = zvuk slotu a obrázok, žiadne
    TTS; obrázok = len obrázok. Práca je len obrázok vždy.
  * riadok „Ako sa ozývam“ v Nastaveniach: appka môže ísť sama tichšie,
    hlasnejšie než toto nikdy - ani v práve bežiacej relácii.
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

KOREN =os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _funkcia(subor, meno, trieda=None):
    # "app.py" = cela appka: app.py aj mixiny DandurfApp v app_*.py
    koren = strom_appky() if subor == "app.py" else ast.parse(_read(subor))
    if trieda:
        koren = next(u for u in ast.walk(koren)
                     if isinstance(u, ast.ClassDef) and u.name == trieda)
    for f in ast.walk(koren):
        if isinstance(f, ast.FunctionDef) and f.name == meno:
            return f
    raise AssertionError(meno)


# --------------------------------------------------------------------------
# Nastavenia: normalizacia a migracia
# --------------------------------------------------------------------------

@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_mod, "SETTINGS_PATH", cesta)
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
    """Nastavenia zo starsej verzie styl nemaju - hrac ostava na hlase."""
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
# Dorucenie podla stylu (skutocne metody app.py na atrape)
# --------------------------------------------------------------------------

class _Vlakno:
    """Synchronne `threading.Thread` - aby sa dalo overit, co sa spustilo."""

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


def _relacia_so_stylom(monkeypatch, styl, svet="play"):
    """Otvori relaciu ako `_open_hr_session` (stupen + hlas automatu) a
    doruci jednu hlasku z hlasneho ramena. Vrati (stupen, spustene _emit,
    vykreslene piktogramy, zaznam hlasky)."""
    import app as app_mod
    D = app_mod.DandurfApp
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
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
    # rovnaka podmienka ako `open_session(voice=...)` v `_open_hr_session`
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
    """Obrazok ako styl: ani tri ciste relacie s hlaskou nevratia hlas."""
    ciste = [{"started": 1_789_000_000.0 + i * 3600.0, "duration_s": 1800.0,
              "auto_triggers": 1} for i in range(6)]
    assert rebrik.stupen(ciste, styl="visual")["stupen"] == rebrik.OBRAZ
    assert rebrik.stupen(ciste, styl="sound")["stupen"] == rebrik.HLAS
    # a po vyhrade ide aj "neviem" (= hlas) hned o stupen nizsie
    vyhrada = [dict(ciste[0], cue_verdict="disruptive")]
    assert rebrik.stupen(vyhrada, styl="voice")["stupen"] == rebrik.OBRAZ


# --------------------------------------------------------------------------
# Zmena stylu: tichsi plati hned, hlasnejsi od dalsej relacie
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
    # pri otvoreni dalsej relacie sa uz rata s novym stylom
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
# Onboarding: krok 5 ulozi volbu
# --------------------------------------------------------------------------

def test_onboarding_ma_styri_schvalene_odpovede_bez_predvolby():
    import ui_dialogs
    W = ui_dialogs.OnboardingWizard
    assert [v for v, _k in W.CUE_VOLBY] == ["voice", "sound", "visual", "unsure"]
    sk = [i18n.STRINGS[k]["sk"] for _v, k in W.CUE_VOLBY]
    assert sk == ["Pokojne aj hlasom", "Radšej len zvuk a obrázok",
                  "Len obrázok, nič nehovor", "Neviem, nech si to appka zistí sama"]
    assert i18n.STRINGS["ob.cue.title"]["sk"] == (
        "Keď ťa hra poriadne vytočí, ako chceš, aby sa appka ozvala?")
    assert i18n.STRINGS["ob.cue.title"]["en"] == (
        "When a game really winds you up, how do you want the app to speak up?")
    # nic nie je predvybrane a vsetky styri tlacidla su rovnako velke
    init = ast.unparse(_funkcia("ui_dialogs.py", "__init__", "OnboardingWizard"))
    assert "self.cue_style = None" in init and "self._cue_volba = None" in init
    krok = _funkcia("ui_dialogs.py", "_step5", "OnboardingWizard")
    tlacidla = [u for u in ast.walk(krok) if isinstance(u, ast.Call)
                and ast.unparse(u.func) == "ctk.CTkButton"]
    assert len(tlacidla) == 1, "jedno tlacidlo v cykle cez vsetky styri odpovede"
    kw = {k.arg: ast.unparse(k.value) for k in tlacidla[0].keywords}
    assert kw["width"] == "460" and kw["height"] == "46"
    assert "for volba, kluc in self.CUE_VOLBY" in ast.unparse(krok)
    # ziadna predvolba ani "odporucane" (telo bez docstringu)
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
    # prvy start aj opakovany onboarding; pri opakovanom pred ulozenim
    src = zdroj_appky()
    assert src.count("self._prevezmi_styl_z_onboardingu(wizard)") == 2
    znova = ast.unparse(_funkcia("app.py", "replay_onboarding"))
    assert znova.index("self._prevezmi_styl_z_onboardingu(wizard)") < znova.index(
        "self.save_settings()")


def test_preskocit_uvod_neprekoci_otazku():
    """"Preskočiť úvod" ide na prvú voľbu (svet), krok 5 príde po nej."""
    import ui_dialogs
    W = ui_dialogs.OnboardingWizard
    assert W.STEP_COUNT == 5 and W.PRVA_VOLBA == 3
    ud = _read("ui_dialogs.py")
    assert "command=lambda: self._show_step(self.PRVA_VOLBA))" in ud
    krok = ast.unparse(_funkcia("ui_dialogs.py", "_show_step", "OnboardingWizard"))
    assert "self._step5)[index]" in krok
    assert "index >= self.PRVA_VOLBA" in krok


# --------------------------------------------------------------------------
# Nastavenia -> Zvuk: riadok "Ako sa ozyvam"
# --------------------------------------------------------------------------

def test_riadok_v_nastaveniach_meni_styl_a_uklada():
    import app as app_mod
    D = app_mod.DandurfApp
    ulozene = []
    pripravy = []
    a = _beziaca("voice")
    a._nastav_styl_hlasky = lambda s: D._nastav_styl_hlasky(a, s)
    a.save_settings = lambda: ulozene.append(a.cue_style)
    # styl rozhoduje, ci sa Edge hlasky pripravuju (`_hlasky_hovoria`)
    a.schedule_pregenerate = lambda *_: pripravy.append(a.cue_style)
    assert D._cue_style_label("sound") == i18n.tr("ob.cue.sound")
    assert D._cue_style_label(None) == i18n.tr("ob.cue.voice")
    assert D._cue_style_labels(a) == [i18n.tr("ob.cue.voice"), i18n.tr("ob.cue.sound"),
                                      i18n.tr("ob.cue.visual")]
    D._on_cue_style_label(a, i18n.tr("ob.cue.visual"))
    assert ulozene == ["visual"] and a._cue_rung == rebrik.OBRAZ
    assert pripravy == ["visual"], "po zmene stylu sa priprava hlasok prepocita"
    D._on_cue_style_label(a, "nieco ine")
    assert ulozene == ["visual"], "neznamy popisok nic nezmeni"
    stranka = ast.unparse(_funkcia("app.py", "_build_zvuk_page"))
    assert "tr('settings.cue_style')" in stranka
    assert "tr('settings.cue_style_sub')" in stranka
    assert "command=self._on_cue_style_label" in stranka
    assert stranka.index("settings.cue_style") < stranka.index("settings.audio_voice_title")


def test_texty_su_vo_vsetkych_jazykoch_a_hovoria_pravdu():
    for kluc in ("ob.step5.kicker", "ob.cue.title", "ob.cue.voice", "ob.cue.sound",
                 "ob.cue.visual", "ob.cue.unsure", "ob.cue.note",
                 "settings.cue_style", "settings.cue_style_sub"):
        assert set(i18n.STRINGS[kluc]) == set(i18n.LANGUAGES), kluc
    sub = i18n.STRINGS["settings.cue_style_sub"]
    # appka o sebe v zenskom rode; tichsie sama, hlasnejsie nikdy; praca obraz
    assert "stíšim sa aj sama" in sub["sk"] and "nikdy" in sub["sk"]
    assert "V práci" in sub["sk"] and "obrazom" in sub["sk"]
    assert "never louder" in sub["en"] and "At work" in sub["en"]
    assert "never louder" in i18n.STRINGS["ob.cue.note"]["en"]
    assert i18n.STRINGS["settings.cue_style"]["sk"] == "Ako sa ozývam"


def test_onboarding_povie_co_posiela_prirodzeny_hlas():
    """Pod otázkou na štýl hlášky stojí tichý riadok o online hlase: texty
    hlášok (nikdy tep) idú do Microsoftu, hlas z Windows neposiela nič - a
    kde sa prepína (karta Nastavení tak, ako sa v danom jazyku naozaj volá)."""
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
    # nie „…, um ihn … umzuwandeln“ - podmetom by bol text sám
    assert "und wird dort in Sprache umgewandelt" in zaznam["de"]
    krok = ast.unparse(_funkcia("ui_dialogs.py", "_step5", "OnboardingWizard"))
    assert "tr('ob.cue.online_note')" in krok
    # tichý štýl ako riadok nad ním, a až pod odpoveďami
    assert krok.index("tr('ob.cue.note')") < krok.index("tr('ob.cue.online_note')")
    riadok = krok[krok.index("tr('ob.cue.online_note')"):]
    assert "ui_kit.ui(11)" in riadok and "pal['text_faint']" in riadok
