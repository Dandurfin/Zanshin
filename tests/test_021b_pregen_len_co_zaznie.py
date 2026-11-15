# -*- coding: utf-8 -*-
"""0.2.1: Microsoft gets only the cue texts the natural voice will really say.

Two bugs in the Edge voice preparation (`pregen_jobs` / `pregenerate`,
app_audio.py):

  1. The texts of ALL slots with voice were sent for synthesis - also a
     switched-off cue (`_dalsi_cue_slot` skips it in game), cues with
     their own recording (`_speak_text` plays the recording, not TTS) and
     the extra slot from 0.1 (index 4+, "+ Pridať spúšťač" - the app does
     not fire it by itself). Now only `_slot_na_pripravu`: an enabled
     category with voice, with text and without a valid recording.
     Enabling a cue (`SlotCard.on_enabled_change`) and deleting a
     recording start the preparation again - like the other changes,
     including "nothing new while listening", the voice style and the
     Play world.

  2. Switching to the Windows voice (`on_engine_change`) did not increase
     `_pregen_seq`, so a running preparation sent the rest to Microsoft
     too. The same when switching to the style without words / to Work /
     when turning off all cues: `pregenerate` with an empty list did not
     increase `seq` at all. Now every change that schedules preparation
     stops the old preparation AT ONCE (`_zrus_rozbehnutu_pripravu`); a
     cue already in flight finishes - just as when listening is turned on.
"""
import os
import sys
import threading
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
from settings_model import (ENGINE_EDGE, ENGINE_SAPI, MODE_COMBO,  # noqa: E402
                            MODE_SFX, MODE_TTS, engine_labels)

HLAS = "en-GB-SoniaNeural"


def _app():
    import app as app_mod
    return app_mod


def _slot(index, text, mode=MODE_TTS, enabled=True, voice_path=""):
    return types.SimpleNamespace(index=index, mode=mode, text_value=text,
                                 voice_edge="", voice_sapi="",
                                 enabled_value=enabled, voice_path=voice_path,
                                 refresh_summary=lambda: None)


class _Root:
    def __init__(self):
        self.ulohy = []

    def after(self, ms, fn):
        self.ulohy.append((ms, fn))
        return len(self.ulohy)

    def after_cancel(self, job):
        pass

    def spusti(self):
        """Runs the scheduled tasks (the `schedule_pregenerate` delay)."""
        ulohy, self.ulohy = self.ulohy, []
        for _ms, fn in ulohy:
            fn()


def _atrapa(monkeypatch, slots, pocuva=False, styl="voice", svet="play"):
    """A dummy with the real preparation (`pregenerate`,
    `schedule_pregenerate`, `pregen_jobs`, `on_engine_change`...). The
    thread is not started, only recorded (`a.vlakna`); the cache remembers
    what was "sent" (`a.posielane`)."""
    import audio_engine
    app_mod = _app()
    import app_audio
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    D = app_mod.DandurfApp
    a = types.SimpleNamespace(
        cue_style=styl, world=svet, edge_voice_id=HLAS, slots=slots,
        engine=ENGINE_EDGE, engine_pref=ENGINE_EDGE, rate_value=0,
        saved_voice_id="sapi", _pregen_job=None, _pregen_seq=0,
        _pregen_po_hre=False, listening=pocuva,
        pal={"success": "g", "warn": "y", "danger": "r", "text_dim": "d"},
        stavy=[], posielane=[], hotove=set(), vlakna=[], ui=[], logy=[],
        hovorene=[], root=_Root(),
        # in-game pictures on (default) - a cue with its picture off is not
        # prepared, that is guarded by test_021c_pregen_obrazok.py
        overlay_configs=[{"enabled": True} for _ in range(4)])

    def ensure(text, voice, rate, abort=None):
        if text in a.hotove:
            return "hotova.mp3"             # from the cache - does not go to the network
        a.posielane.append(text)
        a.hotove.add(text)
        return "hotova.mp3"

    a.edge_cache = types.SimpleNamespace(
        has=lambda text, voice, rate: text in a.hotove, ensure=ensure)
    a.set_edge_status = lambda text, color=None: a.stavy.append(text)
    a.ui_call = a.ui.append
    a.log_threadsafe = a.logy.append
    a.log = lambda *_x: None
    a.save_settings = lambda: None
    a._prune_cache = lambda *_x: None
    a.refresh_edge_banner = a.refresh_voice_box = lambda: None
    a.refresh_slot_summaries = lambda: None
    a.audio = types.SimpleNamespace(speak=lambda *x: a.hovorene.append(x))
    for meno in ("pregenerate", "schedule_pregenerate", "pregen_jobs",
                 "_dopriprav_hlasky_po_hre", "_slot_na_pripravu",
                 "_slot_voice_clip", "_hlasky_hovoria", "_ma_obrazok_v_hre",
                 "_zrus_rozbehnutu_pripravu", "on_engine_change"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    # `pregenerate` reads `threading` from the app_audio module (module
    # docstring)
    monkeypatch.setattr(app_audio.threading, "Thread",
                        lambda *x, **k: a.vlakna.append(k) or types.SimpleNamespace(
                            start=lambda: None))
    return a


def _dobehni(a):
    """Runs the body of the last preparation thread in place (no thread)."""
    a.vlakna[-1]["target"]()


def _prepni_na_windows(a):
    a.engine_var = types.SimpleNamespace(
        get=lambda: engine_labels()[ENGINE_SAPI])
    a.on_engine_change()


# --------------------------------------------------------------------------
# 1. What gets prepared
# --------------------------------------------------------------------------

def test_pripravuju_sa_len_hlasky_ktore_edge_v_hre_povie(monkeypatch, tmp_path):
    nahravka = tmp_path / "voice_abc.wav"
    nahravka.write_bytes(b"RIFF")
    a = _atrapa(monkeypatch, [
        _slot(0, "Breathe", MODE_COMBO),
        _slot(1, "Jaw", enabled=False),                       # switched off
        _slot(2, "Release", voice_path=str(nahravka)),       # own recording
        _slot(3, "Ground", voice_path=str(tmp_path / "zmazana.wav")),
        _slot(4, "Stary spustac z 0.1"),                      # extra slot
        _slot(5, "Druhy z 0.1", MODE_COMBO, enabled=False),
    ])
    # A recording whose file has disappeared is not played
    # (`_slot_voice_clip`) - TTS says the cue, so it must be prepared.
    assert a.pregen_jobs() == [("Breathe", HLAS), ("Ground", HLAS)]

    a.pregenerate()
    _dobehni(a)
    assert a.posielane == ["Breathe", "Ground"]
    for text in ("Jaw", "Release", "Stary spustac z 0.1", "Druhy z 0.1"):
        assert text not in a.posielane, text


def test_zvuk_bez_slov_a_prazdny_text_sa_nepripravuju(monkeypatch):
    a = _atrapa(monkeypatch, [_slot(0, "Breathe", MODE_SFX),
                              _slot(1, "   ", MODE_TTS)])
    assert a.pregen_jobs() == []


def test_vsetky_vypnute_nic_neposle_ani_nezacne(monkeypatch):
    a = _atrapa(monkeypatch, [_slot(i, f"s{i}", enabled=False) for i in range(4)])
    a.pregenerate(force=True)
    assert a.vlakna == [] and a.posielane == []
    assert a.stavy == [""], "stav nesľubuje prípravu"


# --------------------------------------------------------------------------
# 1b. Enabling a cue / deleting a recording starts the preparation again
# --------------------------------------------------------------------------

def _zapni(a, slot, zapnut=True):
    """Switch on the cue card - the real `SlotCard.on_enabled_change`."""
    import ui_dialogs
    slot.app = a
    slot.enabled_var = types.SimpleNamespace(get=lambda: zapnut)
    ui_dialogs.SlotCard.on_enabled_change(slot)


def test_zapnutie_hlasky_ju_pripravi(monkeypatch):
    a = _atrapa(monkeypatch, [_slot(0, "Breathe"), _slot(1, "Jaw", enabled=False)])
    a.pregenerate()
    _dobehni(a)
    assert a.posielane == ["Breathe"]

    _zapni(a, a.slots[1])
    assert a.slots[1].enabled_value is True
    assert [ms for ms, _fn in a.root.ulohy] == [200], "príprava je naplánovaná"
    a.root.spusti()
    _dobehni(a)
    assert a.posielane == ["Breathe", "Jaw"], "posiela sa len chýbajúca hláška"
    assert a.stavy[-1] == i18n.tr("edge.generating")


def test_zapnutie_pocas_hry_pocka_na_koniec_pocuvania(monkeypatch):
    a = _atrapa(monkeypatch, [_slot(0, "Breathe"), _slot(1, "Jaw", enabled=False)],
                pocuva=True)
    a.hotove.add("Breathe")
    _zapni(a, a.slots[1])
    a.root.spusti()
    assert a.vlakna == [] and a.posielane == [], "počas hry sa na Microsoft nejde"
    assert a._pregen_po_hre is True
    assert a.stavy[-1] == i18n.tr("edge.after_game")

    a.listening = False
    a._dopriprav_hlasky_po_hre()
    a.root.spusti()
    _dobehni(a)
    assert a.posielane == ["Jaw"]


def test_zapnutie_v_style_bez_slov_ani_v_praci_nic_neposle(monkeypatch):
    for styl, svet in (("sound", "play"), ("visual", "play"), ("voice", "work")):
        a = _atrapa(monkeypatch, [_slot(0, "Breathe", enabled=False)],
                    styl=styl, svet=svet)
        _zapni(a, a.slots[0])
        a.root.spusti()
        assert a.vlakna == [] and a.posielane == [], (styl, svet)


def test_zmazanie_nahravky_hlasku_pripravi(monkeypatch, tmp_path):
    """Recording back to voice - the real `clear_voice` / `_commit_voice`."""
    import ui_dialogs
    nahravka = tmp_path / "voice_abc.wav"
    nahravka.write_bytes(b"RIFF")
    a = _atrapa(monkeypatch, [_slot(0, "Breathe", voice_path=str(nahravka))])
    assert a.pregen_jobs() == []

    D = ui_dialogs.SlotSettingsDialog
    dialog = types.SimpleNamespace(
        slot=a.slots[0], app=a, _voice_clip_text=lambda: "",
        voice_clip_status=types.SimpleNamespace(configure=lambda **_k: None))
    dialog._commit_voice = types.MethodType(D._commit_voice, dialog)
    D.clear_voice(dialog)
    assert a.slots[0].voice_path == ""
    a.root.spusti()
    _dobehni(a)
    assert a.posielane == ["Breathe"]


def test_test_vypnutej_alebo_starej_hlasky_zaznie_cez_windows(monkeypatch):
    """The Test button on a cue that is not prepared: the Windows voice
    sounds, nothing is prepared and the journal does not promise a
    preparation that will not come."""
    D = _app().DandurfApp
    for pocuva in (False, True):
        for slot in (_slot(0, "Jaw", enabled=False), _slot(4, "Stary z 0.1")):
            a = _atrapa(monkeypatch, [slot], pocuva=pocuva)
            D._speak_text(a, slot.text_value, slot)
            assert a.ui == [] and a.logy == [], (pocuva, slot.index)
            assert a._pregen_po_hre is False
            assert a.hovorene == [(slot.text_value, "sapi")]

    # An enabled category that is not prepared yet is prepared as before.
    slot = _slot(0, "Breathe")
    a = _atrapa(monkeypatch, [slot])
    D._speak_text(a, "Breathe", slot)
    assert a.ui == [a.pregenerate]
    assert a.logy == [i18n.tr("log.edge_not_cached")]


# --------------------------------------------------------------------------
# 2. Switching to the Windows voice stops the rest of a running preparation
# --------------------------------------------------------------------------

def _tri():
    return [_slot(0, "Breathe"), _slot(1, "Jaw"), _slot(2, "Release")]


def test_prepnutie_na_windows_uprostred_pripravy_zvysok_neposle(monkeypatch):
    a = _atrapa(monkeypatch, _tri())

    def posli(text, voice, rate, abort=None):
        a.posielane.append(text)
        if len(a.posielane) == 1:
            _prepni_na_windows(a)          # the player switches during the first cue
        return "hotova.mp3"

    a.edge_cache.ensure = posli
    a.pregenerate()
    _dobehni(a)
    assert a.engine == ENGINE_SAPI
    assert a.posielane == ["Breathe"], "ďalšia hláška už na sieť nešla"
    assert a.stavy[-1] == "", "stav nehlási prípravu ani chybu"
    assert a.ui == [], "nič sa neplánuje znova"


def test_hlaska_cakajuca_na_zamku_sa_po_prepnuti_vzda(monkeypatch):
    """`abort` (asks after getting the lock, right before sending) returns
    True when the voice has meanwhile been switched to Windows."""
    a = _atrapa(monkeypatch, _tri())
    odpovede = []

    def ensure(text, voice, rate, abort=None):
        if text == "Breathe":
            a.posielane.append(text)
            return "hotova.mp3"
        _prepni_na_windows(a)              # while it was waiting on the lock
        odpovede.append(abort())
        return None

    a.edge_cache.ensure = ensure
    a.pregenerate()
    _dobehni(a)
    assert odpovede == [True]
    assert a.posielane == ["Breathe"]
    assert i18n.tr("edge.partial", ok=1, total=3) not in a.stavy


def test_prepnutie_na_windows_so_skutocnou_cache_a_vlaknom(monkeypatch, tmp_path):
    """Real `EdgeTTSCache` and a real thread; instead of Microsoft a dummy
    `edge_tts.Communicate`. A cue in flight finishes - the next one does
    not start."""
    import asyncio
    import audio_engine
    realne_vlakno = threading.Thread
    a = _atrapa(monkeypatch, _tri())
    leti, pusti = threading.Event(), threading.Event()
    odoslane = []

    class _Hovor:
        def __init__(self, text, voice, rate=None):
            odoslane.append(text)

        async def save(self, cesta):
            if len(odoslane) == 1:
                leti.set()
                assert pusti.wait(5)
            with open(cesta, "wb") as fh:
                fh.write(b"mp3")

    monkeypatch.setattr(audio_engine, "asyncio", asyncio)
    monkeypatch.setattr(audio_engine, "edge_tts",
                        types.SimpleNamespace(Communicate=_Hovor))
    monkeypatch.setattr(audio_engine, "TTS_CACHE_DIR", str(tmp_path))
    a.edge_cache = audio_engine.EdgeTTSCache(lambda *_: None)

    a.pregenerate()
    vlakno = realne_vlakno(target=a.vlakna[0]["target"])
    vlakno.start()
    assert leti.wait(5)
    _prepni_na_windows(a)                  # in the middle of the first cue
    pusti.set()
    vlakno.join(5)
    assert not vlakno.is_alive()
    assert odoslane == ["Breathe"], "po prepnutí nezačala žiadna požiadavka"
    assert a.edge_cache.has("Breathe", HLAS, 0), "hláška, čo letela, dobehla"


def test_navrat_na_prirodzeny_hlas_dopripravi_zvysok(monkeypatch):
    a = _atrapa(monkeypatch, _tri())

    def posli(text, voice, rate, abort=None):
        if text in a.hotove:
            return "hotova.mp3"
        a.posielane.append(text)
        a.hotove.add(text)
        if len(a.posielane) == 1:
            _prepni_na_windows(a)
        return "hotova.mp3"

    a.edge_cache.ensure = posli
    a.pregenerate()
    _dobehni(a)
    assert a.posielane == ["Breathe"]

    a.engine_var = types.SimpleNamespace(get=lambda: engine_labels()[ENGINE_EDGE])
    a.edge_voice_map = {"Sonia": HLAS}
    a.on_engine_change()
    _dobehni(a)
    assert a.posielane == ["Breathe", "Jaw", "Release"]


# --------------------------------------------------------------------------
# 2b. Other changes after which a cue will not sound stop the preparation too
# --------------------------------------------------------------------------

def _styl_bez_slov(a):
    """The real `_on_cue_style_label` (Settings -> Sound)."""
    D = _app().DandurfApp
    a._nastav_styl_hlasky = lambda styl: setattr(a, "cue_style", styl)
    D._on_cue_style_label(a, i18n.tr("cue_style.sound"))


def _do_prace(a):
    # `set_world` finally calls `schedule_pregenerate(200)` (test_worlds.py)
    a.world = "work"
    a.schedule_pregenerate(200)


def _vypni_jaw(a):
    _zapni(a, a.slots[1], zapnut=False)


def _nahravka_na_jaw(a):
    """Own recording for Jaw - `_commit_voice` as after recording."""
    import ui_dialogs
    a.slots[1].voice_path = __file__        # an existing file
    D = ui_dialogs.SlotSettingsDialog
    dialog = types.SimpleNamespace(
        slot=a.slots[1], app=a, _voice_clip_text=lambda: "",
        voice_clip_status=types.SimpleNamespace(configure=lambda **_k: None))
    D._commit_voice(dialog, "log")


def test_zmena_uprostred_pripravy_zastavi_zvysok_hned(monkeypatch):
    """After a change that silences the cue, no next request starts, not
    even during the `schedule_pregenerate` delay - the old preparation
    ends at once."""
    for zmena, potom in ((_styl_bez_slov, []), (_do_prace, []),
                         (_vypni_jaw, ["Release"]),
                         (_nahravka_na_jaw, ["Release"])):
        a = _atrapa(monkeypatch, _tri())

        def posli(text, voice, rate, abort=None, a=a, zmena=zmena):
            if text in a.hotove:
                return "hotova.mp3"
            a.posielane.append(text)
            a.hotove.add(text)
            if len(a.posielane) == 1:
                zmena(a)                   # during the first cue
            return "hotova.mp3"

        a.edge_cache.ensure = posli
        a.pregenerate()
        _dobehni(a)
        assert a.posielane == ["Breathe"], zmena.__name__
        # The scheduled run checks what is still allowed and still missing.
        vlakna = len(a.vlakna)
        a.root.spusti()
        if len(a.vlakna) > vlakna:
            _dobehni(a)
        assert a.posielane == ["Breathe"] + potom, zmena.__name__
        assert "Jaw" not in a.posielane


def test_prazdna_priprava_zastavi_rozbehnutu(monkeypatch):
    """A `pregenerate` that finds nothing is needed (e.g. after switching the
    style via a path other than `schedule_pregenerate`) also stops the old
    preparation."""
    a = _atrapa(monkeypatch, _tri())

    def posli(text, voice, rate, abort=None):
        a.posielane.append(text)
        if len(a.posielane) == 1:
            a.cue_style = "visual"
            a.pregenerate()
        return "hotova.mp3"

    a.edge_cache.ensure = posli
    a.pregenerate()
    _dobehni(a)
    assert a.posielane == ["Breathe"]
    assert a.stavy[-1] == ""


def test_windows_hlas_neplanuje_nic_ale_zastavi(monkeypatch):
    """`schedule_pregenerate` schedules nothing with the Windows voice - but
    it still stops a preparation that might be running."""
    a = _atrapa(monkeypatch, _tri())
    a.engine = ENGINE_SAPI
    seq = a._pregen_seq
    a.schedule_pregenerate(200)
    assert a.root.ulohy == [] and a._pregen_seq > seq
