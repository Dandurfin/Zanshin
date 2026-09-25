# -*- coding: utf-8 -*-
"""0.2.1 (zaverecna kontrola): vlastny zvuk z karty hlasky zastavi pripravu.

`SlotCard.choose_file` (vyber suboru) a `SlotCard.record_audio` (nahratie
zvuku) prepnu hlasku s hlasom (TTS) na zvuk bez slov (SFX). Na rozdiel od
`on_mode_change` doteraz nevolali `schedule_pregenerate`, takze rozbehnuta
priprava poslala Microsoftu aj text hlasky, ktora uz nehovori - hoci
PRIVACY/README slubuju, ze po "give it your own recording" priprava hned
konci. Teraz obe cesty pripravu zastavia rovnako ako prepnutie rezimu.

Popri tom: zoznam "kedy sa pripravuje" v README/PRIVACY menuje aj kazdy
start a import profilu - obe pripravu naozaj spustia.
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from settings_model import ENGINE_EDGE, MODE_SFX, MODE_TTS  # noqa: E402

HLAS = "en-GB-SoniaNeural"


class _Root:
    def __init__(self):
        self.ulohy = []

    def after(self, ms, fn):
        self.ulohy.append((ms, fn))
        return len(self.ulohy)

    def after_cancel(self, job):
        pass

    def wait_window(self, _okno):
        pass

    def spusti(self):
        ulohy, self.ulohy = self.ulohy, []
        for _ms, fn in ulohy:
            fn()


def _karta(index, text):
    """Karta hlasky bez Tk: len to, co `choose_file` / `record_audio` citaju."""
    k = types.SimpleNamespace(
        index=index, uid=f"uid{index}", mode=MODE_TTS, text_value=text,
        voice_edge="", voice_sapi="", enabled_value=True, voice_path="",
        sfx_key="", audio_path="", refresh_mode_widgets=lambda: None,
        refresh_summary=lambda: None)
    k.mode_var = types.SimpleNamespace(set=lambda _v: None)
    k.sfx_var = types.SimpleNamespace(set=lambda _v: None)
    k._import_into_store = lambda src, name: src
    return k


def _atrapa(monkeypatch):
    """Ozajstna priprava (`pregenerate`, `schedule_pregenerate`, `pregen_jobs`
    ...) na atrape appky. Vlakno sa nespusta, len zapise (`a.vlakna`)."""
    import app as app_mod
    import app_audio
    import audio_engine
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    D = app_mod.DandurfApp
    a = types.SimpleNamespace(
        cue_style="voice", world="play", edge_voice_id=HLAS,
        engine=ENGINE_EDGE, rate_value=0, _pregen_job=None, _pregen_seq=0,
        _pregen_po_hre=False, listening=False,
        pal={"success": "g", "warn": "y", "danger": "r", "text_dim": "d"},
        posielane=[], hotove=set(), vlakna=[], root=_Root(),
        overlay_configs=[{"enabled": True} for _ in range(4)])
    a.slots = [_karta(0, "Breathe"), _karta(1, "Jaw"), _karta(2, "Release")]
    for karta in a.slots:
        karta.app = a

    def ensure(text, voice, rate, abort=None):
        if text in a.hotove:
            return "hotova.mp3"
        a.posielane.append(text)
        a.hotove.add(text)
        if len(a.posielane) == 1:
            a.zmena()                  # hrac zmeni kartu pocas prvej hlasky
        return "hotova.mp3"

    a.edge_cache = types.SimpleNamespace(
        has=lambda text, voice, rate: text in a.hotove, ensure=ensure)
    a.set_edge_status = lambda *_x, **_k: None
    a.ui_call = lambda fn: None
    a.log_threadsafe = a.log = lambda *_x: None
    a.save_settings = lambda: None
    a._prune_cache = lambda *_x: None
    for meno in ("pregenerate", "schedule_pregenerate", "pregen_jobs",
                 "_slot_na_pripravu", "_slot_voice_clip", "_hlasky_hovoria",
                 "_zrus_rozbehnutu_pripravu", "_ma_obrazok_v_hre"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    monkeypatch.setattr(app_audio.threading, "Thread",
                        lambda *x, **k: a.vlakna.append(k) or types.SimpleNamespace(
                            start=lambda: None))
    return a


def _vyber_subor(monkeypatch, a, karta):
    import ui_dialogs
    monkeypatch.setattr(ui_dialogs.filedialog, "askopenfilename",
                        lambda **_k: "C:/zvuky/gong.wav")
    ui_dialogs.SlotCard.choose_file(karta)


def _nahraj_zvuk(monkeypatch, a, karta):
    import ui_dialogs

    class _Nahravanie:
        def __init__(self, app, n, target):
            self.top = object()
            self.saved_path = target

    monkeypatch.setattr(ui_dialogs, "RecordDialog", _Nahravanie)
    ui_dialogs.SlotCard.record_audio(karta)


def test_vlastny_zvuk_z_karty_zastavi_rozbehnutu_pripravu(monkeypatch):
    for zmena in (_vyber_subor, _nahraj_zvuk):
        a = _atrapa(monkeypatch)
        jaw = a.slots[1]
        a.zmena = lambda a=a, jaw=jaw, zmena=zmena: zmena(monkeypatch, a, jaw)
        a.pregenerate()
        a.vlakna[-1]["target"]()
        assert jaw.mode == MODE_SFX, zmena.__name__
        assert a.posielane == ["Breathe"], (
            zmena.__name__, "hlaska uz nehovori - zvysok pripravy ju neposle")
        # Naplanovana priprava posle len to, co este chyba a smie ist.
        a.root.spusti()
        a.vlakna[-1]["target"]()
        assert a.posielane == ["Breathe", "Release"], zmena.__name__


def _plain(meno):
    koren = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(koren, meno), encoding="utf-8-sig") as fh:
        return " ".join(" ".join(r.lstrip(">") for r in fh.read().splitlines())
                        .split())


def test_dokumenty_menuju_kazdy_start_a_import_profilu():
    """Zoznam "kedy sa pripravuje" v README a PRIVACY je uplny: kazdy start
    s prirodzenym hlasom spusti pripravu chybajucich hlasok a import profilu
    (novy aktivny profil) tiez. Ked sa kod zmeni, tieto vety musia ist prec."""
    from _zdroj_appky import zdroj_metody
    assert "self._load_edge_voices()" in zdroj_metody("__init__")
    assert "def _load_edge_voices(self, pregen=True)" in zdroj_metody("_load_edge_voices")
    assert "self.pregenerate()" in zdroj_metody("_apply_edge_voices")
    assert "self.schedule_pregenerate(200)" in zdroj_metody("import_profile_from_code")

    readme, privacy = _plain("README.md"), _plain("PRIVACY.md")
    assert "That happens at every start (the first time for all of them)" in readme
    assert "only for lines that aren't in the cache yet — at every start" in privacy
    for meno, text in (("README.md", readme), ("PRIVACY.md", privacy)):
        assert "import a profile" in text, meno
