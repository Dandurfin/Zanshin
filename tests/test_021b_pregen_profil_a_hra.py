# -*- coding: utf-8 -*-
"""0.2.1: priprava Edge hlasok po kontrole opravy "len co zaznie".

  1. Novy profil (`create_profile`) meni aktivne hlasky rovnako ako
     prepnutie profilu - no pripravu nespustal. Rozbehnuta priprava
     predosleho profilu tak poslala Microsoftu aj zvysok hlasok, ktore uz
     k aktivnemu profilu nepatria, a zapnute hlasky noveho profilu sa
     nepripravili (v hre zazneli hlasom z Windows).

  2. Poistka proti prilis prisnemu filtru (`_slot_na_pripravu`): kazda
     hlaska, ktoru v hre moze vybrat striedanie kategorii
     (`_dalsi_cue_slot`) a povie ju TTS, sa pripravuje - oprava nesmie
     vyradit hlasku, ktora v hre naozaj zaznie.
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from settings_model import (ENGINE_EDGE, MODE_COMBO, MODE_SFX,  # noqa: E402
                            MODE_TTS, default_slots, normalize_slot)

HLAS = "en-GB-SoniaNeural"


def _slot(index, text, mode=MODE_TTS, enabled=True, voice_path=""):
    return types.SimpleNamespace(index=index, mode=mode, text_value=text,
                                 voice_edge="", voice_sapi="",
                                 enabled_value=enabled, voice_path=voice_path)


class _Root:
    def __init__(self):
        self.ulohy = []

    def after(self, ms, fn):
        self.ulohy.append((ms, fn))
        return len(self.ulohy)

    def after_cancel(self, job):
        pass

    def spusti(self):
        ulohy, self.ulohy = self.ulohy, []
        for _ms, fn in ulohy:
            fn()


def _atrapa(monkeypatch, slots):
    """Ozajstne `pregenerate` / `schedule_pregenerate` / `pregen_jobs` /
    `create_profile`; vlakno sa len zapise a spusti sa rucne (`_dobehni`)."""
    import app as app_mod
    import app_audio
    import audio_engine
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    D = app_mod.DandurfApp
    a = types.SimpleNamespace(
        cue_style="voice", world="play", edge_voice_id=HLAS, slots=slots,
        engine=ENGINE_EDGE, rate_value=0, _pregen_job=None, _pregen_seq=0,
        _pregen_po_hre=False, listening=False,
        pal={"success": "g", "warn": "y", "danger": "r", "text_dim": "d"},
        stavy=[], posielane=[], hotove=set(), vlakna=[], root=_Root(),
        profiles=[{"name": "Default", "slots": []}],
        active_profile_name="Default",
        # obrazky v hre zapnute (predvolene) - `_slot_na_pripravu` aj
        # `_dalsi_cue_slot` sa na ne pytaju
        overlay_configs=[{"enabled": True} for _ in range(4)])
    a.edge_cache = types.SimpleNamespace(
        has=lambda text, voice, rate: text in a.hotove)
    a.set_edge_status = lambda text, color=None: a.stavy.append(text)
    a.ui_call = lambda fn: None
    a.log_threadsafe = a.log = lambda *_x: None
    a.save_settings = lambda: None
    a._prune_cache = lambda *_x: None
    a._sync_active_profile_slots = lambda: None
    a.refresh_profile_switch = lambda: None
    # `rebuild_slots` stavia karty z dict-ov profilu; tu staci ich obsah
    a.rebuild_slots = lambda data: setattr(a, "slots", [
        _slot(i, d["text"], d["mode"], d["enabled"], d["voice_path"])
        for i, d in enumerate(data)])
    for meno in ("pregenerate", "schedule_pregenerate", "pregen_jobs",
                 "_slot_na_pripravu", "_slot_voice_clip", "_hlasky_hovoria",
                 "_zrus_rozbehnutu_pripravu", "create_profile",
                 "_dalsi_cue_slot", "_ma_obrazok_v_hre"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    monkeypatch.setattr(app_audio.threading, "Thread",
                        lambda *x, **k: a.vlakna.append(k) or types.SimpleNamespace(
                            start=lambda: None))
    return a


def _dobehni(a):
    a.vlakna[-1]["target"]()


def test_novy_profil_zastavi_pripravu_stareho_a_pripravi_svoj(monkeypatch):
    a = _atrapa(monkeypatch, [_slot(0, "Stary A"), _slot(1, "Stary B"),
                              _slot(2, "Stary C")])

    def posli(text, voice, rate, abort=None):
        if text in a.hotove:
            return "hotova.mp3"
        a.posielane.append(text)
        a.hotove.add(text)
        if len(a.posielane) == 1:
            a.create_profile("Novy")       # hrac zalozi profil pocas pripravy
        return "hotova.mp3"

    a.edge_cache.ensure = posli
    a.pregenerate()
    _dobehni(a)
    assert a.active_profile_name == "Novy"
    assert a.posielane == ["Stary A"], "zvysok stareho profilu na siet nesiel"

    assert [ms for ms, _fn in a.root.ulohy] == [200], "priprava je naplanovana"
    a.root.spusti()
    _dobehni(a)
    nove = [normalize_slot(s)["text"] for s in default_slots()]
    assert a.posielane == ["Stary A"] + nove, "zapnute hlasky noveho profilu"


def test_kazda_hlaska_ktoru_hra_vyberie_a_povie_tts_sa_pripravuje(monkeypatch, tmp_path):
    nahravka = tmp_path / "voice.wav"
    nahravka.write_bytes(b"RIFF")
    slots = [
        _slot(0, "Tazisko", MODE_COMBO),
        _slot(1, "Celust", MODE_TTS),
        _slot(2, "Uvolnenie", MODE_TTS, voice_path=str(nahravka)),
        _slot(3, "Dych", MODE_SFX),
        _slot(4, "Navyse z 0.1"),
    ]
    a = _atrapa(monkeypatch, slots)
    a.overlay_configs = [{"enabled": True} for _ in range(4)]
    jobs = a.pregen_jobs()

    vybrane = {a._dalsi_cue_slot() for _ in range(12)}
    assert vybrane == {0, 1, 2, 3}
    for index in vybrane:
        slot = slots[index]
        povie_tts = (slot.mode in (MODE_TTS, MODE_COMBO)
                     and slot.text_value.strip()
                     and not a._slot_voice_clip(slot))
        if povie_tts:
            assert (slot.text_value, HLAS) in jobs, slot.text_value
    assert jobs == [("Tazisko", HLAS), ("Celust", HLAS)]
