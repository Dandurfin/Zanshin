# -*- coding: utf-8 -*-
"""Rebrík hlášky (0.2): appka sa sama stíši, keď hláška prekáža.

    hlas -> obraz -> pauza

Rozhodnutia zadávateľa, ktoré tieto testy strážia:
  * žiadny stupeň „zvuk“ ani meraný strop - styl „sound“ je stupeň hlasu so
    stlmenými slovami, nie samostatný stupeň,
  * vrchol dáva svet (práca = len obraz, B3-worlds) a štýl hráča
    (`cue_style`); rebrík ide len POD vrchol,
  * dole o stupeň za reláciu: verdikt „rušila“ / „rozhodila ma“ pri relácii
    s hláškou, alebo „teraz nie“ do 60 s po hláške - ten len keď relácia
    potom ešte bežala aspoň 120 s a verdikt nie je „sadla“,
  * hore po 3 reláciách s hláškou bez signálu, pauza 3 relácie >= 300 s
    alebo do verdiktu „áno, mala“, potom obraz.
"""
import ast
import os
import random
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_insights  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
import measure  # noqa: E402
import rebrik  # noqa: E402
import trigger  # noqa: E402
from settings_model import MODE_COMBO, MODE_SFX, MODE_TTS  # noqa: E402
from _zdroj_appky import strom_appky  # noqa: E402

KOREN =os.path.join(os.path.dirname(__file__), "..")


def rel(i, **kw):
    """Relácia `i` (poradie podľa `started`): 30 min, jedna hláška."""
    s = {"started": 1_789_000_000.0 + i * 3600.0, "duration_s": 1800.0,
         "auto_triggers": 1}
    s.update(kw)
    return s


def stav(relacie, svet="play", styl=None):
    return rebrik.stupen(relacie, svet=svet, styl=styl)


# --------------------------------------------------------------------------
# Rebrík - čistá funkcia
# --------------------------------------------------------------------------

def test_nova_historia_je_na_vrchole():
    s = stav([])
    assert s["stupen"] == rebrik.HLAS == s["vrchol"]
    assert s["dovod"] is None and s["zostava"] == 0
    assert rebrik.STUPNE == ("voice", "visual", "pause"), "ziadny stupen zvuk"


def test_rusila_ide_o_stupen_nizsie():
    s = stav([rel(0, cue_verdict="disruptive")])
    assert s["stupen"] == rebrik.OBRAZ
    assert s["dovod"] == rebrik.D_RUSILA
    assert s["zostava"] == rebrik.NAVRAT_RELACII


def test_rozhodila_ma_ide_o_stupen_nizsie():
    s = stav([rel(0, cue_verdict="agitated")])
    assert (s["stupen"], s["dovod"]) == (rebrik.OBRAZ, rebrik.D_ROZHODILA)


def test_verdikt_bez_hlasky_sa_nerata():
    """„Rušila“ pri relácii, v ktorej žiadna hláška neprišla, nehovorí nič
    o hláške."""
    assert stav([rel(0, auto_triggers=0, cue_verdict="disruptive")])["stupen"] \
        == rebrik.HLAS


def test_snooze_po_hlaske_a_hralo_sa_dalej_ide_nizsie():
    s = stav([rel(0, snooze_after_cue_s=20.0, snooze_then_s=600.0)])
    assert (s["stupen"], s["dovod"]) == (rebrik.OBRAZ, rebrik.D_SNOOZE)


def test_snooze_a_sadla_nie_je_signal():
    """„Sadla“ a hneď „teraz nie“ = skôr „končím“ než „prekážala“."""
    s = stav([rel(0, snooze_after_cue_s=20.0, snooze_then_s=600.0,
                  cue_verdict="landed")])
    assert s["stupen"] == rebrik.HLAS


def test_snooze_a_relacia_skoncila_do_120_s_nie_je_signal():
    """Zadávateľ nevie, či Ctrl+Alt+Z nemyslí „končím“ - bez pokračovania
    relácie sa to neráta. (Od 24. 9. `_start_snooze` reláciu nezatvára, takže
    signál naozaj môže padnúť - celá cesta je v tests/test_teraz_nie.py.)"""
    for potom in (0.0, 119.9, None):
        s = stav([rel(0, snooze_after_cue_s=20.0, snooze_then_s=potom)])
        assert s["stupen"] == rebrik.HLAS, potom


def test_snooze_neskoro_po_hlaske_nie_je_signal():
    s = stav([rel(0, snooze_after_cue_s=200.0, snooze_then_s=900.0)])
    assert s["stupen"] == rebrik.HLAS


def test_jedna_relacia_je_najviac_jeden_stupen():
    s = stav([rel(0, cue_verdict="agitated", snooze_after_cue_s=5.0,
                  snooze_then_s=900.0)])
    assert (s["stupen"], s["dovod"]) == (rebrik.OBRAZ, rebrik.D_ROZHODILA)


def test_pauza_trva_tri_relacie_aspon_5_minut_potom_obraz():
    zaklad = [rel(0, cue_verdict="disruptive"), rel(1, cue_verdict="agitated")]
    s = stav(zaklad)
    assert s["stupen"] == rebrik.PAUZA and s["zostava"] == rebrik.PAUZA_RELACII
    ticho = [rel(2 + i, auto_triggers=0) for i in range(2)]
    # kratka relacia sa do pauzy nerata
    kratka = [rel(4, auto_triggers=0, duration_s=200.0)]
    s = stav(zaklad + ticho + kratka)
    assert s["stupen"] == rebrik.PAUZA and s["zostava"] == 1
    s = stav(zaklad + ticho + kratka + [rel(5, auto_triggers=0)])
    assert (s["stupen"], s["dovod"]) == (rebrik.OBRAZ, rebrik.D_ZNOVA)


def test_ano_mala_ukonci_pauzu_hned():
    zaklad = [rel(0, cue_verdict="disruptive"), rel(1, cue_verdict="disruptive")]
    s = stav(zaklad + [rel(2, auto_triggers=0, duration_s=90.0,
                           cue_verdict="missed")])
    assert (s["stupen"], s["dovod"]) == (rebrik.OBRAZ, rebrik.D_MALA)


def test_navrat_pomaly_tri_relacie_s_hlaskou_bez_vyhrad():
    zaklad = [rel(0, cue_verdict="disruptive")]
    ciste = [rel(1), rel(2, auto_triggers=0), rel(3, cue_verdict="unneeded")]
    s = stav(zaklad + ciste)
    # relacia bez hlasky sa nerata ani nerusi
    assert s["stupen"] == rebrik.OBRAZ and s["zostava"] == 1
    s = stav(zaklad + ciste + [rel(4)])
    assert (s["stupen"], s["dovod"]) == (rebrik.HLAS, rebrik.D_NAVRAT)
    assert s["zostava"] == 0


def test_praca_ma_vrchol_obraz_a_nikdy_nad_neho():
    assert stav([], svet="work")["stupen"] == rebrik.OBRAZ
    s = stav([rel(0, cue_verdict="disruptive", world="work")], svet="work")
    assert s["stupen"] == rebrik.PAUZA
    s = stav([rel(i) for i in range(9)], svet="work")
    assert s["stupen"] == rebrik.OBRAZ, "praca sa nesmie vyskriabat na hlas"


def test_zvoleny_styl_obmedzi_vrchol():
    assert rebrik.vrchol("play", "visual") == rebrik.OBRAZ
    assert rebrik.vrchol("play", "sound") == rebrik.HLAS, \
        "zvuk je stupen hlasu so stlmenymi slovami, nie vlastny stupen"
    assert rebrik.vrchol("play", None) == rebrik.HLAS
    assert rebrik.vrchol("work", "voice") == rebrik.OBRAZ
    s = stav([rel(i) for i in range(9)], styl="visual")
    assert s["stupen"] == rebrik.OBRAZ == s["vrchol"]
    s = stav([rel(0, cue_verdict="disruptive")], styl="visual")
    assert s["stupen"] == rebrik.PAUZA


def test_nezmyselny_styl_je_hlas():
    for zly in (None, "", "loud", 3, "VOICE"):
        assert rebrik.normalize_cue_style(zly) == rebrik.STYL_HLAS
    for dobry in rebrik.STYLY:
        assert rebrik.normalize_cue_style(dobry) == dobry


def test_importovane_relacie_sa_nerataju():
    s = stav([rel(0, cue_verdict="disruptive", imported=True)])
    assert s["stupen"] == rebrik.HLAS


def test_peciatka_najstarsej_relacie_prezije_orezanie():
    """Po `MAX_SESSIONS` staré záznamy odídu - hlas sa nesmie vrátiť len
    preto. Pečiatka platí, len keď bola pod VLASTNÝM vrcholom."""
    s = stav([rel(0, cue_rung="pause", cue_style="voice", auto_triggers=0)])
    assert s["stupen"] == rebrik.PAUZA
    # kto mal styl "obraz" a prepol na hlas, nema ostat na obraze
    s = stav([rel(0, cue_rung="visual", cue_style="visual")])
    assert s["stupen"] == rebrik.HLAS
    s = stav([rel(0, cue_rung="visual", cue_style="voice", auto_triggers=0)])
    assert s["stupen"] == rebrik.OBRAZ


def test_pokazene_zaznamy_nezhodia_rebrik():
    s = stav([None, "x", {"started": "zle"}, rel(0, auto_triggers="?",
                                                  snooze_after_cue_s="nie")])
    assert s["stupen"] == rebrik.HLAS


def test_realne_agregaty_z_testovania_ostanu_na_vrchole():
    """9 relácií, jedna „áno, mala“ (review stress-cue): hra = hlas."""
    relacie = [rel(i, auto_triggers=(1 if i == 3 else 0)) for i in range(8)]
    relacie.append(rel(8, auto_triggers=0, cue_verdict="missed"))
    assert stav(relacie)["stupen"] == rebrik.HLAS
    assert stav(relacie, svet="work")["stupen"] == rebrik.OBRAZ


# --------------------------------------------------------------------------
# Automat: pauza = nenatiahne sa, diagnostika beží
# --------------------------------------------------------------------------

def test_pauza_sa_nenatiahne_ale_diagnostika_bezi():
    t = trigger.CueTrigger(params={"cues_enabled": False},
                           rng=random.Random(1), clock=lambda: 0.0)
    t.open_session(silent_share=0.0)
    udalosti = []
    for i in range(400):
        ev = t.note_load(80.0, 1000.0 + i, zona="high")
        if ev:
            udalosti.append(ev)
    assert not udalosti and t.armed_count == 0
    # ako pri plnej hodine: pocitanie sa zacina odznova, nic sa nezahodi
    assert t.behov_nad >= 1
    assert t.najdlhsi_nad_s >= t.params["stress_hold_s"]


def test_predvolene_parametre_nesu_branu_a_zapnute_hlasky():
    p = trigger.default_params()
    assert p["cues_enabled"] is True
    assert p["brana"] == "po_vrchole"


# --------------------------------------------------------------------------
# Verdikt „rozhodila ma“
# --------------------------------------------------------------------------

def test_verdikt_rozhodila_ma(tmp_path):
    assert "agitated" in hr_stats.CUE_VERDICTS
    assert hr_stats.normalize_cue_verdict("agitated") == "agitated"
    cesta = str(tmp_path / "hr_sessions.json")
    assert hr_stats.save_session(cesta, {"started": 1_789_000_000.5,
                                         "duration_s": 600.0, "samples": 400})
    assert hr_stats.attach_context(cesta, 1_789_000_000.5, [],
                                   cue_verdict="agitated")
    assert hr_stats.load_sessions(cesta)[0]["cue_verdict"] == "agitated"


def test_dotaznik_ponuka_styri_verdikty_po_hlaske():
    src = _zdroj("ui_dialogs.py")
    assert '"landed", "unneeded", "disruptive", "agitated")' in src
    for jazyk in i18n.LANGUAGES:
        assert i18n.STRINGS["session.felt.cue.agitated"][jazyk].strip()
    assert i18n.STRINGS["session.felt.cue.agitated"]["sk"] == "rozhodila ma"
    assert i18n.STRINGS["session.felt.cue.agitated"]["en"] == "it wound me up"


# --------------------------------------------------------------------------
# Záznam o doručení a graf účinnosti
# --------------------------------------------------------------------------

def test_hlaska_nesie_zaznam_o_doruceni_az_do_okna():
    hs = hr_stats.HeartStats()
    hs.session_start = 1000.0
    hs.note_trigger(ts=1200.0, auto=True, category="jaw", arm="voice",
                    source="auto", delivery="pause", rung="visual",
                    audible=False, load_at=61.0, load_peak=74.0,
                    zone_at="high")
    cue = dict(hs.cues[-1], snooze_after_s=12.5)
    okno = measure.build_window(cue, [], [1200.0])
    assert (okno["rung"], okno["audible"], okno["load_at"], okno["load_peak"],
            okno["zone_at"], okno["snooze_after_s"]) == \
        ("visual", False, 61.0, 74.0, "high", 12.5)
    # stary zaznam bez tych poli sa postavi a nic si nevymysli
    hs.note_trigger(ts=1500.0, auto=True, category="jaw")
    stare = measure.build_window(hs.cues[-1], [], [1500.0])
    assert not {"rung", "audible", "load_at", "snooze_after_s"} & set(stare)


def _okno(**kw):
    w = {"category": "breath", "pre_bpm": 100.0, "post_bpm": 94.0,
         "arm": "voice", "valid": True, "delivery": "pause"}
    w.update(kw)
    return w


def test_graf_rata_len_hlasky_ktore_zazneli_na_pauze_v_hre():
    okna = [_okno(), _okno(audible=True),
            _okno(delivery="timeout", post_bpm=50.0),
            _okno(delivery=None, post_bpm=50.0),
            _okno(audible=False, post_bpm=50.0),
            _okno(world="work", post_bpm=50.0),
            _okno(arm="silent", post_bpm=50.0)]
    vysledok = measure.by_category(okna)["breath"]
    assert vysledok["n"] == 2 and vysledok["delta_bpm"] == -6.0


def test_graf_po_brane_nezlucuje_stare_okna():
    stare = [_okno(post_bpm=80.0) for _ in range(6)]
    assert measure.by_category(stare)["breath"]["n"] == 6
    nove = [_okno(params={"brana": "po_vrchole"}, post_bpm=97.0)]
    vysledok = measure.by_category(stare + nove)["breath"]
    assert vysledok["n"] == 1 and vysledok["delta_bpm"] == -3.0
    # ani importovane okno s branou neprepne vlastne data
    cudzie = [_okno(params={"brana": "po_vrchole"}, imported=True)]
    assert measure.by_category(stare + cudzie)["breath"]["n"] == 6


def test_veta_pod_grafom_je_poctiva():
    for jazyk in ("sk", "en"):
        veta = i18n.STRINGS["history.effect_hint"][jazyk]
        assert ("aj sám" in veta) if jazyk == "sk" else ("on its own" in veta)
    assert "nie je dôkaz" in i18n.STRINGS["history.effect_hint"]["sk"]
    # stare znenie neprezilo v ziadnom jazyku: jediny `_tr7` riadok je novy
    # preklad z jazykovej fazy 0.2 (ziadny starsi pod nim)
    assert _zdroj("i18n.py").count("_tr7('history.effect_hint'") == 1
    for jazyk in i18n.LANGUAGES:
        if jazyk not in ("sk", "en"):
            assert i18n.STRINGS["history.effect_hint"][jazyk] != \
                i18n.STRINGS["history.effect_hint"]["en"], jazyk


# --------------------------------------------------------------------------
# História: jedna tichá veta pod vrcholom
# --------------------------------------------------------------------------

def _veta(stav_rebrika):
    import app as app_mod
    return app_mod.DandurfApp._rebrik_veta(stav_rebrika)


def test_veta_v_historii_len_pod_vrcholom_a_s_dovodom():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    try:
        assert _veta(stav([])) == ""
        assert _veta(stav([rel(0)], styl="visual")) == "", \
            "zvoleny styl nie je stisenie - nie je co vysvetlovat"
        veta = _veta(stav([rel(0, cue_verdict="agitated")]))
        assert "len obrazom" in veta and "rozhodila" in veta
        assert "treba ešte: 3" in veta
        pauza = _veta(stav([rel(0, cue_verdict="disruptive"),
                            rel(1, cue_verdict="disruptive")]))
        assert "vypnuté" in pauza and "áno, mala" in pauza
        # bez dovodu (peciatka) ziadne dvojite medzery
        bez = _veta(stav([rel(0, cue_rung="visual", cue_style="voice",
                              auto_triggers=0)]))
        assert bez and "  " not in bez
    finally:
        i18n.set_lang(povodny)


def test_kazdy_dovod_pod_vrcholom_ma_vetu():
    for dovod in rebrik.DOVODY_POD_VRCHOLOM:
        kluc = f"history.rebrik.why.{dovod}"
        assert kluc in i18n.STRINGS, kluc
    # appka o sebe v zenskom rode
    assert "som sa mala" in i18n.STRINGS["history.rebrik.why.missed"]["sk"]


# --------------------------------------------------------------------------
# Pauza nesmie klamať inde
# --------------------------------------------------------------------------

def test_pauza_v_dotazniku_a_postrehoch():
    import ui_dialogs
    veta = ui_dialogs.SessionEndDialog._preco_ticho(
        {"cue_rung": "pause", "above_runs": 3, "longest_above_s": 10.0,
         "stress_hold_s": 45.0, "duration_s": 1800.0})
    assert veta == i18n.tr("session.end.none_paused")
    relacie = [{"started": 1789000000.0 + i * 86400.0, "duration_s": 2400.0,
                "samples": 900, "baseline_bpm": 70, "auto_triggers": 0,
                "above_runs": 5, "longest_above_s": 9.0,
                "runs_cancelled_gap": 0, "stress_hold_s": 45.0,
                "cue_rung": "pause"} for i in range(4)]
    kluce = {i["key"] for i in hr_insights.analyze(relacie, now=1789500000.0)}
    assert not kluce & {"cue_far", "cue_almost", "cue_never_above", "steady"}


# --------------------------------------------------------------------------
# app.py (neimportovatelne bez okna - kontrola zdroja)
# --------------------------------------------------------------------------

def _zdroj(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _funkcia(meno_suboru, meno):
    # "app.py" = cela appka: app.py aj mixiny DandurfApp v app_*.py
    strom = strom_appky() if meno_suboru == "app.py" else ast.parse(_zdroj(meno_suboru))
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno:
            return uzol
    raise AssertionError(meno)


def _volania(uzol):
    return [ast.unparse(v.func) for v in ast.walk(uzol) if isinstance(v, ast.Call)]


def test_pod_stupnom_hlasu_nezaznie_ziadne_tts():
    """`_emit` sa v `_fire_somatic_cue` spúšťa JEDINE vo vetve, ktorá
    vyžaduje `hlas` aj stupeň hlasu - pod ním ide hláška len obrazom."""
    fn = _funkcia("app.py", "_fire_somatic_cue")
    vetvy = [u for u in ast.walk(fn) if isinstance(u, ast.If)
             and "self._emit" in ast.unparse(u)
             and not any(isinstance(d, ast.If) and "self._emit" in ast.unparse(d)
                         for d in u.body)]
    assert len(vetvy) == 1
    podmienka = ast.unparse(vetvy[0].test)
    assert "ev.get('hlas')" in podmienka
    assert "stupen == rebrik.HLAS" in podmienka
    assert ast.unparse(fn).count("self._emit") == 1
    assert "bez_slov" in ast.unparse(vetvy[0])


def test_bez_slov_nezaznie_tts_ani_nahravka():
    fn = _funkcia("app.py", "_emit")
    vetva = next(u for u in fn.body if isinstance(u, ast.If)
                 and ast.unparse(u.test) == "bez_slov")
    volania = _volania(vetva)
    assert not [v for v in volania if "speak" in v or "voice" in v], volania
    assert isinstance(vetva.body[-1], ast.Return), "bez slov musi skoncit tu"
    # a je to PRED ostatnymi vetvami
    assert fn.body.index(vetva) < min(
        fn.body.index(u) for u in fn.body if isinstance(u, ast.If)
        and "MODE_COMBO" in ast.unparse(u.test))


def test_snooze_sa_zapise_a_relaciu_nezatvara():
    """24. 9.: „teraz nie“ len stíši hlášky - relácia beží ďalej, inak by
    `snooze_then_s` bolo vždy ~0 a signál rebríka by nepadol nikdy."""
    fn = _funkcia("app.py", "_start_snooze")
    telo = ast.unparse(fn)
    assert telo.index("self._zapis_snooze_po_hlaske(") < telo.index(
        "self._suspend_cue_trigger(trigger.A_SNOOZE)")
    volania = _volania(fn)
    for zakazane in ("self.stop_listening", "self.start_listening",
                     "self._close_hr_session"):
        assert zakazane not in volania, zakazane


def test_relacia_nesie_stupen_styl_a_snooze():
    otvor = ast.unparse(_funkcia("app.py", "_open_hr_session"))
    assert otvor.index("self._urci_stupen_hlasky()") < otvor.index(
        "self.cue_trigger.open_session(")
    assert "self.cue_trigger.params['cues_enabled'] = False" in otvor
    assert "self._cue_rung == rebrik.HLAS" in otvor
    # stupen sa pocita z relacii TOHO sveta, ktory B3 opecatil
    urci = ast.unparse(_funkcia("app.py", "_urci_stupen_hlasky"))
    assert "hr_stats.sessions_in_world(" in urci and "_session_world" in urci
    zatvor = ast.unparse(_funkcia("app.py", "_close_hr_session"))
    for kluc in ("cue_rung", "cue_style", "snooze_after_cue_s", "snooze_then_s"):
        assert f"summary['{kluc}']" in zatvor, kluc
    assert zatvor.index("summary['cue_rung']") < zatvor.index("hr_stats.save_session(")
    # okno nesie parametre (a v nich branu)
    assert "w['params'] = params" in ast.unparse(
        _funkcia("app.py", "_save_measure_windows"))


def test_styl_hlasky_sa_cita_aj_uklada():
    nacitaj = ast.unparse(_funkcia("app.py", "load_settings"))
    assert "rebrik.normalize_cue_style(loaded.get('cue_style'))" in nacitaj
    uloz = ast.unparse(_funkcia("app.py", "save_settings"))
    assert "'cue_style'" in uloz


# --------------------------------------------------------------------------
# app.py na atrape (skutocne metody, bez okna)
# --------------------------------------------------------------------------

class _Vlakno:
    """Synchronne `threading.Thread` - aby sa dalo overit, co sa spustilo."""

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


def _dorucenie(monkeypatch, stupen, styl="voice", hlas=True):
    import app as app_mod
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    spustene = []
    slot = types.SimpleNamespace(index=1, text_value="Teeth")
    a = types.SimpleNamespace(
        _cue_rung=stupen, _cue_style_rel=styl, slots=[slot],
        overlay_manager=types.SimpleNamespace(trigger=lambda i: True),
        hr_stats=hr_stats.HeartStats(), last_global_trigger_time=0.0,
        log=lambda *x: None, _refresh_hud_session_text=lambda: None,
        _refresh_dnes_stats=lambda: None, _dalsi_cue_slot=lambda: 1,
        _slot_zaznie=lambda s, bez_slov=False: True,
        _emit=lambda s, bez_slov=False: spustene.append(bez_slov))
    ev = {"typ": trigger.E_DELIVER, "ts": 1200.0, "arm": "voice",
          "delivery": "pause", "hlas": hlas, "load": 61.0,
          "load_peak": 74.0, "zone_at": "high"}
    assert app_mod.DandurfApp._fire_somatic_cue(a, ev) is True
    return a.hr_stats.cues[-1], spustene


def test_dorucenie_pod_stupnom_hlasu_nic_neprehra(monkeypatch):
    # aj keby udalost tvrdila `hlas` (druha poistka)
    cue, spustene = _dorucenie(monkeypatch, rebrik.OBRAZ, hlas=True)
    assert spustene == []
    assert (cue["rung"], cue["audible"]) == ("visual", False)
    assert (cue["load_at"], cue["load_peak"], cue["zone_at"]) == (61.0, 74.0, "high")


def test_dorucenie_na_stupni_hlasu_a_styl_zvuk_stlmi_slova(monkeypatch):
    cue, spustene = _dorucenie(monkeypatch, rebrik.HLAS, styl="voice")
    assert spustene == [False] and cue["audible"] is True
    cue, spustene = _dorucenie(monkeypatch, rebrik.HLAS, styl="sound")
    assert spustene == [True], "styl zvuk = bez slov"
    cue, spustene = _dorucenie(monkeypatch, rebrik.HLAS, hlas=False)
    assert spustene == [] and cue["audible"] is False, "tiche rameno"


def _emit_atrapa(tmp_path, sfx=True):
    """Atrapa pre `_emit` / `_slot_zaznie`. `sfx=False` = zvuk slotu chyba."""
    import app as app_mod
    cesta = tmp_path / ("thud.wav" if sfx else "chyba.wav")
    if sfx:
        cesta.write_bytes(b"RIFF")
    hrane, hovorene = [], []
    a = types.SimpleNamespace(
        sfx_volume=80, resolve_sfx_path=lambda s: str(cesta),
        audio=types.SimpleNamespace(play=hrane.append, speak=lambda *x: hovorene.append(x),
                                    play_tts=lambda *x: hovorene.append(x)),
        _speak_text=lambda *x, **k: hovorene.append(x),
        _play_concurrent=lambda *x: hrane.append(x),
        _slot_has_voice=lambda s: True, _slot_voice_clip=lambda s: None,
        log_threadsafe=lambda *x: None)
    return app_mod.DandurfApp, a, hrane, hovorene


def test_bez_slov_hra_len_zvuk_slotu(tmp_path):
    D, a, hrane, hovorene = _emit_atrapa(tmp_path)
    for mode in (MODE_COMBO, MODE_SFX, MODE_TTS):
        slot = types.SimpleNamespace(index=0, mode=mode, text_value="Teeth",
                                     voice_path="")
        D._emit(a, slot, bez_slov=True)
    assert len(hrane) == 2 and hovorene == [], "bez slov nesmie zaznet TTS"
    # bez suboru sa TTS nezjavi ani ako zaloha
    D, a, hrane, hovorene = _emit_atrapa(tmp_path, sfx=False)
    D._emit(a, types.SimpleNamespace(index=0, mode=MODE_SFX, text_value="Teeth",
                                     voice_path=""), bez_slov=True)
    assert hrane == [] and hovorene == []
    # bez `bez_slov` sa kombinacia sprava ako doteraz (zvuk aj slova)
    D, a, hrane, hovorene = _emit_atrapa(tmp_path)
    D._emit(a, types.SimpleNamespace(index=0, mode=MODE_COMBO, text_value="Teeth",
                                     voice_path=""))
    assert hrane and hovorene


def test_audible_zodpoveda_tomu_co_emit_zahra(tmp_path):
    D, a, _h, _v = _emit_atrapa(tmp_path)
    a._slot_has_voice = lambda s: bool(s.text_value.strip())
    combo = types.SimpleNamespace(mode=MODE_COMBO, text_value="Teeth")
    tts = types.SimpleNamespace(mode=MODE_TTS, text_value="Teeth")
    sfx = types.SimpleNamespace(mode=MODE_SFX, text_value="Teeth")
    assert D._slot_zaznie(a, combo) and D._slot_zaznie(a, combo, True)
    assert D._slot_zaznie(a, tts) and not D._slot_zaznie(a, tts, True)
    assert D._slot_zaznie(a, sfx)
    D, a, _h, _v = _emit_atrapa(tmp_path, sfx=False)
    assert not D._slot_zaznie(a, sfx), "SFX bez suboru nezaznie (text nema)"


def test_snooze_po_hlaske_sa_zapise_k_hlaske_aj_relacii():
    import app as app_mod
    hs = hr_stats.HeartStats()
    hs.session_start = 900.0
    hs.note_trigger(ts=1000.0, auto=True, source="auto", delivered=True)
    a = types.SimpleNamespace(_hr_session_open=True, hr_stats=hs,
                              _snooze_po_hlaske=None)
    app_mod.DandurfApp._zapis_snooze_po_hlaske(a, 1100.0)
    assert a._snooze_po_hlaske is None, "po 100 s to uz nie je signal"
    app_mod.DandurfApp._zapis_snooze_po_hlaske(a, 1030.0)
    assert a._snooze_po_hlaske == (30.0, 1030.0)
    assert hs.cues[-1]["snooze_after_s"] == 30.0
    a._hr_session_open = False
    a._snooze_po_hlaske = None
    app_mod.DandurfApp._zapis_snooze_po_hlaske(a, 1010.0)
    assert a._snooze_po_hlaske is None, "bez relacie nic"


def test_stupen_relacie_ide_zo_sveta_ktory_b3_opecatil():
    import app as app_mod
    relacie = [rel(0, cue_verdict="disruptive", world="play"),
               rel(1, world="work")]
    a = types.SimpleNamespace(cue_style="voice", _session_world="play",
                              _history_sessions=lambda: relacie)
    app_mod.DandurfApp._urci_stupen_hlasky(a)
    assert a._cue_rung == rebrik.OBRAZ and a._cue_style_rel == "voice"
    a._session_world = "work"
    app_mod.DandurfApp._urci_stupen_hlasky(a)
    assert a._cue_rung == rebrik.OBRAZ, "praca = vrchol obraz"
    a._session_world = "play"
    a.cue_style = "nezmysel"
    a._history_sessions = lambda: [rel(0)]
    app_mod.DandurfApp._urci_stupen_hlasky(a)
    assert (a._cue_rung, a._cue_style_rel) == (rebrik.HLAS, rebrik.STYL_HLAS)

    def zlyha():
        raise OSError("disk")
    a._history_sessions = zlyha
    app_mod.DandurfApp._urci_stupen_hlasky(a)
    assert a._cue_rung == rebrik.OBRAZ, "pri chybe radsej tichsie"


class _Popisok:
    def __init__(self):
        self.text, self.zobrazeny = None, False

    def winfo_exists(self):
        return True

    def configure(self, text=None, **_kw):
        self.text = text

    def pack(self, **_kw):
        self.zobrazeny = True

    def pack_forget(self):
        self.zobrazeny = False


def test_veta_rebrika_sa_v_historii_ukaze_a_skryje():
    import app as app_mod
    D = app_mod.DandurfApp
    a = types.SimpleNamespace(history_rebrik_note=_Popisok(), world="play",
                              cue_style="voice", _rebrik_veta=D._rebrik_veta)
    D._refresh_rebrik_note(a, [rel(0, cue_verdict="disruptive")])
    assert a.history_rebrik_note.zobrazeny and a.history_rebrik_note.text
    D._refresh_rebrik_note(a, [])
    assert not a.history_rebrik_note.zobrazeny


def test_dnes_na_pauze_nesluby_hlasku():
    import app as app_mod
    a = types.SimpleNamespace(listening=True, hr_monitoring_enabled=True,
                              _hr_state="connected", _hr_last_bpm=80,
                              _cue_armed=False, _hr_session_open=True,
                              _cue_rung=rebrik.PAUZA)
    _nadpis, veta = app_mod.DandurfApp._kamae_state_text(a)
    assert veta == i18n.tr("kamae.paused_sub")
    a._cue_rung = rebrik.OBRAZ
    assert app_mod.DandurfApp._kamae_state_text(a)[1] == i18n.tr("kamae.running_sub")


def test_vety_rebrika_hovoria_jazykom_appky():
    """Review: veta o stíšení pomenúva to, čo hráč v appke vidí („stíšenie“,
    Ctrl+Alt+Z), nie interný názov „teraz nie“, ktorý appka nikde neukazuje.
    A appka nežiada, aby jej niekto chýbal - SK hovorí o hláškach ako EN."""
    snooze = i18n.STRINGS["history.rebrik.why.snooze"]
    assert "stíšil" in snooze["sk"] and "teraz nie" not in snooze["sk"]
    assert "snoozed" in snooze["en"] and "not now" not in snooze["en"]
    for kluc in ("history.rebrik.pause", "session.end.none_paused"):
        assert "chýbam" not in i18n.STRINGS[kluc]["sk"], kluc
        assert "chýbajú" in i18n.STRINGS[kluc]["sk"], kluc
        assert "miss them" in i18n.STRINGS[kluc]["en"], kluc
