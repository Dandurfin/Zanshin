# -*- coding: utf-8 -*-
"""Unsaved session (hr_session_pending.json, 0.3 batch 4) - skeptic check:
the added session goes into history at ITS OWN PLACE by time, and an
unreadable file of pending sessions is neither deleted nor overwritten.

History takes the last session in the file as the newest (detail in
History, table from the end). An unsaved session is added only after the
NEXT successfully saved one - without sorting it in, it would stand after a
newer one in the history and pose as the last evening. Synthetic data in a
tmp folder only."""
import json
import os
import time

import data_io
import hr_stats

import test_022b_data_vypnutie as vypnutie


def _relacia(started, minut=20, **k):
    s = {"started": float(started), "duration_s": minut * 60.0, "samples": minut * 30,
         "avg_bpm": 80, "max_bpm": 101, "min_bpm": 64, "peak_stress": 40}
    s.update(k)
    return s


def _zaciatky(cesta):
    return [s["started"] for s in hr_stats.load_sessions(cesta)]


# --------------------------------------------------------------------------
# Order in the history
# --------------------------------------------------------------------------

def test_doplnena_starsia_relacia_ide_na_svoje_miesto(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    teraz = time.time()
    assert hr_stats.save_session(cesta, _relacia(teraz - 86400))
    # A was not saved (full disk) - set aside; B was then saved normally
    assert hr_stats.zapis_cakajucu(cesta, _relacia(teraz - 7200))
    assert hr_stats.save_session(cesta, _relacia(teraz - 3600))
    doplnene = hr_stats.obnov_cakajuce(cesta)
    assert len(doplnene) == 1
    zaciatky = _zaciatky(cesta)
    assert zaciatky == sorted(zaciatky), "doplnena relacia nesmie stat za novsou"
    assert zaciatky[-1] == teraz - 3600, "posledna v subore = naozaj najnovsia"
    assert hr_stats.load_sessions(cesta)[1]["recovered"] is True


def test_zatvorenie_relacie_doplni_cakajucu_pred_seba(tmp_path):
    """The real `_close_hr_session`: saves the running session and only after
    it adds the pending one (the disk is writable again) - the order in the
    file must be right."""
    a = vypnutie._appka(tmp_path)
    teraz = time.time()
    hr_stats.save_session(a.hr_sessions_path, _relacia(teraz - 2 * 86400))
    hr_stats.zapis_cakajucu(a.hr_sessions_path, _relacia(teraz - 3 * 3600))
    beziaca = a.hr_stats.session_start
    a._close_hr_session()
    zaciatky = _zaciatky(a.hr_sessions_path)
    assert len(zaciatky) == 3
    assert zaciatky == sorted(zaciatky)
    assert abs(zaciatky[-1] - beziaca) < 1e-3, "najnovsia je prave zatvorena relacia"
    assert not os.path.exists(hr_stats.cesta_cakajucej(a.hr_sessions_path))


def test_bezna_relacia_sa_dalej_pripaja_na_koniec(tmp_path):
    """Sorting in applies only to added (`recovered`) sessions - normal saving
    does not change (e.g. a clock that ran fast last time)."""
    cesta = str(tmp_path / "hr_sessions.json")
    hr_stats.save_session(cesta, _relacia(2.0e9))
    hr_stats.save_session(cesta, _relacia(1.9e9))
    assert _zaciatky(cesta) == [2.0e9, 1.9e9]


def test_zaradenie_zvladne_pokazene_casy():
    data = [{"started": 10.0}, {"started": "x"}, {"started": 30.0}, {"started": 20.0}]
    hr_stats._zarad_poslednu(data)
    assert [d["started"] for d in data] == [10.0, "x", 20.0, 30.0]
    data = [{"started": 10.0}, {"started": None}]
    hr_stats._zarad_poslednu(data)
    assert data == [{"started": 10.0}, {"started": None}], "bez casu ostava na konci"
    hr_stats._zarad_poslednu([])                 # an empty list does not crash


# --------------------------------------------------------------------------
# Unreadable file of pending sessions
# --------------------------------------------------------------------------

POKAZENE = '[{"started": 1800000000.0, "duration_s": 12'


def _odlozene(tmp_path):
    return sorted(p for p in os.listdir(tmp_path)
                  if p.startswith(hr_stats.CAKAJUCA_MENO + ".corrupt-"))


def test_start_necitatelny_subor_nezmaze_ale_odlozi(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    with open(hr_stats.cesta_cakajucej(cesta), "w", encoding="utf-8") as fh:
        fh.write(POKAZENE)
    assert hr_stats.obnov_cakajuce(cesta) == []
    (odlozeny,) = _odlozene(tmp_path)
    with open(tmp_path / odlozeny, encoding="utf-8") as fh:
        assert fh.read() == POKAZENE, "obsah sa da zachranit"
    assert not os.path.exists(hr_stats.cesta_cakajucej(cesta))


def test_nova_neulozena_relacia_neprepise_necitatelny_subor(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    with open(hr_stats.cesta_cakajucej(cesta), "w", encoding="utf-8") as fh:
        fh.write(POKAZENE)
    nova = _relacia(time.time() - 600)
    assert hr_stats.zapis_cakajucu(cesta, nova)
    (odlozeny,) = _odlozene(tmp_path)
    with open(tmp_path / odlozeny, encoding="utf-8") as fh:
        assert fh.read() == POKAZENE
    assert [s["started"] for s in hr_stats.nacitaj_cakajuce(cesta)] == [nova["started"]]


def test_prazdny_zoznam_sa_zmaze_bez_odkladania(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    with open(hr_stats.cesta_cakajucej(cesta), "w", encoding="utf-8") as fh:
        json.dump([], fh)
    assert hr_stats.obnov_cakajuce(cesta) == []
    assert not os.path.exists(hr_stats.cesta_cakajucej(cesta))
    assert _odlozene(tmp_path) == []


def test_zmazat_historiu_zmaze_aj_odlozeny_pokazeny_subor(tmp_path):
    odlozeny = tmp_path / (hr_stats.CAKAJUCA_MENO + ".corrupt-1800000000")
    odlozeny.write_text(POKAZENE, encoding="utf-8")
    plan = {os.path.normcase(os.path.abspath(p["path"]))
            for p in data_io.delete_plan(str(tmp_path), ())}
    assert os.path.normcase(os.path.abspath(str(odlozeny))) in plan
