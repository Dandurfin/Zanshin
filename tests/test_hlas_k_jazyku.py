# -*- coding: utf-8 -*-
"""Hlas k jazyku rozhrania (0.2, faza jazykov).

Bulharsky Windows od 0.2 startuje po bulharsky a predvolene hlasky slotov su
cyrilikou („Опора“, „Челюст“…), no hlas ostaval anglicky (Sonia) - ten ich
pravdepodobne nevyslovi. Japoncina mala navrh hlasu len pri prepnuti jazyka,
nie pri prvom starte. Teraz jazyky s inym pismom nez latinka (ja/zh/ru/bg)
dostanu hlas svojho jazyka pri prvom starte aj pri prepnuti - ale len kym
ma hrac predvoleny hlas. Hlas, ktory si vybral sam, sa nemeni.
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
    """Appka o sebe hovori v zenskom rode - navrhnuty hlas tiez."""
    rod = {kod: r for kod, _, r in EDGE_FALLBACK_VOICES}
    for jazyk, hlas in VOICE_HINTS.items():
        assert jazyk in i18n.LANGUAGES
        assert hlas.startswith(jazyk + "-"), (jazyk, hlas)
        assert rod[hlas] == "f", hlas


def test_navrh_maju_presne_jazyky_s_inym_pismom():
    """Tam su predvolene hlasky mimo latinky - inde ich Sonia aspon precita."""
    for jazyk in i18n.LANGUAGES:
        slova = "".join(i18n.STRINGS[f"slot.default.{k}"][jazyk]
                        for k in ("grounding", "jaw", "release", "breath"))
        latinka = all(ord(znak) < 0x250 for znak in slova)
        assert (jazyk in VOICE_HINTS) == (not latinka), jazyk


def test_predvoleny_hlas_dostane_navrh():
    assert suggested_voice("bg") == "bg-BG-KalinaNeural"
    assert suggested_voice("ja", DEFAULT_EDGE_VOICE) == "ja-JP-NanamiNeural"
    for jazyk in ("sk", "en", "cs", "es", "de", "fr", "pt"):
        assert suggested_voice(jazyk) == DEFAULT_EDGE_VOICE


def test_vlastny_hlas_hraca_ostava():
    assert suggested_voice("bg", "en-US-GuyNeural") == "en-US-GuyNeural"
    assert suggested_voice("ja", "bg-BG-KalinaNeural") == "bg-BG-KalinaNeural"


def test_prepnutie_jazyka_pouziva_navrh():
    """Staticky (bez Tk): prepinac jazyka ide cez `suggested_voice`."""
    blok = zdroj_metody("on_lang_switch")
    assert "suggested_voice(code, self.edge_voice_id)" in blok


@pytest.fixture
def start(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    # `load_settings` byva v mixine app_prefs (PrefsMixin) a cita
    # SETTINGS_PATH zo svojho modulu - presmerovat ho treba tam.
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
    ("cs-CZ", DEFAULT_EDGE_VOICE), ("de-DE", DEFAULT_EDGE_VOICE),
    ("en-US", DEFAULT_EDGE_VOICE),
])
def test_prvy_start_dostane_hlas_jazyka_windowsu(start, locale, hlas):
    assert start(locale)["edge_voice"] == hlas


def test_ulozeny_hlas_pri_starte_ostava(start):
    d = start("bg-BG", {"lang": "bg", "theme": "zen",
                        "edge_voice": "en-US-GuyNeural"})
    assert d["edge_voice"] == "en-US-GuyNeural"
