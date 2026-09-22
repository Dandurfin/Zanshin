# -*- coding: utf-8 -*-
"""Detekcia "plneho Zanshinu" (promocia / easter egg) - ciste data.

Rovnaky styl ako test_hr_metrics.py: import + synteticke relacie, ziadne Tk.
Kontroluje pravidlo: pokoj voci VLASTNEJ zakladni, seria 5 z 7, poistky
(min 10 relacii, 10 dni), spusti sa raz - a ze kratke/podozrive relacie
NIKDY netrestaju (None = nepocita sa).
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


# ---- je_plne_zanshin: jedna relacia ----

def test_pokojna_relacia_prejde():
    # base 77, krivka 85 = base+8: p80 aj p95 pod base+12/+18, ziadne prekrocenie
    assert hr_stats.je_plne_zanshin(_sess(0, curve_val=85.0)) is True


def test_dlho_vysoka_relacia_neprejde():
    # base+30 = 107: p80 nad base+12
    assert hr_stats.je_plne_zanshin(_sess(0, curve_val=107.0)) is False


def test_viacnasobne_prekrocenie_kritickej_neprejde():
    # krivka pokojna, ale dvakrat vyskoci nad kriticku (105) a vrati sa
    base_flat = [80.0] * 600
    for i in (100, 101, 102, 300, 301, 302):
        base_flat[i] = 120.0
    assert hr_stats.je_plne_zanshin(_sess(0, curve=base_flat)) is False


def test_jedno_vyskocenie_este_prejde():
    # jedno stupajuce prekrocenie kritickej je tolerovane (N=1)
    krivka = [80.0] * 600
    for i in (300, 301, 302):
        krivka[i] = 120.0
    # p95 z prevazne 80-tky ostava nizko -> prejde napriek jednemu blipu
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


# ---- zanshin_graduation: seria + poistky ----

def _pass_history(n, span_days=None):
    """n pokojnych relacii rozlozenych rovnomerne cez `span_days` dni."""
    span = span_days if span_days is not None else (n * 1.2)
    if n == 1:
        return [_sess(0)]
    krok = span * DEN / (n - 1)
    return [_sess(i * krok) for i in range(n)]


def test_promocia_sa_spusti_pri_dlhej_pokojnej_serii():
    sessions = _pass_history(10)          # 10 pokojnych, ~10.8 dni
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
    # 12 pokojnych relacii, ale vsetky v ramci 2 dni -> too_soon
    sessions = _pass_history(12, span_days=2)
    v = hr_stats.zanshin_graduation(sessions, already_graduated=False)
    assert v["fire"] is False and v["reason"] == "too_soon"


def test_posledna_relacia_musi_byt_pokojna():
    # 10 dni, 9 pokojnych + posledny stresovy vecer -> nespusti (current fail)
    sessions = _pass_history(10)
    sessions[-1] = _sess(sessions[-1]["started"], curve_val=110.0)  # stresova
    v = hr_stats.zanshin_graduation(sessions, already_graduated=False)
    assert v["fire"] is False


def test_dve_zle_zo_siedmich_este_graduuju():
    # rolling window 5 z 7: 10 relacii, dve stresove v okne -> stale >=5
    sessions = _pass_history(10)
    sessions[-2] = _sess(sessions[-2]["started"], curve_val=112.0)
    sessions[-4] = _sess(sessions[-4]["started"], curve_val=112.0)
    v = hr_stats.zanshin_graduation(sessions, already_graduated=False)
    assert v["fire"] is True, v


def test_streak_prepocita_bez_ukladania():
    st = hr_stats.zanshin_streak(_pass_history(10))
    assert st["eligible"] == 10 and st["passed_in_window"] == 7


# ---- napojenie v appke (AST - teeth, ze hook nezmizne) ----

def _telo_metody(subor, meno):
    import ast
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
    telo = _telo_metody("ui_dialogs.py", "__init__")  # prvy __init__ = SlotSettings?
    # radsej hladaj v celom subore vyskyt kluca (dialog ho cita)
    src = open("ui_dialogs.py", encoding="utf-8").read()
    assert 'summary.get("zen_graduation")' in src
    assert "session.zanshin.title" in src
