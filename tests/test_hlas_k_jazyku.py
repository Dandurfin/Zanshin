# -*- coding: utf-8 -*-
"""Voice to match the interface language (0.2, languages phase).

Since 0.2 a Bulgarian Windows starts in Bulgarian and the default slot cues
are in Cyrillic („Опора“, „Челюст“…), but the voice stayed English
(Sonia) - it probably cannot pronounce them. Japanese had a voice
suggestion only on a language switch, not on the first start. Now
languages with a script other than Latin (ja/zh/ru/bg) get a voice of
their language on the first start and on a switch - but only while the
player has the default voice. A voice they picked themselves is not
changed.

0.2.1d: on a language switch only when the cues of the active profile are
really in the new language (the switch does not translate them) -
tests/test_021d_hlas_podla_hlasok.py.
"""
import json
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402
from settings_model import (DEFAULT_EDGE_VOICE, EDGE_FALLBACK_VOICES,  # noqa: E402
                            VOICE_HINTS, suggested_voice)


def test_navrhy_su_zo_zoznamu_hlasov_a_zenske():
    """The app speaks of itself in the feminine - the suggested voice too."""
    rod = {kod: r for kod, _, r in EDGE_FALLBACK_VOICES}
    for jazyk, hlas in VOICE_HINTS.items():
        assert jazyk in i18n.LANGUAGES
        assert hlas.startswith(jazyk + "-"), (jazyk, hlas)
        assert rod[hlas] == "f", hlas


def test_navrh_maju_presne_jazyky_s_neanglickymi_slovami():
    """Until 0.2.1 only languages outside Latin script (Sonia would not
    pronounce them). Since 0.3 every language whose built-in words are not
    English - Sonia reads es/de/fr/pt with an English pronunciation
    (tests/test_022c_prvy_vecer_hlas.py). Sk/cs have English built-in
    words, so they have no suggestion."""
    def slova(jazyk):
        return [i18n.STRINGS[f"slot.default.{k}"][jazyk]
                for k in ("grounding", "jaw", "release", "breath")]
    for jazyk in i18n.LANGUAGES:
        assert (jazyk in VOICE_HINTS) == (slova(jazyk) != slova("en")), jazyk


def test_predvoleny_hlas_dostane_navrh():
    assert suggested_voice("bg") == "bg-BG-KalinaNeural"
    assert suggested_voice("ja", DEFAULT_EDGE_VOICE) == "ja-JP-NanamiNeural"
    assert suggested_voice("de") == "de-DE-KatjaNeural"
    for jazyk in ("sk", "en", "cs"):
        assert suggested_voice(jazyk) == DEFAULT_EDGE_VOICE


def test_vlastny_hlas_hraca_ostava():
    assert suggested_voice("bg", "en-US-GuyNeural") == "en-US-GuyNeural"
    assert suggested_voice("ja", "bg-BG-KalinaNeural") == "bg-BG-KalinaNeural"


def test_prepnutie_jazyka_pouziva_navrh():
    """Static (no Tk): the language switch goes through `suggested_voice` -
    since 0.2.1d through `_hlas_k_hlaskam`, which lets the suggestion
    through only when the cues of the active profile are in the new
    language (tests/test_021d_hlas_podla_hlasok.py). The direct
    `suggested_voice(code, ...)` by interface language is gone."""
    blok = zdroj_metody("on_lang_switch")
    assert "self._hlas_k_hlaskam(self.slot_dicts())" in blok
    assert "suggested_voice(" not in blok
    assert "suggested_voice(self.lang, self.edge_voice_id)" in zdroj_metody(
        "_hlas_k_hlaskam")


@pytest.fixture
def start(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    # `load_settings` lives in the app_prefs mixin (PrefsMixin) and reads
    # SETTINGS_PATH from its own module - it has to be redirected there.
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def spusti(locale, ulozene=None):
        monkeypatch.setattr(i18n, "_win_locale", lambda: locale)
        if ulozene is not None:
            with open(cesta, "w", encoding="utf-8") as fh:
                json.dump(ulozene, fh, ensure_ascii=False)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield spusti
    i18n.set_lang(povodny)


@pytest.mark.parametrize("locale, hlas", [
    ("bg-BG", "bg-BG-KalinaNeural"), ("ja-JP", "ja-JP-NanamiNeural"),
    ("ru-RU", "ru-RU-SvetlanaNeural"), ("zh-CN", "zh-CN-XiaoxiaoNeural"),
    ("cs-CZ", DEFAULT_EDGE_VOICE), ("de-DE", "de-DE-KatjaNeural"),
    ("en-US", DEFAULT_EDGE_VOICE),
])
def test_prvy_start_dostane_hlas_jazyka_windowsu(start, locale, hlas):
    assert start(locale)["edge_voice"] == hlas


def test_ulozeny_hlas_pri_starte_ostava(start):
    d = start("bg-BG", {"lang": "bg", "theme": "zen",
                        "edge_voice": "en-US-GuyNeural"})
    assert d["edge_voice"] == "en-US-GuyNeural"
