# -*- coding: utf-8 -*-
"""0.2.1c: a cue with its in-game picture off is not sent to Microsoft.

`_dalsi_cue_slot` takes only cues that are enabled AND have their in-game
picture on (`overlay_configs[i]["enabled"]`) - README: "a reminder whose
picture you switch off never fires". The Edge voice preparation
(`_slot_na_pripravu`) did not ask about the picture, so the text of such
a cue went to Microsoft, although the app never says it in game.

Now `_slot_na_pripravu` excludes it (the same condition,
`_ma_obrazok_v_hre`). Consequences the tests guard:
  * turning the picture on (`on_overlay_config_change`, both switches)
    schedules the preparation again - like `SlotCard.on_enabled_change`;
    turning it off stops a running preparation right away,
  * size / position / colour neither schedule nor cancel the preparation,
  * Test of such a cue is spoken with the Windows voice and sends nothing,
  * "nothing new while listening", the voice style and the Play world
    still hold.
"""
import ast
import itertools
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
from settings_model import (ENGINE_EDGE, MODE_COMBO, MODE_SFX,  # noqa: E402
                            MODE_TTS, default_overlay_configs)

HLAS = "en-GB-SoniaNeural"
KOREN = os.path.join(os.path.dirname(__file__), "..")


def _slot(index, text, mode=MODE_TTS, enabled=True):
    return types.SimpleNamespace(index=index, mode=mode, text_value=text,
                                 voice_edge="", voice_sapi="",
                                 enabled_value=enabled, voice_path="",
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
        ulohy, self.ulohy = self.ulohy, []
        for _ms, fn in ulohy:
            fn()


def _atrapa(monkeypatch, slots, obrazky=(True,) * 4, pocuva=False,
            styl="voice", svet="play"):
    """A dummy with real preparation and the real `on_overlay_config_change`.
    The preparation thread is not started, only recorded (`a.vlakna`); the
    cache remembers what was "sent" (`a.posielane`)."""
    import app as app_mod
    import app_audio
    import audio_engine
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    D = app_mod.DandurfApp
    cfgs = default_overlay_configs()
    for cfg, zapnuty in zip(cfgs, obrazky):
        cfg["enabled"] = bool(zapnuty)
    a = types.SimpleNamespace(
        cue_style=styl, world=svet, edge_voice_id=HLAS, slots=slots,
        engine=ENGINE_EDGE, rate_value=0, saved_voice_id="sapi",
        _pregen_job=None, _pregen_seq=0, _pregen_po_hre=False,
        listening=pocuva, overlay_configs=cfgs, _hr_overlay_warned=True,
        pal={"success": "g", "warn": "y", "danger": "r", "text_dim": "d"},
        stavy=[], posielane=[], hotove=set(), vlakna=[], ui=[], logy=[],
        hovorene=[], ulozene=[], nakreslene=[], root=_Root())

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
    a.save_settings = lambda: a.ulozene.append(True)
    a._prune_cache = lambda *_x: None
    a.audio = types.SimpleNamespace(speak=lambda *x: a.hovorene.append(x),
                                    play_tts=lambda p: a.hovorene.append(p))
    a.overlay_manager = types.SimpleNamespace(
        configure=lambda i, **k: a.nakreslene.append((i, k)))
    for meno in ("pregenerate", "schedule_pregenerate", "pregen_jobs",
                 "_dopriprav_hlasky_po_hre", "_slot_na_pripravu",
                 "_slot_voice_clip", "_hlasky_hovoria", "_ma_obrazok_v_hre",
                 "_zrus_rozbehnutu_pripravu", "_dalsi_cue_slot",
                 "on_overlay_config_change"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    # `pregenerate` reads `threading` from the app_audio module (see the
    # module docstring)
    monkeypatch.setattr(app_audio.threading, "Thread",
                        lambda *x, **k: a.vlakna.append(k) or types.SimpleNamespace(
                            start=lambda: None))
    return a


def _dobehni(a):
    """Runs the body of the last preparation thread in place (no thread)."""
    a.vlakna[-1]["target"]()


def _tri():
    return [_slot(0, "Breathe"), _slot(1, "Jaw"), _slot(2, "Release")]


# --------------------------------------------------------------------------
# What gets prepared
# --------------------------------------------------------------------------

def test_hlaska_s_vypnutym_obrazkom_sa_neposiela(monkeypatch):
    a = _atrapa(monkeypatch, _tri(), obrazky=(True, False, True, True))
    assert a.pregen_jobs() == [("Breathe", HLAS), ("Release", HLAS)]
    a.pregenerate()
    _dobehni(a)
    assert a.posielane == ["Breathe", "Release"]
    assert "Jaw" not in a.posielane


def test_vsetky_obrazky_vypnute_nic_nezacne(monkeypatch):
    """The player turned off all pictures - the app does not speak up in game
    (`_dalsi_cue_slot` returns None), so there is nothing to prepare or
    send."""
    a = _atrapa(monkeypatch, _tri(), obrazky=(False,) * 4)
    assert a._dalsi_cue_slot() is None
    a.pregenerate(force=True)
    assert a.vlakna == [] and a.posielane == []
    assert a.stavy == [""], "stav nesluboval pripravu"


def test_priprava_presne_to_co_hra_vyberie_a_povie_hlasom(monkeypatch):
    """For every combination of cue and picture switches: exactly the cue that
    the in-game rotation can pick (`_dalsi_cue_slot`) and that TTS speaks is
    prepared. Nothing more (needless sending), nothing less (the Windows
    voice would sound in game)."""
    mody = (MODE_TTS, MODE_COMBO, MODE_SFX, MODE_TTS)
    for zapnute in itertools.product((True, False), repeat=4):
        for obrazky in itertools.product((True, False), repeat=4):
            slots = [_slot(i, "s%d" % i, mody[i], zapnute[i]) for i in range(4)]
            a = _atrapa(monkeypatch, slots, obrazky=obrazky)
            vybrane = {a._dalsi_cue_slot() for _ in range(8)} - {None}
            povie = {i for i in vybrane if mody[i] in (MODE_TTS, MODE_COMBO)}
            pripravene = {int(t[1:]) for t, _v in a.pregen_jobs()}
            assert pripravene == povie, (zapnute, obrazky)


# --------------------------------------------------------------------------
# The picture switch schedules / stops the preparation
# --------------------------------------------------------------------------

def test_zapnutie_obrazka_hlasku_pripravi(monkeypatch):
    a = _atrapa(monkeypatch, _tri(), obrazky=(True, False, True, True))
    a.pregenerate()
    _dobehni(a)
    assert a.posielane == ["Breathe", "Release"]

    a.on_overlay_config_change(1, enabled=True)
    assert a.overlay_configs[1]["enabled"] is True
    assert a.ulozene, "nastavenie sa ulozilo"
    assert [ms for ms, _fn in a.root.ulohy] == [200], "priprava je naplanovana"
    a.root.spusti()
    _dobehni(a)
    assert a.posielane == ["Breathe", "Release", "Jaw"], \
        "posiela sa len chybajuca hlaska"
    assert a.stavy[-1] == i18n.tr("edge.generating")


def test_zapnutie_obrazka_pocas_hry_pocka_na_koniec_pocuvania(monkeypatch):
    a = _atrapa(monkeypatch, _tri(), obrazky=(True, False, True, True),
                pocuva=True)
    a.hotove.update({"Breathe", "Release"})
    a.on_overlay_config_change(1, enabled=True)
    a.root.spusti()
    assert a.vlakna == [] and a.posielane == [], "pocas hry sa na Microsoft nejde"
    assert a._pregen_po_hre is True
    assert a.stavy[-1] == i18n.tr("edge.after_game")

    a.listening = False
    a._dopriprav_hlasky_po_hre()
    a.root.spusti()
    _dobehni(a)
    assert a.posielane == ["Jaw"]


def test_zapnutie_obrazka_bez_slov_ani_v_praci_nic_neposle(monkeypatch):
    for styl, svet in (("sound", "play"), ("visual", "play"), ("voice", "work")):
        a = _atrapa(monkeypatch, _tri(), obrazky=(True, False, True, True),
                    styl=styl, svet=svet)
        a.on_overlay_config_change(1, enabled=True)
        a.root.spusti()
        assert a.vlakna == [] and a.posielane == [], (styl, svet)


def test_vypnutie_obrazka_uprostred_pripravy_zvysok_neposle(monkeypatch):
    """Turning off the Jaw picture during the first cue: Jaw does not go to the
    network even in the next scheduled preparation; Release is still
    prepared."""
    a = _atrapa(monkeypatch, _tri())

    def posli(text, voice, rate, abort=None):
        if text in a.hotove:
            return "hotova.mp3"
        a.posielane.append(text)
        a.hotove.add(text)
        if len(a.posielane) == 1:
            a.on_overlay_config_change(1, enabled=False)   # the player turns the picture off
        return "hotova.mp3"

    a.edge_cache.ensure = posli
    a.pregenerate()
    _dobehni(a)
    assert a.posielane == ["Breathe"], "rozbehnuta priprava skoncila hned"
    a.root.spusti()
    _dobehni(a)
    assert a.posielane == ["Breathe", "Release"]
    assert "Jaw" not in a.posielane


def test_velkost_poloha_farba_pripravu_nerusia(monkeypatch):
    """The size slider and dragging the position call
    `on_overlay_config_change` many times a second. They have no effect on
    what is sent - they do not stop a running preparation and do not
    schedule a new one."""
    a = _atrapa(monkeypatch, _tri())
    seq = a._pregen_seq
    a.on_overlay_config_change(0, scale=1.3)
    a.on_overlay_config_change(0, pos=(40.0, 60.0))
    a.on_overlay_config_change(0, color="#ff2020")
    assert a.root.ulohy == [] and a._pregen_seq == seq
    assert a.overlay_configs[0]["scale"] == 1.3
    assert len(a.nakreslene) == 3


def test_oba_prepinace_obrazka_idu_cez_on_overlay_config_change():
    """The picture is turned on on the watch page (app.py, `_build_vhre_page`)
    and in the fine-tuning dialog (ui_dialogs.py, `OverlaySettingsDialog`).
    Both must go through `on_overlay_config_change`, otherwise they would not
    schedule the preparation."""
    for subor in ("app.py", "ui_dialogs.py"):
        with open(os.path.join(KOREN, subor), encoding="utf-8-sig") as fh:
            strom = ast.parse(fh.read())
        volania = [u for u in ast.walk(strom) if isinstance(u, ast.Call)
                   and getattr(u.func, "attr", "") == "on_overlay_config_change"
                   and any(k.arg == "enabled" for k in u.keywords)]
        assert volania, subor


# --------------------------------------------------------------------------
# Test / preview of such a cue
# --------------------------------------------------------------------------

def test_test_hlasky_s_vypnutym_obrazkom_zaznie_cez_windows(monkeypatch):
    """The Test button (and the preview in Settings -> Sound) of a cue with its
    picture off: the Windows voice sounds, nothing is prepared or put off
    until after the game, and the journal did not promise a preparation
    that will not come."""
    import app as app_mod
    D = app_mod.DandurfApp
    for pocuva in (False, True):
        a = _atrapa(monkeypatch, _tri(), obrazky=(True, False, True, True),
                    pocuva=pocuva)
        D._speak_text(a, "Jaw", a.slots[1])
        assert a.ui == [] and a.logy == [], pocuva
        assert a._pregen_po_hre is False
        assert a.hovorene == [("Jaw", "sapi")]
        assert a.posielane == [] and a.vlakna == []

    # The same cue with its picture on is prepared as before.
    a = _atrapa(monkeypatch, _tri())
    D._speak_text(a, "Jaw", a.slots[1])
    assert a.ui == [a.pregenerate]
    assert a.logy == [i18n.tr("log.edge_not_cached")]
