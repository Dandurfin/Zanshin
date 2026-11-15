# -*- coding: utf-8 -*-
"""Switching the world while watching and natural voice preparation (0.3
batch 4) - a skeptic's check.

A session keeps the world it started in (`_hlasky_hovoria` reads
`_session_world`). So a session from Work stays silent even after
switching to Play - but the NEXT session in Play already speaks. Voice
preparation (`pregenerate`) does not go to the network while watching,
and without postponing it would not start after watching at all: the
first play session would speak with the fallback voice. Synthetic texts,
nothing is sent anywhere."""
import test_021b_pregen_len_co_zaznie as pregen


def _atrapa(monkeypatch, svet_relacie="work", svet="play", pocuva=True):
    a = pregen._atrapa(monkeypatch, pregen._tri(), pocuva=pocuva, svet=svet)
    a._hr_session_open = pocuva
    a._session_world = svet_relacie
    return a


def test_relacia_z_prace_prepnuta_na_hru_pripravi_hlas_po_sledovani(monkeypatch):
    a = _atrapa(monkeypatch)
    a.pregenerate()                      # e.g. `set_world` -> `schedule_pregenerate`
    assert a.vlakna == [] and a.posielane == [], "pocas sledovania na siet nie"
    assert a._pregen_po_hre is True
    # watching ended (`stop_listening` -> `_dopriprav_hlasky_po_hre`)
    a.listening = False
    a._hr_session_open = False
    a._dopriprav_hlasky_po_hre()
    a.root.spusti()
    assert len(a.vlakna) == 1, "priprava sa po sledovani spusti"
    pregen._dobehni(a)
    assert a.posielane, "hlasky pre Hru sa pripravia"


def test_bez_zmeny_sveta_sa_nic_neodklada(monkeypatch):
    # a session in Work, view in Work: cues stay silent from then on too
    a = _atrapa(monkeypatch, svet_relacie="work", svet="work")
    a.pregenerate()
    assert a._pregen_po_hre is False and a.vlakna == []


def test_mimo_sledovania_ani_v_praci_nic_neodklada(monkeypatch):
    a = _atrapa(monkeypatch, svet_relacie="play", svet="work", pocuva=False)
    a.pregenerate()
    assert a._pregen_po_hre is False and a.vlakna == []
