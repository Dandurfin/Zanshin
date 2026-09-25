# -*- coding: utf-8 -*-
"""Ucenie vlastnych hranic (0.2.1): co README slubuje, to kod robi.

  1. Svet relacie: odpoved "Hral som / Pracoval som" v dotazniku je OPRAVA
     sveta - presunie relaciu aj do ucenia kritickeho tepu a prahu. Zamerne
     (viz komentar pri `hr_stats.WORLD_DEFAULT`); tieto testy to drzia, aby
     sa to nezmenilo potichu a README to mohlo poctivo povedat.
  2. Kriticky tep (hranica vysokeho tepu) sa uci len z relacii aspon 5 min,
     tym istym pravidlom ako prah zataze (`je_dost_dlha`). Tri kratke
     relacie pri parovani hodiniek uz nenahradia zalohu 110.
  3. Prah zataze: "tri relacie po zhruba desat minut staci, tri po pat nie"
     plati aj pri beznom pokryti signalu (85-90 %), nie len pri 100 %.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats  # noqa: E402


def _relacia(minut, pokrytie=None, kadencia_s=1.0, bodov=None, **kw):
    """Suhrn relacie ako z `HeartStats.summary`, len polia, ktore ucenie cita.

    `pokrytie` None = stara relacia bez `zone_seconds` (prehra sa cele
    trvanie). Inak su pasma spolu `trvanie * pokrytie` a krivka ma tolko
    bodov, kolko by hodinky s danou kadenciou za ten cas poslali (najviac
    `CURVE_POINTS`, ako `downsample`). Plynula vlna - `je_podozriva` ju
    necha tak.
    """
    trvanie = minut * 60.0
    signal = trvanie * (pokrytie if pokrytie is not None else 1.0)
    if bodov is None:
        bodov = min(hr_stats.CURVE_POINTS, int(signal / kadencia_s))
    s = {"duration_s": trvanie, "baseline_bpm": 70.0, "max_bpm": 95.0,
         "curve": [round(75 + 15 * math.sin(i / 7.0), 1) for i in range(bodov)]}
    if pokrytie is not None:
        s["zone_seconds"] = {"calm": signal * 0.5, "raised": signal * 0.3,
                             "high": signal * 0.2, "critical": 0.0}
    s.update(kw)
    return s


def _prah(relacie):
    return hr_stats.dynamicky_prah_zataze(relacie, baseline=70.0, critical=110)


# --------------------------------------------------------------------------
# 3. Prah zataze: tri po desat minut staci aj s dierami v signale
# --------------------------------------------------------------------------

def test_relacia_da_bodov_podla_signalu_bez_kalibracie():
    """Aritmetika z komentara pri `PRAH_MIN_BODOV`: krok 1,5 s, len cas so
    signalom, prvych 29 krokov je kalibracia."""
    for minut, p in ((10, 0.85), (10, 0.9), (10, 1.0), (5, 1.0)):
        body = hr_stats.load_z_krivky(_relacia(minut, p), 70.0, 110)
        assert len(body) == int(minut * 60 * p / 1.5) - 29, (minut, p)


@pytest.mark.parametrize("pokrytie", [0.85, 0.9, 0.95, 1.0, None])
@pytest.mark.parametrize("kadencia_s", [1.0, 2.0])
def test_tri_relacie_po_desat_minut_staci_aj_pri_beznom_pokryti(pokrytie, kadencia_s):
    """README: "three of about ten minutes are enough". Pri starom minime
    1000 bodov nepresli uz pri 90 % pokryti (3 x 331 = 993)."""
    relacie = [_relacia(10, pokrytie, kadencia_s) for _ in range(3)]
    assert all(not hr_stats.je_podozriva(r) for r in relacie)
    prah = _prah(relacie)
    assert prah is not None, (pokrytie, kadencia_s)
    lo, hi = hr_stats.PRAH_ROZSAH
    assert lo <= prah <= hi


@pytest.mark.parametrize("bodov", [None, hr_stats.CURVE_POINTS])
def test_tri_relacie_po_pat_minut_nestacia_ani_pri_plnom_pokryti(bodov):
    """README: "three of five are not" - ani s plnym pokrytim, ani s krivkou
    nahustenou na plnych `CURVE_POINTS` (prehrava sa cas, nie body krivky)."""
    for pokrytie in (1.0, None):
        relacie = [_relacia(5, pokrytie, bodov=bodov) for _ in range(3)]
        assert _prah(relacie) is None, (pokrytie, bodov)


def test_minimum_bodov_lezi_medzi_slubenymi_hranami():
    """Konkretne cisla z komentara - nech sa minimum neposunie tak, ze by
    README znova klamalo jednym alebo druhym smerom."""
    def spolu(minut, p):
        return 3 * len(hr_stats.load_z_krivky(_relacia(minut, p), 70.0, 110))
    assert spolu(5, 1.0) < hr_stats.PRAH_MIN_BODOV      # tri po pat nie
    assert spolu(8, 1.0) < hr_stats.PRAH_MIN_BODOV      # ani tri po osem
    assert spolu(10, 0.85) >= hr_stats.PRAH_MIN_BODOV   # tri po desat ano
    # "zhruba pol hodiny tepu": minimum spolu s kalibraciou troch relacii
    tep_min = (hr_stats.PRAH_MIN_BODOV + 3 * 29) * 1.5 / 60.0
    assert 20.0 <= tep_min <= 30.0, tep_min


def test_dlha_relacia_s_dierami_sa_do_prahu_rata_ako_doteraz():
    """Zmena minima nemeni, KTORE relacie sa rataju - len kolko bodov treba.

    Dve dlhe relacie maju bodov dost aj samy, takze o vysledku rozhoduje
    len pocet relacii a ich dlzka, nie minimum bodov."""
    dve = [_relacia(20, 0.9) for _ in range(2)]
    assert sum(len(hr_stats.load_z_krivky(r, 70.0, 110))
               for r in dve) >= hr_stats.PRAH_MIN_BODOV
    assert _prah(dve) is None, "tri relacie ostavaju podmienkou"
    assert _prah(dve + [_relacia(4.9, 1.0)]) is None, "5 minut tiez"
    assert _prah(dve + [_relacia(5, 1.0)]) is not None


# --------------------------------------------------------------------------
# 2. Kriticky tep: len z relacii aspon 5 minut
# --------------------------------------------------------------------------

def test_je_dost_dlha_to_iste_pravidlo_ako_prah():
    assert hr_stats.je_dost_dlha({"duration_s": hr_stats.PRAH_MIN_TRVANIE_S})
    assert hr_stats.je_dost_dlha({"duration_s": 3600})
    assert not hr_stats.je_dost_dlha({"duration_s": hr_stats.PRAH_MIN_TRVANIE_S - 0.1})
    for zla in ({}, {"duration_s": None}, {"duration_s": "dlho"},
                {"duration_s": [600]}, {"duration_s": float("nan")},
                {"duration_s": float("inf")}, {"duration_s": -600}):
        assert not hr_stats.je_dost_dlha(zla), zla
    assert not hr_stats.je_dost_dlha(None)
    assert not hr_stats.je_dost_dlha("relacia")


def test_tri_kratke_relacie_nenahradia_zalohu_kritickeho_tepu():
    """Tri dvojminutove relacie (parovanie hodiniek, tep pri pokoji) maju
    spolu 360 bodov krivky - nad `KRITICKY_MIN_BODOV`. Do 0.2.1 z nich vysla
    hranica 80 namiesto zalohy 110."""
    kratke = [_relacia(2, 1.0) for _ in range(3)]
    assert sum(len(r["curve"]) for r in kratke) >= hr_stats.KRITICKY_MIN_BODOV
    assert hr_stats.dynamicky_kriticky(kratke) == hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(
        kratke, baseline=70.0) == hr_stats.KRITICKY_ZALOHA
    # Kontrola, ze test meria dlzku, nie body: ta ista krivka s 5 minutami
    # uz vlastnu hranicu da.
    dlhe = [dict(r, duration_s=hr_stats.PRAH_MIN_TRVANIE_S) for r in kratke]
    assert hr_stats.dynamicky_kriticky(dlhe) != hr_stats.KRITICKY_ZALOHA


def test_kratke_relacie_sa_do_troch_potrebnych_nerataju():
    dve_dlhe = [_relacia(20, 1.0) for _ in range(2)]
    kratke = [_relacia(3, 1.0) for _ in range(3)]
    assert hr_stats.dynamicky_kriticky(dve_dlhe + kratke) == hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(
        dve_dlhe + kratke + [_relacia(20, 1.0)]) != hr_stats.KRITICKY_ZALOHA


def test_kratke_relacie_nevytlacia_dlhe_z_okna_poslednych_dvadsiatich():
    """Filtruje sa PRED vyberom poslednych `KRITICKY_Z_RELACII` - rovnako ako
    pri prahu. Inak by par kratkych relacii na konci vyradilo dlhe vecery."""
    # Prvych pat dlhych vecerov je napatejsich. Keby sa najprv rezalo okno
    # a az potom filtrovalo, vypadli by prave oni - s rovnakymi krivkami by
    # to test nepoznal (15 rovnakych vecerov da ten isty percentil ako 20).
    napate = [_relacia(20, 1.0, curve=[120.0] * 400) for _ in range(5)]
    dlhe = napate + [_relacia(20, 1.0)
                     for _ in range(hr_stats.KRITICKY_Z_RELACII - 5)]
    kratke = [_relacia(2, 1.0, curve=[150.0] * 120) for _ in range(5)]
    assert hr_stats.dynamicky_kriticky(dlhe + kratke) == \
        hr_stats.dynamicky_kriticky(dlhe)
    # Predpoklad testu: bez napatych vecerov vyjde ina hranica.
    assert hr_stats.dynamicky_kriticky(dlhe[5:]) != \
        hr_stats.dynamicky_kriticky(dlhe)


def test_pokazene_trvanie_nezhodi_vypocet_ani_neuci():
    """`float("dlho")` doteraz v prahu vyhodil vynimku - a v
    `_open_hr_session` by s nou padla aj dlhodoba zakladna."""
    dobre = [_relacia(10, 1.0) for _ in range(3)]
    zla = _relacia(10, 1.0, duration_s="dlho")
    assert _prah(dobre + [zla]) == _prah(dobre)
    assert hr_stats.dynamicky_kriticky(dobre + [zla]) == \
        hr_stats.dynamicky_kriticky(dobre)


def test_zakladna_berie_aj_kratke_relacie():
    """Pravidlo 5 minut plati pre hranice, nie pre pokojovu zakladnu."""
    kratke = [_relacia(2, 1.0, baseline_bpm=b) for b in (60.0, 62.0, 64.0)]
    assert hr_stats.dlhodoba_zakladna(kratke) is not None


# --------------------------------------------------------------------------
# 1. Svet: odpoved v dotazniku je oprava - aj pre ucenie
# --------------------------------------------------------------------------

def test_praca_odpovedana_ako_hra_sa_uci_ako_hra():
    """Zabudol som prepnut z Prace a hral som - odpoviem "Hral som" a vecer
    sa rata do kritickeho tepu aj prahu zataze Hry."""
    hra = [_relacia(15, 0.95, world="play") for _ in range(2)]
    oprava = _relacia(15, 0.95, world="work", activity="play")
    herna = hr_stats.sessions_in_world(hra + [oprava], "play")
    assert herna == hra + [oprava]
    assert hr_stats.dynamicky_kriticky(herna) != hr_stats.KRITICKY_ZALOHA
    assert _prah(herna) is not None
    # bez odpovede ostava pecat zo startu - a hra ma len dve relacie
    bez_odpovede = dict(oprava)
    del bez_odpovede["activity"]
    herna = hr_stats.sessions_in_world(hra + [bez_odpovede], "play")
    assert herna == hra
    assert hr_stats.dynamicky_kriticky(herna) == hr_stats.KRITICKY_ZALOHA
    assert _prah(herna) is None


def test_hra_odpovedana_ako_praca_z_ucenia_vypadne():
    hra = [_relacia(15, 0.95, world="play") for _ in range(2)]
    praca = _relacia(15, 0.95, world="play", activity="work")
    herna = hr_stats.sessions_in_world(hra + [praca], "play")
    assert herna == hra
    assert hr_stats.dynamicky_kriticky(herna) == hr_stats.KRITICKY_ZALOHA
    assert _prah(herna) is None
    # zakladna ide zo vsetkeho - telo je jedno, svet ju nemeni
    assert hr_stats.dlhodoba_zakladna(hra + [praca]) is not None
