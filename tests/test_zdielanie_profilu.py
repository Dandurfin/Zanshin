# -*- coding: utf-8 -*-
"""Sharing a profile by code (Cues -> Copy profile code).

The code is sent to other people. Before, it carried whole slots including
absolute paths to recordings (C:\\Users\\<meno>\\AppData\\...) - whoever
shared the code revealed their Windows account name. On top of that the
import kept a foreign path if `sfx_key` was not "__custom__", and that path
would have been played if it existed on this PC.

The words in a code (0.3.1): a code from before 0.3.1 still has the old
default words ("Jaw", from 0.1 even ja 脱力 / zh 放松 - "relax", which a cue
never says, tests/test_cue_words.py). The import changes them to the new
words with the exhale, like `load_settings` does once per settings file -
that one-time change cannot catch a code imported later, the settings flag
is already set. A code from 0.3.1 on carries the `exhale_words` marker and
keeps every word exactly ("Jaw" typed back on purpose is the player's own).
The real `export_profile_code` / `import_profile_from_code` run here on a
stand-in for the app - no Tk window, no settings file.
"""
import base64
import json
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app_data  # noqa: E402
import i18n  # noqa: E402
import settings_model  # noqa: E402
from settings_model import (DEFAULT_SLOT, ZDIELANE_POLIA_SLOTU,  # noqa: E402
                            normalize_slot, slot_na_zdielanie, slot_zo_zdielania)
from _zdroj_appky import zdroj_metody  # noqa: E402

import test_cue_words as slova  # noqa: E402

CESTA = "C:\\Users\\hrac\\AppData\\Roaming\\Zanshin\\audio\\rec_abc.wav"
HLAS = "en-GB-SoniaNeural"      # the default shared voice


def _moj_slot(**kw):
    s = normalize_slot(dict(text="Výdych", audio_path=CESTA, voice_path=CESTA,
                            sfx_key="__custom__", uid="abc123abc123",
                            key_repr="f", delay=2.0, every_n=3))
    s.update(kw)
    return s


def _app(lang="en", hlas=HLAS, profily=(), aktivny=None):
    """A stand-in for DandurfApp with only what the profile code reads: the
    clipboard is a list, and `rebuild_slots` / `save_settings` record the
    words they got (so a test sees the words were changed BEFORE them)."""
    zaznam = {"schranka": [], "log": [], "rebuild": None, "ulozene": []}
    app = types.SimpleNamespace(
        profiles=[dict(p) for p in profily], active_profile_name=aktivny,
        lang=lang, edge_voice_id=hlas,
        root=types.SimpleNamespace(clipboard_clear=zaznam["schranka"].clear,
                                   clipboard_append=zaznam["schranka"].append,
                                   update=lambda: None),
        _sync_active_profile_slots=lambda: None,
        refresh_profile_switch=lambda: None,
        schedule_pregenerate=lambda *_: None,
        log=zaznam["log"].append)
    app.rebuild_slots = lambda sloty: zaznam.__setitem__(
        "rebuild", [s["text"] for s in sloty])
    app.save_settings = lambda: zaznam["ulozene"].append(
        [s["text"] for s in app.profiles[-1]["slots"]])
    return app, zaznam


def _exportuj(sloty, meno="Môj"):
    """The code the real `export_profile_code` puts on the clipboard."""
    app, zaznam = _app(profily=[{"name": meno, "slots": sloty}], aktivny=meno)
    app_data.DataMixin.export_profile_code(app)
    kod = "".join(zaznam["schranka"])
    assert zaznam["log"] == [i18n.tr("log.profile_exported", name=meno, n=len(kod))]
    return kod


def _obsah(kod):
    return json.loads(base64.b64decode(kod).decode("utf-8"))


def _stary_kod(sloty, meno="Stary", **navyse):
    """A code as a version before 0.3.1 made it: only `name` and `slots`
    (`navyse` adds top-level keys). A slot is a text or a whole slot dict."""
    payload = {"name": meno, "slots": [
        s if isinstance(s, dict) else slot_na_zdielanie(normalize_slot({"text": s}))
        for s in sloty]}
    payload.update(navyse)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _importuj(kod, lang="en", hlas=HLAS):
    """The real `import_profile_from_code`: the imported profile's slots."""
    app, zaznam = _app(lang, hlas, profily=[{"name": "Hlavny", "slots": []}],
                       aktivny="Hlavny")
    app_data.DataMixin.import_profile_from_code(app, kod)
    profil = app.profiles[-1]
    texty = [s["text"] for s in profil["slots"]]
    assert app.active_profile_name == profil["name"] != "Hlavny"
    # the words are changed before the slot cards are built and saved
    assert zaznam["rebuild"] == texty and zaznam["ulozene"] == [texty]
    return profil["slots"]


def _texty(sloty):
    return [s["text"] for s in sloty]


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
    """The real `export_profile_code`, not a copy of its composition."""
    text = base64.b64decode(_exportuj([_moj_slot()])).decode("utf-8")
    assert "Users" not in text and "hrac" not in text and "abc123" not in text
    assert "Výdych" in text and "Môj" in text, "ensure_ascii=False ostáva"


def test_import_vzdy_vynuluje_cesty_aj_bez_vlastneho_zvuku():
    """Old code (with paths) and an empty `sfx_key`: the path used to stay."""
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
    exp = zdroj_metody("export_profile_code")
    assert "slot_na_zdielanie(s) for s in profile[\"slots\"]" in exp
    assert '"slots": profile["slots"]' not in exp
    assert '"exhale_words": True' in exp
    imp = zdroj_metody("import_profile_from_code")
    assert "slot_zo_zdielania(" in imp
    assert 'if not data.get("exhale_words"):' in imp
    assert "migrate_profile_texts(slots," in imp


# --------------------------------------------------------------------------
# The words in a code (0.3.1)
# --------------------------------------------------------------------------

def test_export_ma_priznak_slov_s_vydychom():
    """Only `name` and `slots` before 0.3.1, which is all any version up to
    0.3 reads - a code with the marker still imports there."""
    kod = _exportuj([normalize_slot({"text": t}) for t in slova.NOVE_SLOVA["en"]])
    obsah = _obsah(kod)
    assert obsah["exhale_words"] is True
    assert set(obsah) == {"name", "slots", "exhale_words"}
    assert _texty(obsah["slots"]) == list(slova.NOVE_SLOVA["en"])
    # compact JSON, as before: no spaces after the separators
    assert base64.b64decode(kod).decode("utf-8").startswith('{"name":"Môj","slots":[{')


def test_kod_z_03_dostane_nove_slova():
    sloty = _importuj(_stary_kod(["Grounded", "Jaw", "Release", "Breathe"]))
    assert _texty(sloty) == list(slova.NOVE_SLOVA["en"])
    assert _texty(sloty) == ["Exhale, grounded", "Exhale, jaw", "Exhale, release",
                             "Long exhale"]


@pytest.mark.parametrize("jazyk, stare", [
    ("zh", ["落地", "牙关", "放松", "呼吸"]),       # 0.1: 放松 = "relax"
    ("ja", ["重心", "脱力", "解放", "呼吸"]),       # 0.1: 脱力 = "relax"
])
def test_kod_z_01_nepovie_uvolni_sa(jazyk, stare):
    """The 0.1 words mean "relax" - after the import the cue must not say it
    (app in English, the default English voice: the profile itself tells the
    language, also for 呼吸, which ja and zh shared)."""
    assert slova._zakazane(stare[1] + stare[2]), "safeguard: the old words are forbidden"
    sloty = _importuj(_stary_kod(stare))
    assert _texty(sloty) == list(slova.NOVE_SLOVA[jazyk])
    for slot in sloty:
        assert not slova._zakazane(slot["text"]), slot["text"]


@pytest.mark.parametrize("jazyk", sorted(slova.STARE_SLOVA))
@pytest.mark.parametrize("vek", [0, -1])
def test_stary_kod_v_kazdom_jazyku(jazyk, vek):
    """`vek` 0 = a code from 0.2-0.3, -1 = the oldest words (0.1)."""
    sloty = _importuj(_stary_kod([s[vek] for s in slova.STARE_SLOVA[jazyk]]))
    assert _texty(sloty) == list(slova.NOVE_SLOVA[jazyk])


@pytest.mark.parametrize("lang, hlas, nove", [
    ("en", "zh-CN-XiaoxiaoNeural", "长长地呼气"),
    ("zh", "ja-JP-NanamiNeural", "息を長く吐いて"),   # the voice before the app language
    ("zh", HLAS, "长长地呼气"),                       # the app language
    ("en", HLAS, "息を長く吐いて"),                   # nothing tells: LANGUAGES order
])
def test_spolocne_slovo_podla_hlasu_a_jazyka_appky(lang, hlas, nove):
    """呼吸 alone (ja and zh shared it): the same hints as on load - this
    app's shared voice, then its language."""
    sloty = _importuj(_stary_kod(["A", "B", "C", "呼吸"]), lang=lang, hlas=hlas)
    assert _texty(sloty) == ["A", "B", "C", nove]


def test_vlastne_slova_v_starom_kode_ostanu():
    sloty = _importuj(_stary_kod(["Feet", "my teeth", "Release", "Jaw", "Navyse"]))
    # an old default word in ANOTHER slot is the player's word too
    assert _texty(sloty) == ["Feet", "my teeth", "Exhale, release", "Jaw", "Navyse"]


def test_oznaceny_kod_necha_kazde_slovo():
    """A code from 0.3.1: "Jaw" there was typed back on purpose."""
    stare = ["Grounded", "Jaw", "Moje slovo", "Breathe"]
    sloty = _importuj(_stary_kod(stare, exhale_words=True))
    assert _texty(sloty) == stare


def test_export_a_import_necha_slova_presne():
    """Export -> import gives back exactly the same words - the player's own,
    old words typed back ("Jaw", "Release", 呼吸), the new ones - with any
    app language and voice."""
    sloty = [normalize_slot(s) for s in (
        {"text": "Exhale, grounded"},
        {"text": "Jaw", "voice_edge": "en-US-GuyNeural"},
        {"text": "Release", "enabled": False, "mode": "tts"},
        {"text": "呼吸"},
        {"text": "Moje slovo", "mode": "combo"})]
    kod = _exportuj(sloty)
    for lang, hlas in (("en", HLAS), ("zh", "zh-CN-XiaoxiaoNeural"), ("ja", "ja-JP-NanamiNeural")):
        spat = _importuj(kod, lang=lang, hlas=hlas)
        assert _texty(spat) == _texty(sloty), (lang, hlas)
        assert ([slot_na_zdielanie(s) for s in spat]
                == [slot_na_zdielanie(s) for s in sloty]), (lang, hlas)


def test_kod_z_01_s_menej_slotmi():
    """A 0.1 code: whole slots (paths, uid, key fields) and fewer than four.
    The words change, the missing categories come at the end, switched off."""
    stare = [dict(_moj_slot(text="Grounded", sfx_key="")),
             dict(_moj_slot(text="Teeth", sfx_key="", uid="def456def456"))]
    zaklad = settings_model.default_slots()
    sloty = _importuj(_stary_kod(stare, meno="Z 0.1"))
    assert len(sloty) == 4
    assert _texty(sloty) == ["Exhale, grounded", "Exhale, jaw"] + _texty(zaklad[2:])
    assert all(s["enabled"] for s in sloty[:2]) and not any(s["enabled"] for s in sloty[2:])
    for slot in sloty:
        assert slot["audio_path"] == "" and slot["voice_path"] == ""
        assert slot["uid"] not in ("", "abc123abc123", "def456def456")


@pytest.mark.parametrize("priznak, zmeni", [
    (None, True), (False, True), (0, True), ("", True), ([], True),
    ("no", False), (1, False), ([1], False),
])
def test_cudny_priznak_v_kode(priznak, zmeni):
    """A hand-edited marker counts by its truth value - a truthy one keeps the
    words like a code from 0.3.1, anything else changes them. Either way only
    the words are at stake: paths and the uid are still dropped."""
    stare = [dict(_moj_slot(text="Grounded", sfx_key="")), "Jaw", "Release", "Breathe"]
    sloty = _importuj(_stary_kod(stare, exhale_words=priznak))
    assert _texty(sloty) == (list(slova.NOVE_SLOVA["en"]) if zmeni
                             else ["Grounded", "Jaw", "Release", "Breathe"])
    for slot in sloty:
        assert slot["audio_path"] == "" and slot["voice_path"] == ""
        assert slot["uid"] not in ("", "abc123abc123")


def test_import_bez_hlasu_a_jazyka_appky():
    """The hints are the app's shared voice and language - the same attributes
    `save_settings` writes. Without them the import still runs and the
    profile itself tells the language."""
    uloz = zdroj_metody("save_settings")
    assert '"edge_voice": self.edge_voice_id' in uloz and '"lang": self.lang' in uloz
    app, _zaznam = _app(profily=[{"name": "Hlavny", "slots": []}], aktivny="Hlavny")
    del app.lang, app.edge_voice_id
    app_data.DataMixin.import_profile_from_code(app, _stary_kod(["重心", "脱力", "解放", "呼吸"]))
    assert _texty(app.profiles[-1]["slots"]) == list(slova.NOVE_SLOVA["ja"])
