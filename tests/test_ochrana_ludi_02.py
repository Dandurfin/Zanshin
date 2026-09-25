# -*- coding: utf-8 -*-
"""Opravy z triaze 0.2 - veci, na ktore by sa clovek spolahol.

  * vypnute vizualy: jednorazova naprava predvolby ostala naozaj jednorazova
    - kto si vypne vsetky styri, appka ich pri dalsom starte nezapne,
  * dennik nepise „odpocuvanie pozastavene“, ked pocuvanie bezi dalej,
  * uvod pusteny znova z palety zacina na aktualnom svete a hlasitosti,
  * export sa vola podla toho, co naozaj nesie (historia, nie „vsetko“),
  * postrehy a Sprievodca netvrdia zdravotny fakt ani ucinok.
"""
import ast
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
from _zdroj_appky import strom_appky  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# Vypnute vizualy
# --------------------------------------------------------------------------

@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    # `load_settings` byva v mixine app_prefs (PrefsMixin) a cita
    # SETTINGS_PATH zo svojho modulu - presmerovat ho treba tam.
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def nacitaj(obsah):
        with open(cesta, "w", encoding="utf-8") as fh:
            json.dump(obsah, fh)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield nacitaj
    i18n.set_lang(povodny)


def _vypnute():
    return [{"enabled": False, "scale": 1.0, "pos_x": 50.0, "pos_y": 50.0,
             "color": None} for _ in range(4)]


def test_stara_predvolba_sa_narovna_raz(nastavenia):
    d = nastavenia({"lang": "sk", "theme": "zen", "overlay_configs": _vypnute()})
    assert all(c["enabled"] for c in d["overlay_configs"])
    assert d.get("_vizualy_napravene") is True


def test_vedome_vypnute_vizualy_ostanu_vypnute(nastavenia):
    d = nastavenia({"lang": "sk", "theme": "zen", "overlay_configs": _vypnute(),
                    "visuals_repaired": True})
    assert not any(c["enabled"] for c in d["overlay_configs"])
    assert not d.get("_vizualy_napravene")


def test_znacka_napravy_sa_uklada():
    zdroj = ast.unparse(next(
        f for f in ast.walk(strom_appky())
        if isinstance(f, ast.FunctionDef) and f.name == "save_settings"))
    assert "'visuals_repaired': True" in zdroj


# --------------------------------------------------------------------------
# Dennik pri skonceni hry
# --------------------------------------------------------------------------

def _hra_skoncila(pocuva, spustila_appka):
    import app as app_mod
    zapisane, zastavene = [], []
    a = types.SimpleNamespace(
        auto_profile_enabled=True, listening=pocuva,
        _auto_started_listening=spustila_appka,
        log=zapisane.append, stop_listening=lambda: zastavene.append(True))
    app_mod.DandurfApp._handle_game_gone(a)
    return zapisane, zastavene


def test_pozastavene_sa_pise_len_ked_sa_naozaj_zastavilo():
    zapisane, zastavene = _hra_skoncila(pocuva=True, spustila_appka=True)
    assert zastavene and zapisane == [i18n.tr("log.auto_profile_ended")]
    zapisane, zastavene = _hra_skoncila(pocuva=True, spustila_appka=False)
    assert not zastavene and not zapisane, "hrac pocuvanie spustil sam - bezi dalej"


# --------------------------------------------------------------------------
# Uvod znova z palety
# --------------------------------------------------------------------------

def test_uvod_znova_zacina_na_aktualnom_svete_a_hlasitosti():
    telo = ast.unparse(next(
        f for f in ast.walk(strom_appky())
        if isinstance(f, ast.FunctionDef) and f.name == "replay_onboarding"))
    assert "choice=self.theme_key" in telo and "volume=self.volume_value" in telo
    init = next(
        f for f in ast.walk(ast.parse(_read("ui_dialogs.py")))
        if isinstance(f, ast.ClassDef) and f.name == "OnboardingWizard")
    init = next(f for f in init.body
                if isinstance(f, ast.FunctionDef) and f.name == "__init__")
    assert [a.arg for a in init.args.args] == ["self", "root", "choice", "volume"]


# --------------------------------------------------------------------------
# Texty
# --------------------------------------------------------------------------

def test_export_sa_vola_podla_obsahu():
    assert i18n.tr_lang("sk", "data.export.btn") == "Exportovať históriu (JSON)"
    assert i18n.tr_lang("en", "data.export.btn") == "Export history (JSON)"


def test_pomalsie_zotavenie_je_naznak_nie_diagnoza():
    sk = i18n.tr_lang("sk", "insight.hrr_down", delta=5)
    en = i18n.tr_lang("en", "insight.hrr_down", delta=5)
    assert "náznak" in sk and "spánok" in sk
    assert "hint, not a certainty" in en


def test_postrehy_a_uvod_netvrdia_ucinok():
    assert "exactly when breathing helps" not in i18n.tr_lang("en", "insight.over_up",
                                                               minutes=5)
    assert "presne vtedy pomáha" not in i18n.tr_lang("sk", "insight.over_up", minutes=5)
    assert "meant to help" in i18n.tr_lang("en", "ob.step1.body")
    assert "trénuje odísť" not in i18n.tr_lang("sk", "ob.step1.body")
    for jazyk in ("sk", "en"):
        assert "fyziologicky uvoľnený a zároveň" not in i18n.tr_lang(
            jazyk, "guide.philosophy.block3_text")
        assert "can't be physiologically relaxed" not in i18n.tr_lang(
            jazyk, "guide.philosophy.block3_text")
