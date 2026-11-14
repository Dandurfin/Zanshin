# -*- coding: utf-8 -*-
"""Prepnutie sveta pocas sledovania a priprava prirodzeneho hlasu (0.2.2
davka 4) - kontrola skeptika.

Relacia drzi svet, v ktorom zacala (`_hlasky_hovoria` cita `_session_world`).
Relacia z Prace teda mlci aj po prepnuti na Hru - ale DALSIA relacia v Hre
uz hovori. Priprava hlasu (`pregenerate`) pocas sledovania na siet nejde a
bez odkladu by sa po sledovani nespustila vobec: prva herna relacia by
hovorila nahradnym hlasom. Synteticke texty, nic sa nikam neposiela."""
import test_021b_pregen_len_co_zaznie as pregen


def _atrapa(monkeypatch, svet_relacie="work", svet="play", pocuva=True):
    a = pregen._atrapa(monkeypatch, pregen._tri(), pocuva=pocuva, svet=svet)
    a._hr_session_open = pocuva
    a._session_world = svet_relacie
    return a


def test_relacia_z_prace_prepnuta_na_hru_pripravi_hlas_po_sledovani(monkeypatch):
    a = _atrapa(monkeypatch)
    a.pregenerate()                      # napr. `set_world` -> `schedule_pregenerate`
    assert a.vlakna == [] and a.posielane == [], "pocas sledovania na siet nie"
    assert a._pregen_po_hre is True
    # sledovanie skoncilo (`stop_listening` -> `_dopriprav_hlasky_po_hre`)
    a.listening = False
    a._hr_session_open = False
    a._dopriprav_hlasky_po_hre()
    a.root.spusti()
    assert len(a.vlakna) == 1, "priprava sa po sledovani spusti"
    pregen._dobehni(a)
    assert a.posielane, "hlasky pre Hru sa pripravia"


def test_bez_zmeny_sveta_sa_nic_neodklada(monkeypatch):
    # relacia v Praci, pohlad v Praci: hlasky nehovoria ani dalej
    a = _atrapa(monkeypatch, svet_relacie="work", svet="work")
    a.pregenerate()
    assert a._pregen_po_hre is False and a.vlakna == []


def test_mimo_sledovania_ani_v_praci_nic_neodklada(monkeypatch):
    a = _atrapa(monkeypatch, svet_relacie="play", svet="work", pocuva=False)
    a.pregenerate()
    assert a._pregen_po_hre is False and a.vlakna == []
