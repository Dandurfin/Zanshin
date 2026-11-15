# -*- coding: utf-8 -*-
"""Detection of "full Zanshin" (graduation / easter egg) - pure data.

The same style as test_hr_metrics.py: import + synthetic sessions, no Tk.
Checks the rule: calm relative to one's OWN baseline, a streak of 5 out of 7,
safeguards (min 10 sessions, 10 days), it fires once - and that
short/suspicious sessions NEVER penalise (None = does not count).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats


DEN = 86400.0


def _sess(started, curve_val=85.0, base=77.0, crit=105.0, dur=1200.0,
          samples=400, n=600, curve=None, max_bpm=None, **extra):
    krivka = curve if curve is not None else [float(curve_val)] * n
    mx = max_bpm if max_bpm is not None else (max(krivka) if krivka else 0) + 2
    s = dict(baseline_bpm=base, critical_bpm=crit, curve=krivka,
             duration_s=dur, samples=samples, started=float(started),
             max_bpm=mx, imported=False)
    s.update(extra)
    return s


# ---- je_plne_zanshin: one session ----

def test_pokojna_relacia_prejde():
    # base 77, curve 85 = base+8: p80 and p95 below base+12/+18, no crossing
    assert hr_stats.je_plne_zanshin(_sess(0, curve_val=85.0)) is True


def test_dlho_vysoka_relacia_neprejde():
    # base+30 = 107: p80 above base+12
    assert hr_stats.je_plne_zanshin(_sess(0, curve_val=107.0)) is False


def test_viacnasobne_prekrocenie_kritickej_neprejde():
    # the curve is calm, but jumps above the critical (105) twice and comes
    # back
    base_flat = [80.0] * 600
    for i in (100, 101, 102, 300, 301, 302):
        base_flat[i] = 120.0
    assert hr_stats.je_plne_zanshin(_sess(0, curve=base_flat)) is False


def test_jedno_vyskocenie_este_prejde():
    # one rising crossing of the critical is tolerated (N=1)
    krivka = [80.0] * 600
    for i in (300, 301, 302):
        krivka[i] = 120.0
    # p95 of mostly 80s stays low -> passes despite one blip
    assert hr_stats.je_plne_zanshin(_sess(0, curve=krivka)) is True


def test_kratka_relacia_sa_nepocita():
    assert hr_stats.je_plne_zanshin(_sess(0, dur=300.0)) is None


def test_podozriva_relacia_sa_nepocita():
    assert hr_stats.je_plne_zanshin(_sess(0, max_bpm=250.0)) is None


def test_importovana_relacia_sa_nepocita():
    assert hr_stats.je_plne_zanshin(_sess(0, imported=True)) is None


def test_rising_crossings():
    assert hr_stats._rising_crossings([80, 80, 110, 111, 80, 80, 112, 80], 105) == 2
    assert hr_stats._rising_crossings([80, 80, 80], 105) == 0


# ---- zanshin_graduation: streak + safeguards ----

def _pass_history(n, span_days=None):
    """n calm sessions spread evenly over `span_days` days."""
    span = span_days if span_days is not None else (n * 1.2)
    if n == 1:
        return [_sess(0)]
    krok = span * DEN / (n - 1)
    return [_sess(i * krok) for i in range(n)]


def test_promocia_sa_spusti_pri_dlhej_pokojnej_serii():
    sessions = _pass_history(10)          # 10 calm, ~10.8 days
    v = hr_stats.zanshin_graduation(sessions, already_graduated=False)
    assert v["fire"] is True, v


def test_promocia_sa_spusti_len_raz():
    sessions = _pass_history(10)
    v = hr_stats.zanshin_graduation(sessions, already_graduated=True)
    assert v["fire"] is False and v["graduated"] is True


def test_promocia_potrebuje_dost_relacii():
    v = hr_stats.zanshin_graduation(_pass_history(5), already_graduated=False)
    assert v["fire"] is False and v["reason"] == "need_more"


def test_promocia_sa_neda_nahrat_za_vikend():
    # 12 calm sessions, but all within 2 days -> too_soon
    sessions = _pass_history(12, span_days=2)
    v = hr_stats.zanshin_graduation(sessions, already_graduated=False)
    assert v["fire"] is False and v["reason"] == "too_soon"


def test_posledna_relacia_musi_byt_pokojna():
    # 10 days, 9 calm + a stressful last evening -> does not fire (current
    # fail)
    sessions = _pass_history(10)
    sessions[-1] = _sess(sessions[-1]["started"], curve_val=110.0)  # stressful
    v = hr_stats.zanshin_graduation(sessions, already_graduated=False)
    assert v["fire"] is False


def test_dve_zle_zo_siedmich_este_graduuju():
    # rolling window 5 of 7: 10 sessions, two stressful in the window -> still
    # >=5
    sessions = _pass_history(10)
    sessions[-2] = _sess(sessions[-2]["started"], curve_val=112.0)
    sessions[-4] = _sess(sessions[-4]["started"], curve_val=112.0)
    v = hr_stats.zanshin_graduation(sessions, already_graduated=False)
    assert v["fire"] is True, v


def test_streak_prepocita_bez_ukladania():
    st = hr_stats.zanshin_streak(_pass_history(10))
    assert st["eligible"] == 10 and st["passed_in_window"] == 7


# ---- inputs after the 0.2 changes (easter-egg-check) ----

def test_rovnomerne_vysoky_vecer_nie_je_pokoj_voci_dlhodobej_zakladni():
    """A whole evening at 95 (coffee, sustained stress): the session baseline
    catches up with the heart rate and the variance is small. Relative to
    the long-term baseline (a cap, as for zones and load) that is not calm;
    an old session without the field is judged as before."""
    vysoky = _sess(0, curve_val=95.0, base=95.0)
    assert hr_stats.je_plne_zanshin(vysoky) is True          # without the field: the old way
    vysoky["long_baseline_bpm"] = 72.0
    assert hr_stats.je_plne_zanshin(vysoky) is False
    # A cap, not a replacement: a calmer-than-usual evening stays relative to
    # itself.
    pokojny = _sess(0, curve_val=66.0, base=62.0, long_baseline_bpm=72.0)
    assert hr_stats.je_plne_zanshin(pokojny) is True


def test_pocita_sa_cas_s_tepom_nie_cas_na_hodinach():
    """20 min session, 12 min dropout: 8 min of heart rate is no evening."""
    assert hr_stats.je_plne_zanshin(_sess(0, dur=1200.0, blind_s=720.0)) is None
    assert hr_stats.je_plne_zanshin(_sess(0, dur=1200.0, blind_s=200.0)) is True
    # A broken field is not taken as a replacement for time.
    assert hr_stats.je_plne_zanshin(_sess(0, dur=1200.0, blind_s=-500.0)) is True


def test_do_serie_sa_rataju_len_herne_relacie():
    """Calm work afternoons do not fill the streak (same as the thresholds)."""
    praca = [dict(s, world="work") for s in _pass_history(10)]
    v = hr_stats.zanshin_graduation(praca, already_graduated=False)
    assert v["fire"] is False and v["reason"] == "need_more" and v["eligible"] == 0
    assert hr_stats.zanshin_streak(praca)["eligible"] == 0
    # The answer in the questionnaire takes precedence over the world from the
    # start.
    potvrdena_hra = [dict(s, world="work", activity="play") for s in _pass_history(10)]
    assert hr_stats.zanshin_graduation(potvrdena_hra)["fire"] is True


# ---- wiring in the app (AST - teeth, so the hook does not disappear) ----

def _telo_metody(subor, meno):
    import ast
    if subor == "app.py":
        # the whole app: app.py and the DandurfApp mixins in app_*.py
        from _zdroj_appky import zdroj_appky
        src = zdroj_appky()
    else:
        src = open(subor, encoding="utf-8-sig").read()
    for u in ast.walk(ast.parse(src)):
        if isinstance(u, ast.FunctionDef) and u.name == meno:
            return ast.unparse(u)
    raise AssertionError(f"{meno} sa nenasla v {subor}")


def test_close_session_vola_promociu():
    telo = _telo_metody("app.py", "_close_hr_session")
    assert "_maybe_graduate" in telo


def test_maybe_graduate_je_napojeny():
    telo = _telo_metody("app.py", "_maybe_graduate")
    for kluc in ("zanshin_graduation", "save_settings", "zen_graduation",
                 "graduate", "zanshin_graduated"):
        assert kluc in telo, f"_maybe_graduate nepouziva {kluc}"


def test_dialog_cita_zen_graduation():
    telo = _telo_metody("ui_dialogs.py", "__init__")  # first __init__ = SlotSettings?
    # better search the whole file for the key (the dialog reads it)
    src = open("ui_dialogs.py", encoding="utf-8").read()
    assert 'summary.get("zen_graduation")' in src
    assert "session.zanshin.title" in src
