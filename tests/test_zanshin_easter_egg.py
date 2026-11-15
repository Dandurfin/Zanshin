# -*- coding: utf-8 -*-
"""Full Zanshin (easter egg) from start to finish - after all the 0.2 changes.

Sessions here are not made up as ready-made dicts. Every evening goes through
the real `hr_stats.HeartStats` - calibration at the start, an occasional
heart-rate dropout, zones, summary - with the critical heart rate and the
long-term baseline from the history so far, the way `app._open_hr_session`
sets them (baseline from everything, critical heart rate from play). Closing
goes the `_close_hr_session` way: `hr_stats.save_session` and right after it
the real `DandurfApp._maybe_graduate` on a small dummy app with the real
`save_settings` / `load_settings` and the real `ui_shell._EnsoHero`.

Decision (easter-egg-check): ONLY GAME sessions count towards the streak
(`hr_stats.ZEN_SVET`), the same as the critical heart rate and the load
threshold. The circle closes only after a game session - not in the
questionnaire after work.

No Tk: `_EnsoHero` is not a widget, it only draws a PIL image.
"""
import json
import os
import random
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

DEN = 86400.0
T0 = 1_780_000_000.0


@pytest.fixture
def hodiny(monkeypatch):
    """Clock for `hr_stats`: sessions start and end in scenario time, not now."""
    teraz = [T0]
    monkeypatch.setattr(hr_stats, "time",
                        types.SimpleNamespace(time=lambda: teraz[0]))
    return teraz


def _vecer(hodiny, historia, den, druh="calm", svet="play", hodina=20,
           minut=22, rest=72.0, vypadok_min=0.0):
    """One session through the real `HeartStats` - returns a saveable summary.

    calm = heart rate at rest, every fifth round 8 higher (a tenser match);
    tilt = alternately +12 and +30 above rest. Every evening starts with
    calibration at a raised heart rate (just sat down after the stairs) and
    the watch noise is random.
    """
    rnd = random.Random(den * 100 + hodina)
    t0 = T0 + den * DEN + hodina * 3600.0
    # Like `_open_hr_session`: baseline from all sessions, critical from play.
    dlhodoba = hr_stats.dlhodoba_zakladna(historia)
    herna = hr_stats.sessions_in_world(historia, "play")
    kriticky = int(hr_stats.dynamicky_kriticky(herna, baseline=dlhodoba))
    hodiny[0] = t0
    st = hr_stats.HeartStats(critical_bpm=kriticky)
    st.long_baseline = dlhodoba
    st.reset_session()
    koniec = t0 + minut * 60.0
    vypadok_od = t0 + minut * 30.0 if vypadok_min else None
    t = t0 + 2.0
    bpm = rest + 14.0
    slepy = False
    while t < koniec:
        if vypadok_od and vypadok_od <= t < vypadok_od + vypadok_min * 60.0:
            if not slepy:                      # app: note_dropout, clear_live
                st.note_dropout(od=st.last_beat_ts)
                st.clear_live()
                slepy = True
            t += 1.0
            continue
        uplynulo = t - t0
        if uplynulo < 90.0:
            ciel = rest + 14.0 - uplynulo / 90.0 * 14.0
        elif druh == "calm":
            ciel = rest + (8.0 if (uplynulo // 240) % 5 == 3 else 0.0)
        else:
            ciel = rest + (30.0 if (uplynulo // 180) % 2 else 12.0)
        bpm += (ciel - bpm) * 0.15 + rnd.gauss(0.0, 1.2)
        st.add(round(bpm), ts=t)
        t += rnd.uniform(0.8, 1.3)
    hodiny[0] = koniec
    s = st.summary()
    s["world"] = svet
    s["long_baseline_bpm"] = round(float(dlhodoba), 1) if dlhodoba is not None else None
    return s


@pytest.fixture
def appka(tmp_path, monkeypatch, hodiny):
    """Minimal `DandurfApp` dummy for `_maybe_graduate`.

    The settings are from the first start (`load_settings` without a file)
    and the real `save_settings` saves them to a temporary file; the mark is
    the real enso.
    """
    import app as app_mod
    import app_prefs
    import ui_shell
    # `load_settings` / `save_settings` live in the app_prefs mixin
    # (PrefsMixin) and read SETTINGS_PATH from their own module.
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH",
                        str(tmp_path / "dandurf_settings.json"))
    povodny = i18n._lang["code"]
    D = app_mod.DandurfApp

    def z_nastaveni(d):
        return types.SimpleNamespace(
            _ready=True, slots=list(d["profiles"][0]["slots"]),
            _sync_active_profile_slots=lambda: None,
            profiles=d["profiles"], active_profile_name=d["active_profile"],
            saved_voice_id=d["voice_id"], rate_value=d["rate"],
            volume_value=d["volume"], balance_value=d["balance"],
            engine_pref=d["engine_pref"], edge_voice_id=d["edge_voice"],
            theme_key=d["theme"], world=d["world"], cue_style=d["cue_style"],
            lang=d["lang"], start_minimized=d["start_minimized"],
            auto_profile_enabled=d["auto_profile_enabled"],
            overlay_configs=d["overlay_configs"], tour_seen=d["tour_seen"],
            tour_step=d["tour_step"], game_lang=d["game_lang"],
            hr_ip=d["hr_ip"], hr_port=d["hr_port"],
            hr_monitoring_enabled=d["hr_monitoring_enabled"],
            zanshin_graduated=d["zanshin_graduated"],
            zanshin_graduated_at=d["zanshin_graduated_at"],
            snooze_hotkey=d["snooze_hotkey"],
            background_opacity=d["background_opacity"],
            monitor_target=d["monitor_target"], hud_config=d["hud_config"],
            dashboard_stats=d["dashboard_stats"],
            breath_inhale_s=d["breath_inhale_s"],
            breath_exhale_s=d["breath_exhale_s"],
            log=lambda *a, **k: None, log_threadsafe=lambda *a, **k: None,
            hr_sessions_path=str(tmp_path / "hr_sessions.json"))

    def spusti(d=None):
        """One "app start" over the same files."""
        a = z_nastaveni(d if d is not None else D.load_settings(types.SimpleNamespace()))
        a.zmeny_ensa = []
        a.ulozenia = []
        a.enso = ui_shell._EnsoHero(theme.tokens(theme.ZEN), size=48,
                                    on_change=lambda: a.zmeny_ensa.append(1))
        # Exactly what `_build_dnes_page` does when building the window.
        if getattr(a, "zanshin_graduated", False):
            a.enso.graduate()

        def uloz():
            a.ulozenia.append(1)
            D.save_settings(a)
        a.save_settings = uloz
        a._maybe_graduate = lambda summary: D._maybe_graduate(a, summary)
        return a

    spusti.nacitaj = lambda: D.load_settings(types.SimpleNamespace())
    spusti.nastavenia = str(tmp_path / "dandurf_settings.json")
    yield spusti
    i18n.set_lang(povodny)


def _zatvor(a, summary):
    """The end of `_close_hr_session`: save and, once saved, graduation."""
    if hr_stats.save_session(a.hr_sessions_path, summary):
        a._maybe_graduate(summary)
        return True
    return False


def _prehraj(hodiny, a, plan):
    """Plan = [(den, druh, svet, hodina, minut, vypadok_min)] - sessions open
    and close in this order. Returns all the closed summaries."""
    zatvorene = []
    for den, druh, svet, hodina, minut, vypadok in plan:
        historia = hr_stats.load_sessions(a.hr_sessions_path)
        s = _vecer(hodiny, historia, den, druh=druh, svet=svet, hodina=hodina,
                   minut=minut, vypadok_min=vypadok)
        assert _zatvor(a, s)
        zatvorene.append(s)
    return zatvorene


def test_realna_pokojna_historia_spusti_promociu_prave_raz(hodiny, appka):
    """Two tilts at the start, then calm evenings of play. In between, calm
    work afternoons, one 6-minute peek and an evening with a 4-minute
    heart-rate dropout. The graduation comes after the FIRST evening when
    everything holds at once: 10 counted game evenings, 10 days, 5 of 7
    calm, the last one calm. That is the evening of day 10 - not earlier,
    and never again."""
    a = appka()
    plan = []
    for den in range(14):
        if den in (3, 6, 9, 12):
            plan.append((den, "calm", "work", 14, 30, 0.0))
        if den == 5:
            plan.append((den, "calm", "play", 16, 6, 0.0))
        plan.append((den, "tilt" if den < 2 else "calm", "play", 20, 22,
                     4.0 if den == 7 else 0.0))
    zatvorene = _prehraj(hodiny, a, plan)

    # The inputs mean what the graduation assumes.
    herne = [s for s in zatvorene if s["world"] == "play"]
    assert [hr_stats.je_plne_zanshin(s) for s in herne if s["started"] < T0 + 2 * DEN] \
        == [False, False], "tilt nie je pokoj"
    vypadok = next(s for s in herne if s["started"] == T0 + 7 * DEN + 20 * 3600)
    assert vypadok["dropouts"] == 1 and vypadok["blind_s"] >= 230
    assert hr_stats.je_plne_zanshin(vypadok) is True, "18 min tepu je stale vecer"
    nahlad = next(s for s in herne if s["duration_s"] < 900)
    assert hr_stats.je_plne_zanshin(nahlad) is None, "nahliadnutie netresta"

    # Exactly once - and exactly after the evening of day 10.
    oznacene = [s for s in zatvorene if s.get("zen_graduation")]
    assert len(oznacene) == 1
    assert oznacene[0]["started"] == T0 + 10 * DEN + 20 * 3600
    assert oznacene[0]["world"] == "play"
    assert a.zanshin_graduated is True
    assert isinstance(a.zanshin_graduated_at, float)
    assert a.ulozenia == [1], "nastavenia sa ulozili raz"
    assert a.enso._moon is True and a.zmeny_ensa == [1], "mesiac raz"
    assert a.enso.render(48) is not None, "mesiac sa da nakreslit"

    # The mark lives in the settings, not in the session history.
    with open(appka.nastavenia, encoding="utf-8") as fh:
        ulozene = json.load(fh)
    assert ulozene["zanshin_graduated"] is True
    assert ulozene["zanshin_graduated_at"] == a.zanshin_graduated_at
    assert not any(s.get("zen_graduation")
                   for s in hr_stats.load_sessions(a.hr_sessions_path))

    # Restart: the flag is loaded, the moon is restored without a new "change",
    # the next calm evening triggers nothing.
    d = appka.nacitaj()
    assert d["zanshin_graduated"] is True
    assert d["zanshin_graduated_at"] == a.zanshin_graduated_at
    b = appka(d)
    assert b.enso._moon is True
    dalsi = _prehraj(hodiny, b, [(14, "calm", "play", 20, 22, 0.0)])
    assert not dalsi[0].get("zen_graduation")
    assert b.ulozenia == []


def test_takmer_splnena_historia_nespusti_nic(hodiny, appka):
    """In every 7 evenings of play four are calm - one fewer than needed. The
    last evening is calm, there are enough sessions and days. Every
    afternoon is calm work: if it counted, the streak would fill up - but
    the graduation counts only play, so it never came."""
    a = appka()
    vzor = ("tilt", "calm", "tilt", "calm", "tilt", "calm", "calm")
    plan = []
    for den in range(14):
        plan.append((den, "calm", "work", 14, 30, 0.0))
        plan.append((den, vzor[den % 7], "play", 20, 22, 0.0))
    zatvorene = _prehraj(hodiny, a, plan)

    assert not any(s.get("zen_graduation") for s in zatvorene)
    assert a.zanshin_graduated is False and a.zanshin_graduated_at is None
    assert a.ulozenia == [] and not os.path.exists(appka.nastavenia)
    assert a.enso._moon is False and a.zmeny_ensa == []

    historia = hr_stats.load_sessions(a.hr_sessions_path)
    v = hr_stats.zanshin_graduation(historia)
    assert v["reason"] == "not_yet" and v["passed_in_window"] == 4
    assert v["eligible"] == 14, "pracovne relacie sa nerataju"
    assert hr_stats.zanshin_streak(historia)["current_pass"] is True
    # Check that it really is "almost": with work as play it would fire.
    ako_hra = [dict(s, world="play") for s in historia]
    assert hr_stats.zanshin_graduation(ako_hra)["fire"] is True


def test_start_obnovi_zlaty_mesiac_z_flagu():
    """The flag is loaded in `__init__` before the window is built, and
    `_build_dnes_page` calls `graduate()` right after creating the enso
    (also after a window rebuild)."""
    init = zdroj_metody("__init__")
    assert (init.index('self.zanshin_graduated = bool(settings["zanshin_graduated"])')
            < init.index("self._build_ui()"))
    telo = zdroj_metody("_build_dnes_page")
    i_enso = telo.index("self.enso = ui_shell._EnsoHero(")
    i_flag = telo.index('if getattr(self, "zanshin_graduated", False):')
    i_grad = telo.index("self.enso.graduate()")
    assert i_enso < i_flag < i_grad


def test_hook_po_praci_mlci():
    """After a work session `_maybe_graduate` does not touch the history."""
    telo = zdroj_metody("_maybe_graduate")
    i_svet = telo.index("hr_stats.session_world(summary) != hr_stats.ZEN_SVET")
    assert i_svet < telo.index("hr_stats.load_sessions(")


@pytest.mark.parametrize("jazyk", ["sk", "en"])
def test_sprava_nesluby_zdravie_ani_vykon(jazyk):
    """The message talks only about what the app really saw (heart rate close
    to your own resting rate on most of the recent evenings of play). No
    "the body now remembers on its own", no health, performance or lasting
    effect."""
    telo = i18n.STRINGS["session.zanshin.body"][jazyk].lower()
    zakazane = {
        "sk": ("pamätá", "zdrav", "lieč", "lepš", "výkon", "natrvalo",
               "naučil", "vyliečen", "diagn"),
        "en": ("remember", "health", "heal", "better", "perform", "for good",
               "learned", "trained", "cure", "diagnos"),
    }[jazyk]
    for slovo in zakazane:
        assert slovo not in telo, slovo
    if jazyk == "sk":
        assert "tep" in telo and "pokoj" in telo and "pri hre" in telo
        assert "beze mňa" in telo, "appka hovori sama za seba (ja)"
    else:
        assert "pulse" in telo and "calm" in telo and "play" in telo
        assert "without me" in telo
