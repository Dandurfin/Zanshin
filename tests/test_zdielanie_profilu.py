# -*- coding: utf-8 -*-
"""Zdieľanie profilu kódom (Spúšťače -> Exportovať profil).

Kód sa posiela iným ľuďom. Predtým niesol celé sloty vrátane absolútnych
ciest k nahrávkam (C:\\Users\\<meno>\\AppData\\...) - kto kód zdieľal,
prezradil meno účtu vo Windows. Import navyše nechal cudziu cestu, ak
`sfx_key` nebol "__custom__", a tá sa prehrala, keby na tomto PC existovala.
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from settings_model import (DEFAULT_SLOT, ZDIELANE_POLIA_SLOTU,  # noqa: E402
                            normalize_slot, slot_na_zdielanie, slot_zo_zdielania)

CESTA = "C:\\Users\\hrac\\AppData\\Roaming\\Zanshin\\audio\\rec_abc.wav"


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8-sig") as fh:
        return fh.read()


def _moj_slot(**kw):
    s = normalize_slot(dict(text="Výdych", audio_path=CESTA, voice_path=CESTA,
                            sfx_key="__custom__", uid="abc123abc123",
                            key_repr="f", delay=2.0, every_n=3))
    s.update(kw)
    return s


def test_export_vynecha_cesty_uid_a_mrtve_polia():
    von = slot_na_zdielanie(_moj_slot())
    assert set(von) <= set(ZDIELANE_POLIA_SLOTU)
    for mrtve in ("audio_path", "voice_path", "uid", "key_type", "key_repr",
                  "cooldown", "delay", "every_n", "repeat", "repeat_gap", "jitter"):
        assert mrtve not in von, mrtve
    assert von["text"] == "Výdych"
    assert von["sfx_key"] == "", "vlastný zvuk je súbor na tomto PC"


def test_zdielane_polia_su_skutocne_polia_slotu():
    assert set(ZDIELANE_POLIA_SLOTU) <= set(DEFAULT_SLOT)


def test_kod_profilu_neprezradi_meno_uctu():
    """Rovnaké zloženie ako `export_profile_code`."""
    payload = {"name": "Môj", "slots": [slot_na_zdielanie(_moj_slot())]}
    kod = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    text = base64.b64decode(kod).decode("utf-8")
    assert "Users" not in text and "hrac" not in text and "abc123" not in text


def test_import_vzdy_vynuluje_cesty_aj_bez_vlastneho_zvuku():
    """Starý kód (s cestami) a prázdny `sfx_key`: cesta sa predtým nechala."""
    stary_kod = dict(_moj_slot(), sfx_key="")
    slot = slot_zo_zdielania(stary_kod)
    assert slot["audio_path"] == "" and slot["voice_path"] == ""
    assert slot["uid"] and slot["uid"] != "abc123abc123", "čerstvé uid"
    assert slot["text"] == "Výdych"
    assert slot_zo_zdielania("nezmysel") is None


def test_import_prevezme_zmysluplne_polia():
    cudzi = {"text": "Čeľusť", "mode": "sfx", "sfx_key": "zen:earth_thud",
             "enabled": False, "voice_edge": "sk-SK-ViktoriaNeural"}
    slot = slot_zo_zdielania(cudzi)
    for k, v in cudzi.items():
        assert slot[k] == v, k


def test_app_exportuje_a_importuje_cez_zdielanie():
    src = _read("app.py")
    exp = src[src.index("    def export_profile_code("):]
    exp = exp[:exp.index("\n    def ", 5)]
    assert "slot_na_zdielanie(s) for s in profile[\"slots\"]" in exp
    assert '"slots": profile["slots"]' not in exp
    imp = src[src.index("    def import_profile_from_code("):]
    imp = imp[:imp.index("\n    def ", 5)]
    assert "slot_zo_zdielania(" in imp
